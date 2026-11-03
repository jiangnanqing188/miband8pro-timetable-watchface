#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把课表直接写进手机日历（走 adb，不需要在手机上点任何东西）
==========================================================
    python3 tools/push_calendar.py --dry-run    # 只看会写什么
    python3 tools/push_calendar.py              # 真写
    python3 tools/push_calendar.py --clear      # 先删掉上次写的

为什么这么做：手环只认「手机通知」，所以课前提醒靠日历弹通知 →
Gadgetbridge 把通知镜像到手环 → 手环振动。日历导入 .ics 各家 App 差异大，
直接写日历数据库最稳。
"""
import argparse
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config", "timetable.json")
TAG = "[课表]"          # 事件标题前缀，方便一键清理
TZ = 8 * 3600           # 北京时间
TZNAME = "Asia/Shanghai"
CAL_ID = 1              # Local calendar


def adb(*args, check=False):
    p = subprocess.run(["adb"] + list(args), capture_output=True, text=True,
                       errors="replace", timeout=60)
    if check and p.returncode != 0:
        print(p.stderr.strip())
        sys.exit(1)
    return (p.stdout or "") + (p.stderr or "")


def parse_weeks(s):
    out = set()
    for part in str(s).replace("，", ",").split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out |= set(range(int(a), int(b) + 1))
        elif part.isdigit():
            out.add(int(part))
    return sorted(out)


def runs(nums):
    """连续周次分段： [7,11,13] → [(7,7),(11,11),(13,13)]"""
    if not nums:
        return []
    out, a, p = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == p + 1:
            p = n
            continue
        out.append((a, p))
        a = p = n
    out.append((a, p))
    return out


def epoch_ms(d):
    """本地墙上时间 → epoch 毫秒（设备是 +8）"""
    return int((d.replace(tzinfo=dt.timezone.utc).timestamp() - TZ) * 1000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--clear", action="store_true", help="先删掉之前写入的课表事件")
    ap.add_argument("--lead", type=int, default=20, help="提前多少分钟提醒")
    args = ap.parse_args()

    cfg = json.load(open(CFG, encoding="utf-8"))
    periods = {p["no"]: p for p in cfg["periods"]}
    start = dt.date.fromisoformat(cfg["meta"]["semester_start"])
    start -= dt.timedelta(days=start.weekday())
    print(f"学期第 1 周周一：{start}")

    if adb("devices").find("\tdevice") < 0:
        sys.exit("没检测到手机（adb devices 里没有 device）")

    if args.clear:
        ids = re.findall(r"_id=(\d+)",
                         adb("shell", "content", "query",
                             "--uri", "content://com.android.calendar/events",
                             "--projection", "_id:title"))
        n = 0
        for m in re.finditer(r"_id=(\d+), title=([^\r\n]*)", adb(
                "shell", "content", "query", "--uri",
                "content://com.android.calendar/events",
                "--projection", "_id:title")):
            if m.group(2).startswith(TAG):
                adb("shell", "content", "delete", "--uri",
                    f"content://com.android.calendar/events/{m.group(1)}")
                n += 1
        print(f"已删除 {n} 条旧课表事件")

    made = 0
    for c in cfg["courses"]:
        ps = sorted(c["periods"])
        t0 = periods[ps[0]]["start"]
        t1 = periods[ps[-1]]["end"]
        sh, sm = map(int, t0.split(":"))
        eh, em = map(int, t1.split(":"))
        title = f"{TAG} {c['name']}" + (f"（{c['room']}）" if c.get("room") else "")
        for (w_from, w_to) in runs(parse_weeks(c["weeks"])):
            d = start + dt.timedelta(days=(c["weekday"] - 1) + 7 * (w_from - 1))
            ds = dt.datetime.combine(d, dt.time(sh, sm))
            de = dt.datetime.combine(d, dt.time(eh, em))
            count = w_to - w_from + 1
            rrule = f"FREQ=WEEKLY;COUNT={count};WKST=MO"
            binds = [
                f"calendar_id:i:{CAL_ID}", f"title:s:{title}",
                f"dtstart:l:{epoch_ms(ds)}", f"dtend:l:{epoch_ms(de)}",
                f"eventTimezone:s:{TZNAME}", f"rrule:s:{rrule}",
                "allDay:i:0", "hasAlarm:i:1",
            ]
            cmd = ["shell", " ".join(
                ["content", "insert", "--uri", "content://com.android.calendar/events"]
                + sum([["--bind", shlex.quote(b)] for b in binds], []))]
            if args.dry_run:
                print(f"  [dry] {ds:%m-%d %H:%M} 周{c['weekday']} × {count}周  {title}")
                made += 1
                continue
            out = adb(*cmd)
            m = re.search(r"/events/(\d+)", out)
            if not m:
                print(f"  ✗ 写入失败 {title}: {out.strip()[:80]}")
                continue
            eid = m.group(1)
            # 加一条提前 N 分钟的提醒（手机弹通知 → 手环振）
            for lead in range(args.lead, args.lead - 5, -1):   # 5 次，每分钟一次
                if lead > 0:
                    rb = [f"event_id:i:{eid}", f"minutes:i:-{lead}", "method:i:1"]
                    adb("shell", " ".join(
                        ["content", "insert", "--uri",
                         "content://com.android.calendar/reminders"]
                        + sum([["--bind", shlex.quote(b)] for b in rb], [])))
            made += 1
            print(f"  ✓ {ds:%m-%d} 周{'一二三四五六日'[c['weekday']-1]} "
                  f"{t0} × {count}周  {c['name']}")

    print(f"\n{'将写入' if args.dry_run else '已写入'} {made} 条日程（每条带 "
          f"{args.lead}/{args.lead-1}/{args.lead-2} 分钟三次提醒）")


if __name__ == "__main__":
    main()
