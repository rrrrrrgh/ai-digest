#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「速报」从英文简介升级成中文图文：

  1. 抓每个项目 README → 提炼一段摘要 + 找出封面图 + 演示视频
  2. 把英文描述/摘要翻成中文（术语做人工修正）
  3. 如果配了大模型 Key（LLM_API_KEY），让它写成带梗的人话文案；
     没配就退化成「翻译 + README 摘要」，不编造。

用法:
    python enrich.py [auto-issue.json]
环境变量（都可选）:
    LLM_API_KEY / LLM_BASE_URL / LLM_MODEL   —— 有就用人话重写，没有就只翻译
    NO_TRANSLATE=1                            —— 完全不翻译（离线调试用）
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

# 机器翻译常翻车的 AI 术语，翻完做一遍替换
GLOSSARY = [
    ('克劳德·代码', 'Claude Code'), ('克劳德 代码', 'Claude Code'), ('克劳德代码', 'Claude Code'),
    ('《基米》', 'Kimi'), ('基米', 'Kimi'), ('法典', 'Codex'), ('光标', 'Cursor'),
    ('杰米尼', 'Gemini'), ('双子座', 'Gemini'),
    ('病毒视频', '爆款视频'), ('病毒式', '病毒式传播的'), ('幕后花絮', '空镜素材'),
    ('B 卷', '空镜素材'), ('B卷', '空镜素材'), ('人工智能代理', 'AI Agent'),
    ('人工智能代理', 'AI Agent'), ('智能体', 'Agent'), ('大型语言模型', '大语言模型'),
    ('每个代理的模型', '每个 Agent 的模型'), ('开源代理工具', '开源 Agent 工具'),
    ('代理的模型', 'Agent 的模型'), ('AI 代理', 'AI Agent'),
    ('本地优先', '本地优先'), ('无头', '无头（headless）'), ('瞬态', '瞬时'),
    ('张量', '张量'), ('管道', '流水线'), ('微调', '微调'),
]
BADGE_HOSTS = ("shields.io", "badgen.net", "badge.fury.io", "travis-ci", "codecov.io",
               "coveralls.io", "cirrus-ci", "github.com/workflows", "snyk.io",
               "star-history", "visitor-badge", "img.shields.io", "gitpod.io/button",
               "open.vscode.dev", "nodei.co", "pepy.tech", "hits.seeyoufarm.com")


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


def fetch_readme(full_name):
    """返回 (README 文本, 分支名)。raw 不通就试 gh-proxy 镜像。"""
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
    txt = re.sub(r"\|[^\n]*\|", " ", txt)          # 表格
    txt = re.sub(r"^[=\-#>*·•\s]+", "", txt, flags=re.M)
    txt = re.sub(r"[ \t]+", " ", txt)
    return txt


def summarize(readme, limit=520):
    """从 README 抽一段能读的正文：跳过徽章行、目录行、安装命令行。"""
    txt = strip_md(readme)
    keep = []
    for raw in txt.splitlines():
        line = raw.strip()
        if len(line) < 24:
            continue
        if line.lower().startswith(("http", "npm ", "npx ", "pip ", "git clone", "curl ",
                                    "docker ", "brew ", "$ ", "cargo ", "uv ")):
            continue
        if line.count("|") >= 2 or line.count("](") >= 2:
            continue
        low = line.lower()
        if "http://" in low or "https://" in low:
            continue
        if any(x in low for x in ("use code", "pay-as-you-go", "pay as you go", "sponsor",
                                  "badge", "npm i", "pnpm", "yarn", "install")):
            continue
        # 语言列表 / 国旗刷屏的行
        if line.count("·") >= 3 or sum(1 for ch in line if ord(ch) > 0x1F000) >= 3:
            continue
        # 中英混排的短标签行（导航类）
        if len(line) < 40 and (line.count(" ") <= 2 or line.count("·") >= 2):
            continue
        keep.append(line)
        if sum(len(x) for x in keep) > limit:
            break
    out = " ".join(keep)
    out = re.sub(r"\s+", " ", out).strip()
    return out[:limit]


