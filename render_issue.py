#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 issue.json 渲染成：手机友好的 HTML / Markdown / 纯文本速览。

用法:
    python render_issue.py issue.json
输出:
    build/issue-<no>.html   (微信里点开就是一张长图的感觉)
    build/issue-<no>.md
    build/issue-<no>.txt    (通知栏预览用的一句话)
"""
import html
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")

CSS_WRAP = ("max-width:680px;margin:0 auto;padding:26px 18px 34px;"
            "font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;"
            "font-size:16px;line-height:1.75;color:#1b1b1f;background:#ffffff;"
            "-webkit-text-size-adjust:100%;word-break:break-word;")
CSS_CARD = ("margin:20px 0 0;padding:18px 16px 16px;background:#f7f8fa;"
            "border-radius:14px;border:1px solid #eceef2;")
CSS_NAME = "font-size:18px;font-weight:700;line-height:1.45;margin:4px 0 6px;color:#111;"
CSS_TAG = ("display:inline-block;font-size:12px;padding:1px 8px;border-radius:20px;"
           "background:#e8f1ff;color:#2b6cb0;margin-right:6px;vertical-align:2px;")
CSS_ONE = "font-size:17px;font-weight:600;line-height:1.7;margin:8px 0 12px;color:#0f172a;"
CSS_BODY = "font-size:15.5px;line-height:1.85;color:#33363d;margin:0 0 10px;"
CSS_META = ("font-size:13px;line-height:1.7;color:#6b7280;background:#fff;"
            "border:1px dashed #dfe3ea;border-radius:10px;padding:9px 12px;margin:12px 0 0;")
CSS_BTN = ("display:block;text-align:center;margin:14px 0 0;padding:11px 12px;"
           "background:#111;color:#fff;text-decoration:none;border-radius:10px;"
           "font-size:15px;font-weight:600;")
CSS_SEC = "font-size:13px;font-weight:700;letter-spacing:.06em;color:#8a8f98;margin:0 0 4px;"
CSS_HR = "border:0;border-top:1px solid #eceef2;margin:28px 0 0;"

# ---- 收藏（红心）样式：独立 <style>，被剥掉也不影响正文 ----
FAV_STYLE = """<style>
.aid-fav{border:1px solid #e3e6ec;background:#fff;color:#8a8f98;border-radius:999px;
  padding:2px 10px;font-size:13px;line-height:1.5;cursor:pointer;
  font-family:-apple-system,'PingFang SC',sans-serif;float:right;margin:-2px -2px 0 0;}
