#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判断「现在该不该发一期」，只输出 yes / no。云端的定时任务靠它防止重复发送。

用法:
    python due.py            # 距上次满 2.5 天就 yes
    python due.py --force    # 直接 yes
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
MIN_DAYS = 2.5


def main():
    if "--force" in sys.argv:
        print("yes")
        return
    if not os.path.exists(STATE):
        print("yes")
        return
    try:
        st = json.load(open(STATE, encoding="utf-8-sig"))
    except Exception:
        print("yes")
        return
    last = (st.get("last_sent") or "").strip()
    if not last:
        print("yes")
        return
    try:
        t = datetime.strptime(last, "%Y-%m-%d %H:%M")
    except Exception:
        print("yes")
        return
    days = (datetime.now(CST) - t.replace(tzinfo=CST)).total_seconds() / 86400.0
    print("yes" if days >= MIN_DAYS else f"no ({days:.1f} 天前刚发过)")


if __name__ == "__main__":
    main()
