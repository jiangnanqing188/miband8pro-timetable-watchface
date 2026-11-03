#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把课表导出成 .ics 日历文件
==========================
导入手机日历后，每节课会变成一条「每周重复」的日程，手环开通知权限就能按时震动提醒
—— 这是让课表在手表上「活起来」（自动提醒、自动刷新）的唯一靠谱办法，
因为手环表盘本身没有联网更新数据的能力。

用法：
  python3 export_ics.py                 # 输出 out/课表.ics
  python3 export_ics.py --weeks 1-16    # 只导前 16 周
"""

import argparse
import datetime as dt
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
WEEKDAY_ICS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def parse_weeks(v):
    out = set()
    if isinstance(v, list):
        for x in v:
            if isinstance(x, str) and "-" in x:
                a, b = x.split("-", 1)
                out |= set(range(int(a), int(b) + 1))
            else:
                out.add(int(x))
        return out
    for part in str(v).replace("，", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out |= set(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def runs(weeks):
    """把 [3,4,5,9,10] 切成连续段 [(3,5),(9,10)]"""
    ws = sorted(weeks)
    if not ws:
        return []
    out, start, prev = [], ws[0], ws[0]
    for w in ws[1:]:
        if w == prev + 1:
            prev = w
            continue
        out.append((start, prev))
        start = prev = w
    out.append((start, prev))
    return out


def esc(s):
    """RFC 5545 文本转义"""
    s = str(s).replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,")
    return s.replace("\n", r"\n")


def fold(line):
    """RFC 5545 每行不超过 75 字节，超长折行"""
    raw = line.encode("utf-8")
    if len(raw) <= 73:
        return line
    out, buf, n = [], bytearray(), 0
    for ch in line:
        b = ch.encode("utf-8")
        if n + len(b) > 73:
            out.append(buf.decode("utf-8"))
            buf, n = bytearray(), 0
        buf += b
        n += len(b)
    out.append(buf.decode("utf-8"))
    return "\r\n ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config", "timetable.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "课表.ics"))
    ap.add_argument("--weeks", default="", help="限制导出周次，如 1-16")
    ap.add_argument("--lead", type=int, default=20, help="提前多少分钟提醒，默认 20")
    ap.add_argument("--ring", type=int, default=60, help="提醒持续多少秒，默认 60")
    args = ap.parse_args()

    cfg = json.load(open(args.config, encoding="utf-8"))
    meta = cfg.get("meta", {})
    tz = meta.get("timezone", "Asia/Shanghai")
    start = dt.date.fromisoformat(meta.get("semester_start", "2025-09-01"))
    # 学期起始日对齐到当周周一
    start -= dt.timedelta(days=start.weekday())
    periods = {p["no"]: p for p in cfg["periods"]}
    limit = parse_weeks(args.weeks) if args.weeks else None

    repeat = max(1, args.ring // 5 - 1)      # 约每 5 秒响一次
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//MiBand8Pro//Kebiao//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:我的课表",
        f"X-WR-TIMEZONE:{tz}",
        "BEGIN:VTIMEZONE",
        f"TZID:{tz}",
        "BEGIN:STANDARD",
        "DTSTART:19700101T000000",
        "TZOFFSETFROM:+0800",
        "TZOFFSETTO:+0800",
        "TZNAME:CST",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]

    count = 0
    for c in cfg["courses"]:
        weeks = parse_weeks(c.get("weeks", "1-16"))
        if limit:
            weeks &= limit
        if not weeks:
            continue
        ps = sorted(c["periods"])
        p0, p1 = ps[0], ps[-1]
        sh, sm = map(int, periods[p0]["start"].split(":"))
        eh, em = map(int, periods[p1]["end"].split(":"))
        wd = int(c["weekday"])

        for (w_from, w_to) in runs(weeks):
            d = start + dt.timedelta(days=(wd - 1) + 7 * (w_from - 1))
            ds = d.strftime("%Y%m%d")
            uid = f"{ds}T{sh:02d}{sm:02d}-{abs(hash((c['name'], wd, w_from)))%10**8}@miband8pro"
            summary = c["name"] + (f"（{c.get('room')}）" if c.get("room") else "")
            desc = " / ".join([x for x in (c.get("teacher", ""), c.get("room", "")) if x])
            lines += [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{stamp}",
                f"DTSTART;TZID={tz}:{ds}T{sh:02d}{sm:02d}00",
                f"DTEND;TZID={tz}:{ds}T{eh:02d}{em:02d}00",
                f"RRULE:FREQ=WEEKLY;COUNT={w_to - w_from + 1}",
                f"SUMMARY:{esc(summary)}",
                f"LOCATION:{esc(c.get('room', ''))}",
                f"DESCRIPTION:{esc(desc)}",
                # 提前 lead 分钟开始提醒，然后每约 5 秒再响一次，连续覆盖 ring 秒
                # —— 手机响一次，通知镜像到手环震一次，凑出"震一分钟"的效果
                "BEGIN:VALARM",
                f"TRIGGER:-PT{args.lead}M",
                f"DURATION:PT{args.ring}S",
                f"REPEAT:{repeat}",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{esc(c['name'])} {args.lead} 分钟后开始",
                "END:VALARM",
                "END:VEVENT",
            ]
            count += 1

    lines.append("END:VCALENDAR")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(fold(x) for x in lines) + "\r\n")

    print(f"✓ 导出 {count} 条重复日程 → {args.out}")
    print("  导入方法：手机上打开这个 .ics 文件 → 用「日历」打开 → 添加到日历")


if __name__ == "__main__":
    main()