.aid-fav.on{border-color:#ffc9c9;background:#fff5f5;color:#e5484d;}
.aid-bar{margin:22px 0 0;padding:12px 14px;background:#fff5f5;border:1px solid #ffd9d9;
  border-radius:12px;font-size:14px;color:#7a3b3b;line-height:1.7;}
.aid-bar b{color:#e5484d;}
.aid-chip{display:inline-block;margin:4px 6px 0 0;padding:2px 9px;border-radius:999px;
  background:#fff;border:1px solid #ffd9d9;font-size:13px;color:#a13d3d;text-decoration:none;}
</style>"""



def esc(s):
    return html.escape(str(s or ""), quote=True)


def nl(s):
    return esc(s).replace("\n", "<br>")


def li(items):
    return "".join(
        f'<div style="{CSS_BODY}margin-bottom:6px;">'
        f'<span style="color:#9aa0aa;">·</span> {esc(x)}</div>'
        for x in items if str(x).strip())


def fav_config():
    """收藏配置：Worker 模式（fav_base+fav_key）或 GitHub issue 模式（fav_repo）。

    优先级：环境变量 > channels.json（本机私密）> config.json（公开，会进仓库）。
    fav_repo 不是敏感信息，放 config.json 里就不用额外配 Secret。
    """
    base = os.environ.get("FAV_BASE", "").strip()
    key = os.environ.get("FAV_KEY", "").strip()
    frepo = os.environ.get("FAV_REPO", "").strip()
    ch = os.path.join(HERE, "channels.json")
    if os.path.exists(ch):
        try:
            cfg = json.load(open(ch, encoding="utf-8-sig"))
            base = base or (cfg.get("fav_base") or "").strip()
            key = key or (cfg.get("fav_key") or "").strip()
            frepo = frepo or (cfg.get("fav_repo") or "").strip()
        except Exception:
            pass
    if not frepo:
        try:
            pub = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8-sig"))
            frepo = (pub.get("fav_repo") or "").strip()
            base = base or (pub.get("fav_base") or "").strip()
        except Exception:
            pass
    return base.rstrip("/"), key, frepo


def fav_list_url():
    base, key, frepo = fav_config()
    if frepo:
        q = urllib.parse.quote("is:issue [收藏]")
        return f"https://github.com/{frepo}/issues?q={q}"
    if base and key:
        return f"{base}/l/{key}"
    return "#"


def render_html(issue):
    picks = issue["picks"]
    FB, FK, FREPO = fav_config()
    fav_on = bool(FREPO) or bool(FB and FK)

    def fav_link(item):
        repo = (item.get("repo") or "").strip()
        if not repo:
            return "#"
        if FREPO:
            title = urllib.parse.quote(f"[收藏] {repo}")
            body = urllib.parse.quote(
                f"{item.get('one_liner') or ''}\n\n{item.get('url') or ''}\n\n"
                "（从微信推送里点爱心自动建的，用来攒收藏清单）")
            return (f"https://github.com/{FREPO}/issues/new"
                    f"?title={title}&body={body}")
        name = urllib.parse.quote((item.get("name") or "")[:30])
        one = urllib.parse.quote((item.get("one_liner") or "")[:60])
        return f"{FB}/a/{FK}/{urllib.parse.quote(repo)}?n={name}&o={one}"

    parts = []
    parts.append(FAV_STYLE)
    parts.append(f'<div style="{CSS_WRAP}">')
    badge = ("机翻" if issue.get("copy_mode") == "mt" else
             "AI 润色" if issue.get("copy_mode") == "llm" else "")
    parts.append(f'<div style="{CSS_SEC}">第 {issue.get("issue_no",1)} 期 · '
                 f'{esc(issue.get("date",""))}' + (f' · {badge}' if badge else '')
                 + '</div>')
    parts.append(f'<div style="font-size:23px;font-weight:800;line-height:1.4;color:#0b0d12;'
                 f'margin:6px 0 14px;">{esc(issue["title"])}</div>')
    if issue.get("hook"):
        parts.append(f'<div style="font-size:16.5px;line-height:1.8;color:#3b3f47;'
                     f'margin:0 0 6px;">{esc(issue["hook"])}</div>')
    if issue.get("intro"):
        parts.append(f'<div style="font-size:15px;line-height:1.85;color:#6b7280;'
                     f'margin:10px 0 0;">{esc(issue["intro"])}</div>')

    if len(picks) > 1:
        parts.append('<div style="margin:18px 0 0;padding:13px 15px;background:#f2f5fa;'
                     'border-radius:12px;">')
        parts.append(f'<div style="{CSS_SEC}">本期速览 · 点一句直接跳</div>')
        for i, q in enumerate(picks, 1):
            short = re.sub(r'\s+', ' ', (q.get("one_liner") or ""))[:26]
            parts.append(f'<a href="#p{i}" style="display:block;padding:5px 0;'
                         f'font-size:14.5px;line-height:1.65;color:#22262e;'
                         f'text-decoration:none;"><span style="color:#98a2b3;">{i}.</span> '
                         f'{esc(q["name"])} — {esc(short)}…</a>')
        parts.append('</div>')

    if fav_on:
        parts.append(f'<a href="{esc(fav_list_url())}" style="display:inline-block;'
                     f'margin:14px 0 0;font-size:13.5px;color:#e5484d;'
                     f'text-decoration:none;">&#9829; 我的收藏清单</a>')

    for i, p in enumerate(picks, 1):
        parts.append(f'<div id="p{i}" style="{CSS_CARD}">')
        parts.append('<div>'
                     + (f'<a class="aid-fav" style="text-decoration:none;" href="{esc(fav_link(p))}">'
                        f'&#9825; 收藏</a>' if fav_on else "")
                     + (f'<span style="{CSS_TAG}">{esc(p["tag"])}</span>' if p.get("tag") else "")
                     + (f'<span style="font-size:12px;color:#98a2b3;">{esc(p.get("meta",""))}</span>'
                        if p.get("meta") else "")
                     + (f'<span style="font-size:11.5px;color:#b08968;margin-left:6px;">'
                        f'· 之前推过</span>' if p.get("repeat") else "")
                     + '</div>')
        parts.append(f'<div style="{CSS_NAME}">{esc(p.get("emoji",""))} '
                     f'{i}. {esc(p["name"])}</div>')
        if p.get("tags"):
            chips = "".join(
                f'<span style="display:inline-block;font-size:11.5px;line-height:1.6;'
                f'padding:1px 7px;margin:2px 5px 2px 0;border-radius:20px;'
                f'background:#eef2f7;color:#5b6472;">{esc(t)}</span>'
                for t in p["tags"] if t)
            parts.append(f'<div style="margin:2px 0 2px;">{chips}</div>')
        if p.get("repo"):
            parts.append(f'<div style="font-size:12.5px;color:#98a2b3;margin:0 0 2px;">'
                         f'{esc(p["repo"])}</div>')
        if p.get("cover"):
            parts.append(f'<img src="{esc(p["cover"])}" alt="{esc(p["name"])}" '
                         f'style="display:block;width:100%;max-height:280px;'
                         f'object-fit:cover;object-position:top;border-radius:10px;'
                         f'margin:12px 0 4px;border:1px solid #e7e9ee;background:#fff;" />')
        if p.get("one_liner"):
            parts.append(f'<div style="{CSS_ONE}">{esc(p["one_liner"])}</div>')
        if p.get("detail"):
            parts.append(f'<div style="font-size:15.5px;line-height:1.9;color:#2b2f36;'
                         f'margin:0 0 8px;">{esc(p["detail"])}</div>')
        if p.get("desc_en"):
            parts.append(f'<div style="font-size:12.5px;line-height:1.7;color:#9aa0aa;'
                         f'margin:0 0 6px;">原文：{esc(p["desc_en"])}</div>')
        if p.get("why"):
            parts.append(f'<div style="{CSS_SEC}">为啥值得看</div>')
            parts.append(li(p["why"]))
        if p.get("how"):
            parts.append(f'<div style="{CSS_SEC}">上手难度</div>')
            parts.append(f'<div style="{CSS_BODY}">{esc(p["how"])}</div>')
        if p.get("try_it"):
            parts.append(f'<div style="{CSS_META}">💡 可以先这么玩：{esc(p["try_it"])}</div>')
        if p.get("demo"):
            parts.append(f'<a href="{esc(p["demo"])}" style="display:block;text-align:center;'
                         f'margin:14px 0 0;padding:11px 12px;background:#fff;color:#111;'
                         f'text-decoration:none;border-radius:10px;border:1.5px solid #111;'
                         f'font-size:15px;font-weight:600;">▶ 看演示</a>')
        if p.get("url"):
            parts.append(f'<a href="{esc(p["url"])}" style="{CSS_BTN}">打开 GitHub 看看 →</a>')
        parts.append('</div>')

    if issue.get("compare"):
        parts.append(f'<div style="margin:26px 0 0;padding:12px 15px;background:#f2f7ff;'
                     f'border:1px solid #d9e6fb;border-radius:12px;font-size:14.5px;'
                     f'line-height:1.75;color:#2b4a72;">'
                     f'<b>同类怎么选</b>：{esc(issue["compare"])}</div>')

    if issue.get("outro"):
        parts.append(f'<div style="font-size:15.5px;line-height:1.85;color:#33363d;'
                     f'margin:26px 0 0;padding:14px 16px;background:#fffbe8;'
                     f'border-radius:12px;border:1px solid #f6e7a8;">{nl(issue["outro"])}</div>')

    if issue.get("bonus"):
        parts.append('<div style="margin:30px 0 0;">')
        parts.append(f'<div style="{CSS_SEC}">顺手扫到的另外几个</div>')
        for b in issue["bonus"]:
            parts.append(f'<div style="font-size:14.5px;line-height:1.8;color:#4a4f57;'
                         f'margin:6px 0 0;padding-left:14px;text-indent:-14px;">'
                         f'<span style="color:#9aa0aa;">·</span> {esc(b)}</div>')
        parts.append('</div>')

    if fav_on:
        parts.append(f'<div style="margin:26px 0 0;padding:13px 15px;background:#fff5f5;'
                     f'border:1px solid #ffd9d9;border-radius:12px;font-size:14px;'
                     f'line-height:1.75;color:#7a3b3b;">')
        parts.append('<div style="font-weight:700;color:#e5484d;font-size:15px;margin:0 0 4px;">'
                     '&#9829; 想留着以后看的，点卡片右上角的爱心</div>')
        if FREPO:
            parts.append('<div style="font-size:13px;color:#a56b6b;">点一下会打开 GitHub 的'
                         '「新建 issue」页面，标题已经填好，按一下 <b>Submit new issue</b> 就存下了。'
                         '攒多了回去一眼能翻到。</div>')
        else:
            parts.append('<div style="font-size:13px;color:#a56b6b;">点一下会跳到「已收藏」小页面，'
                         '返回就继续读。收藏存在云端，跨期累积、换手机也不丢。</div>')
        parts.append(f'<a href="{esc(fav_list_url())}" style="display:inline-block;margin:10px 0 0;'
                     f'padding:8px 16px;border-radius:8px;background:#e5484d;color:#fff;'
                     f'text-decoration:none;font-size:14px;font-weight:600;">看我的收藏清单</a>')
        parts.append('</div>')
    else:
        parts.append(f'<div style="margin:26px 0 0;padding:13px 15px;background:#f7f8fa;'
                     f'border:1px dashed #dfe3ea;border-radius:12px;font-size:13.5px;'
                     f'line-height:1.8;color:#5b6270;">')
        parts.append('<div style="font-weight:700;color:#3b3f47;margin:0 0 6px;">本期清单'
                     '（长按可复制）</div>')
        for i, q in enumerate(picks, 1):
            parts.append(f'<div>{i}. {esc(q.get("repo",""))} — '
                         f'{esc((q.get("one_liner") or "")[:40])}</div>')
        parts.append('</div>')

    parts.append(f'<hr style="{CSS_HR}">')
    parts.append(f'<div style="font-size:12.5px;line-height:1.8;color:#9aa0aa;margin:14px 0 0;">'
                 f'{nl(issue.get("footer",""))}</div>')
    parts.append('</div>')
    return "".join(parts)


def render_md(issue):
    out = [f'# {issue["title"]}', ""]
    if issue.get("hook"):
        out += [issue["hook"], ""]
    if issue.get("intro"):
        out += [f'> {issue["intro"]}', ""]
    for i, p in enumerate(issue["picks"], 1):
        out.append(f'## {i}. {p.get("emoji","")} {p["name"]}')
        if p.get("repo"):
            out.append(f'`{p["repo"]}`' + (f' · {p["meta"]}' if p.get("meta") else ""))
        out += ["", f'**{p.get("one_liner","")}**', ""]
        if p.get("why"):
            out += ["**为啥值得看**", ""] + [f'- {x}' for x in p["why"]] + [""]
        if p.get("how"):
            out += [f'**上手难度**：{p["how"]}', ""]
        if p.get("try_it"):
            out += [f'> 💡 可以先这么玩：{p["try_it"]}', ""]
        if p.get("url"):
            out += [f'[打开 GitHub]({p["url"]})', ""]
    if issue.get("outro"):
        out += ["---", "", issue["outro"], ""]
    if issue.get("bonus"):
        out += ["### 顺手扫到的另外几个", ""] + [f'- {b}' for b in issue["bonus"]] + [""]
    out += [f'_{issue.get("footer","")}_']
    return "\n".join(out)


def render_txt(issue):
    names = " / ".join(p["name"].split("/")[-1] for p in issue["picks"][:3])
    return f'{issue["title"]}\n本期：{names}'


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "issue.json")
    issue = json.load(open(path, encoding="utf-8-sig"))
    os.makedirs(BUILD, exist_ok=True)
    no = issue.get("issue_no", 1)
    h = os.path.join(BUILD, f"issue-{no}.html")
    m = os.path.join(BUILD, f"issue-{no}.md")
    t = os.path.join(BUILD, f"issue-{no}.txt")
    open(h, "w", encoding="utf-8").write(render_html(issue))
    open(m, "w", encoding="utf-8").write(render_md(issue))
    open(t, "w", encoding="utf-8").write(render_txt(issue))
    print("HTML:", h)
    print("MD  :", m)
    print("TXT :", t)
    print("标题预览:", render_txt(issue).replace("\n", " | "))
    print("HTML 体积:", len(open(h, encoding="utf-8").read()), "字符")


if __name__ == "__main__":
    main()
