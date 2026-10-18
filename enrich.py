#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「速报」从英文简介升级成中文图文（第二版）。

做四件事：
  1. 抓 README → 提炼「这玩意儿到底干嘛的」详细描述 + 找封面图 + 演示视频
  2. 翻译：Google（分块）→ MyMemory（分块 + 校验）→ 宁可留空也不放垃圾
  3. 配了 LLM_API_KEY 就让大模型写人话（一句话 / 详细说明 / 三条看点 / 土办法玩法）
  4. 封面图先验活，加载不出来就换 GitHub 自动卡片图

用法:
    python enrich.py [auto-issue.json]
环境变量:
    LLM_API_KEY / LLM_BASE_URL / LLM_MODEL   —— 有就用人话重写
    NO_TRANSLATE=1                            —— 不翻译（调试用）
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (compatible; ai-digest/1.0)"}
PROXY = "https://gh-proxy.com/"

GLOSSARY = [
    ("DeepSeek 线束 桌面版", "DeepSeek Harness 桌面版"),
    ("DeepSeek线束 桌面版", "DeepSeek Harness 桌面版"),
    ("DeepSeek线束桌面", "DeepSeek Harness 桌面"),
    ("线束", "Harness"),
    ("克劳德·代码", "Claude Code"), ("克劳德 代码", "Claude Code"), ("克劳德代码", "Claude Code"),
    ("《基米》", "Kimi"), ("基米", "Kimi"), ("法典", "Codex"), ("光标", "Cursor"),
    ("杰米尼", "Gemini"), ("双子座", "Gemini"),
    ("病毒视频", "爆款视频"), ("病毒式", "病毒式传播的"), ("幕后花絮", "空镜素材"),
    ("B 卷", "空镜素材"), ("B卷", "空镜素材"), ("人工智能代理", "AI Agent"),
    ("人工智能同事", "AI 同事"), ("智能体", "Agent"), ("大型语言模型", "大语言模型"),
    ("无头", "无头（headless）"), ("管道", "流水线"),
    ("每个代理的模型", "每个 Agent 的模型"), ("开源代理工具", "开源 Agent 工具"),
    ("代理的模型", "Agent 的模型"), ("AI 代理", "AI Agent"),
]
BADGE_HOSTS = ("shields.io", "badgen.net", "badge.fury.io", "travis-ci", "codecov.io",
               "coveralls.io", "cirrus-ci", "github.com/workflows", "snyk.io",
               "star-history", "visitor-badge", "gitpod.io/button", "open.vscode.dev",
               "nodei.co", "pepy.tech", "hits.seeyoufarm.com")
BAD_TRANSLATIONS = ("QUERY LENGTH LIMIT", "MYMEMORY WARNING", "INVALID LANGUAGE PAIR",
                    "PLEASE SELECT TWO DISTINCT LANGUAGES", "PLEASE USE A VALID",
                    "NO QUERY SPECIFIED")


# ---------------------------------------------------------------- 网络


def http_get(url, timeout=20, retries=1):
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(1 + i)
    raise last


