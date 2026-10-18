#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条命令跑完：该不该发 → 抓 → 组一期 → 渲染 → 发邮件。

和你之前那个「抖音热榜发邮件」的项目是一个形状：一个入口脚本 + 一个 workflow + 几个 Secret。
只是内容从「一行热榜标题」变成「整篇图文」。

用法:
    python cloud_digest.py            # 到点了才发（云端定时用这个）
    python cloud_digest.py --force    # 无视周期，立刻发
    python cloud_digest.py --dry      # 只生成不发送（本地看效果）
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run(script, args=None, allow_codes=(0,)):
    cmd = [PY, "-X", "utf8", os.path.join(HERE, script)] + list(args or [])
    p = subprocess.run(cmd, cwd=HERE)
    if p.returncode not in allow_codes:
        raise SystemExit(f"{script} 失败，退出码 {p.returncode}")
    return p.returncode


def main():
    args = sys.argv[1:]
    force = "--force" in args
    dry = "--dry" in args
    n = "4"
    for i, a in enumerate(args):
        if a == "--n" and i + 1 < len(args):
            n = args[i + 1]

    # 0. 到点了吗
    if not force:
        out = subprocess.run([PY, "-X", "utf8", os.path.join(HERE, "due.py")],
                             cwd=HERE, capture_output=True, text=True).stdout.strip()
        if not out.startswith("yes"):
            log(f"还没到时间（{out}），本次跳过")
            return 0
        log("到点了，开始干活")

    # 1. 抓
    log("抓 GitHub 上新鲜的 AI 项目…")
    rc = run("fetch_repos.py", ["--days", "120"], allow_codes=(0, 3))
    if rc == 3:
        log("GitHub 不通，本次跳过（不发垃圾）")
        return 0

    # 2. 组一期
    log("挑项目、组一期…")
    run("build_auto_issue.py", ["--n", n])

    # 3. 补中文 + 找配图/演示
    log("翻成中文、找封面图…")
    run("enrich.py", ["auto-issue.json"])

    # 4. 渲染
    log("渲染手机版页面…")
    run("render_issue.py", ["auto-issue.json"])

    # 5. 发
    push_args = ["--issue", "auto-issue.json"] + (["--dry"] if dry else [])
    log("发邮件…" if not dry else "（dry：只生成，不发送）")
    rc = run("push.py", push_args, allow_codes=(0, 2))
    if rc == 2:
        log("还没配置发信通道：channels.json 或环境变量里缺 MAIL_USER / MAIL_PASS")
        return 2
    log("这一期发出去了 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
