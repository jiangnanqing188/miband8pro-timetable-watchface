#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课表导入器：把课简 / 时光课表 / 教务系统 / 手写表格 变成 config/timetable.json
=============================================================================
支持格式（自动识别，不用告诉我是哪种）：

    python3 import_kebiao.py 我的课表.csv
    python3 import_kebiao.py 课简导出.json
    python3 import_kebiao.py 教务系统.xlsx
    python3 import_kebiao.py 课表.txt

识别逻辑：先看文件后缀，再猜内容。列名能认这些写法：
    课程  课程名  课程名称  course  name  名称
    星期  周几  weekday  day
    节次  节  上课节次  period  periods
    周次  周  上课周  weeks
    教室  地点  上课地点  room  location
    老师  教师  teacher
"""

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(ROOT, "config", "timetable.json")

WEEKDAY_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 7,
}

KEYS = {
    "name":  ["课程名称", "课程名", "课程", "name", "course", "科目", "名称", "title"],
    "weekday": ["星期", "周几", "weekday", "day", "上课星期", "日期"],
    "periods": ["节次", "上课节次", "节", "period", "periods", "时段", "节数"],
    "weeks": ["周次", "上课周", "周数", "weeks", "week", "起止周"],
    "room":  ["教室", "地点", "上课地点", "room", "location", "课室"],
    "teacher": ["老师", "教师", "任课教师", "teacher", "授课教师"],
}


DEFAULT_PERIODS = [
    {"no": i + 1, "start": s, "end": e} for i, (s, e) in enumerate([
        ("08:00", "08:45"), ("08:55", "09:40"), ("10:00", "10:45"),
        ("10:55", "11:40"), ("14:00", "14:45"), ("14:55", "15:40"),
        ("16:00", "16:45"), ("16:55", "17:40"), ("19:00", "19:45"),
        ("19:55", "20:40"), ("20:50", "21:35"), ("21:45", "22:30")])
]


# ------------------------------------------------------------------ 解析小工具
def parse_weekday(v):
    s = str(v).strip().lower()
    s = s.replace("星期", "").replace("周", "").replace("礼拜", "").strip()
    if s in WEEKDAY_MAP:
        return WEEKDAY_MAP[s]
    for k, w in WEEKDAY_MAP.items():
        if s.startswith(k):
            return w
    raise ValueError(f"认不出星期：{v!r}")


def parse_periods(v):
    """'1-2' / '第1-2节' / '1,2' / '3' / '1-2节' / 2 → [int]"""
    if isinstance(v, (list, tuple)):
        out = []
        for x in v:
            out += parse_periods(x)
        return sorted(set(out))
    if isinstance(v, int):
        return [v]
    s = str(v)
    s = re.sub(r"[第节\s（）()]", "", s)
    s = s.replace("－", "-").replace("—", "-").replace("~", "-").replace("至", "-")
    out = []
    for part in re.split(r"[,，、;；]", s):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\d+)\s*-\s*(\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                a, b = b, a
            out += list(range(a, b + 1))
        elif re.match(r"^\d+$", part):
            out.append(int(part))
    if not out:
        raise ValueError(f"认不出节次：{v!r}")
    return sorted(set(out))


def parse_weeks(v):
    if isinstance(v, list):
        return sorted({int(x) for x in v})
    s = str(v)
    s = re.sub(r"[第周\s]", "", s)
    s = s.replace("－", "-").replace("—", "-").replace("~", "-").replace("至", "-")
    out = []
    for part in re.split(r"[,，、;；]", s):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\d+)-(\d+)$", part)
        if m:
            out += list(range(int(m.group(1)), int(m.group(2)) + 1))
        elif part.isdigit():
            out.append(int(part))
    return sorted(set(out)) or [1]


def compact_ranges(nums):
    """[1,2,3,5] → '1-3,5'"""
    if not nums:
        return "1-16"
    nums = sorted(set(nums))
    segs, s, p = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == p + 1:
            p = n
            continue
        segs.append((s, p))
        s = p = n
    segs.append((s, p))
    return ",".join(f"{a}-{b}" if b > a else str(a) for a, b in segs)


def pick(row, field):
    """在字典里按同义词找字段值"""
    low = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
    for alias in KEYS[field]:
        if alias.lower() in low and str(low[alias.lower()]).strip():
            return low[alias.lower()]
    for k, v in low.items():
        for alias in KEYS[field]:
            if alias.lower() in k and str(v).strip():
                return v
    return None


def norm_course(row, idx):
    name = pick(row, "name")
    if not name or not str(name).strip():
        return None
    c = {"name": str(name).strip()}
    wd = pick(row, "weekday")
    ps = pick(row, "periods")
    if wd is None or ps is None:
        raise ValueError(f"第 {idx} 条缺星期或节次：{row}")
    c["weekday"] = parse_weekday(wd)
    c["periods"] = parse_periods(ps)
    wk = pick(row, "weeks")
    c["weeks"] = compact_ranges(parse_weeks(wk)) if wk not in (None, "") else "1-16"
    room = pick(row, "room")
    if room:
        c["room"] = str(room).strip()
    tch = pick(row, "teacher")
    if tch:
        c["teacher"] = str(tch).strip()
    return c


# ------------------------------------------------------------------ 各格式读取
def read_csv(path):
    import csv
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        return [dict(r) for r in csv.DictReader(f, dialect=dialect)]


def read_xlsx(path):
    try:
        import openpyxl
    except ImportError:
        sys.exit("需要 openpyxl：pip install openpyxl")
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    head = [str(h).strip() if h is not None else "" for h in rows[0]]
    return [dict(zip(head, r)) for r in rows[1:] if any(v is not None for v in r)]


def read_json(path):
    d = json.load(open(path, encoding="utf-8"))
    if isinstance(d, dict):
        for key in ("courses", "课程", "list", "data", "lessons", "课表"):
            if key in d and isinstance(d[key], list):
                return d[key]
        return [d]
    return d


TXT_PAT = re.compile(
    r"(?:周|星期|礼拜)(?P<wd>[一二三四五六日天])"
    r".*?(?:第(?P<p1>\d+)\s*[-~至]\s*(?P<p2>\d+)节|第(?P<p>\d+)节)"
    r".*?(?P<name>[^\s，,、|]+)"
    r"(?:\s+(?P<room>[^\s，,、|]+))?"
)


def read_txt(path):
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        m = TXT_PAT.search(line)
        if not m:
            continue
        row = {
            "课程": m.group("name"),
            "星期": m.group("wd"),
            "节次": (f"{m.group('p1')}-{m.group('p2')}" if m.group("p1")
                     else m.group("p")),
        }
        if m.group("room"):
            row["教室"] = m.group("room")
        wk = re.search(r"(?:第)?(\d+)\s*[-~至]\s*(\d+)\s*周", line)
        if wk:
            row["周次"] = f"{wk.group(1)}-{wk.group(2)}"
        out.append(row)
    return out


def read_ics(path, periods=None, monday1=None):
    """读 .ics —— 兼容课简 / 苹果日历 / Google 日历 的真实导出

    处理这些真实情况：
      · DTSTART;TZID=Asia/Shanghai:...  和  DTSTART:...Z（UTC，会换算成 +8）
      · RRULE:FREQ=WEEKLY;COUNT=16  /  UNTIL=...  /  INTERVAL=2（单双周！）
      · 没有 RRULE、一节课一个 VEVENT（逐次导出），自动合并成"1-16 周"
      · EXDATE（停课）会从周次里扣掉
      · SUMMARY 里带教室 （教三-201）会拆出来
    """
    import datetime as _dt
    try:
        from zoneinfo import ZoneInfo
        LOCAL_TZ = ZoneInfo("Asia/Shanghai")
    except Exception:
        LOCAL_TZ = None

    raw = open(path, encoding="utf-8-sig", errors="replace").read()
    lines = []
    for ln in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if ln[:1] in (" ", "\t") and lines:      # RFC5545 折行
            lines[-1] += ln[1:]
        else:
            lines.append(ln)

    events, cur, depth = [], None, 0
    for ln in lines:
        u = ln.strip().upper()
        if u == "BEGIN:VEVENT":
            cur, depth = {"_raw": {}}, 1
            continue
        if cur is None:
            continue
        if u.startswith("BEGIN:"):
            depth += 1
            continue
        if u.startswith("END:"):
            depth -= 1
            if u == "END:VEVENT":
                events.append(cur)
                cur = None
            continue
        if depth > 1 or ":" not in ln:
            continue
        key, val = ln.split(":", 1)
        cur["_raw"].setdefault(key.strip().upper(), val)   # 保留 TZID 等参数
        cur[key.split(";")[0].strip().upper()] = val

    def unescape(x):
        return (x or "").replace("\\n", " ").replace("\\,", ",") \
                      .replace("\\;", ";").replace("\\\\", "\\")

    def prop(ev, name):
        for k, v in ev["_raw"].items():
            if k == name or k.startswith(name + ";"):
                return k, v
        return None, None

    def parse_dt(key, val):
        v = (val or "").strip()
        m = re.match(r"^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2})?)?", v)
        if not m:
            return None
        naive = _dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                             int(m.group(4) or 0), int(m.group(5) or 0))
        if v.endswith("Z"):                        # UTC → 本地（默认 +8）
            try:
                if LOCAL_TZ:
                    return naive.replace(tzinfo=_dt.timezone.utc) \
                                 .astimezone(LOCAL_TZ).replace(tzinfo=None)
            except Exception:
                pass
            return naive + _dt.timedelta(hours=8)
        return naive                               # 带 TZID 或浮动时间 → 按墙上时间用

    def expand(st, rrule, exdates, cap=400):
        out = [st]
        if rrule:
            prm = dict(kv.split("=", 1) for kv in rrule.split(";") if "=" in kv)
            interval = max(1, int(prm.get("INTERVAL", 1) or 1))
            count = int(prm["COUNT"]) if prm.get("COUNT", "").isdigit() else None
            until = None
            um = re.match(r"^(\d{4})(\d{2})(\d{2})", prm.get("UNTIL", ""))
            if um:
                until = _dt.date(int(um.group(1)), int(um.group(2)), int(um.group(3)))
            cur_dt, n = st, 1
            while len(out) < cap:
                if count is not None and n >= count:
                    break
                cur_dt = cur_dt + _dt.timedelta(days=7 * interval)
                if until and cur_dt.date() > until:
                    break
                out.append(cur_dt)
                n += 1
        return [x for x in out if x.date() not in exdates]

    # ---- 展开成"具体哪一天有这门课" ----
    groups, skipped = {}, 0
    for ev in events:
        sumv = unescape(ev.get("SUMMARY", "")).strip()
        if not sumv:
            continue
        room = unescape(ev.get("LOCATION", "")).strip()
        name, m = sumv, re.match(r"^(.+?)[（(]([^）)]+)[）)]\s*$", sumv)
        if m:
            name = m.group(1).strip()
            if not room:
                room = m.group(2).strip()

        k0, v0 = prop(ev, "DTSTART")
        st = parse_dt(k0, v0)
        if not st:
            skipped += 1
            continue
        k1, v1 = prop(ev, "DTEND")
        en = parse_dt(k1, v1)

        exd = set()
        for k, v in ev["_raw"].items():
            if k.startswith("EXDATE"):
                for part in v.split(","):
                    d = parse_dt(k, part)
                    if d:
                        exd.add(d.date())

        occ = expand(st, (ev.get("RRULE") or "").upper(), exd)
        if not occ:
            continue
        key = (name, room, st.isoweekday(), st.hour, st.minute,
               en.hour if en else None, en.minute if en else None)
        groups.setdefault(key, set()).update(o.date() for o in occ)

    if not groups:
        sys.exit("这个 .ics 里没找到课程事件")

    # ---- 日期 → 教学周 ----
    import datetime as _dt2
    earliest = min(min(v) for v in groups.values())
    if monday1 is None:
        monday1 = earliest - _dt2.timedelta(days=earliest.weekday())
        print(f"⚠️  没读到学期起始日，按 {monday1} 当作第 1 周周一"
              f"（不对就改 config 里的 meta.semester_start）")

    # ---- 时间 → 节次 ----
    periods = periods or DEFAULT_PERIODS
    def mins(t):
        h, mm = t.split(":")
        return int(h) * 60 + int(mm)
    starts = [(mins(p["start"]), p["no"]) for p in periods]
    ends = [(mins(p["end"]), p["no"]) for p in periods]

    def nearest(table, minute, tol=30):
        if minute is None:
            return None
        d, no = min(((abs(minute - m), no) for m, no in table), key=lambda x: x[0])
        return no if d <= tol else None

    out, bad = [], 0
    for (name, room, wd, sh, sm, eh, em), dates in groups.items():
        weeks = sorted({(d - monday1).days // 7 + 1 for d in dates})
        p0 = nearest(starts, sh * 60 + sm)
        p1 = nearest(ends, (eh * 60 + em) if eh is not None else (sh * 60 + sm + 45))
        if p0 is None:
            print(f"  ⚠️  「{name}」{sh:02d}:{sm:02d} 对不上作息表，跳过（改 periods 后重试）")
            bad += 1
            continue
        p1 = max(p0, p1 or p0)
        c = {"name": name, "weekday": wd,
             "periods": list(range(p0, p1 + 1)),
             "weeks": compact_ranges(weeks)}
        if room:
            c["room"] = room
        out.append(c)

    # 同名同天同节次的合并（逐次导出会产生重复）
    merged = {}
    for c in out:
        k = (c["name"], c["weekday"], tuple(c["periods"]))
        if k in merged:
            w = set()
            for src in (merged[k]["weeks"], c["weeks"]):
                for part in src.replace("，", ",").split(","):
                    if "-" in part:
                        a, b = part.split("-")
                        w |= set(range(int(a), int(b) + 1))
                    elif part.strip().isdigit():
                        w.add(int(part))
            merged[k]["weeks"] = compact_ranges(sorted(w))
        else:
            merged[k] = dict(c)
    print(f"从 .ics 解出 {len(merged)} 门课" + (f"（{bad} 条时间对不上）" if bad else ""))
    return list(merged.values())


def read_any(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".csv", ".tsv"):
        return read_csv(path)
    if ext in (".xlsx", ".xlsm"):
        return read_xlsx(path)
    if ext == ".json":
        return read_json(path)
    if ext == ".ics":
        return read_ics(path)
    if ext in (".txt", ".md"):
        return read_txt(path)
    for fn in (read_json, read_csv, read_xlsx, read_txt):
        try:
            rows = fn(path)
            if rows:
                return rows
        except Exception:
            continue
    sys.exit(f"认不出文件格式：{path}")


# ------------------------------------------------------------------ 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="课简导出的 json / 教务系统 csv、xlsx / 手写 txt")
    ap.add_argument("--config", default=CFG)
    ap.add_argument("--semester-start", default=None, help="开学第一周的周一，如 2026-09-07")
    ap.add_argument("--current-week", type=int, default=None)
    ap.add_argument("--out", default=CFG, help="输出到哪（默认覆盖 config/timetable.json）")
    args = ap.parse_args()

    base_early = json.load(open(args.config, encoding="utf-8")) if os.path.exists(args.config) else {}
    _periods = base_early.get("periods") or DEFAULT_PERIODS
    _monday = None
    _ss = (base_early.get("meta") or {}).get("semester_start")
    if _ss:
        import datetime as _dt
        _monday = _dt.date.fromisoformat(_ss)
        _monday -= _dt.timedelta(days=_monday.weekday())

    if args.source.lower().endswith(".ics"):
        rows = read_ics(args.source, _periods, _monday)
    else:
        rows = read_any(args.source)
        print(f"读入 {len(rows)} 行")

    courses, bad = [], 0
    for i, r in enumerate(rows, 1):
        try:
            c = r if r.get("_ready") or ("weekday" in r and "periods" in r
                                         and isinstance(r.get("periods"), list)) \
                else norm_course(r, i)
            if c:
                courses.append(c)
        except ValueError as e:
            bad += 1
            print(f"  ⚠️  跳过第 {i} 行：{e}")

    if not courses:
        sys.exit("一条都没解析出来，看看列名是不是太特殊了")

    # 保留原来的作息时间表
    base = json.load(open(args.config, encoding="utf-8")) if os.path.exists(args.config) else {}
    periods = base.get("periods") or [
        {"no": i + 1, "start": s, "end": e} for i, (s, e) in enumerate([
            ("08:00", "08:45"), ("08:55", "09:40"), ("10:00", "10:45"),
            ("10:55", "11:40"), ("14:00", "14:45"), ("14:55", "15:40"),
            ("16:00", "16:45"), ("16:55", "17:40"), ("19:00", "19:45"),
            ("19:55", "20:40"), ("20:50", "21:35"), ("21:45", "22:30")])
    ]
    meta = dict(base.get("meta") or {})
    meta["sample_data"] = False
    if args.semester_start:
        meta["semester_start"] = args.semester_start
    if args.current_week:
        meta["current_week"] = args.current_week

    cfg = {"_说明": "由 import_kebiao.py 生成，可继续手改", "meta": meta,
           "periods": periods, "courses": courses}

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    used = sorted({c["weekday"] for c in courses})
    print(f"\n✓ 导入 {len(courses)} 门课" + (f"（跳过 {bad} 行）" if bad else ""))
    print(f"  上课日：{'、'.join('周' + '一二三四五六日'[d - 1] for d in used)}")
    print(f"  写入：{args.out}")
    print(f"\n下一步：python3 make_watchface.py --preview && python3 export_ics.py")


if __name__ == "__main__":
    main()
