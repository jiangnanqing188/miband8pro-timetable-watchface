// 网页版编辑器的纯逻辑测试（node tests/logic_test.mjs）
// 直接从未经改动的 editor.html 里抽出那段逻辑来跑，保证测的就是线上代码
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// 路径里有中文，必须用 fileURLToPath 解码
const root = path.dirname(fileURLToPath(import.meta.url));
const html = fs.readFileSync(path.join(root, '..', 'editor.html'), 'utf8');
const script = html.split('<script>')[1].split('</script>')[0];
const pure = script.split('/* =========================================================\n   画表盘')[0];

const out = path.join(root, '_logic.mjs');
fs.writeFileSync(out,
  'const store={};\n' +
  'const localStorage={getItem:k=>(k in store?store[k]:null),setItem:(k,v)=>{store[k]=v}};\n' +
  'const prompt=()=>null,confirm=()=>true;\n' +
  pure + '\n' +
  'export {parseWeeks,weeksValid,weekOf,phaseOf,norm,parsePeriods,PERIODS,PHASES};\n');

const m = await import('file://' + out + '?v=' + Date.now());

let pass = 0, fail = 0;
const ok = (name, cond, extra) => {
  if (cond) { pass++; console.log('  ✓', name); }
  else { fail++; console.log('  ✗', name, extra === undefined ? '' : ` (${JSON.stringify(extra)})`); }
};

console.log('周次解析');
ok('"1-16" 共 16 周', m.parseWeeks('1-16').size === 16);
ok('"1-8,10-16" 不含第 9 周', !m.parseWeeks('1-8,10-16').has(9));
ok('"3" 单周', JSON.stringify([...m.parseWeeks('3')]) === '[3]');
ok('中文逗号也能分', m.parseWeeks('1-2，5，7-9').size === 6);
ok('乱码兜底成全学期（不再静默消失）', m.parseWeeks('abc').size === 16);
ok('空字符串兜底成全学期', m.parseWeeks('').size === 16);

console.log('周次格式校验');
ok('拒绝乱码', m.weeksValid('abc') === false);
ok('接受 1-16', m.weeksValid('1-16') === true);
ok('接受 1-8,10-16', m.weeksValid('1-8,10-16') === true);
ok('空值按设计视为默认', m.weeksValid('') === true && m.parseWeeks('').size === 16);

console.log('教学周推算');
ok('学期首个周一 = 第 1 周', m.weekOf(new Date('2026-09-07T12:00:00')) === 1);
ok('2026-11-03 = 第 9 周', m.weekOf(new Date('2026-11-03T12:00:00')) === 9);
ok('2026-09-13 仍属第 1 周', m.weekOf(new Date('2026-09-13T12:00:00')) === 1);

console.log('时段归段边界');
ok('08:00 → 上午', m.phaseOf('08:00') === 'morning');
ok('11:59 → 上午', m.phaseOf('11:59') === 'morning');
ok('12:00 → 下午', m.phaseOf('12:00') === 'afternoon');
ok('17:59 → 下午', m.phaseOf('17:59') === 'afternoon');
ok('18:00 → 晚上', m.phaseOf('18:00') === 'evening');
ok('20:50 → 晚上', m.phaseOf('20:50') === 'evening');

console.log('作息表');
ok('12 节课', m.PERIODS.length === 12);
ok('第 1 节 08:00 开始', m.PERIODS[0].start === '08:00');
ok('第 12 节 22:30 结束', m.PERIODS[11].end === '22:30');

console.log('课程归一化');
const c = m.norm({name:' 高数 ', weekday:'2', periods:'4,3', weeks:'1-16', room:' A '});
ok('去空格', c.name === '高数' && c.room === 'A');
ok('星期转数字', c.weekday === 2);
ok('字符串 4,3 → [3,4]', JSON.stringify(c.periods) === '[3,4]');
ok('"第3-4节" → [3,4]', JSON.stringify(m.parsePeriods('第3-4节')) === '[3,4]');
ok('"5-8" 四节连上', JSON.stringify(m.parsePeriods('5-8')) === '[5,6,7,8]');
ok('数字 7 → [7]', JSON.stringify(m.parsePeriods(7)) === '[7]');
ok('数组去重排序', JSON.stringify(m.parsePeriods([4,3,4])) === '[3,4]');
ok('周次数组转字符串', m.norm({name:'x',periods:1,weeks:[1,2,3]}).weeks === '1,2,3');
ok('星期越界夹紧到 7', m.norm({name:'x',periods:1,weekday:99}).weekday === 7);

fs.unlinkSync(out);
console.log(`\n${pass} 通过 / ${fail} 失败`);
process.exit(fail ? 1 : 0);
