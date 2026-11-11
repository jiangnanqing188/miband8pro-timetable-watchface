/**
 * timetable.js —— 课表核心逻辑（纯函数，浏览器和 node 通用）
 * ==========================================================
 * 负责：周次解析、开学日期推算第几周、生成 data.lua / main.lua 文本。
 * 不碰 DOM、不碰 canvas，所以能被 node 单测覆盖。
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Timetable = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const DAY = 86400000;
  const WEEK_CN = '一二三四五六日';

  /** '1-16' / '1,3,5' / [1,2] → [1,2,...] */
  function parseWeeks(v) {
    if (Array.isArray(v)) return v.map(Number).sort((a, b) => a - b);
    const out = new Set();
    String(v || '1-16').replace(/，/g, ',').split(',').forEach((part) => {
      part = part.trim();
      if (!part) return;
      const m = part.match(/^(\d+)\s*[-~至]\s*(\d+)$/);
      if (m) {
        const a = +m[1], b = +m[2];
        for (let i = Math.min(a, b); i <= Math.max(a, b); i++) out.add(i);
      } else if (/^\d+$/.test(part)) out.add(+part);
    });
    if (!out.size) for (let i = 1; i <= 16; i++) out.add(i);
    return [...out].sort((a, b) => a - b);
  }

  /** [1,2,3,5] → '1-3,5' */
  function compactWeeks(nums) {
    const a = [...new Set(nums)].sort((x, y) => x - y);
    if (!a.length) return '1-16';
    const segs = [];
    let s = a[0], p = a[0];
    for (const n of a.slice(1)) {
      if (n === p + 1) { p = n; continue; }
      segs.push([s, p]); s = p = n;
    }
    segs.push([s, p]);
    return segs.map(([x, y]) => (y > x ? x + '-' + y : String(x))).join(',');
  }

  /** 本地日期字符串 'YYYY-MM-DD' → Date（当天 00:00 本地） */
  function parseDate(s) {
    const m = String(s || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return new Date();
    return new Date(+m[1], +m[2] - 1, +m[3]);
  }

  /** 开学日期所在周的周一（周一为一周开始） */
  function mondayOf(date) {
    const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const shift = (d.getDay() + 6) % 7;        // 周一=0
    d.setDate(d.getDate() - shift);
    return d;
  }

  /** 两个本地日期相差多少"日历天"（走 UTC 运算，避开夏令时导致的 ±1 小时偏移） */
  function daysBetween(a, b) {
    const u = (d) => Date.UTC(d.getFullYear(), d.getMonth(), d.getDate());
    return Math.round((u(b) - u(a)) / DAY);
  }

  /** 第几周：开学那周算第 1 周 */
  function weekOf(semesterStart, date) {
    const m0 = mondayOf(parseDate(semesterStart));
    const m1 = mondayOf(date || new Date());
    return Math.floor(daysBetween(m0, m1) / 7) + 1;
  }

  /** 第 week 周、星期 wd 的日期（按日历天加，不受夏令时影响） */
  function dateOfWeek(semesterStart, week, wd) {
    const m0 = mondayOf(parseDate(semesterStart));
    const add = (week - 1) * 7 + (wd - 1);
    return new Date(m0.getFullYear(), m0.getMonth(), m0.getDate() + add);
  }

  /** 'HH:MM' → 分钟 */
  function minutes(hhmm) {
    const [h, m] = String(hhmm || '00:00').split(':').map(Number);
    return h * 60 + (m || 0);
  }

  /** 某个开课时间属于哪个时段 */
  function phaseOf(min) {
    if (min < 12 * 60) return 'morning';
    if (min < 18 * 60) return 'afternoon';
    return 'evening';
  }

  /** 课程 → 上课时间/下课时间（按 periods 表） */
  function courseTime(course, periods) {
    const list = (periods || []).slice().sort((a, b) => a.no - b.no);
    const map = {};
    list.forEach((p) => { map[p.no] = p; });
    const nos = list.map((p) => p.no);
    // 课引用了不存在的节次时，就近取一节（比如删掉了第 7 节）
    const nearest = (n) => {
      if (map[n]) return n;
      if (!nos.length) return n;
      return nos.reduce((best, x) => (Math.abs(x - n) < Math.abs(best - n) ? x : best), nos[0]);
    };
    const ps = [...course.periods].sort((a, b) => a - b);
    const n0 = nearest(ps[0]), n1 = nearest(ps[ps.length - 1]);
    const p0 = map[n0] || { start: '08:00', end: '09:35' };
    const p1 = map[n1] || p0;
    return { start: p0.start, end: p1.end, p0: n0, p1: n1 };
  }

  /** 'HH:MM' + n 分钟 */
  function addMinutes(hhmm, n) {
    const t = minutes(hhmm) + n;
    const h = Math.floor((t % 1440) / 60), m = t % 60;
    const pad = (x) => String(x).padStart(2, '0');
    return pad(h) + ':' + pad(m);
  }

  /** 这一周这一天要上的课（按开始时间排） */
  function lessonsOf(cfg, weekday, week) {
    const out = [];
    (cfg.courses || []).forEach((c, idx) => {
      if (Number(c.weekday) !== Number(weekday)) return;
      const weeks = parseWeeks(c.weeks);
      if (weeks.indexOf(week) < 0) return;
      const t = courseTime(c, cfg.periods);
      out.push(Object.assign({ idx }, c, {
        start: t.start, end: t.end, p0: t.p0, p1: t.p1,
        from: minutes(t.start), to: minutes(t.end),
        phase: phaseOf(minutes(t.start)),
      }));
    });
    out.sort((a, b) => a.from - b.from);
    return out;
  }

  /** 课程配色（同名的用同一个颜色） */
  const PALETTE = ['#5B8CFF', '#4ED0A6', '#FF9F5B', '#C77DFF', '#FF6B81', '#FFD166', '#4FC3F7', '#A3E635'];

  function colorMap(courses) {
    const byName = {}, map = {};
    let i = 0;
    (courses || []).forEach((c, idx) => {
      const key = c.name + '|' + (c.teacher || '');
      if (!(key in byName)) { byName[key] = PALETTE[i % PALETTE.length]; i++; }
      map[idx] = byName[key];
    });
    return map;
  }

  /** 生成 data.lua：坐标、图元宽度、课程表 */
  function buildDataLua(o) {
    const L = o.layout;
    const lines = [];
    lines.push('-- 由手机 App 生成，不要手改');
    lines.push('local M = {}');
    lines.push(`M.SEMESTER_MONDAY = { y = ${o.monday.y}, m = ${o.monday.m}, d = ${o.monday.d} }`);
    lines.push(`M.LAYOUT = { clock_y = ${L.clockY}, date_y = ${L.dateY}, card1_y = ${L.card1Y}, ` +
               `card2_y = ${L.card2Y}, card_x = ${L.cardX}, card_w = ${L.cardW}, card_h = ${L.cardH} }`);
    lines.push('M.W = {');
    Object.keys(o.widths).sort().forEach((k) => {
      lines.push(`  ["${k}"] = ${Math.round(o.widths[k])},`);
    });
    lines.push('}');
    lines.push('M.COURSES = {');
    (o.courses || []).forEach((c) => {
      lines.push(`  { day=${c.weekday}, from=${c.from}, to=${c.to}, ` +
                 `normal="${c.normal}", hi="${c.hi}", weeks={${parseWeeks(c.weeks).join(',')}}, ` +
                 `name="${String(c.name).replace(/\\/g, '\\\\').replace(/"/g, '\\"')}" },`);
    });
    lines.push('}');
    lines.push('return M');
    return lines.join('\n') + '\n';
  }

  /** 把 data.lua 内联进 main.lua，手环上只留一个文件 */
  function buildMainLua(dataLua, logicLua) {
    return '-- 由手机 App 组装：数据内联 + 表盘逻辑\n' +
           'local DATA_INLINE = (function()\n' + dataLua + 'end)()\n\n' + logicLua;
  }

  return {
    DAY, WEEK_CN, PALETTE,
    parseWeeks, compactWeeks, parseDate, mondayOf, weekOf, dateOfWeek,
    minutes, phaseOf, courseTime, lessonsOf, colorMap, addMinutes,
    buildDataLua, buildMainLua,
  };
});
