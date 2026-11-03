#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ICS 导入的真实场景测试（python3 tests/ics_test.py）

课简/日历导出的 .ics 有好几种写法，这里全部造一遍看解析对不对。
每个用例都断言到具体周次，不靠"看着差不多"。
"""

import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

HEAD = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//CN
CALSCALE:GREGORIAN
BEGIN:VTIMEZONE
TZID:Asia/Shanghai
BEGIN:STANDARD
DTSTART:19700101T000000
TZOFFSETFROM:+0800
TZOFFSETTO:+0800
END:STANDARD
END:VTIMEZONE
"""
TAIL = "END:VCALENDAR\r\n"


def ics(*events):
    return HEAD + "".join(events) + TAIL


def ev(summary, start, end, rrule=None, exdate=None, loc=None):
    body = [f"BEGIN:VEVENT", "UID:x@t", "DTSTAMP:20261103T000000Z",
            f"SUMMARY:{summary}", f"DTSTART:{start}", f"DTEND:{end}"]
    if loc:
        body.append(f"LOCATION:{loc}")
    if rrule:
        body.append(f"RRULE:{rrule}")
    if exdate:
        body.append(f"EXDATE:{exdate}")
    body.append("END:VEVENT")
    return "\r\n".join(body) + "\r\n"


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("标准写法：TZID + COUNT=16")
def _():
    txt = ics(ev("高等数学 A（教三-201）", "20260907T080000", "20260907T094000",
                 "FREQ=WEEKLY;COUNT=16"))
    return txt, [{"name": "高等数学 A", "room": "教三-201", "weekday": 1,
                  "periods": [1, 2], "weeks": "1-16"}]


@case("UTC 时间（Z 结尾）要换算成 +8")
def _():
    # 00:00 UTC = 08:00 北京时间 → 第 1 节
    txt = ics(ev("数据结构（计科楼 402）", "20260907T000000Z", "20260907T014000Z",
                 "FREQ=WEEKLY;COUNT=16"))
    return txt, [{"name": "数据结构", "room": "计科楼 402", "weekday": 1,
                  "periods": [1, 2], "weeks": "1-16"}]


@case("单双周：INTERVAL=2 → 第 1,3,5.. 周")
def _():
    txt = ics(ev("体育（体育馆）", "20260908T160000", "20260908T174000",
                 "FREQ=WEEKLY;INTERVAL=2;COUNT=8"))
    return txt, [{"name": "体育", "room": "体育馆", "weekday": 2,
                  "periods": [7, 8], "weeks": "1,3,5,7,9,11,13,15"}]


@case("逐次导出：16 个独立 VEVENT 要合并成一门课")
def _():
    import datetime as dt
    evs = []
    for i in range(16):
        d = dt.date(2026, 9, 7) + dt.timedelta(weeks=i)
        ds = d.strftime("%Y%m%d")
        evs.append(ev("线性代数", f"{ds}T100000", f"{ds}T114000"))
    return ics(*evs), [{"name": "线性代数", "weekday": 1, "periods": [3, 4],
                        "weeks": "1-16"}]


@case("EXDATE 停课：第 2 周要扣掉")
def _():
    txt = ics(ev("操作系统（计科楼 301）", "20260909T080000", "20260909T094000",
                 "FREQ=WEEKLY;COUNT=4", exdate="20260916T080000"))
    return txt, [{"name": "操作系统", "room": "计科楼 301", "weekday": 3,
                  "periods": [1, 2], "weeks": "1,3-4"}]


@case("UNTIL 截止：到第 8 周为止")
def _():
    txt = ics(ev("大学物理（理科楼 501）", "20260910T140000", "20260910T154000",
                 "FREQ=WEEKLY;UNTIL=20261029T000000Z"))
    return txt, [{"name": "大学物理", "room": "理科楼 501", "weekday": 4,
                  "periods": [5, 6], "weeks": "1-8"}]


@case("LOCATION 有值，SUMMARY 也带括号 → 用 LOCATION")
def _():
    txt = ics(ev("语文（A）", "20260911T080000", "20260911T094000", loc="计科楼 405"))
    return txt, [{"name": "语文", "room": "计科楼 405", "weekday": 5,
                  "periods": [1, 2], "weeks": "1"}]


@case("折行 + 转义字符")
def _():
    txt = ics("BEGIN:VEVENT\r\nUID:y@t\r\nDTSTAMP:20261103T000000Z\r\n"
              "SUMMARY:计算机网络（计科楼 502）\r\nDTSTART:20260907T0800"
              "00\r\nDTEND:20260907T094000\r\nEND:VEVENT\r\n")
    return txt, [{"name": "计算机网络", "room": "计科楼 502", "weekday": 1,
                  "periods": [1, 2], "weeks": "1"}]


def main():
    from import_kebiao import read_ics, DEFAULT_PERIODS
    import datetime as dt

    periods = DEFAULT_PERIODS
    monday1 = dt.date(2026, 9, 7)
    passed = failed = 0
    tmp = tempfile.mkdtemp()
    for name, fn in CASES:
        txt, want = fn()
        path = os.path.join(tmp, "t.ics")
        open(path, "w", encoding="utf-8").write(txt)
        try:
            got = read_ics(path, periods, monday1)
        except SystemExit as e:
            print(f"  ✗ {name}\n     解析失败：{e}")
            failed += 1
            continue
        got_n = [{k: c.get(k) for k in ("name", "room", "weekday", "periods", "weeks")}
                 for c in got]
        for g in got_n:
            if g["room"] is None:
                g.pop("room")
        if got_n == want:
            print(f"  ✓ {name}")
            passed += 1
        else:
            print(f"  ✗ {name}\n     得到 {got_n}\n     期望 {want}")
            failed += 1

    print(f"\n{passed} 通过 / {failed} 失败")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
