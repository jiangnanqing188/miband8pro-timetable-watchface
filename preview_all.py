#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把三套界面方案拼成一个对比页 out/index.html，方便一眼挑"""

import os

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")

THEMES = [
    ("card", "卡片", "深色卡片 + 左侧色条，层次最清楚，字最稳"),
    ("line", "极简", "纯黑底 + 细线分隔，没有色块，最省电最像系统原生"),
    ("bar", "时间轴", "一条竖线串起今天的课，圆点是节点，时间顺序感最强"),
]
DAYS = ["周一", "周二", "周三", "周四", "周五"]

CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin:0; padding:44px 32px 64px; background:#07080A; color:#E8EAEE;
       font:15px/1.65 -apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif; }
.wrap { max-width:1240px; margin:0 auto; }
h1 { margin:0 0 6px; font-size:26px; letter-spacing:-.01em; }
.sub { margin:0 0 42px; color:#8A9099; font-size:14px; }
.cols { display:grid; grid-template-columns:repeat(3,1fr); gap:34px; }
.pick { display:flex; align-items:baseline; gap:10px; margin-bottom:4px; }
.pick b { font-size:17px; }
.pick code { color:#5B8CFF; font-size:13px; background:#101317;
             padding:2px 7px; border-radius:5px; }
.pick span { color:#6B717B; font-size:12px; }
.note { margin:0 0 18px; color:#8A9099; font-size:12.5px; min-height:40px; }
.frame { width:100%; border-radius:26px; overflow:hidden; background:#000;
         box-shadow:0 0 0 1px #1E2228, 0 20px 44px -20px #000; }
.frame img { display:block; width:100%; height:auto; }
.thumbs { display:grid; grid-template-columns:repeat(5,1fr); gap:7px; margin-top:14px; }
.thumbs a { display:block; border-radius:7px; overflow:hidden; background:#000;
            box-shadow:0 0 0 1px #171A1F; }
.thumbs img { display:block; width:100%; height:auto; opacity:.86; }
.thumbs a:hover img { opacity:1; }
.cap { color:#5A606B; font-size:11px; margin-top:8px; }
.week { margin-top:56px; display:grid; grid-template-columns:336px 1fr;
        gap:34px; align-items:start; }
.week .frame { width:336px; }
.week h2 { margin:0 0 8px; font-size:18px; }
.week p { margin:0 0 16px; color:#8A9099; font-size:13px; max-width:560px; }
.hr { border:0; border-top:1px solid #15181C; margin:52px 0 0; }
footer { color:#4E545E; font-size:12.5px; margin-top:22px; }
"""


def exists(p):
    return os.path.exists(p)


def rel(p):
    return os.path.relpath(p, OUT)


def build():
    cols = []
    for key, name, note in THEMES:
        d = os.path.join(OUT, f"theme_{key}")
        hero = os.path.join(d, "mock_周三.png")
        if not exists(hero):
            hero = os.path.join(d, "watchface_周三.png")
        thumbs = "".join(
            f'<a href="{rel(os.path.join(d, "watchface_" + day + ".png"))}" '
            f'title="{day}"><img src="{rel(os.path.join(d, "watchface_" + day + ".png"))}" '
            f'alt="{day}"></a>' for day in DAYS
            if exists(os.path.join(d, "watchface_" + day + ".png")))
        cols.append(f'''
    <div>
      <div class="pick"><b>{name}</b><code>--theme {key}</code></div>
      <p class="note">{note}</p>
      <div class="frame"><img src="{rel(hero)}" alt="{name}"></div>
      <p class="cap">↑ 模拟手环把时间叠上去的效果</p>
      <div class="thumbs">{thumbs}</div>
      <p class="cap">周一到周五的详情图（点开看原图）</p>
    </div>''')

    weekdir = os.path.join(OUT, "theme_card")
    week_png = os.path.join(weekdir, "watchface_week.png")
    week_block = ""
    if exists(week_png):
        week_block = f'''
  <hr class="hr">
  <div class="week">
    <div>
      <div class="frame"><img src="{rel(week_png)}" alt="一周总览"></div>
      <p class="cap">一周总览</p>
    </div>
    <div>
      <h2>一周总览：不用每天换图</h2>
      <p>上面三套都是「一天一张」，课多的时候看得最清楚，但每天得手动换一次表盘。
         如果你懒得每天换，用这张总览图：一周五天全在上面，装上就不用管了。</p>
      <p>两张配合用最舒服：把总览设成主表盘，哪天课特别满就把当天那张换上看一眼。</p>
    </div>
  </div>'''

    html = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>课表表盘 · 三套界面方案</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{CSS}</style></head><body><div class="wrap">
  <h1>课表表盘 · 挑一套</h1>
  <p class="sub">336 × 480 · 只有时间、日期、课表三样东西 · 顶部空白是留给手环自己画时钟的位置</p>
  <div class="cols">{''.join(cols)}</div>
  {week_block}
  <footer>选好告诉我主题名（card / line / bar），我把 out/theme_&lt;名字&gt;/ 里的图整理成可直接上传的一套。</footer>
</div></body></html>'''

    p = os.path.join(OUT, "index.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)
    return p


if __name__ == "__main__":
    print("✓", build())
