// 端到端：在 node 里跑 App 的 renderForms + buildFace，产出真 .face 并校验结构
//   node wf/jspack/test_app.mjs
// 用 @napi-rs/canvas 提供真 canvas（和浏览器同一套 Canvas2D API）
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);
const { createCanvas } = require('@napi-rs/canvas');

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const html = fs.readFileSync(path.join(root, 'out/kebiao-app.html'), 'utf8');

// 取最后一个 <script>（App 逻辑）
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
const appCode = scripts[scripts.length - 1];

// ---- 极简 DOM 桩 ----
function fakeEl() {
  const el = {
    textContent: '', innerHTML: '', value: '', src: '', disabled: false,
    style: {}, dataset: {},
    addEventListener() {}, appendChild() {}, removeChild() {}, remove() {},
    click() {}, getContext: () => null, focus() {},
    classList: { add() {}, remove() {}, toggle() {} },
  };
  return el;
}
const doc = {
  querySelector: () => fakeEl(),
  querySelectorAll: () => [],
  createElement: (tag) => (tag === 'canvas' ? createCanvas(1, 1) : fakeEl()),
  body: fakeEl(),
};

const sandbox = {
  document: doc,
  window: {},
  localStorage: { getItem() { throw new Error('no ls'); }, setItem() { throw new Error('no ls'); } },
  performance: { now: () => Date.now() },
  atob: (s) => Buffer.from(s, 'base64').toString('binary'),
  TextEncoder,
  setTimeout, clearTimeout, console,
  URL: { createObjectURL: () => '', revokeObjectURL() {} },
  Blob: class {},
  FileReader: class {},
};
sandbox.self = sandbox;
vm.createContext(sandbox);

// 先把依赖注入（bundle 里前面两个 script 是 facepack / timetable）
for (const code of scripts.slice(0, -1)) vm.runInContext(code, sandbox);
// 再跑 App
try {
  vm.runInContext(appCode, sandbox);
} catch (e) {
  console.log('⚠️ App 初始化抛错（表单渲染相关，可忽略）:', e.message);
}

let pass = 0, fail = 0;
const ok = (name, cond, extra) => {
  if (cond) { pass++; console.log('  ✓', name); }
  else { fail++; console.log('  ✗', name, extra === undefined ? '' : JSON.stringify(extra)); }
};

console.log('环境');
ok('FacePack 可用', typeof sandbox.FacePack === 'object');
ok('Timetable 可用', typeof sandbox.Timetable === 'object');
ok('buildFace 可调用', typeof sandbox.buildFace === 'function');

// 塞一份课表（含不连续周次、长课名、多节课）
const S = sandbox.window.__app.state;
S.semesterStart = '2026-09-07';
S.periods = [
  { no: 1, start: '08:00', end: '09:35' }, { no: 2, start: '10:05', end: '11:40' },
  { no: 3, start: '14:00', end: '15:35' }, { no: 4, start: '16:05', end: '17:40' },
  { no: 5, start: '19:00', end: '20:35' },
];
S.courses = [
  { name: '数值分析', room: '东13-C-117c', weekday: 1, periods: [1], weeks: '1-17' },
  { name: '汇编语言与微型计算机技术', room: '东16-B-201', weekday: 2, periods: [1], weeks: '1-15' },
  { name: '机器学习', room: '东13-C-316c', weekday: 2, periods: [4], weeks: '1-13' },
  { name: '人工智能基础上机', room: '4教110', weekday: 4, periods: [4], weeks: '9,12,14-15' },
  { name: '不做HR也要了解的人力资源管理(慕课)', room: '东16-A-213', weekday: 6, periods: [2], weeks: '3-17' },
];

const t0 = Date.now();
const face = await sandbox.window.__app.buildFace();
console.log(`\n生成 ${(face.length / 1024).toFixed(0)} KB，耗时 ${Date.now() - t0} ms`);

ok('返回了字节', face && face.length > 100000, face && face.length);

// ---- 结构校验 ----
const u32 = (o) => (face[o] | (face[o + 1] << 8) | (face[o + 2] << 16) | (face[o + 3] << 24)) >>> 0;
const u16 = (o) => face[o] | (face[o + 1] << 8);
const txt = (o, n) => Buffer.from(face.buffer, face.byteOffset + o, n).toString('binary');

ok('magic 5aa53412', face[0] === 0x5A && face[1] === 0xA5 && face[2] === 0x34 && face[3] === 0x12);
ok('设备标志 0x800', u32(0x10) === 0x800, u32(0x10));
ok('faceCount=1', u16(0x1C) === 1);
ok('styleCount=0', u16(0x1E) === 0);
ok('ID', txt(0x28, 9).replace(/\0/g, '') === '167200916', txt(0x28, 9));
ok('名字=课表', Buffer.from(face.buffer, face.byteOffset + 0x68, 60).toString('utf8').split('\0')[0] === '课表');

const jsCount = u32(0xA8 + 0x30);
ok('JS 资源数合理（>40）', jsCount > 40, jsCount);

