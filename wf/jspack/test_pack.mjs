// 用 JS 打包器复刻 Java 产物，逐字节比对（node wf/jspack/test_pack.mjs）
// 这是整个手机 App 方案的地基：JS 打出来的包必须和 Java 打的一模一样。
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execFileSync } from 'child_process';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);
const FacePack = require('./facepack.js');

const wf = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const root = path.resolve(wf, '..');

// 用 python 把 PNG 解成 RGBA（node 没有内置解码器）
function pngToRGBA(file) {
  const out = execFileSync('python3', ['-c', `
import sys, json
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGBA")
sys.stdout.write(json.dumps({"w": im.width, "h": im.height,
                             "px": list(im.tobytes())}))
`, file], { maxBuffer: 1 << 28 });
  const o = JSON.parse(out.toString());
  return { width: o.w, height: o.h, rgba: Uint8Array.from(o.px) };
}

const srcDir = path.join(wf, 'build/face/app/lua');
const pngs = fs.readdirSync(srcDir).filter((f) => f.endsWith('.png')).sort();
const lua = fs.readFileSync(path.join(srcDir, 'main.lua'));
const preview = pngToRGBA(path.join(wf, 'preview_morning.png'));

// 顺序必须和 build.sh 一致：main.lua 打头，然后 PNG 按名字排序
const resources = [
  { name: 'lua/main.lua', bytes: new Uint8Array(lua) },
  ...pngs.map((f) => ({ name: 'lua/' + f, bytes: new Uint8Array(fs.readFileSync(path.join(srcDir, f))) })),
];

console.log(`资源 ${resources.length} 个（1 个 lua + ${pngs.length} 张图）`);
console.log(`预览 ${preview.width}×${preview.height}`);

const t0 = Date.now();
const mine = FacePack.pack({ id: '167200916', name: '课表', preview, resources });
console.log(`JS 打包完成，${(mine.length / 1024).toFixed(0)} KB，耗时 ${Date.now() - t0} ms`);

const ref = fs.readFileSync(path.join(root, 'out/kebiao.face'));
const a = Buffer.from(mine);
console.log(`Java 产物 ${(ref.length / 1024).toFixed(0)} KB`);

let pass = 0, fail = 0;
const ok = (name, cond, extra) => {
  if (cond) { pass++; console.log('  ✓', name); }
  else { fail++; console.log('  ✗', name, extra === undefined ? '' : extra); }
};

ok('字节数一致', a.length === ref.length, `${a.length} vs ${ref.length}`);

if (a.length === ref.length) {
  let firstDiff = -1;
  for (let i = 0; i < a.length; i++) if (a[i] !== ref[i]) { firstDiff = i; break; }
  ok('逐字节完全一致', firstDiff < 0,
     firstDiff < 0 ? '' : `首个差异 @${firstDiff} (0x${firstDiff.toString(16)}): ` +
       `js=${a[firstDiff]} java=${ref[firstDiff]}`);

  if (firstDiff >= 0) {
    const lo = Math.max(0, firstDiff - 8), hi = Math.min(a.length, firstDiff + 24);
    console.log('    js  :', a.subarray(lo, hi).toString('hex').match(/.{1,2}/g).join(' '));
    console.log('    java:', ref.subarray(lo, hi).toString('hex').match(/.{1,2}/g).join(' '));
    console.log(`    差异位置 0x${firstDiff.toString(16)}，所在区段：` +
      (firstDiff < 0xA8 ? '主头' : firstDiff < 0x100 ? '子表盘头'
        : firstDiff < 0x100 + (1 + resources.length) * 16 ? '定义表'
        : firstDiff < 0x614 ? '元件记录' : '预览/资源'));
  }
}

// 结构自检
ok('magic', a[0] === 0x5A && a[1] === 0xA5 && a[2] === 0x34 && a[3] === 0x12);
ok('设备标志 0x800', a[0x10] === 0x00 && a[0x11] === 0x08);
ok('faceCount=1', a[0x1C] === 1);
ok('styleCount=0', a[0x1E] === 0);
ok('ID 正确', Buffer.from(a.subarray(0x28, 0x31)).toString().replace(/\0/g, '') === '167200916');
ok('名字正确', Buffer.from(a.subarray(0x68, 0xA4)).toString('utf8').split('\0')[0] === '课表');

console.log(`\n${pass} 通过 / ${fail} 失败`);
process.exit(fail ? 1 : 0);
