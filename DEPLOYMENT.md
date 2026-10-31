# 部署清单（GitHub Actions + Netlify）

> 上传包：`D:\DSH工作区\运动科学知识库_上传包.zip`（解压后，把里面的**内容**上传到仓库根目录；`index.html` 要在根目录）。

目标：仓库每天自动抓 PubMed → 重新构建 → 提交 → Netlify 自动部署。

> 当前电脑没有 git / gh / netlify CLI 的登录态，所以最后“创建仓库/连接 Netlify”需要你在浏览器点授权。  
> 如果给我一个 GitHub Personal Access Token（repo 权限）或仓库地址，我可以直接帮你推送。

---

## 一、把文件夹变成 GitHub 仓库

**仓库根目录必须是 `运动科学知识库` 里的内容**，不要多套一层文件夹。

需要上传的内容：

```
index.html
netlify.toml
README.md
data/
scripts/
.github/workflows/daily.yml
daily/
.gitignore
```

### 方法 A：GitHub 网页上传（不需要装 git）

1. GitHub → New repository → 名称如 `sports-knowledge`（Private/Public 均可）；
2. 仓库页 → **Add file → Upload files**；
3. 把 `运动科学知识库` 里的**文件和文件夹**拖进去（`index.html` 要在仓库根目录）；
4. Commit changes。

### 方法 B：GitHub Desktop / 命令行

```bash
cd "D:\DSH工作区\运动科学知识库"
git init
git add .
git commit -m "init sports knowledge base"
git branch -M main
git remote add origin https://github.com/<你的用户名>/sports-knowledge.git
git push -u origin main
```

---

## 二、开启 Actions 写权限

1. 仓库 → **Settings → Actions → General**；
2. **Workflow permissions** → 选 **Read and write permissions** → Save；
3. 可选：**Settings → Secrets and variables → Actions → New repository secret**
   - Name: `NCBI_API_KEY`
   - Value: NCBI 免费申请的 API Key（提高抓取频率上限；不填也能跑）。

---

## 三、手动跑一次每日任务

1. 仓库 → **Actions** → 左侧 **Daily knowledge base**；
2. 右侧 **Run workflow** → Run；
3. 等 1–3 分钟，应看到：
   - `data/latest.json` 更新；
   - `daily/日期.md` 新增；
   - 自动 commit。

如果失败，点进日志看：
- `CERTIFICATE_VERIFY_FAILED`：GitHub Actions 一般不会；本地脚本有 curl 兜底。
- 403 / rate limit：加 `NCBI_API_KEY`。
- `git push` 失败：检查 Actions 写权限。

---

## 四、Netlify 连接仓库

1. Netlify → **Add new site → Import an existing project**；
2. 选 **GitHub** → 授权 → 选 `sports-knowledge`；
3. 配置：
   - **Build command**：留空；
   - **Publish directory**：`.`（根目录）；
   - 其他默认；
4. Deploy site；
5. 得到网址，如 `https://sports-knowledge-xxx.netlify.app/`；
6. 手机 Safari 打开 → 分享 → 添加到主屏幕。

之后 Actions 每次提交，Netlify 会自动重新部署。

> 如果 Netlify 用拖拽部署（不用 Git），也可以上线，但**不会**随 GitHub Actions 自动更新；每日更新需要重新拖。要自动更新，请用 Import from Git。

---

## 五、验证

- 首页显示 48 篇笔记 / 5 个交叉 / 期刊数 / 文献数；
- 「每日」能看到最新文献，点 PMID 能跳 PubMed；
- 「交叉」能看到 5 个专题；
- 手机打开不白屏；
- Actions 第二天自动跑一次（北京时间 06:00 左右）。

---

## 六、如果让我直接部署

把以下任一信息发我即可：

1. GitHub 仓库地址 + 有 repo 权限的 Personal Access Token；或
2. 你已建好仓库，我只需要给远程地址和分支；或
3. Netlify 的 Personal Access Token + 站点名（如果要我直接建站/触发部署）。

没有 token 时，我无法替你登录 GitHub/Netlify；这是账号授权限制，不是代码问题。