// 定义表：检查 type 与名字前缀
const defCount = 1 + jsCount;
let types = {};
let hasLua = false, hasCard = false, hasGlyph = false, badName = 0;
for (let i = 0; i < defCount; i++) {
  const p = 0x100 + i * 16;
  const typ = face[p + 3];
  types[typ] = (types[typ] || 0) + 1;
  if (typ !== 5) continue;
  const ofs = u32(p + 8);
  const nameLen = face[ofs + 3];
  const name = txt(ofs + 0x14, nameLen);
  if (!/^lua\/[A-Za-z0-9_.]+$/.test(name)) badName++;
  if (name === 'lua/main.lua') hasLua = true;
  if (/^lua\/c\d+h?\.png$/.test(name)) hasCard = true;
  if (/^lua\/t\d\.png$/.test(name)) hasGlyph = true;
}
ok('定义表：1 个基础元件', types[0] === 1, types);
ok('定义表：其余全是 JS 资源', types[5] === jsCount, types);
ok('资源名格式正确', badName === 0, badName);
ok('包含 main.lua', hasLua);
ok('包含课程卡', hasCard);
ok('包含时钟图元', hasGlyph);

// 资源内容自检
{
  const p = 0x100 + 16;
  const ofs = u32(p + 8), len = u32(p + 12);
  const nameLen = face[ofs + 3];
  const rawLen = face[ofs] | (face[ofs + 1] << 8) | (face[ofs + 2] << 16);
  ok('资源块长度自洽', len === 0x14 + nameLen + rawLen, [len, 0x14 + nameLen + rawLen]);
  const lua = Buffer.from(face.buffer, face.byteOffset + ofs + 0x14 + nameLen, rawLen).toString('utf8');
  ok('main.lua 含 DATA_INLINE', lua.includes('local DATA_INLINE'), lua.slice(0, 30));
  ok('main.lua 含课程数据', lua.includes('M.COURSES'), '');
  ok('main.lua 含开学日期', /M\.SEMESTER_MONDAY = \{ y = 2026, m = 9, d = 7 \}/.test(lua));
  fs.writeFileSync(path.join(root, 'out/_extracted_main.lua'), lua);

  // 再抽一张 PNG，确认是合法 PNG
  for (let i = 1; i < defCount; i++) {
    const q = 0x100 + i * 16;
    const o2 = u32(q + 8);
    const nl = face[o2 + 3];
    const nm = txt(o2 + 0x14, nl);
    if (nm.endsWith('.png')) {
      const png = face.subarray(o2 + 0x14 + nl, o2 + u32(q + 12));
      ok('PNG 签名正确 (' + nm + ')',
         png[0] === 0x89 && png[1] === 0x50 && png[2] === 0x4E && png[3] === 0x47);
      break;
    }
  }
}

// 预览块
{
  const pv = u32(0x20);
  ok('预览偏移合理', pv > 0 && pv < face.length, pv);
  ok('预览是压缩图块', face[pv + 1] === 4, face[pv + 1]);
  const payload = pv + 12;
  ok('预览 RLE 头 magic', face[payload] === 0xE0 && face[payload + 1] === 0x21
     && face[payload + 2] === 0xA5 && face[payload + 3] === 0x5A);
  const info = u32(payload + 4);
  ok('预览 bpp=4 / 原始长度 336*480*4', (info & 15) === 4 && (info >>> 4) === 336 * 480 * 4,
     [(info & 15), info >>> 4]);
}

// 日期行最宽情形：两位月 + 两位日 + 周X + 时段（不含「·」）
{
  const seq = ['d2','d0','d2','d6','y','d1','d2','mo','d2','d8','dd','wk','w4','p_afternoon'];
  let wsum = 0;
  seq.forEach((k) => { wsum += 0; });
  // 用 App 内部的图元宽度表
  const gw = {};
  for (const d of '0123456789') gw['d' + d] = sandbox.window.__app.glyphPNG(d, 500, 26, '#fff', 1).width;
  gw['y'] = sandbox.window.__app.glyphPNG('年', 500, 26, '#fff', 1).width;
  gw['mo'] = sandbox.window.__app.glyphPNG('月', 500, 26, '#fff', 1).width;
  gw['dd'] = sandbox.window.__app.glyphPNG('日', 500, 26, '#fff', 1).width;
  gw['wk'] = sandbox.window.__app.glyphPNG('周', 500, 26, '#fff', 1).width;
  gw['w4'] = sandbox.window.__app.glyphPNG('四', 500, 26, '#fff', 1).width;
  gw['p_afternoon'] = sandbox.window.__app.glyphPNG('下午', 500, 26, '#fff', 1).width;
  let total = 0;
  seq.forEach((k) => { total += gw[k] || 0; });
  ok('日期行最宽情形不溢出（≤328px）', total <= 328, total);
}

fs.writeFileSync(path.join(root, 'out/kebiao-app.face'), face);
console.log(`\n已写出 out/kebiao-app.face（${(face.length / 1024).toFixed(0)} KB）`);
console.log(`${pass} 通过 / ${fail} 失败`);
process.exit(fail ? 1 : 0);
