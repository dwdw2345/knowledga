# 运动科学知识库

一个可持续更新的运动科学知识库：
- **四学科分栏**：运动解剖学、运动生理学、筋膜学、营养学
- **交叉主题**：同一问题用四学科分别分析，再整合成可执行方案
- **筋膜链深度**：6 条肌筋膜链，逐节点拆解构成、走向、问题、评估与解决
- **智能问答**：DeepSeek API，key 只存本机，基于知识库检索回答
- **每日文献**：按顶级期刊 ISSN 抓取 PubMed 最新标题/摘要/链接，去重、筛选、归档；支持 Europe PMC 与摘要翻译
- **证据分级**：A/B/C，每条核心笔记都有来源

> 原则：**不胡编乱造**。自动任务只抓原文元数据/摘要；核心笔记和交叉分析必须写来源并标注证据等级；证据不足标 C，不把模型当事实。

## 当前规模

- 四学科各 **12 篇**，共 **48 篇**核心笔记
- **5 个**交叉主题（肩胛/卧推、跑步膝、久坐腰痛、踝扭伤、增肌平台期）
- **6 条**筋膜链深度专题（浅背线、浅前线、侧线、螺旋线、深前线、臂线）
- **30 本**期刊
- **177 条**原始文献 / **138 条**关键词筛选后进入前端

## 已上线

- GitHub 仓库：`https://github.com/dwdw2345/Knowledga`
- GitHub Pages：`https://dwdw2345.github.io/knowledga/`
- 问答页：`https://dwdw2345.github.io/knowledga/#/ask`
- GitHub Actions：`Daily knowledge base`，每天北京时间约 06:00 抓取/构建/提交
- Netlify：待连接（Import from Git，或 `https://app.netlify.com/start/deploy?repository=https://github.com/dwdw2345/Knowledga`）

---

## 一、目录结构

```
运动科学知识库/
├─ index.html                 # 前端（手机优先）
├─ data/
│  ├─ curated.json            # 四学科核心笔记 + 交叉主题（人工/智能体整理）
│  ├─ journals.json           # 期刊清单（ISSN、学科）
│  ├─ keywords.json           # 学科关键词（用于相关度筛选）
│  ├─ latest.json             # 抓取到的文献（原始）
│  ├─ seen.json               # 已处理 PMID（去重）
│  ├─ kb.json / kb.js         # 构建产物（前端加载）
│  └─ archive/                # 每日抓取归档
├─ scripts/
│  ├─ kb_update.py            # 每日抓取 PubMed
│  └─ kb_build.py             # 合并 + 关键词筛选 + 生成 kb.js
├─ daily/                     # 每日 Markdown 摘要（只列原文信息）
└─ .github/workflows/daily.yml# GitHub Actions 每日任务
```

---

## 二、本地预览

```bash
cd 运动科学知识库
python -m http.server 8080
# 打开 http://localhost:8080/
```

也可以直接双击 `index.html`（`kb.js` 是本地脚本，不依赖网络）。

首次或修改 `curated.json` 后：

```bash
python scripts/kb_build.py
```

---

## 三、每日更新

```bash
python scripts/kb_update.py --days 7
python scripts/kb_build.py
```

- `--days 7`：抓最近 7 天；
- `--max-per-journal 8`：每本期刊最多 8 条；
- `--only "Journal of Orthopaedic"`：只抓某本（测试用）；
- `--dry-run`：只打印，不写文件；
- 可选环境变量 `NCBI_API_KEY`（提高 NCBI 频率限制）。

脚本会：
1. 按 `journals.json` 的 ISSN 查询 PubMed；
2. 保存标题、作者、期刊、日期、摘要、PMID、DOI、链接；
3. 按 `keywords.json` 计算相关度（标题命中权重 2，摘要命中权重 1，≥2 进入前端）；
4. 去重（`seen.json`）、归档（`archive/`）、生成 `daily/YYYY-MM-DD.md`；
5. 保留最近 300 条原始记录。

> 抓取失败时保留旧数据，不会用空内容覆盖。

### Windows 证书问题

如果本地 Python 报 `CERTIFICATE_VERIFY_FAILED`，脚本会自动用系统 `curl` 兜底，并在 Windows 上加 `--ssl-no-revoke`（关闭吊销检查，仍校验证书链）。GitHub Actions 不需要这个兜底。

