// Lua 表盘逻辑测试：用 fengari 真跑 main.lua（桩掉 lvgl）
// 断言写在 Lua 里（避免跨语言传 table），node 只负责统计结果
// 运行：node wf/test/run_test.mjs
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);
const { lua, lauxlib, lualib, to_luastring, to_jsstring } = require('fengari');

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => fs.readFileSync(path.join(root, p), 'utf8');

const L = lauxlib.luaL_newstate();
lualib.luaL_openlibs(L);

const PRELUDE = `
local ALL = {}
local function obj(props)
  local o = { props = {}, flags = {} }
  for k, v in pairs(props or {}) do o.props[k] = v end
  ALL[#ALL + 1] = o
  function o:set(q) for k, v in pairs(q) do self.props[k] = v end end
  function o:add_flag(f) self.flags[f] = true end
  function o:clear_flag(f) self.flags[f] = nil end
  function o:Image(p) return obj(p) end
  function o:pause() end
  function o:resume() end
  return o
end
package.preload["lvgl"] = function()
  return {
    HOR_RES = function() return 336 end,
    VER_RES = function() return 480 end,
    OPA = function(x) return x end,
    FLAG = { HIDDEN = 4, EVENT_BUBBLE = 2, SCROLLABLE = 1, CLICKABLE = 3 },
    Object = function(_, p) return obj(p) end,
    Image = function(_, p) return obj(p) end,
    Timer = function(p) local t = obj(p); t.cb = p.cb; TIMER = t; return t end,
  }
end
package.preload["dataman"] = function() return { subscribe = function() end } end
SCRIPT_PATH = "app/lua/"

-- 当前可见图元的文件名列表
function VISIBLE()
  local out = {}
  for _, o in ipairs(ALL) do
    if not o.flags[4] and o.props.src then
      out[#out + 1] = (o.props.src:gsub("^app/lua/", ""))
    end
  end
  return table.concat(out, "|")
end
function COUNT(sub)
  local n = 0
  for w in VISIBLE():gmatch("[^|]+") do if w:find(sub, 1, true) then n = n + 1 end end
  return n
end
local SRC = FILES_TBL
function dofile(name)
  local src = SRC[name] or SRC[(name or ""):match("([^/]+)$")]
  if not src then error("dofile 找不到 " .. tostring(name)) end
  return assert(load(src, name))()
end
`;

lua.lua_newtable(L);
// 固定测试数据：不依赖用户真实课表，换课表也不会误报
const FIXTURE_COURSES = `M.COURSES = {
  { day=2, from=480, to=575, normal="c0.png", hi="c0h.png", weeks={1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}, name="早课" },
  { day=2, from=840, to=935, normal="c1.png", hi="c1h.png", weeks={1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}, name="下午课" },
  { day=5, from=840, to=935, normal="c2.png", hi="c2h.png", weeks={9,10,11,12,13,14,15,16}, name="九周才开" },
}`;
const dataSrc = read('app/lua/data.lua').replace(/M\.COURSES = \{[\s\S]*?\n\}/, FIXTURE_COURSES);
lua.lua_pushstring(L, to_luastring(dataSrc));
lua.lua_setfield(L, -2, to_luastring('data.lua'));
lua.lua_pushstring(L, to_luastring(read('app/lua/main.lua')));
lua.lua_setfield(L, -2, to_luastring('main.lua'));
lua.lua_setglobal(L, to_luastring('FILES_TBL'));

function run(name, code) {
  if (lauxlib.luaL_dostring(L, to_luastring(code)) !== 0) {
    const err = to_jsstring(lua.lua_tostring(L, -1));
    lua.lua_pop(L, 1);
    console.error(`Lua 执行失败 (${name}): ${err}`);
    process.exit(1);
  }
}

run('prelude', PRELUDE);
const BUILT = process.argv.includes('--built');
const MAIN = BUILT ? 'build/face/app/lua/main.lua' : 'app/lua/main.lua';
console.log('被测文件:', MAIN);
run('main.lua', read(MAIN));

