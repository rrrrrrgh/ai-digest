#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 项目雷达：抓 GitHub 上最近冒头、正在涨星的 AI 项目。

用法:
    python fetch_repos.py                # 用 config.json
    python fetch_repos.py --days 60      # 只看最近 60 天创建的
    python fetch_repos.py --readme       # 额外抓 Top 项目的 README 摘要(更慢)

输出: candidates.json  (给下游选题/写作使用)
退出码: 0 正常, 3 网络不可用(GitHub 打不开，可能梯子没开)
"""
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")
OUT = os.path.join(HERE, "candidates.json")
UA = {"User-Agent": "ai-digest/1.0", "Accept": "application/vnd.github+json"}
API = os.environ.get("GITHUB_API_BASE", "https://api.github.com").rstrip("/")
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()


def log(*a):
    print(*a, flush=True)


def http_json(url, timeout=20, retries=2):
    headers = dict(UA)
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 429, 500, 502, 503, 504):
                time.sleep(2 + 2 * i)
                continue
            raise
        except Exception as e:  # URLError / timeout / tls
            last = e
            time.sleep(1.5 + 1.5 * i)
    raise last


def http_text(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-digest/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def pick_api():
    """直连 api.github.com；不通就试几个镜像代理（梯子没开时的兜底）。"""
    global API
    candidates = [API] + [c.rstrip('/') for c in
                          ("https://gh-proxy.com/https://api.github.com",
                           "https://ghfast.top/https://api.github.com")]
    seen = []
    for base in candidates:
        if base in seen:
            continue
        seen.append(base)
        try:
            r = http_json(base + "/rate_limit", timeout=8, retries=0)
            if "resources" in r:
                API = base
                log(f"   接口地址: {base}")
                return True
        except Exception:
            log(f"   接口不通: {base}")
    return False


def utcnow():
    return datetime.now(timezone.utc)


def days_since(iso):
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return 9999
    return max(0.0, (utcnow() - d).total_seconds() / 86400.0)


def is_noise(repo, noise):
    name = (repo.get("full_name") or "").lower()
    desc = (repo.get("description") or "").lower()
    topics = " ".join(repo.get("topics") or []).lower()
    blob = f"{name} {desc} {topics}"
    for bad in noise:
        if bad.lower() in blob:
            return True
    # 纯资源库 / 纯文档: 语言为空 + 没代码迹象
    if not repo.get("language") and not repo.get("topics"):
        return True
    return False


def score(repo, bonus):
    stars = repo.get("stargazers_count") or 0
    age = max(days_since(repo.get("created_at") or ""), 1.0)
    vel = stars / age  # 每天涨多少星
    s = math.log1p(vel) * 14 + math.log1p(stars) * 3
    # 最近还在更新，加分
    idle = days_since(repo.get("pushed_at") or "")
    if idle < 3:
        s += 6
    elif idle > 60:
        s -= 10
    desc = ((repo.get("description") or "") + " " + " ".join(repo.get("topics") or [])).lower()
    for kw, w in bonus.items():
        if kw.lower() in desc:
            s += w
    if repo.get("archived"):
        s -= 50
    return round(s, 2), round(vel, 1)


def main():
    ap = sys.argv[1:]
    days = 150
    want_readme = "--readme" in ap
    for i, a in enumerate(ap):
        if a == "--days" and i + 1 < len(ap):
            days = int(ap[i + 1])
        if a.startswith("--days="):
            days = int(a.split("=", 1)[1])

    cfg = json.load(open(CONFIG, encoding="utf-8"))
    min_stars = cfg["min_stars"]
    since = (utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    noise = cfg["noise"]
    bonus = cfg["bonus"]

    log(f"[1/3] 抓取中 · 时间窗 {since} 起 · 至少 {min_stars} 星")
    if not pick_api():
        log("!! GitHub API 完全不通 —— 梯子没开？")
        return 3
    seen = {}
    for item in cfg["queries"]:
        q = item["q"].format(since=since, min=min_stars)
        url = (f"{API}/search/repositories?q={urllib.parse.quote(q)}"
               f"&sort={item.get('sort','stars')}&order=desc&per_page=50")
        try:
            data = http_json(url)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):                 # 未登录的搜索接口限速，歇一会儿再试
                log(f"  ~ {item['label']} 被限速，等 30 秒重试")
                time.sleep(30)
                try:
                    data = http_json(url)
                except Exception as e3:
                    log(f"  ! {item['label']} 仍然失败: {type(e3).__name__}")
                    continue
            elif e.code == 422 and "topic:" in q:      # 这个 topic 不存在，退化成普通关键词
                q2 = q.replace("topic:", "")
                url2 = (f"{API}/search/repositories?q={urllib.parse.quote(q2)}"
                        f"&sort={item.get('sort','stars')}&order=desc&per_page=50")
                try:
                    data = http_json(url2)
                except Exception as e2:
                    log(f"  ! {item['label']} 失败: {type(e2).__name__}")
                    continue
            else:
                log(f"  ! {item['label']} 失败: HTTP {e.code}")
                continue
        except Exception as e:
            log(f"  ! {item['label']} 失败: {type(e).__name__}")
            continue
        n_new = 0
        for r in data.get("items", []):
            key = r["full_name"].lower()
            if key in seen:
                continue
            seen[key] = r
            n_new += 1
        log(f"  · {item['label']:<12} +{n_new:<3} (累计 {len(seen)})")
        time.sleep(6.0)

    if not seen:
        log("!! 一个项目都没抓到 —— GitHub API 不通，大概率是梯子没开。")
        return 3

    log(f"[2/3] 过滤 & 打分（{len(seen)} 个候选）")
    scored = []
    for r in seen.values():
        if is_noise(r, noise):
            continue
        s, vel = score(r, bonus)
        scored.append({
            "full_name": r["full_name"],
            "url": r["html_url"],
            "desc": (r.get("description") or "").strip(),
            "stars": r.get("stargazers_count") or 0,
            "stars_per_day": vel,
            "created": (r.get("created_at") or "")[:10],
            "age_days": round(days_since(r.get("created_at") or ""), 1),
            "pushed": (r.get("pushed_at") or "")[:10],
            "language": r.get("language"),
            "topics": r.get("topics") or [],
            "forks": r.get("forks_count") or 0,
            "homepage": r.get("homepage") or "",
            "score": s,
        })
    scored.sort(key=lambda x: -x["score"])
    top = scored[: cfg["top_n"]]

    if want_readme:
        log(f"[3/3] 抓 README 摘要（前 {min(12, len(top))} 个）")
        for it in top[:12]:
            for br in ("main", "master"):
                try:
                    txt = http_text(
                        f"https://raw.githubusercontent.com/{it['full_name']}/{br}/README.md",
                        timeout=12)
                    txt = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", txt)
                    txt = re.sub(r"<[^>]+>", " ", txt)
                    txt = re.sub(r"[ \t]+", " ", txt)
                    lines = [l.strip() for l in txt.splitlines()
                             if l.strip() and not l.strip().startswith(("|", "```", "#", ">", "-", "="))]
                    it["readme"] = " ".join(lines)[:900]
                    break
                except Exception:
                    continue
            time.sleep(0.2)
    else:
        log("[3/3] 跳过 README")

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "window_days": days,
        "count": len(top),
        "repos": top,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    log(f"\n✅ 写入 {OUT} · {len(top)} 个项目\n")
    for i, it in enumerate(top[:20], 1):
        log(f"{i:>2}. ★{it['stars']:>6} (+{it['stars_per_day']:>5}/天) "
            f"{it['full_name']}\n    {(it['desc'] or '')[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