def find_image(readme, full_name, branch):
    """README 里第一张非徽章的位图；找不到就返回空。"""
    cands = []
    for m in re.finditer(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)", readme):
        cands.append(m.group(1))
    for m in re.finditer(r"<img[^>]+src=[\"']([^\"']+)", readme):
        cands.append(m.group(1))
    for url in cands:
        low = url.lower()
        if low.endswith(".svg") or any(b in low for b in BADGE_HOSTS):
            continue
        # 只认「像截图」的图：docs/ assets/ screenshots/ images/ demo 或 gif
        looks_shot = any(k in low for k in ("/docs/", "/assets/", "/screenshots/", "/images/",
                                            "/img/", "demo", ".gif", "user-images"))
        if not looks_shot and not low.endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue
        if low.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")) or "user-images" in low or "githubassets" in low:
            if url.startswith("http"):
                fixed = url
            else:
                fixed = f"https://raw.githubusercontent.com/{full_name}/{branch}/{url.lstrip('./')}"
            if "raw.githubusercontent.com" in fixed:
                fixed = PROXY + fixed
            return fixed
    return ""


def find_demo(readme):
    patterns = [
        r"https?://(?:www\.)?youtube\.com/watch\?[^\s)\"']+",
        r"https?://youtu\.be/[^\s)\"']+",
        r"https?://(?:www\.)?bilibili\.com/video/[^\s)\"']+",
        r"https?://[^\s)\"']+\.(?:mp4|webm)",
    ]
    for p in patterns:
        m = re.search(p, readme)
        if m:
            return m.group(0).rstrip(").,")
    return ""


# ---------------------------------------------------------------- 翻译


def has_cjk(s):
    if not s:
        return False
    n = sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff")
    return n / max(1, len(s)) > 0.15


def _fix_terms(s):
    for a, b in GLOSSARY:
        s = s.replace(a, b)
    return s


def translate(text, timeout=20):
    """英文 → 中文：先试 Google 免费接口，失败退 MyMemory，再失败就原样返回。"""
    text = (text or "").strip()
    if not text or has_cjk(text) or os.environ.get("NO_TRANSLATE"):
        return text
    # Google
    try:
        q = urllib.parse.quote(text[:1800])
        url = ("https://translate.googleapis.com/translate_a/single"
               f"?client=gtx&sl=en&tl=zh-CN&dt=t&q={q}")
        data = json.loads(http_get(url, timeout=timeout))
        out = "".join(seg[0] for seg in data[0] if seg and seg[0]).strip()
        if out:
            return _fix_terms(out)
    except Exception:
        pass
    # MyMemory（有长度限制，只翻前 800 字符）
    try:
        q = urllib.parse.quote(text[:800])
        url = f"https://api.mymemory.translated.net/get?q={q}&langpair=en|zh-CN"
        data = json.loads(http_get(url, timeout=timeout))
        out = (data.get("responseData") or {}).get("translatedText") or ""
        if out and "MYMEMORY WARNING" not in out.upper():
            return _fix_terms(out)
    except Exception:
        pass
    return text


# ---------------------------------------------------------------- 可选：大模型润色


