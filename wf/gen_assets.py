#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课表表盘素材生成器（Lua 表盘版）
=================================
手环上的表盘是 Lua 程序，文字/数字全靠预渲染的 PNG 图元拼出来
（手环不一定带中文字库，这是社区通用做法）。

这个脚本干三件事：
  1. 把时钟数字、日期数字、汉字标签渲染成小 PNG
  2. 把每节课渲染成一张整卡 PNG（普通版 + 高亮版）
  3. 生成 Lua 数据表：每门课在第几天、几分开始/结束、对应哪张图

输出：wf/images/  +  wf/app/lua/data.lua
"""
import datetime as dt
import json
import re
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_IMG = os.path.join(ROOT, "wf", "images")
OUT_LUA = os.path.join(ROOT, "wf", "app", "lua")
FONT_DIR = "/usr/share/fonts/opentype/noto"
S = 3                       # 超采样

INK = "#F4F6FA"
INK2 = "#8E949E"
INK3 = "#5A606B"
CARD = "#101317"
CARD_HI = "#1B2028"
EDGE = "#1F2329"
PALETTE = ["#5B8CFF", "#4ED0A6", "#FF9F5B", "#C77DFF",
           "#FF6B81", "#FFD166", "#4FC3F7", "#A3E635"]
WEEK_CN = "一二三四五六日"

W, H = 336, 480
CLOCK_Y = 34            # 大号时间
DATE_Y = 126            # 日期行
CARD1_Y = 186           # 第一节课卡片
CARD2_Y = 328           # 第二节课卡片（和第一张留 10px 间距）
CARD_X, CARD_W, CARD_H = 18, 300, 132


def font(weight, size):
    name = {"bold": "NotoSansCJK-Bold.ttc", "medium": "NotoSansCJK-Medium.ttc",
            "regular": "NotoSansCJK-Regular.ttc", "light": "NotoSansCJK-Light.ttc"}[weight]
    return ImageFont.truetype(os.path.join(FONT_DIR, name), int(size * S), index=2)


def new(w, h):
    im = Image.new("RGBA", (int(w * S), int(h * S)), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def save(im, path):
    """缩小并压到纯黑底上存成 RGB —— 手环上不透明图走快路径，
    带 alpha 的每帧都要混合，300×116 两张就够卡了。"""
    im = im.resize((im.width // S, im.height // S), Image.LANCZOS)
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (0, 0, 0))
        bg.paste(im, mask=im.split()[-1])
        bg.save(path, optimize=True)
    else:
        im.convert("RGB").save(path, optimize=True)
    return im.width


def bbox(draw, text, f):
    b = draw.textbbox((0, 0), text, font=f)
    return b


def glyph(text, weight, size, color=INK, pad=1):
    """渲染单字/单词为 PNG，返回原图（已在 3 倍画布上，save() 时缩小）"""
    f = font(weight, size)                      # 3 倍字号
    tmp = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    b = tmp.textbbox((0, 0), text, font=f)      # 3 倍像素
    pad3 = pad * S
    w3, h3 = b[2] - b[0] + pad3 * 2, b[3] - b[1] + pad3 * 2
    im = Image.new("RGBA", (max(w3, 1), max(h3, 1)), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad3 - b[0], pad3 - b[1]), text, font=f, fill=color)
    return im, w3 / S, h3 / S


def make_glyphs():
    widths = {}
    os.makedirs(OUT_IMG, exist_ok=True)
    # 大号时间数字（76px）
    for c in "0123456789":
        im, w, h = glyph(c, "bold", 76, INK, pad=2)
        w = save(im, os.path.join(OUT_IMG, f"t{c}.png"))
        widths[f"t{c}"] = w
    im, w, h = glyph(":", "bold", 60, INK3, pad=2)
    widths["tc"] = save(im, os.path.join(OUT_IMG, "tc.png"))

    # 日期用的小数字（17px）
    for c in "0123456789":
        im, w, h = glyph(c, "medium", 26, INK2, pad=1)
        widths[f"d{c}"] = save(im, os.path.join(OUT_IMG, f"d{c}.png"))

    # 汉字与符号
    for key, txt, size in [
        ("y", "年", 26), ("mo", "月", 26), ("dd", "日", 26), ("wk", "周", 26),
        ("di", "第", 22),
        ("dot", "·", 14),
        ("p_morning", "上午", 26), ("p_afternoon", "下午", 26), ("p_evening", "晚上", 26),
    ]:
        im, w, h = glyph(txt, "medium", size, INK3, pad=1)
        widths[key] = save(im, os.path.join(OUT_IMG, f"{key}.png"))

    # 间隔图元：日期行里把「周三」和「上午」分开（纯黑，看不见但占宽度）
    gap = Image.new("RGB", (6 * S, 26 * S), (0, 0, 0))
    widths["sp"] = save(gap, os.path.join(OUT_IMG, "sp.png"))

    for i, c in enumerate(WEEK_CN, 1):
        im, w, h = glyph(c, "medium", 26, INK2, pad=1)
        widths[f"w{i}"] = save(im, os.path.join(OUT_IMG, f"w{i}.png"))

    # 时间分隔符（日期行用的小斜杠，画在数字之间）
    return widths


def wrap_name(d, name, maxw_px):
    """按宽度贪心折行：先 31px 一行，不行就 26/24 两行，再不行 22/20 三行，最后截断"""
    for size, max_lines in ((34, 1), (29, 2), (26, 2), (24, 3), (22, 3)):
        f = font("bold", size)
        if d.textlength(name, font=f) / S <= maxw_px:
            return [name], size
        lines, cur = [], ""
        for ch in name:
            if d.textlength(cur + ch, font=f) / S <= maxw_px:
                cur += ch
            else:
                if cur:
                    lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
        if len(lines) <= max_lines:
            return lines, size
    f = font("bold", 22)
    lines, cur = [], ""
    for ch in name:
        if d.textlength(cur + ch, font=f) / S <= maxw_px:
            cur += ch
        else:
            lines.append(cur); cur = ch
        if len(lines) == 2:
            break
    rest = name[len("".join(lines)):]
    while rest and d.textlength(rest + "…", font=f) / S > maxw_px:
        rest = rest[:-1]
    lines.append(rest + "…")
    return lines[:3], 20


def card_png(course, highlight, path, color):
    """一节课的整块卡片：左侧色条 + 时间 + 课名（可两行）+ 教室，内容垂直居中"""
    im, d = new(CARD_W, CARD_H)
    fill = CARD_HI if highlight else CARD
    edge = color if highlight else EDGE
    d.rounded_rectangle([0, 0, CARD_W * S - 1, CARD_H * S - 1], radius=13 * S, fill=color)
    d.rounded_rectangle([4 * S, 0, CARD_W * S - 1, CARD_H * S - 1], radius=9 * S,
                        fill=fill, outline=edge, width=S)

    tx = 96
    maxw = CARD_W - tx - 20
    lines, nsize = wrap_name(d, course["name"], maxw)
    lh = nsize + 4                      # 行高
    name_h = len(lines) * lh
    room = course.get("room", "")
    room_h = 22 if room else 0
    block = name_h + room_h
    top = (CARD_H - block) / 2 - 2

    # 时间列：和内容块垂直居中对齐
    d.text((14 * S, (top - 2) * S), course["start"], font=font("bold", 24), fill=INK)
    d.text((14 * S, (top + 34) * S), course["end"], font=font("regular", 15), fill=INK3)

    f = font("bold", nsize)
    for i, ln in enumerate(lines):
        d.text((tx * S, (top + i * lh) * S), ln, font=f, fill=INK)
    if room:
        d.text((tx * S, (top + name_h + 4) * S), room,
               font=font("regular", 17), fill=INK2)

    if highlight:
        cx, cy, r = CARD_W - 20, 20, 5
        d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=color)
    return save(im, path)


def empty_png(label, path):
    im, d = new(CARD_W, 120)
    d.rounded_rectangle([0, 0, CARD_W * S - 1, 119 * S], radius=13 * S, fill=CARD)
    d.text((CARD_W * S // 2, 50 * S), label, font=font("bold", 27), fill=INK2, anchor="mm")
    d.text((CARD_W * S // 2, 88 * S), "好好休息", font=font("regular", 16), fill=INK3, anchor="mm")
    return save(im, path)


def load_timetable():
    cfg = json.load(open(os.path.join(ROOT, "config", "timetable.json"), encoding="utf-8"))
    periods = {p["no"]: p for p in cfg["periods"]}
    m = cfg.get("meta", {})
    start = dt.date.fromisoformat(m.get("semester_start", "2026-09-07"))
    start -= dt.timedelta(days=start.weekday())
    out = []
    for c in cfg["courses"]:
        ps = sorted(c["periods"])
        out.append({
            "name": c["name"], "room": c.get("room", ""),
            "weekday": c["weekday"],
            "start": periods[ps[0]]["start"], "end": periods[ps[-1]]["end"],
            "weeks": c.get("weeks", "1-16"),
        })
    return cfg, out, start


def weeks_lua(expr):
    """'1-16' / '1,3,5' → Lua 表 {1,2,...,16}"""
    nums = []
    for part in str(expr).replace("，", ",").split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            nums += list(range(int(a), int(b) + 1))
        elif part.isdigit():
            nums.append(int(part))
    return "{" + ",".join(str(n) for n in sorted(set(nums))) + "}"


def main():
    os.makedirs(OUT_IMG, exist_ok=True)
    os.makedirs(OUT_LUA, exist_ok=True)

    widths = make_glyphs()

    cfg, courses, semester_monday = load_timetable()

    # 每门课一张普通卡 + 一张高亮卡
    data_rows = []
    for i, c in enumerate(courses):
        color = PALETTE[i % len(PALETTE)]
        normal = f"c{i}.png"
        hi = f"c{i}h.png"
        card_png(c, False, os.path.join(OUT_IMG, normal), color)
        card_png(c, True, os.path.join(OUT_IMG, hi), color)
        sh, sm = map(int, c["start"].split(":"))
        eh, em = map(int, c["end"].split(":"))
        data_rows.append(
            f'  {{ day={c["weekday"]}, from={sh * 60 + sm}, to={eh * 60 + em}, '
            f'normal="{normal}", hi="{hi}", weeks={weeks_lua(c["weeks"])}, '
            f'name="{c["name"]}" }},')

    for key, lab in [("morning", "上午没课"), ("afternoon", "下午没课"), ("evening", "晚上没课")]:
        empty_png(lab, os.path.join(OUT_IMG, f"empty_{key}.png"))

    lua = f'''-- 由 wf/gen_assets.py 自动生成，不要手改
-- 学期第 1 周的周一：{semester_monday}
local M = {{}}
M.SEMESTER_MONDAY = {{ y = {semester_monday.year}, m = {semester_monday.month}, d = {semester_monday.day} }}
-- 时钟区、日期区的坐标（和素材对齐）
M.LAYOUT = {{ clock_y = {CLOCK_Y}, date_y = {DATE_Y}, card1_y = {CARD1_Y}, card2_y = {CARD2_Y},
             card_x = {CARD_X}, card_w = {CARD_W}, card_h = {CARD_H} }}
-- 每个图元的宽度，用来居中排版
M.W = {{
'''
    for k, v in widths.items():
        lua += f'  ["{k}"] = {v},\n'
    lua += "}\n\nM.COURSES = {\n" + "\n".join(data_rows) + "\n}\n\nreturn M\n"
    open(os.path.join(OUT_LUA, "data.lua"), "w", encoding="utf-8").write(lua)

    n_g = len([f for f in os.listdir(OUT_IMG) if re.match(r"^(t|d|y|mo|dd|wk|w\d|dot|p_)", f)])
    n_c = len([f for f in os.listdir(OUT_IMG) if f.endswith(".png")])
    print(f"✓ 图元 {n_g} 个")
    print(f"✓ 课程卡 {n_c} 张（含高亮版）+ 3 张没课图")
    print(f"✓ 数据表 wf/app/lua/data.lua（{len(courses)} 门课）")


if __name__ == "__main__":
    main()
