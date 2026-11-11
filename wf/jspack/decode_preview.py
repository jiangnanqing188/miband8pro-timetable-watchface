#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 .face 里解出预览图（验证 App 画的东西对不对）
   python3 wf/jspack/decode_preview.py out/kebiao-app.face out/_preview.png
"""
import struct, sys
from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
d = open(src, "rb").read()
u32 = lambda o: struct.unpack("<I", d[o:o+4])[0]
u16 = lambda o: struct.unpack("<H", d[o:o+2])[0]

pv = u32(0x20)                     # previewOffset
sign, flag = d[pv], d[pv+1]
w, h, blen = u16(pv+4), u16(pv+6), u32(pv+8)
p = pv + 12
assert d[p:p+4] == bytes([0xE0,0x21,0xA5,0x5A]), "不是 RLE 块"
info = u32(p+4)
bpp, rawlen = info & 15, info >> 4
assert bpp == 4, f"预期 4 字节/像素，实际 {bpp}"

enc = d[p+8:p+8+(blen-8)]
out = bytearray()
i = 0
while i < len(enc) and len(out) < rawlen:
    cnt = enc[i]; i += 1
    px = enc[i:i+4]; i += 4
    out += px * cnt
out = out[:rawlen]

# 手环是 BGRA，转回 RGBA
rgba = bytearray(len(out))
for k in range(0, len(out), 4):
    rgba[k]   = out[k+2]
    rgba[k+1] = out[k+1]
    rgba[k+2] = out[k]
    rgba[k+3] = out[k+3]

im = Image.frombytes("RGBA", (w, h), bytes(rgba)).convert("RGB")
im.save(dst)
print(f"✓ 预览 {w}×{h}，原始 {rawlen//1024}KB → RLE {len(enc)//1024}KB  → {dst}")