def llm_polish(repo, readme_brief):
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        return None
    base = (os.environ.get("LLM_BASE_URL") or "https://api.deepseek.com").rstrip("/")
    model = os.environ.get("LLM_MODEL") or "deepseek-flash"
    prompt = (
        "你在给一个爱刷短视频的普通用户写 GitHub 项目推荐，像给朋友发微信介绍新玩具。\n"
        "要求：说人话；不用『旨在/致力于/赋能/一站式/生态』这类词；不编造材料里没有的功能；\n"
        "每条短句；允许带一点比喻和吐槽，但别油。\n\n"
        f"项目：{repo['full_name']}\n"
        f"官方描述：{repo.get('desc') or '(无)'}\n"
        f"语言：{repo.get('language')}｜星数：{repo.get('stars')}｜涨星：约 {repo.get('stars_per_day')}/天\n"
        f"README 摘录：{readme_brief[:1200]}\n\n"
        "只输出 JSON，格式："
        '{"one_liner":"一句话说清这是什么东西，40 字内，可带生活化比喻",'
        '"why":["为啥值得看，三条，每条 40 字内"],'
        '"try_it":"一个具体的土办法玩法，50 字内"}'
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.85,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"},
    }
    if "deepseek.com" in base:
        # 这个场景不需要思考链，关掉省钱又省时间
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
                # 有些兼容接口不认 response_format / thinking，去掉再试一次
                slim = {k: v for k, v in payload.items()
                        if k not in ("response_format", "thinking")}
                res = _post(slim)
            else:
                print(f"    ! 大模型报错 {e.code}：{body}")
                return None
        txt = res["choices"][0]["message"].get("content") or ""
        print(f"    · 模型用掉 {res.get('usage', {}).get('total_tokens', '?')} tokens")
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            print(f"    ! 模型没返回 JSON：{txt[:120]}")
            return None
        data = json.loads(m.group(0))
        if not data.get("one_liner"):
            return None
        return {
            "one_liner": str(data.get("one_liner"))[:160],
            "why": [str(x)[:80] for x in (data.get("why") or [])][:3],
            "try_it": str(data.get("try_it") or "")[:100],
        }
    except Exception as e:
        print(f"    ! 大模型润色失败（{type(e).__name__}: {str(e)[:80]}），退回翻译模式")
        return None


# ---------------------------------------------------------------- 主流程


def enrich_issue(path):
    issue = json.load(open(path, encoding="utf-8-sig"))
    use_llm = bool(os.environ.get("LLM_API_KEY", "").strip())
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
        if not cover:
            owner, name = full.split("/", 1)
            cover = f"https://opengraph.githubassets.com/1/{owner}/{name}"

        fallback = {
            "one_liner": translate(p.get("one_liner") or ""),
            "why": [],
            "try_it": "",
        }
        if brief:
            zh = translate(brief)
            # 中文摘要按句号切，取前两三句当"这是什么"
            sentences = [s.strip() for s in re.split(r"(?<=[。！？.!?])\s*", zh) if len(s.strip()) > 8]
            if sentences:
                fallback["why"] = sentences[:3]

        repo_ctx = {
            "full_name": full,
            "desc": p.get("desc_raw") or p.get("desc_en") or "",
            "stars": p.get("stars"),
            "stars_per_day": p.get("stars_per_day"),
            "language": p.get("language"),
        }
        got = llm_polish(repo_ctx, brief) if use_llm else None
        text = got or fallback

        p["desc_en"] = (p.get("desc_raw") or p.get("desc_en") or "").strip()
        p["one_liner"] = text.get("one_liner") or p.get("one_liner") or ""
        def _dedupe(items, head):
            out = []
            for it in items:
                if not it:
                    continue
                # 和一句话高度重合的就不要了
                a, b = set(it), set(head or '')
                if head and len(a & b) / max(1, len(a)) > 0.75:
                    continue
                out.append(it)
            return out

        if text.get("why"):
            p["why"] = _dedupe(text["why"], text.get("one_liner")) or p.get("why") or []
        elif fallback["why"]:
            p["why"] = _dedupe(fallback["why"], text.get("one_liner")) or p.get("why") or []
        if text.get("try_it"):
            p["try_it"] = text["try_it"]
        elif brief and not p.get("try_it"):
            p["try_it"] = ""
        if cover:
            p["cover"] = cover
        if demo:
            p["demo"] = demo
        p["how"] = p.get("how") or "看 README 照着装"
    json.dump(issue, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"   ✅ 已更新 {path}")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "auto-issue.json")
    if not os.path.exists(path):
        raise SystemExit(f"没有 {path}，先跑 build_auto_issue.py")
    enrich_issue(path)


if __name__ == "__main__":
    main()
