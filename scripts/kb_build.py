#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 curated.json + latest.json + journals.json 合并成前端数据：
  data/kb.json  （给程序/检索用）
  data/kb.js    （给 index.html 直接加载，支持 file:// 打开）

用法：
  python scripts/kb_build.py
"""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] {path}: {e}")
        return default


def main():
    curated = load(DATA / "curated.json", {})
    latest = load(DATA / "latest.json", {"updated": "", "articles": []})
    journals = load(DATA / "journals.json", [])
    keywords = load(DATA / "keywords.json", {})
    fascia_lines = load(DATA / "fascia_lines.json", {"lines": []})
    agent_drafts = load(DATA / "agent_drafts.json", {"items": []})

    disciplines = curated.get("disciplines", [])
    cross = curated.get("cross", [])

    # 按学科关键词计算相关度；标题命中权重 2，摘要命中权重 1；>=2 才进入「每日」
    def relevance(a):
        title = (a.get("title") or "").lower()
        abstract = (a.get("abstract") or "").lower()
        kws = keywords.get(a.get("discipline", ""), []) + keywords.get("general", [])
        title_hits = [k for k in kws if k in title]
        text_hits = [k for k in kws if k in abstract]
        score = 2 * len(title_hits) + len(text_hits)
        matched = list(dict.fromkeys(title_hits + text_hits))[:6]
        return score, matched

    raw_articles = latest.get("articles", [])
    for a in raw_articles:
        s, m = relevance(a)
        a["relevance"] = s
        a["matched"] = m
    filtered_articles = [a for a in raw_articles if a.get("relevance", 0) >= 2]
    filtered_articles.sort(key=lambda x: (x.get("relevance", 0), x.get("date") or ""), reverse=True)
    latest_out = {
        "updated": latest.get("updated", ""),
        "updated_at": latest.get("updated_at", ""),
        "raw_count": len(raw_articles),
        "articles": filtered_articles,
    }

    note_ids = set()
    for d in disciplines:
        for n in d.get("notes", []):
            note_ids.add(n.get("id"))
    cross_ids = {c.get("id") for c in cross}
    all_ids = note_ids | cross_ids

    missing = []
    for d in disciplines:
        for n in d.get("notes", []):
            for r in n.get("related", []):
                if r not in all_ids:
                    missing.append((n.get("id"), r))
    for c in cross:
        if c.get("id") not in cross_ids:
            missing.append((c.get("id"), c.get("id")))

    kb = dict(curated)
    kb["latest"] = latest_out
    kb["journals"] = journals
    kb["fascia_lines"] = fascia_lines
    kb["agent_drafts"] = agent_drafts
    kb["built_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    kb.setdefault("meta", {})
    kb["meta"]["counts"] = {
        "disciplines": len(disciplines),
        "notes": len(note_ids),
        "cross": len(cross),
        "journals": len(journals),
        "latest_articles": len(filtered_articles),
        "raw_articles": len(raw_articles),
        "fascia_lines": len(fascia_lines.get("lines", [])),
        "agent_drafts": len(agent_drafts.get("items", [])),
    }

    (DATA / "kb.json").write_text(json.dumps(kb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    js = "window.KB_DATA = " + json.dumps(kb, ensure_ascii=False) + ";\n"
    (DATA / "kb.js").write_text(js, encoding="utf-8")

    print(f"build ok: {len(disciplines)} disciplines, {len(note_ids)} notes, {len(cross)} cross, "
          f"{len(filtered_articles)} relevant / {len(raw_articles)} raw articles")
    if missing:
        print("[WARN] related id 不存在：")
        for a, b in missing:
            print(f"  - {a} -> {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