const TEST = String.raw`
local pass, fail = 0, 0
local function ok(name, cond, detail)
  if cond then pass = pass + 1; print("OK\t" .. name)
  else
    fail = fail + 1
    print("FAIL\t" .. name .. "\t" .. tostring(detail))
  end
end

-- CST(年,月,日,时,分) → epoch 秒（借 WF.days_of，避免依赖时区）
local function CST(y, mo, d, h, mi)
  return WF.days_of(y, mo, d) * 86400 + h * 3600 + mi * 60 - 8 * 3600
end

-- 1. 日期换算
local r = WF.render(CST(2026, 11, 3, 8, 30))
ok("2026-11-03 年", r.y == 2026, r.y)
ok("2026-11-03 月", r.m == 11, r.m)
ok("2026-11-03 日", r.d == 3, r.d)
ok("2026-11-03 是周二", r.wd == 2, r.wd)
ok("2026-11-03 是第 9 周", r.week == 9, r.week)
ok("时刻 08:30", r.hh == 8 and r.mm == 30, r.hh .. ":" .. r.mm)
-- 08:30 → 数字 0,8,3,0 加一个冒号
ok("时钟是 08:30 的图元", COUNT("t0.png") == 2 and COUNT("t8.png") == 1
   and COUNT("t3.png") == 1 and COUNT("tc.png") == 1, VISIBLE())

local function wd_of(y, mo, d) return WF.render(CST(y, mo, d, 12, 0)).wd end
ok("2026-09-07 是周一", wd_of(2026, 9, 7) == 1, wd_of(2026, 9, 7))
ok("2026-09-13 是周日", wd_of(2026, 9, 13) == 7, wd_of(2026, 9, 13))
ok("2026-01-01 是周四", wd_of(2026, 1, 1) == 4, wd_of(2026, 1, 1))
ok("2024-02-29 是周四（闰日）", wd_of(2024, 2, 29) == 4, wd_of(2024, 2, 29))
ok("跨年 2027-01-01 是周五", wd_of(2027, 1, 1) == 5, wd_of(2027, 1, 1))

-- 2. 三个时段
if not IS_BUILT then
local am = WF.render(CST(2026, 11, 3, 8, 30))
ok("08:30 属于上午", am.phase == "morning", am.phase)
ok("上午 1 节课", am.n == 1, am.n)
ok("上午画了课卡", COUNT("c0") == 1, COUNT("c0"))

local pm = WF.render(CST(2026, 11, 3, 13, 0))
ok("13:00 属于下午", pm.phase == "afternoon", pm.phase)
ok("下午 1 节课", pm.n == 1, pm.n)

local ev = WF.render(CST(2026, 11, 3, 19, 30))
ok("19:30 属于晚上", ev.phase == "evening", ev.phase)
ok("晚上 0 节课", ev.n == 0, ev.n)
ok("晚上显示「没课」图", COUNT("empty_evening.png") == 1, VISIBLE())

ok("11:59 还是上午", WF.phase_of(11 * 60 + 59) == "morning")
ok("12:00 变下午", WF.phase_of(12 * 60) == "afternoon")
ok("17:59 还是下午", WF.phase_of(17 * 60 + 59) == "afternoon")
ok("18:00 变晚上", WF.phase_of(18 * 60) == "evening")

end

-- 3. 高亮正在上的课
if not IS_BUILT then
WF.render(CST(2026, 11, 3, 8, 30))
ok("08:30 有 1 张高亮卡", COUNT("h.png") == 1, COUNT("h.png") .. " / " .. VISIBLE())
WF.render(CST(2026, 11, 3, 12, 30))
ok("12:30 课间无高亮", COUNT("h.png") == 0, COUNT("h.png"))
WF.render(CST(2026, 11, 3, 9, 45))
ok("课间没有高亮卡", COUNT("h.png") == 0, COUNT("h.png"))
end

-- 4. 周次过滤
if not IS_BUILT then
local w3fri = WF.render(CST(2026, 9, 25, 14, 30))
local w9fri = WF.render(CST(2026, 11, 6, 14, 30))
ok("第 3 周周五是周五", w3fri.wd == 5, w3fri.wd)
ok("第 9 周周五有课", w9fri.n > 0, w9fri.n)
ok("第 9 周周五有 1 节课", w9fri.n == 1, w9fri.n)
ok("第 3 周周五课更少（9-16 周才开的课还没开）", w3fri.n < w9fri.n, w3fri.n .. " vs " .. w9fri.n)

end

-- 5. 极端情况不崩
ok("学期开始前不崩", pcall(WF.render, CST(2026, 8, 1, 9, 0)))
ok("远期日期不崩", pcall(WF.render, CST(2030, 1, 1, 9, 0)))
ok("午夜 00:00 不崩", pcall(WF.render, CST(2026, 11, 3, 0, 0)))
ok("23:59 不崩", pcall(WF.render, CST(2026, 11, 3, 23, 59)))

print("SUMMARY\t" .. pass .. "\t" .. fail)
`;

run('tests', `IS_BUILT = ${BUILT ? 'true' : 'false'}\n` + TEST);
process.exit(0);
