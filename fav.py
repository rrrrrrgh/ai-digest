#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收藏清单的「落地」工具：把手机上复制出来的清单存到 favorites.md，方便以后翻。

用法:
    python fav.py --add "【AI雷达收藏 · 3 个】\n1. lexmount/moli — 给 AI 用的迷你浏览器\n..."
    python fav.py --list
    python fav.py --add-file some.txt
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "favorites.md")

HEAD = """# 我收藏的项目

> 从手机微信「AI 项目雷达」里点红心收藏，再点「复制清单」粘过来，就能攒到这里。
> 想聊哪个，直接说编号或名字。

"""


def parse(text):
    items = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^(\d+)[.、]\s*([\w.\-]+/[\w.\-]+)\s*(?:[—-]+\s*(.*))?$", line)
        if m:
            items.append({"repo": m.group(2).strip(),
                          "one": (m.group(3) or "").strip().rstrip("）)")})
    return items


def load():
    if not os.path.exists(STORE):
        return []
    out, cur = [], None
    for line in open(STORE, encoding="utf-8"):
        m = re.match(r"^- \[ \] `([^`]+)`(?: — (.*))?$", line.strip())
        if m:
            cur = {"repo": m.group(1), "one": (m.group(2) or "").strip()}
            out.append(cur)
    return out


def save(items):
    seen, rows = set(), []
    for it in items:
        if it["repo"] in seen:
            continue
        seen.add(it["repo"])
        rows.append(f'- [ ] `{it["repo"]}`' + (f' — {it["one"]}' if it["one"] else ""))
    with open(STORE, "w", encoding="utf-8") as f:
        f.write(HEAD + f"（更新于 {time.strftime('%Y-%m-%d %H:%M')}）\n\n" + "\n".join(rows) + "\n")
    return len(rows)


def parse_issues(issues):
    """从 GitHub issue 列表里挑出 [收藏] xxx 的条目。"""
    items = []
    for it in issues:
        if it.get("pull_request"):
            continue
        title = (it.get("title") or "").strip()
        m = re.match(r"^\[收藏\]\s*([\w.\-]+/[\w.\-]+)", title)
        if not m:
            continue
        body = (it.get("body") or "").strip()
        one = ""
        for line in body.splitlines():
            line = line.strip()
            if line and not line.startswith("http") and "（从微信" not in line:
                one = line[:60]
                break
        items.append({"repo": m.group(1), "one": one})
    return items


def _scrape_issues(repo):
    """API 被限流时的兜底：直接抓 issues 页面里的内嵌 JSON。"""
    import urllib.request
    found = []
    for q in ("is%3Aissue", "is%3Aissue+is%3Aclosed"):
        url = f"https://github.com/{repo}/issues?q={q}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
        m = re.search(
            r'<script type="application/json" data-target="react-app.embeddedData">(.*?)</script>',
            html, re.S)
        if not m:
            continue
        data = json.loads(m.group(1))

        def walk(o):
            if isinstance(o, dict):
                if isinstance(o.get("title"), str) and "number" in o:
                    found.append({"title": o.get("title"), "body": o.get("body") or "",
                                  "state": (o.get("state") or "")})
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(data)
    uniq, seen = [], set()
    for it in found:
        k = (it["title"], it["body"][:40])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    return uniq


