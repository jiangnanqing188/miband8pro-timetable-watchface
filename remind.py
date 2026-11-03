#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上课提醒引擎：每节课前 20 分钟开始提醒，连续提醒 1 分钟
=======================================================
在电脑上跑（笔记本上课/自习时最有用）：

    python3 remind.py --dry-run          # 只看今天几点会提醒，不真响
    python3 remind.py                    # 前台常驻，到点就响
    python3 remind.py --test             # 立刻试响一次，确认声音和通知正常
    python3 remind.py --loop             # 同上（默认就是常驻，兼容写法）

提醒长什么样：桌面弹窗（红色紧急提示）+ 双音提示音，每 5 秒一次、持续 60 秒。
手环那边靠日历：python3 export_ics.py 导出的 .ics 里也写了同样的 -20 分钟重复提醒，
手机日历到点响 → 小米运动健康把通知镜像到手环 → 手环震。见 README。
"""

import argparse
import datetime as dt
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import time
import wave

ROOT = os.path.dirname(os.path.abspath(__file__))
WEEK_CN = ["一", "二", "三", "四", "五", "六", "日"]

# 一天三个时段：7 点换上午，12 点换下午，18 点换晚上
PHASES = [("morning", "上午", "07:00"), ("afternoon", "下午", "12:00"),
          ("evening", "晚上", "18:00")]


def phase_now(now=None):
    now = now or dt.datetime.now()
    t = now.hour * 60 + now.minute
    key, lab = "morning", "上午"
    for k, l, start in PHASES:
        h, m = map(int, start.split(":"))
        if t >= h * 60 + m:
            key, lab = k, l
    return key, lab


def regen_phase_image(theme="card"):
    """时段变了就重新出一张当段的图，让 today.png 永远对应「现在」"""
    key, lab = phase_now()
    try:
        subprocess.run([sys.executable, os.path.join(ROOT, "make_watchface.py"),
                        "--today", "--phase", key, "--theme", theme],
                       cwd=ROOT, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=120, check=False)
        return key, lab
    except Exception:
        return key, lab


def dwidth(s):
    """中文按 2 列宽计算，终端表格才对得齐"""
    return sum(2 if ord(ch) > 0x1100 else 1 for ch in str(s))


def pad(s, width):
    s = str(s)
    return s + " " * max(0, width - dwidth(s))


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
    cfg = json.load(open(path, encoding="utf-8"))
    cfg["_periods"] = {p["no"]: p for p in cfg["periods"]}
    for c in cfg["courses"]:
        c["_weeks"] = parse_weeks(c.get("weeks", "1-16"))
        c["_ps"] = sorted(c["periods"])
    return cfg


def week_of(cfg, date):
    start = dt.date.fromisoformat(cfg["meta"].get("semester_start", "2025-09-01"))
    start -= dt.timedelta(days=start.weekday())
    return (date - start).days // 7 + 1


def today_lessons(cfg, date, week=None):
    """返回按开始时间排序的 (datetime, course_dict)"""
    w = week if week is not None else week_of(cfg, date)
    wd = date.isoweekday()
    out = []
    for c in cfg["courses"]:
        if c["weekday"] != wd or w not in c["_weeks"]:
            continue
        p0, p1 = c["_ps"][0], c["_ps"][-1]
        sh, sm = map(int, cfg["_periods"][p0]["start"].split(":"))
        eh, em = map(int, cfg["_periods"][p1]["end"].split(":"))
        out.append({
            "start": dt.datetime.combine(date, dt.time(sh, sm)),
            "end": dt.datetime.combine(date, dt.time(eh, em)),
            "name": c["name"], "room": c.get("room", ""),
            "p0": p0, "p1": p1, "week": w,
        })
    out.sort(key=lambda x: x["start"])
    return out


# ------------------------------------------------------------------ 声音
_BEEP = None


def beep_path():
    global _BEEP
    if _BEEP and os.path.exists(_BEEP):
        return _BEEP
    p = os.path.join(tempfile.gettempdir(), "dsh_kebiao_beep.wav")
    sr = 44100

    def tone(freq, dur, vol=0.45):
        n = int(sr * dur)
        return [int(32767 * vol * math.sin(2 * math.pi * freq * i / sr) * (1 - i / n))
                for i in range(n)]

    data = tone(880, 0.16) + [0] * int(sr * 0.05) + tone(1318, 0.22)
    with wave.open(p, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", s) for s in data))
    _BEEP = p
    return p


def play_sound():
    p = beep_path()
    for cmd in (["paplay", p], ["aplay", "-q", p],
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", p]):
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            continue
    return False


def notify(title, body, urgent=True):
    try:
        subprocess.Popen(
            ["notify-send", "-u", "critical" if urgent else "normal",
             "-a", "课表提醒", "-t", "8000", title, body],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        return False


# ------------------------------------------------------------------ 提醒
def log(msg, logfile=None):
    line = f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    if logfile:
        try:
            with open(logfile, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def alert_session(lesson, lead, duration, logfile=None):
    """连续提醒 duration 秒，每 5 秒一次"""
    mins = max(0, int(round((lesson["start"] - dt.datetime.now()).total_seconds() / 60)))
    title = f"{lesson['name']} 还有 {mins} 分钟"
    body = f"{lesson['start']:%H:%M} 开始"
    if lesson["room"]:
        body += f" · {lesson['room']}"
    log(f"🔔 开始提醒（{duration}s）：{title} / {body}", logfile)

    end = time.time() + duration
    n = 0
    while True:
        play_sound()
        notify(title, body)
        n += 1
        left = end - time.time()
        if left <= 0:
            break
        time.sleep(min(5.0, left))
    log(f"🔔 提醒结束，共响 {n} 次", logfile)


def run(lead=20, duration=60, test=False, dry_run=False, week=None,
        logfile=None, theme="card", no_phase=False, now_fn=dt.datetime.now):
    cfg = load_cfg(os.path.join(ROOT, "config", "timetable.json"))
    today = now_fn().date()
    lessons = today_lessons(cfg, today, week)

    if not lessons:
        print("今天没有课。")
        if not test:
            return

    print(f"今天 周{WEEK_CN[today.isoweekday() - 1]} "
          f"{today:%Y-%m-%d}（第 {lessons[0]['week'] if lessons else week_of(cfg, today)} 周）")
    print(f"{pad('课程', 18)}{pad('上课', 7)}{pad('提醒', 7)}教室")
    for L in lessons:
        fire = L["start"] - dt.timedelta(minutes=lead)
        print(pad(L["name"], 18) + pad(f"{L['start']:%H:%M}", 7)
              + pad(f"{fire:%H:%M}", 7) + L["room"])

    if dry_run:
        print(f"\n（--dry-run：只是列出来，没有响）")
        return

    if test:
        probe = next((L for L in lessons if L["start"] > now_fn()),
                     lessons[0] if lessons else None)
        if not probe:
            probe = {"start": now_fn(), "name": "测试课程", "room": "测试教室", "p0": 1}
        print(f"\n[{now_fn():%H:%M:%S}] 试响 {duration} 秒，Ctrl-C 可中断\n")
        alert_session(probe, lead, duration, logfile)
        return

    if not no_phase:
        key, lab = regen_phase_image(theme)
        notify(f"现在是{lab}", "今天的表盘图已按当前时段重新生成，记得换一下")
        log(f"🕒 当前时段 {lab}，已重新生成 out/today.png", logfile)

    print(f"\n已启动：每节课前 {lead} 分钟提醒，每次持续 {duration} 秒；"
          f"7/12/18 点换时段时提醒换图。Ctrl-C 退出。\n")
    fired = set()
    last_day = today
    last_phase = phase_now()[0] if not no_phase else None
    while True:
        try:
            now = dt.datetime.now()
            if now.date() != last_day:                 # 跨天重算
                last_day = now.date()
                fired.clear()
                lessons = today_lessons(cfg, last_day, week)
                if lessons:
                    print(f"—— 新的一天 {last_day:%m-%d}，{len(lessons)} 节课 ——")
            if not no_phase:
                key, lab = phase_now()
                if key != last_phase:
                    last_phase = key
                    regen_phase_image(theme)
                    notify(f"该换表盘了 · {lab}", f"out/today_{key}.png 已生成")
                    log(f"🕒 进入{lab}，重新生成表盘图并提醒", logfile)

            for L in lessons:
                key = (L["start"].date(), L["name"], L["p0"])
                fire = L["start"] - dt.timedelta(minutes=lead)
                if key in fired:
                    continue
                if fire <= now < fire + dt.timedelta(minutes=2):
                    fired.add(key)
                    alert_session(L, lead, duration, logfile)
            time.sleep(15)
        except KeyboardInterrupt:
            print("\n已退出。")
            return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lead", type=int, default=20, help="提前多少分钟提醒，默认 20")
    ap.add_argument("--duration", type=int, default=60, help="一次提醒持续多少秒，默认 60")
    ap.add_argument("--test", action="store_true", help="立刻试响一次")
    ap.add_argument("--dry-run", action="store_true", help="只打印今天的提醒时间表")
    ap.add_argument("--week", type=int, default=None, help="覆盖教学周（默认按日期推算）")
    ap.add_argument("--loop", action="store_true", help="常驻（默认行为）")
    ap.add_argument("--theme", default="card", help="换时段时重新出图用的主题")
    ap.add_argument("--no-phase", action="store_true",
                    help="不在时段切换时提醒换表盘（只按课提醒）")
    ap.add_argument("--log", default=os.path.join(ROOT, "out", "remind.log"))
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.log), exist_ok=True)
    run(args.lead, args.duration, args.test, args.dry_run, args.week, args.log,
        args.theme, args.no_phase)


if __name__ == "__main__":
    main()