def image_ok(url, timeout=12):
    """真去拿前几个字节，确认是张图（避免手机上显示裂图）。"""
    try:
        req = urllib.request.Request(url, headers={**UA, "Range": "bytes=0-4095"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            head = r.read(16)
        if "image" not in ctype and not (
                head.startswith(b"\x89PNG") or head.startswith(b"\xff\xd8")
                or head.startswith(b"GIF8") or head[:4] == b"RIFF"):
            return False
        return True
    except Exception:
        return False


def fetch_readme(full_name):
    for base in (f"https://raw.githubusercontent.com/{full_name}",
                 PROXY + f"https://raw.githubusercontent.com/{full_name}"):
        for br in ("main", "master"):
            for fn in ("README.md", "readme.md", "README.MD", "Readme.md"):
                try:
                    txt = http_get(f"{base}/{br}/{fn}", timeout=15)
                    if txt.strip():
                        return txt, br
                except Exception:
                    continue
    return "", "main"


# ---------------------------------------------------------------- 提炼


def strip_md(txt):
    txt = re.sub(r"```.*?```", " ", txt, flags=re.S)
    txt = re.sub(r"<!--.*?-->", " ", txt, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", txt)
    txt = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", txt)
    txt = re.sub(r"\*\*(.+?)\*\*", r"\1", txt)
    txt = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", txt)
    txt = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", r"\1", txt)
    txt = txt.replace("`", "")
    txt = re.sub(r"\|[^\n]*\|", " ", txt)
    txt = re.sub(r"^[=\-#>*·•\s]+", "", txt, flags=re.M)
    txt = re.sub(r"[ \t]+", " ", txt)
    return txt


def summarize(readme, limit=900):
    txt = strip_md(readme)
    keep = []
    for raw in txt.splitlines():
        line = raw.strip()
        if len(line) < 24:
            continue
        low = line.lower()
        if low.startswith(("http", "npm ", "npx ", "pip ", "git clone", "curl ", "docker ",
                           "brew ", "$ ", "cargo ", "uv ", "yarn ", "pnpm ")):
            continue
        if line.count("|") >= 2 or line.count("](") >= 2:
            continue
        if "http://" in low or "https://" in low:
            continue
        if any(x in low for x in ("use code", "pay-as-you-go", "pay as you go", "sponsor",
                                  "badge", "npm i", "pnpm", "yarn add", "installation")):
            continue
        if line.count("·") >= 3 or sum(1 for ch in line if ord(ch) > 0x1F000) >= 3:
            continue
        if len(line) < 40 and (line.count(" ") <= 2 or line.count("·") >= 2):
            continue
        keep.append(line)
        if sum(len(x) for x in keep) > limit:
            break
    out = re.sub(r"\s+", " ", " ".join(keep)).strip()
    return out[:limit]


def find_image(readme, full_name, branch):
    cands = [m.group(1) for m in re.finditer(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)", readme)]
    cands += [m.group(1) for m in re.finditer(r"<img[^>]+src=[\"']([^\"']+)", readme)]
    for url in cands:
        low = url.lower()
        if low.endswith(".svg") or any(b in low for b in BADGE_HOSTS):
            continue
        if any(k in low for k in ("icon", "logo", "/favicon")):
            continue
        if not (low.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
                or "user-images" in low or "githubassets" in low):
            continue
        fixed = url if url.startswith("http") else \
            f"https://raw.githubusercontent.com/{full_name}/{branch}/{url.lstrip('./')}"
        if "raw.githubusercontent.com" in fixed:
            fixed = PROXY + fixed
        return fixed
    return ""


def find_demo(readme):
    for p in (r"https?://(?:www\.)?youtube\.com/watch\?[^\s)\"']+",
              r"https?://youtu\.be/[^\s)\"']+",
              r"https?://(?:www\.)?bilibili\.com/video/[^\s)\"']+",
              r"https?://[^\s)\"']+\.(?:mp4|webm)"):
        m = re.search(p, readme)
        if m:
            return m.group(0).rstrip(").,")
    return ""


# ---------------------------------------------------------------- 翻译


def has_cjk(s):
    if not s:
        return False
    return sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff") / max(1, len(s)) > 0.15


def _chunks(text, size):
    text = text.strip()
    out, i = [], 0
    while i < len(text):
        cut = text.rfind("。", i, i + size)
        if cut < 0:
            cut = text.rfind(". ", i, i + size)
        if cut < 0:
            cut = i + size
        out.append(text[i:cut + 1] if cut < len(text) else text[i:])
        i = cut + 1 if cut < len(text) else len(text)
        if i <= 0:
            break
    return [c for c in out if c.strip()]


def _g(text):
    url = ("https://translate.googleapis.com/translate_a/single"
           f"?client=gtx&sl=en&tl=zh-CN&dt=t&q={urllib.parse.quote(text)}")
    data = json.loads(http_get(url, timeout=20))
    return "".join(seg[0] for seg in data[0] if seg and seg[0]).strip()


def _mm(text):
    url = ("https://api.mymemory.translated.net/get?q="
           f"{urllib.parse.quote(text)}&langpair=en|zh-CN")
    data = json.loads(http_get(url, timeout=20))
    out = ((data.get("responseData") or {}).get("translatedText") or "").strip()
    if str(data.get("responseStatus")) not in ("200", "None"):
        return ""
    up = out.upper()
    if not out or any(b in up for b in BAD_TRANSLATIONS) or not has_cjk(out):
        return ""
    return out


def translate(text):
    text = (text or "").strip()
    if not text or has_cjk(text) or os.environ.get("NO_TRANSLATE"):
        return text
    for engine, size in ((_g, 1200), (_mm, 420)):
        try:
            pieces = []
            for ch in _chunks(text[:2400], size):
                r = engine(ch)
                if not r:
                    raise ValueError("empty")
                pieces.append(r)
                time.sleep(0.2)
            out = "".join(pieces).strip()
            if out and has_cjk(out):
                for a, b in GLOSSARY:
                    out = out.replace(a, b)
                return out
        except Exception:
            continue
    return ""          # 翻不了就留空，绝不放错误信息进正文


# ---------------------------------------------------------------- 可选：大模型


def llm_polish(repo, readme_brief):
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        return None
    base = (os.environ.get("LLM_BASE_URL") or "https://api.deepseek.com").rstrip("/")
    model = os.environ.get("LLM_MODEL") or "deepseek-flash"
    prompt = (
        "你在给一个爱刷短视频、不懂技术的普通用户写 GitHub 项目推荐，语气像给朋友发微信介绍新玩具。\n"
        "硬要求：全中文（专有名词保留英文）；不用『旨在/致力于/赋能/一站式/生态』；"
        "不编造材料里没有的功能；每条短句；可以有比喻，别油。\n\n"
        f"项目：{repo['full_name']}\n"
        f"官方描述：{repo.get('desc') or '(无)'}\n"
        f"语言：{repo.get('language')}｜星数：{repo.get('stars')}｜涨星：约 {repo.get('stars_per_day')}/天\n"
        f"README 摘录：{readme_brief[:1600]}\n\n"
        "输出 JSON，四个字段：\n"
        '{"one_liner":"一句话说清这是什么，40 字内，可带比喻",'
        '"detail":"它到底在干嘛：3 句话、80~140 字，讲清「解决什么问题 + 怎么用 + 和同类比特别在哪」，'
        '读完要让完全没听过这个领域的人也能明白",'
        '"why":["三条值得看的理由，每条 35 字内，要具体，不要空话"],'
        '"try_it":"一个可以立刻上手的土办法，50 字内"}'
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.85,
        "max_tokens": 1400,
        "response_format": {"type": "json_object"},
    }
    if "deepseek.com" in base:
        payload["thinking"] = {"type": "disabled"}

    def _post(body):
        req = urllib.request.Request(
            base + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    try:
        try:
            res = _post(payload)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code in (400, 422):
                slim = {k: v for k, v in payload.items()
                        if k not in ("response_format", "thinking")}
                res = _post(slim)
            else:
                print(f"    ! 大模型报错 {e.code}：{body}")
                return None
        txt = res["choices"][0]["message"].get("content") or ""
        print(f"    · 模型 token 用量 {res.get('usage', {}).get('total_tokens', '?')}")
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            print(f"    ! 模型没返回 JSON：{txt[:120]}")
            return None
        data = json.loads(m.group(0))
        if not data.get("one_liner"):
            return None
        return {
            "one_liner": str(data.get("one_liner"))[:160],
            "detail": str(data.get("detail") or "")[:400],
            "why": [str(x)[:90] for x in (data.get("why") or [])][:3],
            "try_it": str(data.get("try_it") or "")[:120],
        }
    except Exception as e:
        print(f"    ! 大模型失败（{type(e).__name__}: {str(e)[:80]}），退回翻译模式")
        return None


# ---------------------------------------------------------------- 主流程


def enrich_issue(path):
    issue = json.load(open(path, encoding="utf-8-sig"))
    use_llm = bool(os.environ.get("LLM_API_KEY", "").strip())
    mode = "llm" if use_llm else "mt"
    print(f"   模式：{'大模型润色' if use_llm else '翻译 + README 摘要'}")
    for p in issue.get("picks", []):
        full = p.get("repo") or ""
        if not full:
            continue
        print(f"   · {full}")
        readme, branch = fetch_readme(full)
        brief = summarize(readme) if readme else ""
        cover = find_image(readme, full, branch) if readme else ""
        demo = find_demo(readme) if readme else ""

        owner, name = (full.split("/", 1) + ["", ""])[:2]
        og = f"https://opengraph.githubassets.com/1/{owner}/{name}"
        if not cover or not image_ok(cover):
            cover = og
        p["cover"] = cover
        if demo:
            p["demo"] = demo

        zh_brief = translate(brief) if brief else ""
        sentences = [s.strip() for s in re.split(r"(?<=[。！？.!?])\s*", zh_brief)
                     if len(s.strip()) > 8]

        fallback = {
            "one_liner": translate(p.get("desc_raw") or "") or p.get("one_liner") or "",
            "detail": "",
            "why": [],
            "try_it": "",
        }
        if sentences:
            fallback["detail"] = "".join(sentences[:3])[:300]
            fallback["why"] = sentences[1:4] if len(sentences) > 3 else sentences[:3]

        repo_ctx = {
            "full_name": full,
            "desc": p.get("desc_raw") or p.get("desc_en") or "",
            "stars": p.get("stars"),
            "stars_per_day": p.get("stars_per_day"),
            "language": p.get("language"),
        }
        got = llm_polish(repo_ctx, brief or p.get("desc_raw") or "") if use_llm else None
        if use_llm and not got:
            mode = "mt"
        text = got or fallback

        p["desc_en"] = (p.get("desc_raw") or p.get("desc_en") or "").strip()
        if text.get("one_liner"):
            p["one_liner"] = text["one_liner"]
        detail = (text.get("detail") or fallback["detail"] or "").strip()
        ok = has_cjk(detail) and len(detail) >= 50 and ("。" in detail or "，" in detail)
        p["detail"] = detail if ok else ""

        def keep_cn(items):
            return [x for x in items if x and has_cjk(x)]

        cand = keep_cn(got.get("why") or []) if got else []
        cand = [w for w in cand if len(w) >= 12 and w[:16] not in p["detail"]]
        if cand:
            p["why"] = cand
        elif not p.get("why"):
            p["why"] = []
        if text.get("try_it") and has_cjk(text["try_it"]):
            p["try_it"] = text["try_it"]
        p["how"] = p.get("how") or "看 README 照着装"

    issue["copy_mode"] = mode
    json.dump(issue, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"   ✅ 已更新 {path}（文案来源：{'AI 润色' if mode == 'llm' else '机器翻译'}）")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "auto-issue.json")
    if not os.path.exists(path):
        raise SystemExit(f"没有 {path}，先跑 build_auto_issue.py")
    enrich_issue(path)


if __name__ == "__main__":
    main()
