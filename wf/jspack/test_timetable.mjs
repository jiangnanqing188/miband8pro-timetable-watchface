// 课表核心逻辑测试（node wf/jspack/test_timetable.mjs）
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const T = require('./timetable.js');

let pass = 0, fail = 0;
const ok = (name, cond, extra) => {
  if (cond) { pass++; console.log('  ✓', name); }
  else { fail++; console.log('  ✗', name, extra === undefined ? '' : JSON.stringify(extra)); }
};

console.log('周次解析');
ok('"1-16" 16 周', T.parseWeeks('1-16').length === 16);
ok('"1,3,5" 单周', JSON.stringify(T.parseWeeks('1,3,5')) === '[1,3,5]');
ok('"9,12,14-15" 不连续', JSON.stringify(T.parseWeeks('9,12,14-15')) === '[9,12,14,15]');
ok('中文逗号', T.parseWeeks('1-2，5').length === 3);
ok('空值兜底 16 周', T.parseWeeks('').length === 16);
ok('压缩 "1-3,5"', T.compactWeeks([1, 2, 3, 5]) === '1-3,5');
ok('压缩 单周', T.compactWeeks([1, 3, 5]) === '1,3,5');

console.log('开学日期 → 第几周');
ok('开学当天 = 第 1 周', T.weekOf('2026-09-07', new Date(2026, 8, 7)) === 1);
ok('开学那周周日仍第 1 周', T.weekOf('2026-09-07', new Date(2026, 8, 13)) === 1);
ok('第二周周一 = 第 2 周', T.weekOf('2026-09-07', new Date(2026, 8, 14)) === 2);
ok('2026-11-03 = 第 9 周', T.weekOf('2026-09-07', new Date(2026, 10, 3)) === 9);
ok('开学日期是周三也能对齐到周一', T.weekOf('2026-09-09', new Date(2026, 8, 7)) === 1);
ok('学期开始前是第 0 周或负', T.weekOf('2026-09-07', new Date(2026, 7, 31)) <= 0);

console.log('周次 → 具体日期');
{
  const d = T.dateOfWeek('2026-09-07', 9, 2);   // 第 9 周周二
  ok('第9周周二是 11-03', d.getMonth() === 10 && d.getDate() === 3,
     [d.getMonth() + 1, d.getDate()]);
  const d2 = T.dateOfWeek('2026-09-07', 1, 1);
  ok('第1周周一是 09-07', d2.getMonth() === 8 && d2.getDate() === 7);
}

console.log('时段与课堂筛选');
{
  ok('08:00 上午', T.phaseOf(T.minutes('08:00')) === 'morning');
  ok('11:59 上午', T.phaseOf(T.minutes('11:59')) === 'morning');
  ok('12:00 下午', T.phaseOf(T.minutes('12:00')) === 'afternoon');
  ok('18:00 晚上', T.phaseOf(T.minutes('18:00')) === 'evening');
  ok('00:01 上午（凌晨也算上午）', T.phaseOf(T.minutes('00:01')) === 'morning');

  const cfg = {
    periods: [
      { no: 1, start: '08:00', end: '09:35' },
      { no: 2, start: '10:05', end: '11:40' },
      { no: 5, start: '19:00', end: '20:35' },
    ],
    courses: [
      { name: 'A', weekday: 2, periods: [1], weeks: '1-15' },
      { name: 'B', weekday: 2, periods: [2], weeks: '1-13' },
      { name: 'C', weekday: 2, periods: [5], weeks: '7-8' },
      { name: 'D', weekday: 3, periods: [1], weeks: '1-15' },
    ],
  };
  ok('第9周周二 2 门', T.lessonsOf(cfg, 2, 9).length === 2);
  ok('第8周周二 3 门（7-8 周那门开了）', T.lessonsOf(cfg, 2, 8).length === 3);
  ok('第9周周三 1 门', T.lessonsOf(cfg, 3, 9).length === 1);
  ok('第16周周二 0 门（都结课了）', T.lessonsOf(cfg, 2, 16).length === 0);
  const ls = T.lessonsOf(cfg, 2, 8);
  ok('按时间排序', ls[0].from <= ls[1].from && ls[1].from <= ls[2].from);
  ok('带出上课时间', ls[0].start === '08:00' && ls[0].end === '09:35');
  ok('带出时段', ls[2].phase === 'evening');
}

console.log('data.lua / main.lua 生成');
{
  const dataLua = T.buildDataLua({
    monday: { y: 2026, m: 9, d: 7 },
    layout: { clockY: 34, dateY: 126, card1Y: 186, card2Y: 328, cardX: 18, cardW: 300, cardH: 132 },
    widths: { t0: 49, d0: 11, tc: 23 },
    courses: [{ weekday: 2, from: 480, to: 575, normal: 'c0.png', hi: 'c0h.png', weeks: '9,12', name: '测试"课' }],
  });
  ok('含 SEMESTER_MONDAY', dataLua.includes('M.SEMESTER_MONDAY = { y = 2026, m = 9, d = 7 }'));
  ok('含 LAYOUT', dataLua.includes('card_h = 132'));
  ok('含图元宽度', dataLua.includes('["t0"] = 49'));
  ok('含课程', dataLua.includes('day=2, from=480, to=575'));
  ok('周次展开成表', dataLua.includes('weeks={9,12}'));
  ok('引号转义', dataLua.includes('测试\\"课'));
  ok('以 return M 结尾', dataLua.trim().endsWith('return M'));

  const mainLua = T.buildMainLua(dataLua, 'local x = 1');
  ok('内联成 DATA_INLINE', mainLua.includes('local DATA_INLINE = (function()'));
  ok('逻辑追加在后', mainLua.trim().endsWith('local x = 1'));
}

console.log(`\n${pass} 通过 / ${fail} 失败`);
process.exit(fail ? 1 : 0);
