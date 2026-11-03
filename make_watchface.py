#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小米手环 8 Pro · 课表表盘生成器 v2
==================================
屏幕 336 × 480（AMOLED）。只画两样东西：

    ┌────────────────┐
    │                │  ← 时钟区：留空，交给手环自己叠加大号时间
    │   10:24        │     （时针分针由系统绘制，永远准）
    │                │
    │ 2025年11月3日 周一 │  ← 日期
    │ ─────────────  │
    │ ▌08:00  高等数学 │  ← 今日课程（时间 / 课名 / 教室）
    │ ▌10:00  大学英语 │
    └────────────────┘

不显示步数、电量、卡路里、老师、节次角标 —— 你说"其他可以不显示"。

用法：
  python3 make_watchface.py --preview        # 全部生成 + 预览页
  python3 make_watchface.py --week 12        # 指定教学周
  python3 make_watchface.py --clock bottom   # 手环时间叠在底部时用这个
"""

import argparse
import datetime as dt
import json
import os
import re

from PIL import Image, ImageDraw, ImageFont

W, H = 336, 480
S = 3

FONT_DIR = "/usr/share/fonts/opentype/noto"
FONT_FILES = {
    "bold":    ("NotoSansCJK-Bold.ttc", 2),
    "medium":  ("NotoSansCJK-Medium.ttc", 2),
    "regular": ("NotoSansCJK-Regular.ttc", 2),
    "light":   ("NotoSansCJK-Light.ttc", 2),
    "thin":    ("NotoSansCJK-Thin.ttc", 2),
}

BG        = "#000000"
CARD      = "#101317"
CARD_EDGE = "#1F2329"
CELL      = "#090B0D"
INK       = "#F4F6FA"
INK2      = "#8E949E"
INK3      = "#5A606B"

PALETTE = ["#5B8CFF", "#4ED0A6", "#FF9F5B", "#C77DFF",
           "#FF6B81", "#FFD166", "#4FC3F7", "#A3E635"]

WEEK_CN = ["一", "二", "三", "四", "五", "六", "日"]

# 一天的三个时段：早上 7 点换上午，中午 12 点换下午，傍晚 18 点换晚上
PHASES = [
    ("morning",   "上午", "07:00", "12:00"),
    ("afternoon", "下午", "12:00", "18:00"),
    ("evening",   "晚上", "18:00", "23:59"),
]
PHASE_LABEL = {k: lab for k, lab, _, _ in PHASES}
PHASE_BOUNDS = {k: (a, b) for k, _, a, b in PHASES}


def hm(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def phase_of(clock_str):
    """'13:20' → 'afternoon'"""
    t = hm(clock_str)
    for key, _, a, b in PHASES:
        if hm(a) <= t < hm(b):
            return key
    return "morning"


def now_phase():
    return phase_of(dt.datetime.now().strftime("%H:%M"))


def in_phase(item, phase):
    """按开始时间归段；没有 start 字段就用课程时间推"""
    return phase_of(item["start"]) == phase


# ------------------------------------------------------------------ 基础
def hex2rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def mix(c1, c2, t):
    a, b = hex2rgb(c1), hex2rgb(c2)
    return "#%02X%02X%02X" % tuple(
        int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


class Canvas:
    def __init__(self, w=W, h=H, bg=BG):
        self.img = Image.new("RGB", (w * S, h * S), bg)
        self.d = ImageDraw.Draw(self.img)
        self._cache = {}

    def font(self, kind, size):
        key = (kind, size)
        if key not in self._cache:
            name, idx = FONT_FILES.get(kind, FONT_FILES["regular"])
            px = max(1, int(round(size * S)))
            try:
                self._cache[key] = ImageFont.truetype(
                    os.path.join(FONT_DIR, name), px, index=idx)
            except Exception:
                self._cache[key] = ImageFont.truetype(
                    os.path.join(FONT_DIR, name), px)
        return self._cache[key]

    def text(self, xy, s, kind="regular", size=14, fill=INK, anchor="la"):
        self.d.text((xy[0] * S, xy[1] * S), s,
                    font=self.font(kind, size), fill=fill, anchor=anchor)

    def rrect(self, xy, r, fill=None, outline=None, width=1):
        x0, y0, x1, y1 = xy
        self.d.rounded_rectangle([x0 * S, y0 * S, x1 * S, y1 * S],
                                 radius=max(1, int(r * S)), fill=fill,
                                 outline=outline,
                                 width=max(1, int(width * S)) if outline else 0)

    def rline(self, xy, fill, width=1):
        x0, y0, x1, y1 = xy
        w = max(1, int(width * S))
        self.d.line([x0 * S, y0 * S, x1 * S, y1 * S], fill=fill, width=w)
        r = w / 2
        for (px, py) in ((x0, y0), (x1, y1)):
            self.d.ellipse([px * S - r, py * S - r, px * S + r, py * S + r], fill=fill)

    def text_w(self, s, kind, size):
        return self.d.textlength(s, font=self.font(kind, size)) / S

    def fit(self, s, kind, size, maxw):
        if self.text_w(s, kind, size) <= maxw:
            return s
        while s and self.text_w(s + "…", kind, size) > maxw:
            s = s[:-1]
        return s + "…"

    def save(self, path):
        self.img.resize((W, H), Image.LANCZOS).save(path, optimize=True)
        return path


# ------------------------------------------------------------------ 数据
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


def load_cfg(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["_periods"] = {p["no"]: p for p in cfg["periods"]}
    named = {}
    for i, c in enumerate(cfg["courses"]):
        c["_weeks"] = parse_weeks(c.get("weeks", "1-16"))
        c["_ps"] = sorted(c["periods"])
        key = (c["name"], c.get("teacher", ""))
        if key in named:
            c["color"] = named[key]
        else:
            c["color"] = c.get("color") or PALETTE[i % len(PALETTE)]
            named[key] = c["color"]
    return cfg


def monday_of(cfg, week):
    """第 week 周的周一"""
    m = cfg.get("meta", {})
    start = dt.date.fromisoformat(m.get("semester_start", "2025-09-01"))
    start -= dt.timedelta(days=start.weekday())
    return start + dt.timedelta(weeks=week - 1)


def week_of_date(cfg, d):
    """某个日期是第几教学周"""
    return (d - monday_of(cfg, 1)).days // 7 + 1


def date_of(cfg, week, weekday):
    return monday_of(cfg, week) + dt.timedelta(days=weekday - 1)


def lessons_of(cfg, weekday, week):
    pr = cfg["_periods"]
    out = []
    for c in cfg["courses"]:
        if c["weekday"] != weekday or week not in c["_weeks"]:
            continue
        p0, p1 = c["_ps"][0], c["_ps"][-1]
        out.append({
            "name": c["name"], "room": c.get("room", ""), "color": c["color"],
            "p0": p0, "p1": p1,
            "start": pr[p0]["start"], "end": pr[p1]["end"],
        })
    out.sort(key=lambda x: x["p0"])
    return out


# ------------------------------------------------------------------ 布局常量
CLOCK_H = 104          # 给系统大数字时钟预留的高度
MARGIN = 18


def clock_zone(zone):
    """返回 (课表区上边界, 是否把时钟放底部)"""
    if zone == "bottom":
        return 42, True
    return CLOCK_H + 44, False


# ------------------------------------------------------------------ 视图一：当日
def draw_today(cfg, weekday, week, out, clock="top", theme="card", mock=False,
               phase=None):
    if theme == "line":
        cv = draw_today_line(cfg, weekday, week, clock, phase)
    elif theme == "bar":
        cv = draw_today_bar(cfg, weekday, week, clock, phase)
    else:
        cv = draw_today_card(cfg, weekday, week, clock, phase)
    if mock:
        draw_clock_mock(cv, clock)
    return cv.save(out)



def _head(cv, d, weekday, clock, label=None):
    """日期行 + 分隔线，返回课表区 (top, bottom)"""
    body_top, clock_bottom = clock_zone(clock)
    txt = f"{d.year}年{d.month}月{d.day}日  周{WEEK_CN[weekday - 1]}"
    if label:
        txt += f" · {label}"
    if clock_bottom:
        cv.text((W / 2, 26), txt, "medium", 12.5, INK2, anchor="mm")
        cv.rline((MARGIN, 40, W - MARGIN, 40), "#1E2228", 1)
        return 52, H - CLOCK_H - 16
    cv.text((W / 2, CLOCK_H + 26), txt, "medium", 12.5, INK2, anchor="mm")
    cv.rline((MARGIN, CLOCK_H + 42, W - MARGIN, CLOCK_H + 42), "#1E2228", 1)
    return CLOCK_H + 44, 468


def _empty(cv, top, bottom, label=None):
    cy = (top + bottom) / 2
    cv.text((W / 2, cy - 10), f"{label}没课" if label else "今天没课",
            "bold", 19, INK2, anchor="mm")
    cv.text((W / 2, cy + 20), "好好休息", "regular", 12, INK3, anchor="mm")
    return cv


def draw_today_line(cfg, weekday, week, clock="top", phase=None):
    """极简：纯黑底 + 细线分隔，没有卡片填充，最像系统原生"""
    cv = Canvas()
    label = PHASE_LABEL.get(phase) if phase else None
    top, bottom = _head(cv, date_of(cfg, week, weekday), weekday, clock, label)
    items = lessons_of(cfg, weekday, week)
    if phase:
        items = [it for it in items if in_phase(it, phase)]
    if not items:
        return _empty(cv, top, bottom, label)

    n = len(items)
    avail = bottom - top
    rh = min(96, avail / n)
    y0 = top + max(0, (avail - rh * n) / 2)

    for i, it in enumerate(items):
        y = y0 + rh * i
        cy = y + rh / 2
        # 字随行高自适应
        nsz = max(13.0, min(24.0 if n <= 2 else 20.0, rh * 0.34))
        tsz = nsz * 0.9
        show_room = rh >= 52
        # 时间列（右对齐）
        cv.text((78, cy - nsz * 0.62), it["start"], "bold", tsz, INK, anchor="ra")
        if show_room:
            cv.text((78, cy + nsz * 0.5), it["end"], "regular", 9.5, INK3, anchor="ra")
        # 色条
        cv.rrect((90, cy - nsz * 0.72, 93.5, cy + nsz * 0.72), 1.8, fill=it["color"])
        # 课名 + 教室
        cv.text((104, cy - nsz * 0.86), cv.fit(it["name"], "bold", nsz,
                W - 104 - MARGIN), "bold", nsz, INK)
        if it["room"] and show_room:
            cv.text((104, cy + nsz * 0.34), cv.fit(it["room"], "regular", 10.5,
                    W - 104 - MARGIN), "regular", 10.5, INK2)
        if i < n - 1:
            cv.rline((MARGIN, y + rh, W - MARGIN, y + rh), "#191C21", 1)
    return cv


def draw_today_bar(cfg, weekday, week, clock="top", phase=None):
    """时间轴：一条竖线串起今天的课，圆点是节点"""
    cv = Canvas()
    label = PHASE_LABEL.get(phase) if phase else None
    top, bottom = _head(cv, date_of(cfg, week, weekday), weekday, clock, label)
    items = lessons_of(cfg, weekday, week)
    if phase:
        items = [it for it in items if in_phase(it, phase)]
    if not items:
        return _empty(cv, top, bottom, label)

    n = len(items)
    avail = bottom - top
    rh = min(98, avail / n)
    y0 = top + max(0, (avail - rh * n) / 2)
    rail = 62

    first_cy = y0 + rh / 2
    last_cy = y0 + rh * (n - 1) + rh / 2
    cv.d.line([rail * S, first_cy * S, rail * S, last_cy * S], fill="#20242A", width=S)
    _dots = []
    for i, it in enumerate(items):
        _dots.append((it, y0 + rh * i + rh / 2))

    nsz = max(13.0, min(23.0 if n <= 2 else 19.0, rh * 0.32))
    show_room = rh >= 52
    for it, cy in _dots:
        cv.text((rail - 14, cy - nsz * 0.58), it["start"], "bold", nsz * 0.78, INK, anchor="ra")
        if show_room:
            cv.text((rail - 14, cy + nsz * 0.5), it["end"], "regular", 9, INK3, anchor="ra")
        r = min(5.0, max(3.2, rh * 0.075))
        cv.d.ellipse([(rail - r) * S, (cy - r) * S, (rail + r) * S, (cy + r) * S],
                     fill=it["color"])
        cv.d.ellipse([(rail - r * 0.32) * S, (cy - r * 0.32) * S,
                      (rail + r * 0.32) * S, (cy + r * 0.32) * S], fill=BG)
        cv.text((rail + 20, cy - nsz * 0.84), cv.fit(it["name"], "bold", nsz,
                W - rail - 40), "bold", nsz, INK)
        if it["room"] and show_room:
            cv.text((rail + 20, cy + nsz * 0.32), cv.fit(it["room"], "regular", 10.5,
                    W - rail - 40), "regular", 10.5, INK2)
    return cv


def draw_clock_mock(cv, clock):
    """只在预览里用：模拟手环叠上去的大号时间，让你看清最终效果"""
    if clock == "bottom":
        cy = H - CLOCK_H / 2
    else:
        cy = 30 + CLOCK_H / 2 - 10
    cv.text((W / 2, cy), "10:24", "bold", 56, "#E9ECF1", anchor="mm")
    cv.text((W / 2, cy + 40), "模拟手环时间", "regular", 8, "#4A505A", anchor="mm")


def draw_today_card(cfg, weekday, week, clock="top", phase=None):
    cv = Canvas()
    label = PHASE_LABEL.get(phase) if phase else None
    body_top, body_bottom = _head(cv, date_of(cfg, week, weekday), weekday, clock, label)

    items = lessons_of(cfg, weekday, week)
    if phase:
        items = [it for it in items if in_phase(it, phase)]
    if not items:
        return _empty(cv, body_top, body_bottom, label)

    n = len(items)
    gap = 10 if n <= 4 else 7
    avail = body_bottom - body_top
    cap = 94 if n <= 3 else 104
    h = min(cap, (avail - gap * (n - 1)) / n)
    used = h * n + gap * (n - 1)
    y = body_top + max(0, (avail - used) / 2)

    for it in items:
        x0, x1 = MARGIN, W - MARGIN
        cv.rrect((x0, y, x1, y + h), 13, fill=it["color"])
        cv.rrect((x0 + 4, y, x1, y + h), 9, fill=CARD, outline=CARD_EDGE, width=1)

        # 自适应：卡片越高字越大；1-2 节课走大字版、整块垂直居中
        if h >= 118:
            tsz, esz, namesz, roomsz, gap2 = 20, 12, 28, 14, 40
        elif h >= 84:
            tsz, esz, namesz, roomsz, gap2 = 16.5, 11, 22, 12, 32
        elif h >= 70:
            tsz, esz, namesz, roomsz, gap2 = 15, 10, 19, 11, 26
        elif h >= 54:
            tsz, esz, namesz, roomsz, gap2 = 13.5, 9, 17, 10, 24
        elif h >= 42:
            tsz, esz, namesz, roomsz, gap2 = 12.5, 0, 16, 0, 0
        else:
            tsz, esz, namesz, roomsz, gap2 = 11.5, 0, 14, 0, 0

        if h >= 84:
            # 大字版：内容块整体居中，看着才不飘
            block = namesz + (gap2 if (it["room"] and roomsz) else 0)
            ny = y + (h - block) / 2
        else:
            ny = y + 15 if h >= 70 else (y + 11 if h >= 54 else y + 9)

        # 时间列
        cv.text((x0 + 15, ny), it["start"], "bold", tsz, INK)
        if esz:
            cv.text((x0 + 15, ny + tsz + 8), it["end"], "regular", esz, INK3)

        # 课名 + 教室
        tx = x0 + 66
        tw = x1 - 14 - tx
        cv.text((tx, ny), cv.fit(it["name"], "bold", namesz, tw), "bold", namesz, INK)
        if it["room"] and roomsz:
            cv.text((tx, ny + gap2), cv.fit(it["room"], "regular", roomsz, tw),
                    "regular", roomsz, INK2)
        y += h + gap

    return cv


# ------------------------------------------------------------------ 视图二：一周
def grid_lines(name, per):
    nm = re.sub(r"\s+", "", name).replace("(", "（").replace(")", "）")
    m = re.match(r"^(.+?)（([^）]*)）$", nm)
    if m:
        base, inner = m.group(1), m.group(2)
        if len(base) >= 3:
            nm = base
        elif 0 < len(base) <= per and 0 < len(inner) <= per:
            return [base, inner]
    lines = [nm[k:k + per] for k in range(0, len(nm), per)]
    if len(lines) == 2 and len(lines[1]) == 1 and len(lines[0]) > 2:
        lines[0] = lines[0][:-1]
        lines[1] = nm[len(lines[0]):]
    if len(lines) > 2:
        lines = lines[:2]
        lines[1] = lines[1][:max(1, per - 1)] + "…"
    return lines


def draw_week(cfg, week, out, clock="top"):
    cv = Canvas()
    monday = monday_of(cfg, week)

    days = sorted({c["weekday"] for c in cfg["courses"]
                   if week in c["_weeks"]}) or [1, 2, 3, 4, 5]
    maxp = max(max(c["_ps"]) for c in cfg["courses"]) if cfg["courses"] else 12
    rows = max(8, min(len(cfg["periods"]), maxp))

    if clock == "bottom":
        cv.text((MARGIN, 22), f"{monday.month}月{monday.day}日 – "
                              f"第{week}周", "medium", 12, INK2)
        cv.rline((MARGIN, 40, W - MARGIN, 40), "#1E2228", 1)
        gy0, gy1, lab_y = 58, H - CLOCK_H - 6, 44
    else:
        cv.text((MARGIN, 20), f"{monday.year}年{monday.month}月", "medium", 12, INK3)
        cv.text((W - MARGIN, 20), f"第 {week} 周", "medium", 12, INK3, anchor="ra")
        gy0, gy1, lab_y = CLOCK_H + 46, 468, CLOCK_H + 32
    cv.rline((MARGIN, lab_y + 12, W - MARGIN, lab_y + 12), "#1E2228", 1)

    gutter = 20
    colw = (W - MARGIN * 2 - gutter) / len(days)
    rowh = (gy1 - gy0) / rows

    # 列头：星期 + 日期
    for i, dd in enumerate(days):
        cx = MARGIN + gutter + colw * i + colw / 2
        d = monday + dt.timedelta(days=dd - 1)
        cv.text((cx, lab_y + 2), WEEK_CN[dd - 1], "bold", 11.5, INK, anchor="ma")
        cv.text((cx, lab_y + 16), f"{d.month}/{d.day}", "regular", 8, INK3, anchor="ma")

    for r in range(rows):
        cv.text((MARGIN + 3, gy0 + rowh * r + rowh / 2), str(r + 1),
                "regular", 9.5, INK3, anchor="lm")

    for i in range(len(days)):
        for r in range(rows):
            cx0 = MARGIN + gutter + colw * i
            cv.rrect((cx0 + 1.5, gy0 + rowh * r + 1, cx0 + colw - 1.5,
                      gy0 + rowh * (r + 1) - 1), 5, fill=CELL)

    for d in days:
        for it in lessons_of(cfg, d, week):
            i = days.index(d)
            cx0 = MARGIN + gutter + colw * i
            y0 = gy0 + rowh * (it["p0"] - 1) + 1
            y1 = gy0 + rowh * it["p1"] - 1
            cv.rrect((cx0 + 1.5, y0, cx0 + colw - 1.5, y1), 5,
                     fill=mix(BG, it["color"], 0.34))
            cv.rrect((cx0 + 1.5, y0, cx0 + colw - 1.5, y0 + 2), 1, fill=it["color"])

            size = 9.5 if colw >= 55 else 9
            per = max(2, int((colw - 7) // (size * 1.02)))
            lines = grid_lines(it["name"], per)
            th = len(lines) * (size + 2)
            ty = (y0 + y1) / 2 - th / 2 + size / 2
            for li, ln in enumerate(lines):
                cv.text((cx0 + colw / 2, ty + li * (size + 2)), ln, "medium", size,
                        mix(it["color"], "#FFFFFF", 0.62), anchor="mm")

    return cv.save(out)


# ------------------------------------------------------------------ 预览页
PREVIEW_TMPL = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>小米手环 8 Pro · 课表表盘</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; padding:48px 32px 64px; background:#08090A; color:#E8EAEE;
         font:15px/1.6 -apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif; }
  header { max-width:1180px; margin:0 auto 36px; }
  h1 { margin:0 0 6px; font-size:25px; letter-spacing:-.01em; }
  p.sub { margin:0; color:#8B9099; font-size:14px; }
  .grid { max-width:1180px; margin:0 auto; display:grid;
          grid-template-columns:repeat(auto-fill,minmax(336px,336px)); gap:30px; }
  figure { margin:0; }
  .frame { width:336px; border-radius:26px; overflow:hidden; background:#000;
           box-shadow:0 0 0 1px #20242A, 0 18px 40px -18px #000; }
  .frame img { display:block; width:336px; height:480px; }
  figcaption { margin-top:11px; display:flex; justify-content:space-between;
               align-items:baseline; gap:12px; }
  figcaption b { font-weight:600; font-size:14px; }
  figcaption span { color:#666C76; font-size:12px; font-variant-numeric:tabular-nums; }
  a { color:#5B8CFF; text-decoration:none; font-size:12px; }
  a:hover { text-decoration:underline; }
  footer { max-width:1180px; margin:52px auto 0; color:#565C66; font-size:13px;
           border-top:1px solid #17191D; padding-top:18px; }
</style></head><body>
<header>
  <h1>课表表盘 · 336 × 480</h1>
  <p class="sub">第 __WEEK__ 周 · __RANGE__ · 存到手机相册 → 小米运动健康 → 相册表盘</p>
</header>
<div class="grid">
__CARDS__
</div>
<footer>顶部 __CLOCKH__px 是留给手环自己画的大号时钟，图上不画时间，所以时间永远准。
手环把时间画在底部时，重新生成加 <code>--clock bottom</code>。</footer>
</body></html>"""


