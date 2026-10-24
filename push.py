#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把一期内容推到手机上（微信）。

支持的通道（在 channels.json 里填任意一个即可）：
  mail         —— 自己的邮箱 SMTP（QQ/163/Outlook…）→ 手机上的邮件提醒（不需要实名，推荐）
  pushplus     —— 微信 pushplus 公众号（现在要求账号实名认证才能发）
  serverchan   —— Server酱³  SendKey
  webhook      —— 企业微信/飞书/钉钉群机器人 的 webhook 地址

邮件通道要填（QQ 邮箱举例）：
  "channel": "mail",
  "mail_host": "smtp.qq.com", "mail_port": 587,
  "mail_user": "你的QQ邮箱@qq.com",
  "mail_pass": "SMTP授权码（不是QQ密码）",
  "mail_to":   "收件邮箱，留空就发给自己"

用法:
    python push.py --test                  # 发一条测试消息，验证通道通不通
    python push.py                         # 发 build/issue-1.html 对应那期
    python push.py --issue issue.json
    python push.py --dry                   # 只打印，不真的发
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))


def now_cst():
    """统一用北京时间记账：GitHub 的服务器是 UTC，混着用会差 8 小时。"""
    return datetime.now(CST)
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CH_FILE = os.path.join(HERE, "channels.json")
BUILD = os.path.join(HERE, "build")


def load_channels():
    cfg = {}
    if os.path.exists(CH_FILE):
        cfg = json.load(open(CH_FILE, encoding="utf-8-sig"))
    for k, env in (("pushplus_token", "PUSHPLUS_TOKEN"),
                   ("serverchan_key", "SERVERCHAN_KEY"),
                   ("webhook", "PUSH_WEBHOOK"),
                   ("mail_host", "MAIL_HOST"),
                   ("mail_port", "MAIL_PORT"),
                   ("mail_user", "MAIL_USER"),
                   ("mail_pass", "MAIL_PASS"),
                   ("mail_to", "MAIL_TO")):
        if os.environ.get(env):
            cfg[k] = os.environ[env]
    return cfg


def send_mail(cfg, subject, html, plain=None):
    """用自己的邮箱 SMTP 发一封（图文）邮件。手机上的邮件 App / 微信里的邮箱提醒都能看。"""
    import smtplib
    import ssl
    from email.message import EmailMessage
    from email.utils import formataddr

    user = (cfg.get("mail_user") or "").strip()
    pwd = (cfg.get("mail_pass") or "").strip()
    if not (user and pwd):
        raise SystemExit("缺 mail_user / mail_pass（邮箱账号 + SMTP 授权码）")
    host = (cfg.get("mail_host") or "").strip() or (
        "smtp.qq.com" if user.endswith("qq.com") else
        "smtp.163.com" if user.endswith("163.com") else
        "smtp.office365.com")
    port = int(str(cfg.get("mail_port") or 587))
    to = (cfg.get("mail_to") or user).strip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr(("AI 项目雷达", user))
    msg["To"] = to
    msg.set_content(plain or "这封邮件是图文版，请用支持 HTML 的邮箱/客户端打开。")
    msg.add_alternative(html, subtype="html")

    ctx = ssl.create_default_context()
    if port == 465:
        srv = smtplib.SMTP_SSL(host, port, timeout=40, context=ctx)
    else:
        srv = smtplib.SMTP(host, port, timeout=40)
        srv.ehlo()
        srv.starttls(context=ctx)
        srv.ehlo()
    srv.login(user, pwd)
    srv.send_message(msg)
    try:
        srv.quit()
    except Exception:
        pass
    return {"ok": True, "to": to, "host": host, "port": port}


def http_post_json(url, payload, timeout=20):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "User-Agent": "ai-digest/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def http_post_raw(url, data, headers, timeout=20):
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def send_pushplus(cfg, title, content, template="html"):
    token = cfg.get("pushplus_token", "").strip()
    if not token:
        raise SystemExit("缺 pushplus_token：先在 channels.json 里填上")
    payload = {"token": token, "title": title, "content": content,
               "template": template, "channel": cfg.get("pushplus_channel", "wechat")}
    if cfg.get("pushplus_topic"):
        payload["topic"] = cfg["pushplus_topic"]
    if cfg.get("pushplus_option"):
        payload["option"] = cfg["pushplus_option"]
    res = http_post_json("https://www.pushplus.plus/send", payload)
    if res.get("code") != 200:
        raise SystemExit(f"pushplus 返回失败: {res}")
    return res


def no_channel_msg():
    return ("还没配通道：在 ai-digest/channels.json 里填邮件通道（推荐，不需要实名）：\n"
            '  {"channel":"mail","mail_host":"smtp.qq.com","mail_port":587,\n'
            '   "mail_user":"你的邮箱@qq.com","mail_pass":"SMTP授权码","mail_to":"收件邮箱"}\n'
            "  取授权码：QQ邮箱 → 设置 → 账号 → 开启 POP3/IMAP/SMTP 服务 → 生成授权码")