---

## 四、前端怎么用

- **总览**：四学科入口、交叉主题、最新文献。
- **学科**：四门学科的核心笔记；点开看摘要、关键点、证据等级、来源、相关笔记。
- **交叉**：同一问题四学科视角 + 整合方案 + 红旗。
- **每日**：按学科筛选最新文献；每条带 PMID/DOI 链接和原文摘要。
- **关于**：证据分级、自动化方式、免责声明。

搜索框可搜笔记、交叉主题、文献标题/摘要。

---

## 五、怎么新增/修改笔记

编辑 `data/curated.json`，在对应学科的 `notes` 数组里加：

```json
{
  "id": "unique-id",
  "title": "标题",
  "summary": "2–3 句总结",
  "points": ["要点1", "要点2"],
  "evidence": "A/B/C",
  "sources": ["来源1", "来源2"],
  "related": ["另一个 note id 或 cross id"],
  "tags": ["标签"]
}
```

然后：

```bash
python scripts/kb_build.py
```

- `evidence`：A=指南/教科书/系统综述；B=单项研究/机制/综述；C=模型/假说/经验/证据有限。
- `related` 写错会在构建时警告（不会静默丢）。
- 交叉主题在 `cross` 数组；`sections` 里放 four disciplines 的视角。

---

## 六、GitHub Actions 每日自动更新

1. 新建 GitHub 仓库（例如 `sports-knowledge`），把本文件夹推上去；
2. 仓库 **Settings → Actions → General → Workflow permissions** 选 **Read and write permissions**；
3. 可选：**Settings → Secrets and variables → Actions** 添加 `NCBI_API_KEY`（NCBI 免费申请）；
4. **Actions → Daily knowledge base → Run workflow** 手动跑一次；
5. 之后每天北京时间 06:00 自动运行：
   - 抓取 → 构建 → 提交 `data/` 与 `daily/`；
   - 如果 Netlify 已连接仓库，自动部署；如果用 GitHub Pages，Pages 会自动重建。

### 部署方式

**A. Netlify（推荐，和现有工作台同一套）**
- Netlify → Add new site → Import from Git → 选仓库；
- Build command 留空；Publish directory 填 `/`；
- 之后每次 Actions 提交，Netlify 自动部署。

**B. GitHub Pages**
- Settings → Pages → Deploy from a branch → `main` / root；
- 访问 `https://<user>.github.io/<repo>/`；
- Actions 提交后 Pages 自动更新。

> 如果只想先本地用：每天手动跑两条命令，或 Windows 任务计划程序定时运行。

---

## 七、边界与诚实说明

- **自动任务做的是“抓取、去重、筛选、归档、生成摘要列表”**，不是自动生成医学结论；
- 核心笔记与交叉分析由智能体基于来源整理，必须标证据等级；证据不足会标 C；
- 摘要只代表原文作者观点，单篇研究不能直接当结论；
- 关键词筛选会漏掉一些文章；可以调整 `keywords.json` 或增加期刊；
- 目前不自动下载全文（版权/权限限制），只存 PubMed 摘要与链接；
- 本知识库不构成医疗诊断/治疗建议；疼痛、麻木、无力、红旗症状请先就医。

---

## 八、扩学科/扩期刊

- 加学科：在 `curated.json` 的 `disciplines` 加一项，并在 `index.html` 的底部导航/首页自动读取；
- 加期刊：在 `journals.json` 加 `name/issn/discipline/focus`；
- 加关键词：在 `keywords.json` 对应学科数组加词；
- 加交叉主题：在 `curated.json` 的 `cross` 加一项。

---

## 九、常见问题

**Q：为什么每日文献不是全部期刊文章？**
A：按学科关键词做了相关度筛选（≥2），避免“解剖学教育/传记”等无关内容；原始记录仍在 `latest.json` 和 `archive/`。

**Q：为什么没有自动总结每篇文献？**
A：自动 LLM 总结容易引入无来源结论。当前策略是“原文摘要 + 人工/智能体复核”。如果以后接入 API，应保留引用与证据等级，不能直接发布。

**Q：数据会丢吗？**
A：`latest.json`、`seen.json`、`archive/` 都在仓库里；Actions 失败不会清空旧数据。

**Q：能离线用吗？**
A：可以，`index.html` + `data/kb.js` 本地打开即可；只是每日更新需要联网。
