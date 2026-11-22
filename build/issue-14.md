# 老代码换 Rust，有人连比对工具都做好了

这期是电脑没人看着时自动出的「速报」：项目介绍已经翻成中文，配了图和演示，但我不吹彩虹屁——想看带梗的精读版，等你打开电脑叫我一声。

> 筛选只看三件事：涨星速度、新鲜度、是不是真能上手。介绍来自项目 README 的翻译整理，原文放在每张卡片下面一行，方便你核对。

## 1. 🔭 rust-anything
`erkamyaman/rust-anything` · ★7.9k · +1254/天 · Rust · 6 天龄

**把老代码一块块换成 Rust，每换一块都拿原件比对行为**

**为啥值得看**

- Prettier 的 Rust 版已跑通 1.7 万条记录，字节级一致，这事刚被验证
- 涨星一天一千多，说明「AI 写重写、工具做裁判」正成为新玩法
- 不是自动翻译代码，而是拿行为当裁判，比纯 AI 改写更敢信

**上手难度**：装个 Node 就能跑；装个 Python 环境就能跑

> 💡 可以先这么玩：找个你熟悉的小 CLI 项目，先跑 record 录下行为，再让 AI 写一小块 Rust 试试 diff。

[打开 GitHub](https://github.com/erkamyaman/rust-anything)

## 2. 🔭 neonclipping
`iamajmeena/neonclipping` · ★2.1k · +608/天 · Python · 3 天龄

**把长视频自动剪成竖屏带字幕片段，像有个剪辑小工。**

**为啥值得看**

- 涨星约 608/天，说明很多人正需要这种本地剪辑工具
- 和在线剪辑服务比，它不传视频、不要订阅，隐私和成本都省
- 做短视频搬运或切片的人可以先用它粗筛，再人工挑

**上手难度**：装个 Python 环境就能跑

> 💡 可以先这么玩：先拿一段 10 分钟的 YouTube 视频试，看它切出来的片段合不合你口味，再上长直播。

[打开 GitHub](https://github.com/iamajmeena/neonclipping)

## 3. 🔭 gods-eye-view
`bilawalsidhu/gods-eye-view` · ★6.6万 · +434/天 · JavaScript · 5 个月龄

**把卫星、飞机、轮船的公开数据全叠在一个 3D 地球仪上，像开间谍卫星。**

**为啥值得看**

- YouTube 上同名系列播放量超 2500 万，自带流量和教程
- 和普通航班追踪网站不同，它把天上地下海里的信号汇到一张图
- 星数一周涨几十万，现在进去还算早期，社区正热

**上手难度**：装个 Node 就能跑

> 💡 可以先这么玩：先上官网 godseyeview.ai 看演示，再进 hosted 版排队，或找 Pinokio 一键装本地跑。

[打开 GitHub](https://github.com/bilawalsidhu/gods-eye-view)

## 4. 🔭 open-code-review
`alibaba/open-code-review` · ★5.5万 · +293/天 · Go · 6 个月龄

**阿里内部用了两年的 AI 代码审查工具，现在开源了**

**为啥值得看**

- 阿里内部几万人用过，踩过的坑比一般开源项目多
- 和纯大模型审查不同，规则管死问题、模型管上下文
- 涨星快得离谱，说明很多人正被代码审查折磨

**上手难度**：看 README 照着装，一般半小时内

> 💡 可以先这么玩：装好后配个模型 Key，在项目里跑一次审查，看它挑出的第一条评论准不准。

[打开 GitHub](https://github.com/alibaba/open-code-review)

---

速报只解决「不漏」。精读版会解释这东西到底能干嘛、坑在哪、你该不该动手。

_AI 项目雷达 · 第 14 期（自动速报）· 2026-11-22_