#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""标定页：把不同时钟留白高度的样张拼成一页，装上手环试哪个刚好"""

import os

TMPL = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>时钟留白标定</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
 :root{color-scheme:dark}
 *{box-sizing:border-box}
 body{margin:0;padding:40px 28px;background:#08090A;color:#E8EAEE;
      font:15px/1.65 -apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif}
 h1{margin:0 0 6px;font-size:23px}
 .sub{margin:0 0 10px;color:#8B9099;font-size:13.5px}
 ol{margin:0 0 34px;padding-left:20px;color:#8B9099;font-size:13px;max-width:760px}
 ol b{color:#C8CDD6;font-weight:600}
 .row{display:flex;gap:22px;flex-wrap:wrap}
 figure{margin:0;width:224px}
 .f{border-radius:20px;overflow:hidden;background:#000;
    box-shadow:0 0 0 1px #1E2228,0 14px 30px -16px #000}
 .f img{display:block;width:100%;height:auto}
 figcaption{margin-top:9px;font-size:12.5px;color:#8B9099;font-variant-numeric:tabular-nums}
 figcaption b{color:#5B8CFF;font-weight:600}
 code{background:#101317;padding:1px 5px;border-radius:4px;color:#9AA0AA;font-size:12px}
</style></head><body>
<h1>时钟留白标定</h1>
<p class="sub">__DATE__ 周__WD__ · 第 __WEEK__ 周 · 框住的范围就是留给手环画时间的区域</p>
<ol>
 <li>把这 <b>5 张</b>图按顺序都传到手机（一次装上比较省事）</li>
 <li>在小米运动健康里换成「相册表盘」，逐张试</li>
 <li>看哪个 <b>灰框刚好把系统时间框住</b>（不压到日期、也没有大片空白），记下那个像素值</li>
 <li>回来用 <code>python3 make_watchface.py --today --clock-h 那个值</code> 重新出图</li>
</ol>
<div class="row">__CARDS__</div>
</body></html>"""


def build(caldir, cands, day, week):
    wd = "一二三四五六日"[day.isoweekday() - 1]
    cards = []
    for h in cands:
        f = os.path.join(caldir, f"clock_{h}.png")
        if not os.path.exists(f):
            continue
        cards.append(
            f'<figure><div class="f"><img src="clock_{h}.png" alt="{h}px"></div>'
            f'<figcaption>留白 <b>{h}px</b> · <code>--clock-h {h}</code></figcaption></figure>')
    html = (TMPL.replace("__DATE__", f"{day.year}年{day.month}月{day.day}日")
            .replace("__WD__", wd).replace("__WEEK__", str(week))
            .replace("__CARDS__", "\n".join(cards)))
    p = os.path.join(caldir, "index.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)
    return p


PHASE_TMPL = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>三个时段</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
 :root{color-scheme:dark}
 *{box-sizing:border-box}
 body{margin:0;padding:40px 28px;background:#08090A;color:#E8EAEE;
      font:15px/1.65 -apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif}
 h1{margin:0 0 6px;font-size:23px}
 .sub{margin:0 0 8px;color:#8B9099;font-size:13.5px}
 table{border-collapse:collapse;margin:0 0 30px;font-size:13px;color:#8B9099}
 td{padding:3px 18px 3px 0}
 td.k{color:#C8CDD6}
 .row{display:flex;gap:24px;flex-wrap:wrap}
 figure{margin:0;width:240px}
 .f{border-radius:20px;overflow:hidden;background:#000;
    box-shadow:0 0 0 1px #1E2228,0 14px 30px -16px #000}
 .f img{display:block;width:100%;height:auto}
 figcaption{margin-top:9px;font-size:12.5px;color:#8B9099}
 figcaption b{color:#5B8CFF;font-weight:600}
 code{background:#101317;padding:1px 5px;border-radius:4px;color:#9AA0AA;font-size:11.5px}
</style></head><body>
<h1>三个时段各一张</h1>
<p class="sub">__DATE__ 周__WD__ · 第 __WEEK__ 周 · 主题 __THEME__</p>
<table>
 <tr><td class="k">上午</td><td>07:00 – 12:00</td><td><code>today_morning.png</code></td></tr>
 <tr><td class="k">下午</td><td>12:00 – 18:00</td><td><code>today_afternoon.png</code></td></tr>
 <tr><td class="k">晚上</td><td>18:00 – 23:59</td><td><code>today_evening.png</code></td></tr>
</table>
<div class="row">__CARDS__</div>
<p class="sub" style="margin-top:26px">
 想让图自己跟着时间换：<code>*/30 6-23 * * * cd ~/桌面/小米手环表盘 &amp;&amp; python3 make_watchface.py --today --auto-phase</code>
</p>
</body></html>"""


def build_phases(outdir, day, week, theme):
    wd = "一二三四五六日"[day.isoweekday() - 1]
    cards = []
    for key, lab, a, b in [("morning", "上午", "07:00", "12:00"),
                           ("afternoon", "下午", "12:00", "18:00"),
                           ("evening", "晚上", "18:00", "23:59")]:
        f = os.path.join(outdir, f"today_{key}.png")
        if not os.path.exists(f):
            continue
        cards.append(f'<figure><div class="f"><img src="today_{key}.png" alt="{lab}"></div>'
                     f'<figcaption><b>{lab}</b> · {a}–{b} &nbsp;'
                     f'<code>--phase {key}</code></figcaption></figure>')
    html = (PHASE_TMPL.replace("__DATE__", f"{day.year}年{day.month}月{day.day}日")
            .replace("__WD__", wd).replace("__WEEK__", str(week))
            .replace("__THEME__", theme).replace("__CARDS__", "\n".join(cards)))
    p = os.path.join(outdir, "phases.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)
    return p