def sync_from_github(repo=None):
    """从 GitHub issue 拉收藏（标题形如 `[收藏] owner/repo`），合并进 favorites.md。"""
    import urllib.request
    if not repo:
        for fn in ("channels.json", "config.json"):
            p = os.path.join(HERE, fn)
            if os.path.exists(p):
                try:
                    cfg = json.load(open(p, encoding="utf-8-sig"))
                    repo = repo or (cfg.get("fav_repo") or "").strip()
                except Exception:
                    pass
    if not repo:
        raise SystemExit("还没配置仓库：在 channels.json 里加 "
                         '"fav_repo": "你的用户名/仓库名"')
    url = (f"https://api.github.com/repos/{repo}/issues"
           f"?state=all&per_page=100&sort=created&direction=desc")
    headers = {"User-Agent": "ai-digest/1.0", "Accept": "application/vnd.github+json"}
    tk = os.environ.get("GITHUB_TOKEN", "").strip()
    if tk:
        headers["Authorization"] = "Bearer " + tk
    issues = None
    try:
        url = (f"https://api.github.com/repos/{repo}/issues"
               f"?state=all&per_page=100&sort=created&direction=desc")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=25) as r:
            issues = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print(f"接口不可用（{type(e).__name__}），改用抓页面…")
        issues = _scrape_issues(repo)
    items = parse_issues(issues or [])
    if not items:
        print(f"{repo} 里还没有带「[收藏] 」标题的 issue "
              f"（现有 {len(issues or [])} 条 issue，但标题不匹配，或者仓库是私有的）")
        return
    n = save(load() + items)
    print(f"仓库里有 {len(items)} 条收藏，去重后本地共 {n} 个 → {STORE}")
    for x in items:
        print("  ·", x["repo"], "—", x["one"][:40])


def sync_from_worker(base=None, key=None):
    """从 Cloudflare Worker 拉收藏（/j/{key} 返回 JSON），合并进 favorites.md。"""
    import urllib.request
    if not (base and key):
        ch = os.path.join(HERE, "channels.json")
        if os.path.exists(ch):
            cfg = json.load(open(ch, encoding="utf-8-sig"))
            base = base or cfg.get("fav_base")
            key = key or cfg.get("fav_key")
    if not (base and key):
        raise SystemExit("还没配置收藏服务：在 channels.json 里加 "
                         '\"fav_base\": \"https://xxx.workers.dev\", \"fav_key\": \"暗号\"')
    url = f"{base.rstrip('/')}/j/{key}"
    req = urllib.request.Request(url, headers={"User-Agent": "ai-digest/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        remote = json.loads(r.read().decode("utf-8", "replace"))
    items = [{"repo": x.get("repo", ""), "one": (x.get("one") or "").strip()} for x in remote]
    items = [x for x in items if x["repo"]]
    merged = load() + items
    n = save(merged)
    print(f"云端有 {len(items)} 个，去重后本地共 {n} 个 → {STORE}")
    for x in items:
        print("  ·", x["repo"], "—", x["one"][:40])


def main():
    args = sys.argv[1:]
    if "--sync-github" in args:
        repo = None
        for i, a in enumerate(args):
            if a == "--repo" and i + 1 < len(args):
                repo = args[i + 1]
        sync_from_github(repo)
        return
    if "--sync" in args:
        base = key = None
        for i, a in enumerate(args):
            if a == "--base" and i + 1 < len(args):
                base = args[i + 1]
            if a == "--key" and i + 1 < len(args):
                key = args[i + 1]
        sync_from_worker(base, key)
        return
    if "--list" in args or not args:
        items = load()
        print(f"收藏 {len(items)} 个：")
        for i, it in enumerate(items, 1):
            print(f"  {i}. {it['repo']}" + (f" — {it['one']}" if it["one"] else ""))
        return
    text = ""
    for i, a in enumerate(args):
        if a in ("--add", "--add-file") and i + 1 < len(args):
            text = args[i + 1]
            if a == "--add-file":
                text = open(text, encoding="utf-8").read()
    if not text:
        raise SystemExit("用法：python fav.py --add \"【AI雷达收藏 ...】\"")
    new = parse(text)
    if not new:
        raise SystemExit("没解析到项目。清单应该长这样：\n1. owner/repo — 一句话")
    merged = load() + new
    n = save(merged)
    print(f"新增 {len(new)} 个，现有 {n} 个 → {STORE}")
    for it in new:
        print("  +", it["repo"], "—", it["one"][:40])


if __name__ == "__main__":
    main()
