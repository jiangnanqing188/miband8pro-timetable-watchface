// 把 .face 里的 main.lua 抠出来，在真 Lua VM（fengari）里跑一遍
//   node wf/jspack/test_lua_from_face.mjs
// 这是最后一环：证明「手机生成的包」里的脚本能正常渲染。
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);
const { lua, lauxlib, lualib, to_luastring, to_jsstring } = require('fengari');

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const src = path.join(root, 'out/_extracted_main.lua');
if (!fs.existsSync(src)) {
  console.error('先跑 wf/jspack/test_app.mjs 生成 out/_extracted_main.lua');
  process.exit(1);
}
const mainLua = fs.readFileSync(src, 'utf8');

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
    Timer = function(p) local t = obj(p); t.cb = p.cb; return t end,
  }
end
package.preload["dataman"] = function() return { subscribe = function() end } end
SCRIPT_PATH = "lua/"
function VISIBLE()
  local out = {}
  for _, o in ipairs(ALL) do
    if not o.flags[4] and o.props.src then out[#out + 1] = (o.props.src:gsub("^lua/", "")) end
  end
  return table.concat(out, "|")
end
function COUNT(sub)
  local n = 0
  for w in VISIBLE():gmatch("[^|]+") do if w == sub then n = n + 1 end end
  return n
end
`;

function run(name, code) {
  if (lauxlib.luaL_dostring(L, to_luastring(code)) !== 0) {
    console.error(`✗ ${name}: ` + to_jsstring(lua.lua_tostring(L, -1)));
    process.exit(1);
  }
}

run('prelude', PRELUDE);
run('main.lua(from face)', mainLua);

const TEST = String.raw`
local pass, fail = 0, 0
local function ok(n, cond, d)
  if cond then pass = pass + 1; print("OK\t" .. n) else
    fail = fail + 1; print("FAIL\t" .. n .. "\t" .. tostring(d)) end
end
local function CST(y, mo, d, h, mi)
  return WF.days_of(y, mo, d) * 86400 + h * 3600 + mi * 60 - 8 * 3600
end

local r = WF.render(CST(2026, 11, 3, 8, 30))
ok("包里的脚本能跑", type(r) == "table")
ok("学期起始正确（第9周）", r.week == 9, r.week)
ok("2026-11-03 是周二", r.wd == 2, r.wd)
ok("上午时段", r.phase == "morning", r.phase)
ok("上午有课", r.n >= 1, r.n)
ok("时钟画了 5 个图元", COUNT("t0.png") + COUNT("t8.png") + COUNT("t3.png") + COUNT("tc.png") >= 4,
   VISIBLE())

-- 不连续的周次（第 9,12,14-15 周那门课在周四第4节）
local thu9  = WF.render(CST(2026, 11, 5, 16, 30))
local thu10 = WF.render(CST(2026, 11, 12, 16, 30))
ok("第9周周四下午有课", thu9.n >= 1, thu9.n)
ok("第10周周四下午没课（那门课只在 9,12,14-15 周）", thu10.n == 0, thu10.n)

-- 第 18 周应该全空（1-17 周的课都结课了）
local w18 = WF.render(CST(2027, 1, 5, 8, 30))
ok("第18周没课", w18.n == 0, w18.n)

print("SUMMARY\t" .. pass .. "\t" .. fail)
`;
run('tests', TEST);
