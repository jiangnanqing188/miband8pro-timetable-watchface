/**
 * facepack.js —— 纯 JS 的 .face 打包器（小米手环 8 Pro / mi8pro）
 * ================================================================
 * 在浏览器和 node 里都能跑，不依赖任何库。
 *
 * 格式来自对 Mi8WfBinTool(Java) 产物的逐字节分析与源码对照：
 *
 *   主头 0xA8
 *   子表盘头 0x58 @0xA8        （各 section 的 count/offset）
 *   定义表         @0x100      （(1+N) × 16 字节）
 *   基础元件记录   16 字节      （全屏 Lua 元件，常量）
 *   预览图        12 字节头 + RLE 负载
 *   JS 资源块 × N 每块 [u24 长度][u8 名长][16 字节 0][名字][原始内容]
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.FacePack = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const MAIN_HEADER = 0xA8;
  const FACE_HEADER = 0x58;
  // 全屏 Lua 元件的 16 字节记录（从可用表盘中原样取得）
  const LUA_ELEMENT = [0, 0, 0, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];

  function w16(b, o, v) { b[o] = v & 255; b[o + 1] = (v >> 8) & 255; }
  function w24(b, o, v) { b[o] = v & 255; b[o + 1] = (v >> 8) & 255; b[o + 2] = (v >> 16) & 255; }
  function w32(b, o, v) {
    b[o] = v & 255; b[o + 1] = (v >> 8) & 255;
    b[o + 2] = (v >> 16) & 255; b[o + 3] = (v >>> 24) & 255;
  }

  /** RLE v1.0：每段 [次数][bpp 字节像素]，次数最大 0x7F */
  function rleFixed(rgba, bpp) {
    const out = [];
    let i = 0;
    const n = rgba.length;
    while (i < n) {
      let count = 1;
      while (count < 0x7F && i + (count + 1) * bpp <= n) {
        let same = true;
        for (let k = 0; k < bpp; k++) {
          if (rgba[i + k] !== rgba[i + count * bpp + k]) { same = false; break; }
        }
        if (!same) break;
        count++;
      }
      out.push(count);
      for (let k = 0; k < bpp; k++) out.push(i + k < n ? rgba[i + k] : 0);
      i += count * bpp;
    }
    return Uint8Array.from(out);
  }

  /** RGBA → BGRA：手环的图像是 BGRA 顺序（Java 侧 c&255 取的是蓝通道） */
  function toBGRA(rgba) {
    const out = new Uint8Array(rgba.length);
    for (let i = 0; i < rgba.length; i += 4) {
      out[i] = rgba[i + 2];      // B
      out[i + 1] = rgba[i + 1];  // G
      out[i + 2] = rgba[i];      // R
      out[i + 3] = rgba[i + 3];  // A
    }
    return out;
  }

  /** 预览图块：12 字节头 + (8 字节 RLE 头 + 负载) */
  function imageBlock(rgba, width, height) {
    const enc = rleFixed(toBGRA(rgba), 4);
    const payload = new Uint8Array(8 + enc.length);
    payload[0] = 0xE0; payload[1] = 0x21; payload[2] = 0xA5; payload[3] = 0x5A;
    w32(payload, 4, ((rgba.length << 4) | 4) >>> 0);   // 原始长度<<4 | bpp（按像素字节数算）
    payload.set(enc, 8);

    const head = new Uint8Array(12);
    head[0] = 0;          // sign：0 = 32bpp RGBA（不透明通道也照写）
    head[1] = 4;          // 4 = 已压缩（mi8pro）
    w16(head, 4, width);
    w16(head, 6, height);
    w32(head, 8, payload.length);

    const out = new Uint8Array(head.length + payload.length);
    out.set(head, 0);
    out.set(payload, head.length);
    return out;
  }

  /** JS 资源块：内容原样打包，名字是 ASCII */
  function jsBlock(name, raw) {
    const nb = [];
    for (let i = 0; i < name.length; i++) nb.push(name.charCodeAt(i) & 0x7F);
    const head = new Uint8Array(0x14 + nb.length);
    w24(head, 0, raw.length);
    head[3] = nb.length;
    head.set(Uint8Array.from(nb), 0x14);
    const out = new Uint8Array(head.length + raw.length);
    out.set(head, 0);
    out.set(raw, head.length);
    return out;
  }

  function utf8Bytes(s) {
    if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(s);
    const out = [];
    for (const ch of unescape(encodeURIComponent(s))) out.push(ch.charCodeAt(0));
    return Uint8Array.from(out);
  }

  /**
   * 打包
   * @param {object} o
   *   o.id      表盘 ID（9 位数字字符串）
   *   o.name    表盘名（UTF-8，≤60 字节）
   *   o.preview { rgba:Uint8Array, width, height }
   *   o.resources [{ name, bytes }]   第 1 个必须是 lua 脚本
   * @returns {Uint8Array}
   */
  function pack(o) {
    const res = o.resources || [];
    if (!res.length) throw new Error('至少要有一个资源（Lua 脚本）');
    const blocks = res.map((r) => jsBlock(r.name, r.bytes));
    const preview = imageBlock(o.preview.rgba, o.preview.width, o.preview.height);

    const defCount = 1 + res.length;
    const defStart = MAIN_HEADER + FACE_HEADER;                 // 0x100
    const propStart = defStart + defCount * 16;                 // 元件记录紧跟定义表
    const previewStart = propStart + 16;
    let p = previewStart + preview.length;

    const offsets = [];
    for (const b of blocks) { offsets.push(p); p += b.length; }
    const total = p;

    const out = new Uint8Array(total);

    // ---- 主头 ----
    out[0] = 0x5A; out[1] = 0xA5; out[2] = 0x34; out[3] = 0x12;
    w32(out, 0x10, 0x800);                    // 设备标志：mi8pro 家族
    w16(out, 0x1C, 1);                        // faceCount
    w16(out, 0x1E, 0);                        // styleCount（EasyFace 单表盘写 0）
    w32(out, 0x20, previewStart);             // previewOffset
    const idb = utf8Bytes(String(o.id || '167200001'));
    out.set(idb.subarray(0, 9), 0x28);
    const nb = utf8Bytes(String(o.name || 'watchface'));
    out.set(nb.subarray(0, 0x3C), 0x68);

    // ---- 子表盘头（0x58：10 组 (count, offset)，实测布局见 re/REPORT.md）----
    const fh = MAIN_HEADER;
    const afterBase = defStart + 16;            // 第一个定义项之后
    w32(out, fh + 0x04, previewStart);          // 子表盘预览偏移
    w32(out, fh + 0x08, 1);                     // 基础元件
    w32(out, fh + 0x0C, defStart);
    for (const off of [0x10, 0x18, 0x20, 0x28]) { // 单图/图组/动画 等（都为空）
      w32(out, fh + off, 0);
      w32(out, fh + off + 4, afterBase);
    }
    w32(out, fh + 0x30, res.length);            // JS 资源
    w32(out, fh + 0x34, afterBase);
    for (const off of [0x38, 0x40, 0x48, 0x50]) { // 控件属性/附加属性/跳转 等（都为空）
      w32(out, fh + off, 0);
      w32(out, fh + off + 4, propStart);
    }

    // ---- 定义表 ----
    let d = defStart;
    out[d + 3] = 0;                            // type 0：基础元件
    w32(out, d + 8, propStart);
    w32(out, d + 12, 16);
    d += 16;

    for (let i = 0; i < res.length; i++) {
      w16(out, d, i);                          // idx
      out[d + 3] = 5;                          // type 5：JS 资源
      w32(out, d + 8, offsets[i]);
      w32(out, d + 12, blocks[i].length);
      d += 16;
    }

    // ---- 元件记录 + 预览 + 资源 ----
    out.set(Uint8Array.from(LUA_ELEMENT), propStart);
    out.set(preview, previewStart);
    blocks.forEach((b, i) => out.set(b, offsets[i]));

    return out;
  }

  return { pack, rleFixed, jsBlock, imageBlock, toBGRA, LUA_ELEMENT };
});
