#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""电脑没人看着的时候用的「自动速报」：从 candidates.json 挑几个，生成一期 issue。

和人写的精读版共用同一套渲染/推送。区别是：文案由规则拼装（不瞎编，项目描述用原文），
所以它保守、诚实、但没那么好看——定位是「不漏」，不是「好看」。

用法:
    python build_auto_issue.py                    # 输出 auto-issue.json
    python build_auto_issue.py --n 4 --force      # 强制出期
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = os.path.join(HERE, "candidates.json")
STATE = os.path.join(HERE, "state.json")
OUT = os.path.join(HERE, "auto-issue.json")

TOPIC_CN = {
    "ai-agent": "AI Agent", "ai-agents": "AI Agent", "agent": "AI Agent",
    "llm": "大模型", "llm-app": "大模型应用", "mcp": "MCP 工具", "rag": "检索增强",
    "text-to-video": "视频生成", "video-generation": "视频生成", "ai-video": "视频生成",
    "image-generation": "图像生成", "tts": "语音", "text-to-speech": "语音",
    "voice-cloning": "声音克隆", "music-generation": "音乐生成",
    "local-llm": "本地模型", "local-first": "本地优先", "self-hosted": "自部署",
    "game": "游戏", "fun": "脑洞", "ai-tools": "AI 工具", "developer-tools": "开发工具",
    "browser-automation": "浏览器自动化", "computer-use": "电脑操作",
    "hardware": "硬件", "esp32": "硬件", "claude-code": "Coding Agent", "codex": "Coding Agent",
}

DIFFICULTY = [
    (r"\b(esp32|arduino|raspberry|stm32|usb hid)\b", "要买硬件（一块开发板 + 会烧固件）"),
    (r"\b(ios|iphone|android)\b", "要装 App，手机端折腾"),
    (r"\b(docker|compose|kubernetes)\b", "有 docker，一条命令拉起"),
    (r"\b(npx|npm|node|typescript|javascript)\b", "装个 Node 就能跑"),
    (r"\b(pip|python|conda)\b", "装个 Python 环境就能跑"),
    (r"\b(cuda|gpu|vram|24gb)\b", "要显卡，显存越大越好"),
    (r"\b(macos|swift|xcode)\b", "要 Mac"),
]


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding="utf-8-sig"))
    return {"last_issue": 0, "sent_repos": [], "last_sent": ""}


def label_of(repo):
    for t in repo.get("topics") or []:
        if t in TOPIC_CN:
            return TOPIC_CN[t]
    return "AI 项目"


def difficulty_of(repo):
    blob = " ".join([repo.get("desc") or "", " ".join(repo.get("topics") or []),
                     repo.get("language") or ""]).lower()
    hits = [txt for pat, txt in DIFFICULTY if re.search(pat, blob)]
    if not hits:
        return "看 README 照着装，一般半小时内"
    return "；".join(dict.fromkeys(hits[:2]))


def clean_desc(d):
    d = re.sub(r"\s+", " ", (d or "")).strip()
    if len(d) > 240:
        d = d[:240].rstrip() + "…"
    return d or "（作者没写描述，直接看仓库吧）"


def main():
    n = 4
    force = "--force" in sys.argv
    for i, a in enumerate(sys.argv):
        if a == "--n" and i + 1 < len(sys.argv):
            n = int(sys.argv[i + 1])
    if not os.path.exists(CAND):
        raise SystemExit("没有 candidates.json，先跑 fetch_repos.py")
    data = json.load(open(CAND, encoding="utf-8-sig"))
    st = load_state()
    sent = set(st.get("sent_repos") or [])
    cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8-sig"))
    blocked = [b.lower() for b in cfg.get("block", [])]

    picks = []
    used_cat = set()
    for r in data["repos"]:
        if r["full_name"] in sent:
            continue
        blob = ((r.get("desc") or "") + " " + " ".join(r.get("topics") or [])).lower()
        if any(b in blob for b in blocked):
            continue
        cat = label_of(r)
        if cat in used_cat and len(picks) < n - 1:
            continue
        used_cat.add(cat)
        picks.append(r)
        if len(picks) >= n:
            break
    if not picks:
        print("候选都推过了，这期跳过。")
        return 0

    no = int(st.get("last_issue") or 0) + 1
    today = time.strftime("%Y-%m-%d")
    items = []
    for r in picks:
        items.append({
            "emoji": "🔭",
            "name": r["full_name"].split("/")[-1],
            "repo": r["full_name"],
            "tag": label_of(r),
            "meta": f"★{r['stars']:,} · 约 +{r['stars_per_day']:.0f} 星/天 · "
                    f"{r['language'] or '多语言'} · 建库 {r['created']}",
            "one_liner": clean_desc(r["desc"]),
            "why": [f"热度：{r['stars']:,} 星，平均每天涨 {r['stars_per_day']:.0f} 星，"
                    f"仓库 {r['age_days']:.0f} 天大。"],
            "how": difficulty_of(r),
            "url": r["url"],
        })

    issue = {
        "issue_no": no,
        "date": today,
        "push_title": f"速报 · {len(items)} 个正在涨星的 AI 项目（{today[5:]}）",
        "title": f"{len(items)} 个正在涨星的 AI 项目",
        "hook": "这期是电脑没人看着时自动出的「速报」：不写读后感，只挑正在涨星、"
                "值得你自己点开看一眼的项目。",
        "intro": "项目描述保留作者原文（有的本来就是中文），我只负责按热度和新鲜度挑出来。"
                 "想看带人话翻译的精读版，等你打开电脑叫我一声。",
        "picks": items,
        "outro": "速报只解决「不漏」。精读版会解释这东西到底能干嘛、坑在哪、你该不该动手。",
        "footer": f"AI 项目雷达 · 第 {no} 期（自动速报）· {today}",
    }
    json.dump(issue, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"已生成 {OUT} · 第 {no} 期 · {len(items)} 个项目")
    for p in items:
        print("  -", p["repo"], p["meta"])
    # 不在这里记账：等 push.py 真的发出去了再记，避免「生成了但没发」把项目用掉
    return 0


if __name__ == "__main__":
    sys.exit(main())