def write_preview(outdir, files, week, range_txt, clock_h):
    cards = []
    for path in files:
        name = os.path.basename(path)
        t = name.replace("watchface_", "").replace(".png", "")
        title = "一周总览" if t == "week" else f"周{t}"
        cards.append(
            f'<figure><div class="frame"><img src="{name}" alt="{title}" '
            f'width="336" height="480"></div><figcaption><b>{title}</b>'
            f'<span>{os.path.getsize(path) // 1024} KB · '
            f'<a href="{name}">原图</a></span></figcaption></figure>')
    html = (PREVIEW_TMPL.replace("__WEEK__", str(week))
            .replace("__RANGE__", range_txt)
            .replace("__CLOCKH__", str(clock_h))
            .replace("__CARDS__", "\n".join(cards)))
    p = os.path.join(outdir, "preview.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)
    return p


# ------------------------------------------------------------------ main
def main():
    global CLOCK_H
    root = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(root, "config", "timetable.json"))
    ap.add_argument("--out", default=os.path.join(root, "out"))
    ap.add_argument("--week", type=int, default=None)
    ap.add_argument("--day", type=int, default=None)
    ap.add_argument("--clock", choices=["top", "bottom"], default="top",
                    help="手环把时间画在顶部还是底部，决定图往哪边留白")
    ap.add_argument("--theme", choices=["card", "line", "bar"], default="card",
                    help="界面风格：card 卡片 / line 极简列表 / bar 时间轴")
    ap.add_argument("--clock-h", type=int, default=104,
                    help="顶部给手环时钟预留的高度，默认 104；时间被压到日期就调大")
    ap.add_argument("--mock", action="store_true",
                    help="额外生成 mock_*.png：模拟手环把时间叠上去的样子")
    ap.add_argument("--no-week", action="store_true")
    ap.add_argument("--phase", choices=[k for k, *_ in PHASES], default=None,
                    help="只出某个时段：上午/下午/晚上")
    ap.add_argument("--auto-phase", action="store_true",
                    help="按当前时间自动选时段（配 cron 每半小时跑一次）")
    ap.add_argument("--all-phases", action="store_true",
                    help="三个时段各出一张，附一个挑选页")
    ap.add_argument("--today", action="store_true",
                    help="只出「今天」这一张，文件名 out/today.png（配合 --cron 每天自动换）")
    ap.add_argument("--date", default=None, help="指定日期 YYYY-MM-DD，自动算周几和第几周")
    ap.add_argument("--cron", action="store_true", help="打印每天自动出图的 crontab 行")
    ap.add_argument("--calibrate", action="store_true",
                    help="出几张不同留白高度的标定图，装上手环比出哪个刚好框住系统时间")
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()

    CLOCK_H = args.clock_h
    if args.calibrate:
        cfg = load_cfg(args.config)
        day = dt.date.today()
        week = week_of_date(cfg, day)
        cal = os.path.join(args.out, "calibrate")
        os.makedirs(cal, exist_ok=True)
        cands = [80, 96, 112, 128, 144]
        for h in cands:
            CLOCK_H = h
            cv = draw_today_card(cfg, day.isoweekday(), week, "top")
            # 画一个标定框：框住的区域就是留给系统时钟的
            cv.d.rectangle([8 * S, 8 * S, (W - 8) * S, h * S], outline="#3A4048", width=S)
            cv.text((W - 12, h - 12), f"时钟区 {h}px", "medium", 7.5, "#6B717B", anchor="rs")
            cv.save(os.path.join(cal, f"clock_{h}.png"))
            CLOCK_H = args.clock_h
        import make_calibrate_page as _m
        _m.build(cal, cands, day, week)
        print(f"标定图 {len(cands)} 张 → {os.path.join(cal, 'index.html')}")
        print("装到手环上，看哪个框刚好把系统时间框住，然后 --clock-h 用那个值")
        return

    if args.cron:
        here = os.path.dirname(os.path.abspath(__file__))
        py = "python3"
        print("把下面这行加到 crontab（crontab -e）里，每天早上 6:30 自动出当天的图：\n")
        print(f'30 6 * * *  cd "{here}" && {py} make_watchface.py --today --theme card >/dev/null 2>&1')
        print("\n想连提醒一起挂后台，再加一行：")
        print(f'30 6 * * *  cd "{here}" && nohup {py} remind.py >> out/remind.log 2>&1 &')
        return

    cfg = load_cfg(args.config)
    today_mode = bool(args.today or args.date)
    if args.date:
        day = dt.date.fromisoformat(args.date)
    elif args.today:
        day = dt.date.today()
    else:
        day = None

    week = args.week or cfg["meta"].get("current_week", 1)
    if day:
        week = week_of_date(cfg, day)
    os.makedirs(args.out, exist_ok=True)
    made = []

    if cfg["meta"].get("sample_data"):
        print("⚠️  config/timetable.json 还是示例数据，改成你自己的课表再生成")

    if today_mode:
        if week < 1 or week > 40:
            print(f"⚠️  {day} 不在学期内（算出来是第 {week} 周），先改 config 里的 semester_start")
        wd = day.isoweekday()
        allc = lessons_of(cfg, wd, week)
        head = f"{day:%Y-%m-%d} 周{WEEK_CN[wd - 1]} · 第 {week} 周"

        if args.all_phases:
            for key, lab, _, _ in PHASES:
                dst = os.path.join(args.out, f"today_{key}.png")
                draw_today(cfg, wd, week, dst, args.clock, args.theme, phase=key)
                got = [it for it in allc if in_phase(it, key)]
                print(f"  ✓ {os.path.basename(dst):<22}{lab} {len(got)} 节")
                for it in got:
                    print(f"       {it['start']}-{it['end']}  {it['name']}  {it['room']}")
            import make_calibrate_page as _m
            _m.build_phases(args.out, day, week, args.theme)
            print(f"\n{head}\n  挑时段页 → {os.path.join(args.out, 'phases.html')}")
            return

        phase = args.phase or (now_phase() if args.auto_phase else None)
        items = [it for it in allc if in_phase(it, phase)] if phase else allc
        dst = os.path.join(args.out, "today.png")
        draw_today(cfg, wd, week, dst, args.clock, args.theme, phase=phase)
        if phase:
            named = os.path.join(args.out, f"today_{phase}.png")
            draw_today(cfg, wd, week, named, args.clock, args.theme, phase=phase)
        if args.mock:
            draw_today(cfg, wd, week, os.path.join(args.out, "today_mock.png"),
                       args.clock, args.theme, mock=True, phase=phase)
        lab = PHASE_LABEL.get(phase, "") if phase else ""
        print(f"{head}{(' · ' + lab) if lab else ''} · {len(items)} 节")
        for it in items:
            print(f"   {it['start']}-{it['end']}  {it['name']}  {it['room']}")
        print()
        print(f"  ✓ {os.path.basename(dst)}  {os.path.getsize(dst) // 1024} KB"
              + (f"  （同时存了 today_{phase}.png）" if phase else ""))
        return

    if not args.no_week:
        made.append(draw_week(cfg, week, os.path.join(args.out, "watchface_week.png"),
                              args.clock))

    for d in ([args.day] if args.day else range(1, 8)):
        if not any(c["weekday"] == d for c in cfg["courses"]):
            continue
        made.append(draw_today(cfg, d, week,
                              os.path.join(args.out, f"watchface_周{WEEK_CN[d - 1]}.png"),
                              args.clock, args.theme))

    if args.mock:
        for d in ([args.day] if args.day else range(1, 8)):
            if not any(c["weekday"] == d for c in cfg["courses"]):
                continue
            draw_today(cfg, d, week,
                       os.path.join(args.out, f"mock_周{WEEK_CN[d - 1]}.png"),
                       args.clock, args.theme, mock=True)

    for p in made:
        print(f"  ✓ {os.path.basename(p)}  {os.path.getsize(p) // 1024} KB")
    if args.preview:
        mon = monday_of(cfg, week)
        sun = mon + dt.timedelta(days=6)
        rng = f"{mon.month}月{mon.day}日 – {sun.month}月{sun.day}日"
        pv = write_preview(args.out, made, week, rng,
                           CLOCK_H if args.clock == "top" else 0)
        print(f"  ✓ {os.path.basename(pv)}  ← 浏览器打开对比")
    print(f"共 {len(made)} 张 → {args.out}")


if __name__ == "__main__":
    main()
