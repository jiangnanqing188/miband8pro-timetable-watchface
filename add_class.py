#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
加课 / 改课 / 删课：不用手改 JSON
=================================
    python3 add_class.py add "高等数学" -d 1 -p 1-2 -r 教三-201 -w 1-16
    python3 add_class.py add "体育" -d 3 -p 7-8 -r 体育馆          # 周次默认 1-16
    python3 add_class.py ls                    # 列出全部
    python3 add_class.py ls -d 2               # 只看周二
    python3 add_class.py today                 # 今天的课 + 时段
    python3 add_class.py rm 3                  # 删第 3 条
    python3 add_class.py edit 3 -r 教三-302    # 改第 3 条的教室

-d 星期(1-7)  -p 节次(1-2 / 3 / 5-8)  -r 教室  -w 周次(1-16 / 1-8,10-16)  -t 老师
"""

import argparse
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(ROOT, "config", "timetable.json")
WEEK_CN = "一二三四五六日"
PHASES = [("morning", "上午", "07:00", "12:00"),
          ("afternoon", "下午", "12:00", "18:00"),
          ("evening", "晚上", "18:00", "23:59")]


# ---------------------------------------------------------------- 工具
def dw(s):
    return sum(2 if ord(c) > 0x1100 else 1 for c in str(s))


def pad(s, n):
    s = str(s)
    return s + " " * max(0, n - dw(s))


def load():
    if not os.path.exists(CFG):
        sys.exit(f"找不到 {CFG}")
    return json.load(open(CFG, encoding="utf-8"))


def dump(cfg):
    with open(CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def parse_periods(s):
    s = re.sub(r"[第节\s]", "", str(s))
    s = s.replace("－", "-").replace("—", "-").replace("~", "-").replace("至", "-")
    out = []
    for part in re.split(r"[,，、]", s):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\d+)-(\d+)$", part)
        if m:
            a, b = sorted((int(m.group(1)), int(m.group(2))))
            out += list(range(a, b + 1))
        elif part.isdigit():
            out.append(int(part))
    if not out:
        sys.exit(f"节次看不懂：{s}（写 1-2 或 3 或 5-8）")
    return sorted(set(out))


def parse_weeks(s):
    s = re.sub(r"[第周\s]", "", str(s))
    s = s.replace("－", "-").replace("—", "-").replace("~", "-").replace("至", "-")
    out = []
    for part in re.split(r"[,，、]", s):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\d+)-(\d+)$", part)
        if m:
            out += list(range(int(m.group(1)), int(m.group(2)) + 1))
        elif part.isdigit():
            out.append(int(part))
    return sorted(set(out)) or list(range(1, 17))


def compact(nums):
    nums = sorted(set(nums))
    if not nums:
        return ""
    segs, a, p = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == p + 1:
            p = n
            continue
        segs.append((a, p))
        a = p = n
    segs.append((a, p))
    return ",".join(f"{x}-{y}" if y > x else str(x) for x, y in segs)


def period_time(cfg, no):
    p = next((x for x in cfg["periods"] if x["no"] == no), None)
    return p or {"start": "??:??", "end": "??:??"}


def conflicts(cfg, c, skip_idx=None):
    """返回和 c 撞节的已有课程"""
    out = []
    cw = set(parse_weeks(c["weeks"]))
    for i, o in enumerate(cfg["courses"]):
        if skip_idx is not None and i == skip_idx:
            continue
        if o["weekday"] != c["weekday"]:
            continue
        if not (set(o["periods"]) & set(c["periods"])):
            continue
        if set(parse_weeks(o.get("weeks", "1-16"))) & cw:
            out.append((i, o))
    return out


def show(cfg, courses=None, with_index=True):
    """按星期+节次排序显示，但索引永远是它在文件里的真实位置"""
    if courses is None:
        pairs = list(enumerate(cfg["courses"]))
    else:
        pairs = courses                      # [(idx, course)]
    pairs = sorted(pairs, key=lambda p: (p[1]["weekday"], p[1]["periods"][0]))
    if not pairs:
        print("  课表是空的，用 add 加一节")
        return
    print("  " + pad("", 4) + pad("星期", 6) + pad("节次", 9) + pad("时间", 15)
          + pad("课程", 20) + pad("教室", 16) + "周次")
    for idx, c in pairs:
        ps = c["periods"]
        t0 = period_time(cfg, ps[0])["start"]
        t1 = period_time(cfg, ps[-1])["end"]
        pr = f"{ps[0]}-{ps[-1]}" if len(ps) > 1 else str(ps[0])
        print("  " + pad(str(idx + 1) if with_index else "", 4) + pad("周" + WEEK_CN[c["weekday"] - 1], 6)
              + pad(pr + "节", 9) + pad(f"{t0}-{t1}", 15)
              + pad(c["name"][:16], 20) + pad(c.get("room", "")[:12], 16)
              + c.get("weeks", "1-16"))


# ---------------------------------------------------------------- 子命令
def cmd_add(a, cfg):
    cfg_periods = {p["no"] for p in cfg["periods"]}
    ps = parse_periods(a.periods)
    bad = [p for p in ps if p not in cfg_periods]
    if bad:
        sys.exit(f"作息表里没有第 {bad} 节（只有 1-{max(cfg_periods)} 节）")

    c = {"name": a.name, "weekday": a.day, "periods": ps}
    if a.room:
        c["room"] = a.room
    if a.teacher:
        c["teacher"] = a.teacher
    c["weeks"] = compact(parse_weeks(a.weeks))

    dup = [o for o in cfg["courses"]
           if o["name"] == c["name"] and o["weekday"] == c["weekday"]]
    if dup and not a.force:
        sys.exit(f"周{WEEK_CN[a.day-1]} 已经有「{c['name']}」了，"
                 f"要再加一遍加 --force（比如两节分开的课）")

    hit = conflicts(cfg, c)
    cfg["courses"].append(c)          # 只追加，不重排 —— 索引必须稳定
    dump(cfg)

    t0 = period_time(cfg, ps[0])["start"]
    t1 = period_time(cfg, ps[-1])["end"]
    print(f"✓ 已加：周{WEEK_CN[a.day-1]} {t0}-{t1} 第{ps[0]}-{ps[-1]}节 "
          f"{c['name']}  {c.get('room','')}  [{c['weeks']}周]")
    for i, o in hit:
        print(f"  ! 和「{o['name']}」撞在同一节（它上 {o.get('weeks')} 周）"
              f"—— 要么周次错开，要么删掉一个")
    print(f"  现在共 {len(cfg['courses'])} 门课")


def cmd_ls(a, cfg):
    if a.day:
        cs = [(i, c) for i, c in enumerate(cfg["courses"]) if c["weekday"] == a.day]
        print(f"周{WEEK_CN[a.day-1]}（{len(cs)} 门）：")
    else:
        cs = None
        print(f"全部课程（{len(cfg['courses'])} 门）：")
    show(cfg, cs)


def resolve(cfg, target):
    """'3' → 第3条；'高等数学' → 按名字找（必须唯一）"""
    t = str(target).strip()
    if t.isdigit():
        idx = int(t) - 1
        if not 0 <= idx < len(cfg["courses"]):
            sys.exit(f"没有第 {t} 条，现有 {len(cfg['courses'])} 条（用 ls 看）")
        return idx
    hits = [i for i, c in enumerate(cfg["courses"]) if c["name"] == t]
    if not hits:
        hits = [i for i, c in enumerate(cfg["courses"]) if t in c["name"]]
    if not hits:
        sys.exit(f"没有叫「{t}」的课")
    if len(hits) > 1:
        print(f"「{t}」匹配到 {len(hits)} 条，用编号指定：")
        for i in hits:
            c = cfg["courses"][i]
            print(f"  {i+1}  周{WEEK_CN[c['weekday']-1]} 第{c['periods']}节 "
                  f"{c['name']} {c.get('room','')}")
        sys.exit(1)
    return hits[0]


def cmd_rm(a, cfg):
    idx = resolve(cfg, a.target)
    if not 0 <= idx < len(cfg["courses"]):
        sys.exit(f"没有第 {a.index} 条，现有 {len(cfg['courses'])} 条")
    c = cfg["courses"].pop(idx)
    dump(cfg)
    print(f"✓ 已删：{c['name']}（周{WEEK_CN[c['weekday']-1]} 第{c['periods']}节）")
    print(f"  还剩 {len(cfg['courses'])} 门课")


def cmd_edit(a, cfg):
    idx = resolve(cfg, a.target)
    if not 0 <= idx < len(cfg["courses"]):
        sys.exit(f"没有第 {a.index} 条")
    c = cfg["courses"][idx]
    if a.name:
        c["name"] = a.name
    if a.day:
        c["weekday"] = a.day
    if a.periods:
        ps = parse_periods(a.periods)
        bad = [p for p in ps if p not in {x["no"] for x in cfg["periods"]}]
        if bad:
            sys.exit(f"作息表里没有第 {bad} 节")
        c["periods"] = ps
    if a.room is not None:
        c["room"] = a.room
    if a.teacher is not None:
        c["teacher"] = a.teacher
    if a.weeks:
        c["weeks"] = compact(parse_weeks(a.weeks))
    dump(cfg)
    print(f"✓ 已改：{c['name']}  周{WEEK_CN[c['weekday']-1]}  第{c['periods']}节  "
          f"{c.get('room','')}  [{c['weeks']}周]")


def cmd_today(a, cfg):
    d = dt.date.today()
    start = dt.date.fromisoformat(cfg.get("meta", {}).get("semester_start", "2026-09-07"))
    start -= dt.timedelta(days=start.weekday())
    week = (d - start).days // 7 + 1
    wd = d.isoweekday()
    print(f"{d:%Y-%m-%d} 周{WEEK_CN[wd-1]} · 第 {week} 周")
    cs = [c for c in cfg["courses"]
          if c["weekday"] == wd and week in parse_weeks(c.get("weeks", "1-16"))]
    cs.sort(key=lambda x: x["periods"][0])
    if not cs:
        print("  今天没课")
        return
    for c in cs:
        t0 = period_time(cfg, c["periods"][0])["start"]
        t1 = period_time(cfg, c["periods"][-1])["end"]
        ph = next((lab for _, lab, s, e in PHASES if s <= t0 < e), "")
        print(f"  {ph}  {t0}-{t1}  {pad(c['name'], 16)} {c.get('room','')}")


def main():
    ap = argparse.ArgumentParser(description="加课/改课/删课")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="加一门课")
    p.add_argument("name")
    p.add_argument("-d", "--day", type=int, required=True, help="星期 1-7")
    p.add_argument("-p", "--periods", required=True, help="节次，如 1-2 或 5-8")
    p.add_argument("-r", "--room", default="")
    p.add_argument("-t", "--teacher", default="")
    p.add_argument("-w", "--weeks", default="1-16", help="周次，如 1-16 或 1-8,10-16")
    p.add_argument("--force", action="store_true", help="允许同名同一天再加一节")

    p = sub.add_parser("ls", help="列出课程")
    p.add_argument("-d", "--day", type=int)

    p = sub.add_parser("rm", help="删掉第 N 条，或按课名删")
    p.add_argument("target")

    p = sub.add_parser("edit", help="改第 N 条，或按课名改")
    p.add_argument("target")
    p.add_argument("-n", "--name")
    p.add_argument("-d", "--day", type=int)
    p.add_argument("-p", "--periods")
    p.add_argument("-r", "--room")
    p.add_argument("-t", "--teacher")
    p.add_argument("-w", "--weeks")

    sub.add_parser("today", help="看今天的课")

    a = ap.parse_args()
    cfg = load()
    if a.cmd == "add" and not 1 <= a.day <= 7:
        sys.exit("星期要 1-7")
    {"add": cmd_add, "ls": cmd_ls, "rm": cmd_rm,
     "edit": cmd_edit, "today": cmd_today}[a.cmd](a, cfg)


if __name__ == "__main__":
    main()
