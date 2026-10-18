# AI 项目雷达（云端版）

每 3 天，GitHub 的服务器替你去捞最近在涨星的 AI 项目，写成一期图文，推到你的微信。
**不用开电脑，不用开梯子。**

- 内容：每个项目 4 段 —— 这是啥（人话）→ 为啥值得看 → 上手难在哪 → 可以先怎么玩
- 通道：微信「pushplus 推送加」公众号
- 入口：`python cloud_digest.py`（抓 → 组 → 渲 → 发，一条命令）
- 定时：`.github/workflows/digest.yml`，每 3 天 UTC 12:00（北京 20:00）

## 部署（10 分钟）

看 [部署步骤.md](部署步骤.md)，一步一步照着点。

## 本地试跑

```bash
export PUSHPLUS_TOKEN=你的token      # Windows PowerShell: $env:PUSHPLUS_TOKEN="..."
python cloud_digest.py --dry         # 只生成，不发送
python cloud_digest.py --force       # 立刻发一期
```

## 文件

| 文件 | 干什么 |
|---|---|
| `cloud_digest.py` | 一个入口，串起下面四步 |
| `due.py` | 判断"距上期够 3 天了吗"，云端防重复发送 |
| `fetch_repos.py` | 18 组搜索词抓 GitHub，过滤 + 打分 |
| `build_auto_issue.py` | 挑 4 个项目，拼成一期（速报版） |
| `render_issue.py` | 渲染手机宽度 HTML |
| `push.py` | 推送（pushplus / 邮件 / Server酱 / webhook 都支持） |
| `config.json` | 搜索词、星数门槛、拉黑词、加分词 |
| `issue.json` | 第 1 期（精读版，手写内容） |
| `state.json` | 记账：第几期、推过哪些仓库、上次发送时间 |

## 改口味

- 只推某一类：改 `config.json` 的 `queries`（搜索词）/ `block`（拉黑）/ `bonus`（加分）
- 3 天 → 5 天：`due.py` 里的 `MIN_DAYS` + `digest.yml` 的 cron
- 每期几个：`cloud_digest.py --n 3`

## 安全

- token 放 GitHub Secrets，别写进文件（`.gitignore` 已挡住 `channels.json`）
- `state.json` 会被 workflow 自动提交回仓库，这是故意的：防止仓库 60 天没动静被 GitHub 停掉定时任务
