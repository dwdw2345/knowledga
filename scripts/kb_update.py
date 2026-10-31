#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日文献更新（PubMed E-utilities）
- 按期刊 ISSN 抓取最近 N 天的新文章
- 只保存：标题、作者、期刊、日期、摘要原文、PMID、DOI、链接
- 自动去重；生成 data/latest.json 与 daily/YYYY-MM-DD.md
- 不生成任何“结论/建议”，避免无来源内容

用法：
  python scripts/kb_update.py --days 7
  python scripts/kb_update.py --days 7 --only "JOSPT"
  NCBI_API_KEY=xxx python scripts/kb_update.py
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
JOURNALS = DATA / "journals.json"
LATEST = DATA / "latest.json"
SEEN = DATA / "seen.json"
KEYWORDS = DATA / "keywords.json"
ARCHIVE = DATA / "archive"
DIGEST_DIR = ROOT / "daily"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UA = "SportsScienceKB/0.1 (personal research; https://pubmed.ncbi.nlm.nih.gov/)"
CN_TZ = timezone(timedelta(hours=8))


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.URLError as e:
        # 某些本地 Python 环境没有系统 CA，导致自签证书报错；用系统 curl 兜底（仍做证书校验）
        if "CERTIFICATE_VERIFY_FAILED" not in str(e):
            raise
        curl = shutil.which("curl")
        if not curl:
            raise
        args = [curl, "-sS", "-L", "--max-time", str(timeout)]
        if os.name == "nt":
            # Windows schannel 在离线时可能卡在吊销检查；只关闭吊销检查，仍校验证书链
            args.append("--ssl-no-revoke")
        args += ["-A", UA, url]
        p = subprocess.run(args, capture_output=True)
        if p.returncode != 0:
            raise RuntimeError((p.stderr or b"").decode("utf-8", "replace")[:300])
        return p.stdout


def esearch(issn, days, retmax, api_key):
    params = {
        "db": "pubmed",
        "term": f"{issn}[IS]",
        "retmax": str(retmax),
        "sort": "date",
        "retmode": "json",
        "reldate": str(days),
        "datetype": "pdat",
    }
    if api_key:
        params["api_key"] = api_key
    url = f"{EUTILS}/esearch.fcgi?{urllib.parse.urlencode(params)}"
    raw = fetch(url)
    data = json.loads(raw.decode("utf-8", "replace"))
    return data.get("esearchresult", {}).get("idlist", []) or []


def efetch(pmids, api_key):
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}
    if api_key:
        params["api_key"] = api_key
    url = f"{EUTILS}/efetch.fcgi?{urllib.parse.urlencode(params)}"
    return fetch(url)


def text_of(el):
    if el is None:
        return ""
    return " ".join("".join(el.itertext()).split())