def send_serverchan(cfg, title, content):
    key = cfg.get("serverchan_key", "").strip()
    if not key:
        raise SystemExit("缺 serverchan_key")
    body = urllib.parse.urlencode({"title": title, "desp": content}).encode("utf-8")
    txt = http_post_raw(f"https://sctapi.ftqq.com/{key}.send", body,
                        {"Content-Type": "application/x-www-form-urlencoded"})
    res = json.loads(txt)
    if res.get("code") not in (0, None):
        raise SystemExit(f"serverchan 返回失败: {res}")
    return res


def send_webhook(cfg, title, content, plain):
    url = cfg.get("webhook", "").strip()
    if not url:
        raise SystemExit("缺 webhook 地址")
    if "qyapi.weixin.qq.com" in url:          # 企业微信
        payload = {"msgtype": "markdown", "markdown": {"content": f"**{title}**\n\n{plain}"}}
    elif "open.feishu.cn" in url:             # 飞书
        payload = {"msg_type": "text", "content": {"text": f"{title}\n\n{plain}"}}
    elif "oapi.dingtalk.com" in url:          # 钉钉
        payload = {"msgtype": "markdown",
                   "markdown": {"title": title, "text": f"### {title}\n\n{plain}"}}
    else:
        payload = {"title": title, "content": plain}
    return http_post_json(url, payload)


def main():
    args = sys.argv[1:]
    dry = "--dry" in args
    test = "--test" in args
    issue_path = os.path.join(HERE, "issue.json")
    for i, a in enumerate(args):
        if a == "--issue" and i + 1 < len(args):
            issue_path = args[i + 1]

    cfg = load_channels()
    channel = cfg.get("channel", "")
    if not channel:
        channel = ("mail" if cfg.get("mail_pass") else
                   "pushplus" if cfg.get("pushplus_token") else
                   "serverchan" if cfg.get("serverchan_key") else
                   "webhook" if cfg.get("webhook") else "")

    if test:
        title = "AI 项目雷达 · 通道测试"
        content = ("<div style=\"font-family:-apple-system,'PingFang SC',sans-serif;"
                   "font-size:16px;line-height:1.8;padding:8px 2px;\">"
                   "✅ 通道打通了。<br>以后每 3 天，我会把「GitHub 上最近在涨星的 AI 项目」"
                   "整理成能上下班路上刷完的一篇，直接发到这里。</div>")
        plain = "通道测试：打通了。以后每 3 天给你发一期 GitHub AI 项目精选。"
        print(f"[通道] {channel or '(未配置)'}  [dry={dry}]")
        if dry:
            print(content)
            return
        if channel == "mail":
            print(send_mail(cfg, title, content, plain))
        elif channel == "pushplus":
            print(send_pushplus(cfg, title, content))
        elif channel == "serverchan":
            print(send_serverchan(cfg, title, plain))
        elif channel == "webhook":
            print(send_webhook(cfg, title, content, plain))
        else:
            print(no_channel_msg())
            sys.exit(2)
        return

    issue = json.load(open(issue_path, encoding="utf-8-sig"))
    no = issue.get("issue_no", 1)
    html_path = os.path.join(BUILD, f"issue-{no}.html")
    md_path = os.path.join(BUILD, f"issue-{no}.md")
    if not os.path.exists(html_path):
        raise SystemExit(f"还没渲染：{html_path}（先跑 render_issue.py）")
    content_html = open(html_path, encoding="utf-8").read()
    content_md = open(md_path, encoding="utf-8").read() if os.path.exists(md_path) else ""
    title = issue.get("push_title") or issue["title"]
    plain = f'{title}\n' + "\n".join(
        f'· {p["name"]}：{p.get("one_liner","")}' for p in issue["picks"])

    print(f"[通道] {channel or '(未配置)'}  [dry={dry}]  字数={len(content_html)}")
    if dry:
        print("标题:", title)
        print(plain)
        return
    short_code = ""
    if channel == "mail":
        print("mail:", send_mail(cfg, title, content_html, plain))
    elif channel == "pushplus":
        r = send_pushplus(cfg, title, content_html)
        short_code = (r or {}).get("data") or ""
        print("pushplus:", r, "| 流水号:", short_code)
    elif channel == "serverchan":
        print("serverchan:", send_serverchan(cfg, title, content_md))
    elif channel == "webhook":
        print("webhook:", send_webhook(cfg, title, content_html, plain))
    else:
        print(no_channel_msg())
        sys.exit(2)

    # 本地记账，给「每 3 天一次」的判断用
    state_file = os.path.join(HERE, "state.json")
    st = json.load(open(state_file, encoding="utf-8-sig")) if os.path.exists(state_file) else {}
    st["last_sent"] = now_cst().strftime("%Y-%m-%d %H:%M")
    st["last_issue"] = no
    sent = list(st.get("sent_repos") or [])
    for p in issue.get("picks", []):
        if p.get("repo") and p["repo"] not in sent:
            sent.append(p["repo"])
    st["sent_repos"] = sent[-400:]
    if short_code:
        st["last_shortcode"] = short_code
    st["last_title"] = title
    json.dump(st, open(state_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"已记账：第 {no} 期 · {st['last_sent']} · 已推过 {len(st['sent_repos'])} 个项目")


if __name__ == "__main__":
    import urllib.parse  # noqa: F401  (serverchan 用)
    main()
