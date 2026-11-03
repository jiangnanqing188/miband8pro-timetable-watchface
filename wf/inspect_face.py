#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""拆 .face 的结构：主头 + 子表盘头部各 section 的 (count, offset) + 定义表类型统计"""
import struct, sys

TYPES = {0: "基础图元", 2: "单张图片", 3: "图片组", 4: "动画", 5: "JS资源", 7: "控件属性", 8: "附加属性", 9: "跳转属性"}

def u32(b, o): return struct.unpack("<I", b[o:o+4])[0]
def u16(b, o): return struct.unpack("<H", b[o:o+2])[0]

def report(path):
    d = open(path, "rb").read()
    print(f"\n=== {path}  ({len(d)} 字节) ===")
    print(f"  magic      {d[:4].hex()}   device {hex(u32(d,0x10))}   "
          f"faceCount {u16(d,0x1C)}   styleCount {u16(d,0x1E)}")
    print(f"  previewOfs {hex(u32(d,0x20))}   id {d[0x28:0x31].rstrip(b'\\x00').decode(errors='replace')}")
    print(f"  name       {d[0x68:0xa4].split(b'\\x00')[0].decode('utf-8','replace')}")

    # 子表盘头部 0x58：0x08 基础图元, 0x18 单图, 0x20 图组, 0x28 动画, 0x30 JS, 0x40 prop7 ...
    fh = 0xA8
    sec = [("基础图元", 0x08), ("单张图片", 0x18), ("图片组", 0x20),
           ("动画", 0x28), ("JS资源", 0x30), ("控件属性", 0x40),
           ("附加属性8", 0x48), ("跳转属性9", 0x50)]
    print("  子表盘 section (count, offset):")
    for name, off in sec:
        c, o = u32(d, fh + off), u32(d, fh + off + 4)
        if c or o:
            print(f"    {name:<8} count={c:<4} offset={hex(o) if o else 0}")

    # 定义表：16 字节一项，从 0xA8 + 0x58 开始，数量 = 各 section count 之和
    total = sum(u32(d, fh + off) for _, off in sec)
    print(f"  定义表 {total} 项：")
    base = fh + 0x58
    stats = {}
    for i in range(total):
        p = base + i * 16
        if p + 16 > len(d): break
        idx, typ, ofs, ln = u16(d, p), d[p + 3], u32(d, p + 8), u32(d, p + 12)
        stats[typ] = stats.get(typ, 0) + 1
    for t, n in sorted(stats.items()):
        print(f"    type {t} {TYPES.get(t, '?'):<8} × {n}")

for p in sys.argv[1:]:
    report(p)