def parse_article(art, cfg):
    pmid = text_of(art.find(".//PMID"))
    if not pmid:
        return None
    title = text_of(art.find(".//Article/ArticleTitle"))
    journal = text_of(art.find(".//Journal/Title")) or cfg.get("name", "")
    abstract_parts = []
    for ab in art.findall(".//Abstract/AbstractText"):
        label = ab.get("Label")
        txt = text_of(ab)
        if txt:
            abstract_parts.append((f"{label}: " if label else "") + txt)
    abstract = " ".join(abstract_parts)

    pub_date = art.find(".//JournalIssue/PubDate")
    year = text_of(pub_date.find("Year")) if pub_date is not None else ""
    month = text_of(pub_date.find("Month")) if pub_date is not None else ""
    day = text_of(pub_date.find("Day")) if pub_date is not None else ""
    if not year and pub_date is not None:
        year = text_of(pub_date.find("MedlineDate"))
    date = "-".join(x for x in [year, month, day] if x)

    doi = ""
    for aid in art.findall(".//ArticleId"):
        if aid.get("IdType") == "doi":
            doi = text_of(aid)
            break

    authors = []
    for a in art.findall(".//AuthorList/Author"):
        last = text_of(a.find("LastName"))
        fore = text_of(a.find("ForeName"))
        collective = text_of(a.find("CollectiveName"))
        if last:
            authors.append((fore + " " + last).strip())
        elif collective:
            authors.append(collective)
    author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")

    return {
        "pmid": pmid,
        "title": title,
        "journal": journal,
        "journal_issn": cfg.get("issn", ""),
        "discipline": cfg.get("discipline", ""),
        "date": date,
        "authors": author_str,
        "abstract": abstract,
        "doi": doi,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def relevance(a, keywords):
    title = (a.get("title") or "").lower()
    abstract = (a.get("abstract") or "").lower()
    kws = keywords.get(a.get("discipline", ""), []) + keywords.get("general", [])
    title_hits = [k for k in kws if k in title]
    text_hits = [k for k in kws if k in abstract]
    score = 2 * len(title_hits) + len(text_hits)
    matched = list(dict.fromkeys(title_hits + text_hits))[:6]
    return score, matched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7, help="抓取最近 N 天（默认 7）")
    ap.add_argument("--max-per-journal", type=int, default=8, help="每本期刊最多抓取条数")
    ap.add_argument("--only", default="", help="只抓包含该字符串的期刊名（测试用）")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    args = ap.parse_args()

    api_key = os.environ.get("NCBI_API_KEY", "").strip()
    journals = load_json(JOURNALS, [])
    keywords = load_json(KEYWORDS, {})
    if not journals:
        print("找不到 data/journals.json")
        return 2
    if args.only:
        journals = [j for j in journals if args.only.lower() in j.get("name", "").lower()]
        if not journals:
            print("没有匹配的期刊")
            return 2

    latest = load_json(LATEST, {"updated": "", "articles": []})
    seen = set(load_json(SEEN, []))
    today = datetime.now(CN_TZ).strftime("%Y-%m-%d")
    now = datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M")

    new_articles = []
    all_fetched = []
    per_journal = []

    for cfg in journals:
        name = cfg.get("name", "")
        issn = cfg.get("issn", "")
        if not issn:
            continue
        try:
            pmids = esearch(issn, args.days, args.max_per_journal, api_key)
            time.sleep(0.4)
            if not pmids:
                per_journal.append((name, 0, 0))
                print(f"[0] {name}")
                continue
            xml = efetch(pmids, api_key)
            time.sleep(0.4)
            root = ET.fromstring(xml)
            n_new = 0
            for art in root.findall(".//PubmedArticle"):
                item = parse_article(art, cfg)
                if not item:
                    continue
                item["relevance"], item["matched"] = relevance(item, keywords)
                all_fetched.append(item["pmid"])
                if item["pmid"] in seen:
                    continue
                seen.add(item["pmid"])
                new_articles.append(item)
                n_new += 1
            per_journal.append((name, len(pmids), n_new))
            print(f"[{n_new}] {name} (fetched {len(pmids)})")
        except urllib.error.HTTPError as e:
            print(f"[ERR] {name}: HTTP {e.code}")
        except Exception as e:
            print(f"[ERR] {name}: {e}")

    # 合并到 latest（保留最近 300 条）
    merged = new_articles + [a for a in latest.get("articles", []) if a.get("pmid") not in {x["pmid"] for x in new_articles}]
    merged.sort(key=lambda x: (x.get("date") or "", x.get("pmid") or ""), reverse=True)
    merged = merged[:300]
    latest_out = {"updated": today, "updated_at": now, "articles": merged}

    if args.dry_run:
        print(f"\n[dry-run] 新文章 {len(new_articles)} 条，latest 将保留 {len(merged)} 条")
        for a in new_articles[:10]:
            print("-", a["date"], a["journal"], a["title"][:80])
        return 0

    save_json(LATEST, latest_out)
    save_json(SEEN, sorted(seen))

    # 归档：同一天多次运行时合并，而不是覆盖
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    archive_path = ARCHIVE / f"{today}.json"
    old_archive = load_json(archive_path, {"updated": today, "articles": []})
    archive_map = {a.get("pmid"): a for a in old_archive.get("articles", []) if a.get("pmid")}
    for a in new_articles:
        archive_map[a["pmid"]] = a
    archive_articles = list(archive_map.values())
    for a in archive_articles:
        if "relevance" not in a:
            a["relevance"], a["matched"] = relevance(a, keywords)
    save_json(archive_path, {"updated": today, "articles": archive_articles})

    # Markdown 摘要：从当天归档生成，多次运行会保留当天全部文章
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# 每日文献更新 {today}",
        "",
        "> 自动抓取 PubMed 元数据与摘要原文；不生成结论/建议。点 PMID 看原文。",
        "",
    ]
    digest_articles = [a for a in archive_articles if a.get("relevance", 0) >= 2]
    digest_articles.sort(key=lambda x: (x.get("discipline", ""), x.get("date", "")), reverse=True)
    by_disc = {}
    for a in digest_articles:
        by_disc.setdefault(a.get("discipline", ""), []).append(a)
    for disc in ["anatomy", "physiology", "fascia", "nutrition"]:
        arr = by_disc.get(disc, [])
        if not arr:
            continue
        lines.append(f"## {disc}")
        for a in arr:
            lines.append(f"### {a['title']}")
            lines.append(f"- {a['journal']} · {a['date']} · {a['authors']}")
            lines.append(f"- PMID: [{a['pmid']}]({a['url']})" + (f" · DOI: {a['doi']}" if a.get("doi") else ""))
            if a.get("abstract"):
                lines.append("")
                lines.append(a["abstract"][:700] + ("…" if len(a["abstract"]) > 700 else ""))
            lines.append("")
    (DIGEST_DIR / f"{today}.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"\n完成：新增 {len(new_articles)} 条（高相关 {len(digest_articles)} 条）；latest 共 {len(merged)} 条；当天归档 {len(archive_articles)} 条；写入 {DIGEST_DIR / (today + '.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
