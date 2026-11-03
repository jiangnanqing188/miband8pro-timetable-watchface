#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用同一套素材 + 同一套坐标合成预览图
=====================================
这不是"另一个渲染器"，是把 main.lua 的排版逻辑在 Python 里复刻一遍，
用来确认图元和坐标对得上（Lua 里跑不出画面，只能靠这个看）。

python3 wf/preview.py
→ wf/preview_morning.png / afternoon / evening
"""
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "wf", "images")
OUT = os.path.join(ROOT, "wf")
W, H = 336, 480

import re
LUA = open(os.path.join(ROOT, "wf", "app", "lua", "data.lua"), encoding="utf-8").read()
WID = {k: int(v) for k, v in re.findall(r'\["(\w+)"\] = (\d+)', LUA)}
# 从 data.lua 读坐标，别再写死（表盘用的是它，预览也必须一致）
_m = re.search(r"M\.LAYOUT = \{([^}]*)\}", LUA, re.S)
LAYOUT = {}
if _m:
    for k, v in re.findall(r"(\w+)\s*=\s*(-?\d+)", _m.group(1)):
        LAYOUT[k] = int(v)
LAYOUT.setdefault("clock_y", 34); LAYOUT.setdefault("date_y", 126)
LAYOUT.setdefault("card1_y", 190); LAYOUT.setdefault("card2_y", 328)
LAYOUT.setdefault("card_x", 18)

COURSES = []
for m in re.finditer(r'\{ day=(\d+), from=(\d+), to=(\d+), normal="([^"]+)", hi="([^"]+)", '
                     r'weeks=\{([^}]*)\}, name="([^"]+)" \}', LUA):
    weeks = [int(x) for x in m.group(6).split(",") if x.strip()]
    COURSES.append({"day": int(m.group(1)), "from": int(m.group(2)), "to": int(m.group(3)),
                    "normal": m.group(4), "hi": m.group(5), "name": m.group(7),
                    "weeks": weeks})


def paste(canvas, name, x, y):
    p = os.path.join(IMG, name + ".png")
    if not os.path.exists(p):
        return 0
    im = Image.open(p).convert("RGBA")
    canvas.alpha_composite(im, (int(x), int(y)))
    return WID.get(name, im.width)


WEEK = 9          # 预览用第 9 周（2026-11-03 所在周）


def draw(canvas, y, mo, d, wd, hh, mm, phase_key, phase, now_min, week=WEEK):
    # 右上角：第 N 周
    seq = ["di"] + ["d" + c for c in str(week)] + ["wk"]
    total = sum(WID.get(k, 0) for k in seq)
    x = W - 16 - total
    for k in seq:
        x += paste(canvas, k, x, 14)

    # 时钟
    s = f"{hh:02d}:{mm:02d}"
    total = sum(WID.get("tc" if ch == ":" else "t" + ch, 0) for ch in s)
    x = (W - total) // 2
    for ch in s:
        key = "tc" if ch == ":" else "t" + ch
        x += paste(canvas, key, x, LAYOUT["clock_y"])

    # 日期
    seq = []
    for ch in str(y):
        seq.append("d" + ch)
    seq += ["y"]
    for ch in str(mo):
        seq.append("d" + ch)
    seq += ["mo"]
    for ch in str(d):
        seq.append("d" + ch)
    seq += ["dd", "wk", f"w{wd}", "dot", phase_key]
    total = sum(WID.get(k, 0) for k in seq)
    x = (W - total) // 2
    for k in seq:
        x += paste(canvas, k, x, LAYOUT["date_y"])

    # 课程卡
    # 和 main.lua 一样：只看这一天、这一周、这一段的课
    today = [c for c in COURSES
             if c["day"] == wd and WEEK in c["weeks"] and _phase(c["from"]) == phase]
    today.sort(key=lambda c: c["from"])
    today = today[:2]
    if not today:
        im = Image.open(os.path.join(IMG, f"empty_{phase}.png")).convert("RGBA")
        canvas.alpha_composite(im, (LAYOUT["card_x"], LAYOUT["card1_y"]))
    else:
        for i, c in enumerate(today):
            live = c["from"] <= now_min < c["to"]
            im = Image.open(os.path.join(IMG, c["hi"] if live else c["normal"])).convert("RGBA")
            canvas.alpha_composite(im, (LAYOUT["card_x"],
                                        LAYOUT["card1_y"] if i == 0 else LAYOUT["card2_y"]))


def _phase(minutes):
    if minutes < 720:
        return "morning"
    if minutes < 1080:
        return "afternoon"
    return "evening"


def main():
    # 2026-11-03 周二（第 9 周）
    cases = [("morning", 8, 30), ("afternoon", 14, 30), ("evening", 19, 30)]
    for phase, hh, mm in cases:
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        draw(canvas, 2026, 11, 3, 2, hh, mm, "p_" + phase, phase, hh * 60 + mm)
        p = os.path.join(OUT, f"preview_{phase}.png")
        canvas.convert("RGB").save(p, optimize=True)
        print(f"  ✓ {os.path.basename(p)}  {os.path.getsize(p)//1024} KB")


if __name__ == "__main__":
    main()
