// 把 facepack.js / timetable.js / main.lua 内联进 app-template.html，
// 产出单文件 out/kebiao-app.html（离线可用，直接发到手机就能开）
//   node wf/jspack/bundle.mjs
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const here = path.dirname(fileURLToPath(import.meta.url));
const wf = path.resolve(here, '..');
const root = path.resolve(wf, '..');

const read = (p) => fs.readFileSync(p, 'utf8');

const facepack = read(path.join(here, 'facepack.js'));
const timetable = read(path.join(here, 'timetable.js'));
const logic = read(path.join(wf, 'app/lua/main.lua'));

// main.lua 里的数据加载段要去掉（数据由 App 内联成 DATA_INLINE）
const logicNoLoader = logic.replace(
  /-- 数据（素材生成器产出）[\s\S]*?if type\(D\) ~= "table" then D = \{[\s\S]*?\nend\n/,
  '-- 数据由 App 内联为 DATA_INLINE\n'
);
if (logicNoLoader === logic) {
  console.warn('⚠️ 没能从 main.lua 里摘掉数据加载段，检查正则');
}

let html = read(path.join(here, 'app-template.html'));
html = html.replace('/*__FACEPACK__*/', () => facepack);
html = html.replace('/*__TIMETABLE__*/', () => timetable);
html = html.replace('__LUA_LOGIC__', () => JSON.stringify(logicNoLoader));

const out = path.join(root, 'out', 'kebiao-app.html');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, html);

const kb = (n) => (n / 1024).toFixed(0) + ' KB';
console.log(`✓ ${path.relative(root, out)}  ${kb(Buffer.byteLength(html))}`);
console.log(`   facepack.js ${kb(facepack.length)} · timetable.js ${kb(timetable.length)} · main.lua ${kb(logic.length)}`);
console.log(`   单文件、无外部依赖，手机浏览器直接打开即可`);
