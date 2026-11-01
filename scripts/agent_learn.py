#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能体学习任务（草稿模式）
- 读取 data/latest.json 中尚未处理的文献摘要
- 用 DeepSeek 提取“原理卡”（principle / mechanism / evidence / application / counterexample）
- 写入 data/agent_drafts.json（status=draft，等待审核）
- 不把草稿直接当结论；没有 API key 时安全退出

用法：
  DEEPSEEK_API_KEY=sk-... python scripts/agent_learn.py --limit 6
  DEEPSEEK_API_KEY=sk-... python scripts/agent_learn.py --limit 6 --dry-run
"""
import argparse
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LATEST = DATA / "latest.json"
DRAFTS = DATA / "agent_drafts.json"
SEEN = DATA / "agent_seen.json"
API = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
CN_TZ = timezone(timedelta(hours=8))

SYSTEM = """你是运动科学知识库的研究助理。只根据用户提供的 PubMed 摘要提取“可检验的原理卡”，不得使用摘要之外的知识补全，不得编造 PMID/来源。
输出一个 JSON 对象：{"items": [...]}，每项包含：
- pmid: 摘要对应的 PMID（必须来自输入）
- title: 标题
- discipline: anatomy / physiology / fascia / nutrition 之一
- principle: 一句可检验的原理（不是泛泛而谈）
- mechanism: 机制解释（尽量对应解剖/生理/筋膜/营养）
- evidence_level: A / B / C（A=指南/系统综述/教科书共识；B=单项研究/机制研究；C=摘要不足或推断）
- evidence_note: 研究类型、样本、局限（只写摘要能支持的）
- application: 训练/康复/营养上的可能应用（用“可能/倾向”，不要下诊断）
- counterexample: 反例或边界（什么情况下不成立）
- confidence: 0-1
- status: "draft"
要求：摘要不足时 evidence_level=C、confidence<=0.5，并在 evidence_note 写“摘要信息不足”。不要写医疗诊断或药物建议。只输出 JSON，不要 markdown。"""


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def call_llm(prompt, key):
    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 2600,
        "response_format": {"type": "json_object"},
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "User-Agent": "sports-kb-agent/0.1",
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" not in str(e):
            raise
        curl = shutil.which("curl")
        if not curl:
            raise
        fd, tmp = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(body)
            args = [curl, "-sS", "-L", "--max-time", "120", "-X", "POST", API,
                    "-H", "Authorization: Bearer " + key,
                    "-H", "Content-Type: application/json",
                    "--data-binary", "@" + tmp]
            if os.name == "nt":
                args.insert(2, "--ssl-no-revoke")
            p = subprocess.run(args, capture_output=True)
            if p.returncode != 0:
                raise RuntimeError((p.stderr or b"").decode("utf-8", "replace")[:300])
            return p.stdout.decode("utf-8", "replace")
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass


def parse_items(raw):
    data = json.loads(raw)
    content = data["choices"][0]["message"]["content"]
    obj = json.loads(content)
    if isinstance(obj, dict):
        items = obj.get("items", [])
    elif isinstance(obj, list):
        items = obj
    else:
        items = []
    return [x for x in items if isinstance(x, dict) and x.get("pmid")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        print("没有 DEEPSEEK_API_KEY，跳过学习任务。")
        return 0

    latest = load(LATEST, {"articles": []})
    drafts = load(DRAFTS, {"updated": "", "items": []})
    seen = set(load(SEEN, []))
    have = {x.get("pmid") for x in drafts.get("items", [])}

    candidates = []
    skip_terms = ("education", "bibliometric", "large language model", "biography", "obituary",
                  "editorial", "commentary", "letter", "reply", "erratum", "correction")
    for a in latest.get("articles", []):
        if not a.get("abstract") or a.get("pmid") in seen or a.get("pmid") in have:
            continue
        title = (a.get("title") or "").lower()
        if any(t in title for t in skip_terms):
            continue
        if int(a.get("relevance", 2) or 2) < 2:
            continue
        candidates.append(a)
    candidates.sort(key=lambda a: int(a.get("relevance", 0) or 0), reverse=True)
    candidates = candidates[: args.limit]
    if not candidates:
        print("没有待学习的新文献。")
        return 0

    payload = [{
        "pmid": a["pmid"], "title": a.get("title", ""), "discipline": a.get("discipline", ""),
        "journal": a.get("journal", ""), "date": a.get("date", ""),
        "abstract": (a.get("abstract") or "")[:1800],
    } for a in candidates]
    prompt = "请从以下摘要中提取原理卡，只输出 JSON：\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    raw = call_llm(prompt, key)
    items = parse_items(raw)
    now = datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M")

    if args.dry_run:
        print(f"[dry-run] 输入 {len(candidates)} 条，模型返回 {len(items)} 张卡")
        print(json.dumps(items, ensure_ascii=False, indent=2)[:4000])
        return 0

    by_pmid = {x.get("pmid"): x for x in drafts.get("items", [])}
    for it in items:
        it["status"] = "draft"
        it["generated_at"] = now
        it.setdefault("confidence", 0.5)
        by_pmid[it["pmid"]] = it
    drafts = {"updated": now, "items": sorted(by_pmid.values(), key=lambda x: x.get("generated_at", ""), reverse=True)}
    save(DRAFTS, drafts)
    seen.update(a["pmid"] for a in candidates)
    save(SEEN, sorted(seen))
    print(f"完成：输入 {len(candidates)} 条，生成/更新 {len(items)} 张原理卡草稿，累计 {len(drafts['items'])} 张。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
