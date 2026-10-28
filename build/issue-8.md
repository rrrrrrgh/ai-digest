# 最近这些AI项目有点东西

这期是电脑没人看着时自动出的「速报」：项目介绍已经翻成中文，配了图和演示，但我不吹彩虹屁——想看带梗的精读版，等你打开电脑叫我一声。

> 筛选只看三件事：涨星速度、新鲜度、是不是真能上手。介绍来自项目 README 的翻译整理，原文放在每张卡片下面一行，方便你核对。

## 1. 🔭 android-ad-cleaner
`rddmwmddr/android-ad-cleaner` · ★4.2k · +938/天 · Python · 4 天龄

**插上手机点几下，把国产安卓系统里的广告和推荐关掉。**

**为啥值得看**

- 一天涨九百多星，说明被系统广告烦到的人真不少
- 不root不卸载，只用系统公开设置项，风险比刷机小
- 按机型系统版本存脚本，找不到入口会跳过不乱点

**上手难度**：要装 App，手机端折腾；装个 Python 环境就能跑

> 💡 可以先这么玩：先跑通用检测看能关多少，再找自己机型的脚本；不在表里就照文档写一份提PR。

[打开 GitHub](https://github.com/rddmwmddr/android-ad-cleaner)

## 2. 🔭 gpu-unlock
`Zagitta/gpu-unlock` · ★1.2万 · +1138/天 · C · 11 天龄

**给 GeForce 显卡解除出厂 AI 算力封印，让它跑满血。**

**为啥值得看**

- 这两天涨星一千多，AI 算力紧张，白捡一倍速度很香
- 同价位 GeForce 只要解锁，速度就能接近专业卡
- 适合 Linux 用户本地跑模型；笔记本和 Windows 用不了

**上手难度**：看 README 照着装，一般半小时内

> 💡 可以先这么玩：找台 Linux 台式机，按 README 装好重启，跑个 FP16 模型对比解锁前后的速度。

[打开 GitHub](https://github.com/Zagitta/gpu-unlock)

## 3. 🔭 opencodex
`lidge-jun/opencodex` · ★1.8万 · +137/天 · TypeScript · 4 个月龄

**给 Codex 和 Claude Code 换脑子的本地中转站**

**为啥值得看**

- 一天涨 130 多星，说明很多人正被单一模型绑住手脚
- 和换工具比，它让你留着顺手的 CLI，只换背后模型
- 想省钱或试新模型的人适合，但得自己管 Key 和本地服务

**上手难度**：装个 Node 就能跑

> 💡 可以先这么玩：先装好 Node，clone 下来跑起代理，拿一个 DeepSeek 的 Key 接进 Claude Code 试试。

[打开 GitHub](https://github.com/lidge-jun/opencodex)

## 4. 🔭 open-seo-mcp-skills
`Ryze-AI-Adgent/open-seo-mcp-skills` · ★7.8k · +130/天 · Shell · 9 周龄

**给 Claude 装个 SEO 外挂，用你自己的网站数据查关键词、看排名。**

**为啥值得看**

- SEO 工具圈最近很热，但多数只是套壳收订阅费，这个直接开源技能。
- 跑的是你自己 GSC/GA4 的真实数据，不是别人瞎编的估算。
- 技能是 MIT 协议，能改能抄，适合想折腾 SEO 又不想被月费绑住的人。

**上手难度**：看 README 照着装，一般半小时内

> 💡 可以先这么玩：先照 README 那条命令把 MCP 加上，连上你的 GSC 账号，让 Claude 查一个你网站的关键词试试。

[打开 GitHub](https://github.com/Ryze-AI-Adgent/open-seo-mcp-skills)

---

速报只解决「不漏」。精读版会解释这东西到底能干嘛、坑在哪、你该不该动手。

_AI 项目雷达 · 第 8 期（自动速报）· 2026-10-28_