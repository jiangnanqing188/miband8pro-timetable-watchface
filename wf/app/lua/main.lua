-- 课表表盘（Lua 版，小米手环 8 Pro / 336x480）
-- ------------------------------------------------------------------
-- 和大号数字表盘不同，这个表盘是"程序"：
--   · 时间、日期、教学周都由 os.time() 现算（不依赖系统叠加的大时钟）
--   · 按当前时刻自动切换上午/下午/晚上，只显示这一段的课
--   · 正在上的那节课高亮（卡片边框 + 右上角圆点）
-- 文字都是预渲染图元（手环不保证带中文字库），见 wf/gen_assets.py
-- ------------------------------------------------------------------

local lvgl = require("lvgl")
local W, H = lvgl.HOR_RES(), lvgl.VER_RES()
local DIR = SCRIPT_PATH or "app/lua/"
local HIDDEN = lvgl.FLAG.HIDDEN

-- 数据（素材生成器产出）。打包时会被内联成 DATA_INLINE，
-- 没内联（测试环境）就退回 dofile，再不行用空表兜底
local D = DATA_INLINE
if type(D) ~= "table" then
    local ok, M = pcall(dofile, DIR .. "data.lua")
    D = ok and M or nil
end
if type(D) ~= "table" then
    D = { COURSES = {}, W = {}, LAYOUT = { clock_y = 34, date_y = 126,
          card1_y = 190, card2_y = 320, card_x = 18, card_w = 300, card_h = 116 },
          SEMESTER_MONDAY = { y = 2026, m = 9, d = 7 } }
end
local L = D.LAYOUT
local WID = D.W
local COURSES = D.COURSES

local TZ = 8 * 3600              -- 北京时间（手环给的是 UTC 时间戳）

-- ---------------------------------------------------------------- 日期换算
-- Howard Hinnant 的 days -> (y,m,d)，不依赖 os.date，结果可测
local function civil_from_days(z)
    z = z + 719468
    local era = math.floor(z / 146097)
    local doe = z - era * 146097
    local yoe = math.floor((doe - math.floor(doe / 1460) + math.floor(doe / 36524)
                            - math.floor(doe / 146096)) / 365)
    local y = yoe + era * 400
    local doy = doe - (365 * yoe + math.floor(yoe / 4) - math.floor(yoe / 100))
    local mp = math.floor((5 * doy + 2) / 153)
    local d = doy - math.floor((153 * mp + 2) / 5) + 1
    local m = mp + (mp < 10 and 3 or -9)
    return y + (m <= 2 and 1 or 0), m, d
end

local function days_of(y, m, d)     -- 与 civil_from_days 互逆
    local yy = y
    if m <= 2 then yy = yy - 1 end
    local era = math.floor(yy / 400)
    local yoe = yy - era * 400
    local mp = m + (m > 2 and -3 or 9)
    local doy = math.floor((153 * mp + 2) / 5) + d - 1
    local doe = yoe * 365 + math.floor(yoe / 4) - math.floor(yoe / 100) + doy
    return era * 146097 + doe - 719468
end

local SEM_DAYS = days_of(D.SEMESTER_MONDAY.y, D.SEMESTER_MONDAY.m, D.SEMESTER_MONDAY.d)

-- ---------------------------------------------------------------- 界面对象
-- 满屏纯黑底，把所有能画出"边"的样式全部清零：
-- 手环默认主题会给对象加 1px 边框/外描边/阴影，叠起来就是这个白框
local root = lvgl.Object(nil, {
    x = 0, y = 0, w = W, h = H,
    bg_color = 0x000000, bg_opa = lvgl.OPA(255),
    border_width = 0, border_opa = 0,
    outline_width = 0, outline_opa = 0,
    shadow_width = 0,
    pad_all = 0, pad_top = 0, pad_bottom = 0, pad_left = 0, pad_right = 0,
    radius = 0, scrollable = false, clickable = false,
})
-- 关键：清掉可点击 / 可滚动 flag。
-- 留着它的话，LVGL 会把左右拖动当成"滚动"吃掉，手环固件的滑动切表盘手势就收不到，
-- 表现就是"滑不动、手势不跟手"。
local function untouchable(o)
    pcall(function()
        o:clear_flag(lvgl.FLAG.CLICKABLE)
        o:clear_flag(lvgl.FLAG.SCROLLABLE)
        o:clear_flag(lvgl.FLAG.SCROLL_ON_FOCUS)
    end)
end
untouchable(root)

local pos, srcs, vis = {}, {}, {}

local function at(o, x, y)
    x, y = math.floor(x), math.floor(y)
    local p = pos[o]
    if not p then p = {}; pos[o] = p end
    if p.x ~= x or p.y ~= y then o:set { x = x, y = y }; p.x, p.y = x, y end
end

local function show(o, on)
    if vis[o] == on then return end
    vis[o] = on
    if on then o:clear_flag(HIDDEN) else o:add_flag(HIDDEN) end
end

-- 图片对象也要显式清样式：手环主题会给所有对象套 1px 边框/外描边
local CLEAN = { border_width = 0, border_opa = 0, outline_width = 0, outline_opa = 0,
                shadow_width = 0, pad_all = 0, radius = 0 }

local function glyph_slot(file)
    local o = root:Image { src = DIR .. file,
        border_width = 0, border_opa = 0, outline_width = 0, outline_opa = 0,
        shadow_width = 0, pad_all = 0, radius = 0 }
    srcs[o] = file
    o:add_flag(lvgl.FLAG.EVENT_BUBBLE)   -- 事件冒泡给上层，别自己吞
    untouchable(o)
    at(o, 0, 0)
    show(o, false)
    return o
end

local function paint(o, file, x, y, on)
    if on == false then show(o, false); return 0 end
    if srcs[o] ~= file then o:set { src = DIR .. file }; srcs[o] = file end
    at(o, x, y)
    show(o, true)
    return WID[file:match("([^/]+)%.png$") or ""] or 0
end

-- 图元池：时间 5 格 + 日期 16 格 + 卡片 2 张
local CLOCK_n, DATE_n, CARD_n = 5, 16, 2
local WEEK_n = 4                       -- 「第」+ 数字 + 「周」
local clock_obj, date_obj, card_obj = {}, {}, {}
for i = 1, CLOCK_n do clock_obj[i] = glyph_slot("t0.png") end
for i = 1, DATE_n do date_obj[i] = glyph_slot("d0.png") end
for i = 1, CARD_n do card_obj[i] = glyph_slot("empty_morning.png") end
local week_obj = {}
for i = 1, WEEK_n do week_obj[i] = glyph_slot("di.png") end

-- ---------------------------------------------------------------- 业务逻辑
local function phase_of(minutes)
    if minutes < 12 * 60 then return "morning", "p_morning" end
    if minutes < 18 * 60 then return "afternoon", "p_afternoon" end
    return "evening", "p_evening"
end

local function has_week(list, week)
    for _, v in ipairs(list) do if v == week then return true end end
    return false
end

-- 今天这一段的课，按开始时间排好
local function courses_at(wd, week, phase)
    local out = {}
    for _, c in ipairs(COURSES) do
        if c.day == wd and has_week(c.weeks, week) then
            local p = phase_of(c.from)
            if p == phase then out[#out + 1] = c end
        end
    end
    table.sort(out, function(a, b) return a.from < b.from end)
    return out
end

local function pad2(n)
    return string.format("%02d", n)
end

-- 画时钟 HH:MM
local function draw_clock(hh, mm)
    local s = pad2(hh) .. ":" .. pad2(mm)
    local total = 0
    for i = 1, 5 do
        local ch = s:sub(i, i)
        local key = (ch == ":") and "tc" or ("t" .. ch)
        total = total + (WID[key] or 0)
    end
    local x = math.floor((W - total) / 2)
    for i = 1, 5 do
        local ch = s:sub(i, i)
        local file = (ch == ":") and "tc.png" or ("t" .. ch .. ".png")
        x = x + paint(clock_obj[i], file, x, L.clock_y)
    end
end

-- 画日期：2026年11月3日 周X · 上午
local function draw_date(y, mo, d, wd, phase_key)
    local items = {}
    local function add(t)
        for ch in tostring(t):gmatch("%d") do items[#items + 1] = "d" .. ch end
    end
    local seq = {}
    seq[#seq + 1] = { txt = y, kind = "num" }
    seq[#seq + 1] = { key = "y" }
    seq[#seq + 1] = { txt = mo, kind = "num" }
    seq[#seq + 1] = { key = "mo" }
    seq[#seq + 1] = { txt = d, kind = "num" }
    seq[#seq + 1] = { key = "dd" }
    seq[#seq + 1] = { key = "wk" }
    seq[#seq + 1] = { key = "w" .. wd }
    seq[#seq + 1] = { key = "sp" }
    seq[#seq + 1] = { key = phase_key }   -- 不再画「·」：两位月日时会顶到屏幕边

    local flat, total = {}, 0
    for _, it in ipairs(seq) do
        if it.kind == "num" then
            for ch in tostring(it.txt):gmatch("%d") do
                flat[#flat + 1] = "d" .. ch
                total = total + (WID["d" .. ch] or 0)
            end
        else
            flat[#flat + 1] = it.key
            total = total + (WID[it.key] or 0)
        end
    end
    local x = math.floor((W - total) / 2)
    for i = 1, DATE_n do
        local key = flat[i]
        if key then
            x = x + paint(date_obj[i], key .. ".png", x, L.date_y)
        else
            show(date_obj[i], false)
        end
    end
end

-- 右上角：第 N 周（让"周数算得对不对"一眼可见）
local function draw_week(week)
    local s = tostring(week)
    local seq = { "di" }
    for ch in s:gmatch("%d") do seq[#seq + 1] = "d" .. ch end
    seq[#seq + 1] = "wk"
    local total = 0
    for _, k in ipairs(seq) do total = total + (WID[k] or 0) end
    local x = W - 16 - total
    local y = 14
    for i = 1, WEEK_n do
        local k = seq[i]
        if k then
            x = x + paint(week_obj[i], k .. ".png", x, y)
        else
            show(week_obj[i], false)
        end
    end
end

-- 画课程卡（最多两张）
local function draw_cards(list, now_min)
    for i = 1, CARD_n do
        local c = list[i]
        if c then
            local live = (now_min >= c.from and now_min < c.to)
            local file = live and c.hi or c.normal
            paint(card_obj[i], file, L.card_x,
                  (i == 1) and L.card1_y or L.card2_y)
        else
            show(card_obj[i], false)
        end
    end
end

-- 主渲染：给一个时间戳，把整页画出来（测试也调这个）
local function render(epoch)
    local t = epoch + TZ
    local days = math.floor(t / 86400)
    local secs = t - days * 86400
    local hh = math.floor(secs / 3600)
    local mm = math.floor((secs % 3600) / 60)
    local now_min = hh * 60 + mm

    local y, mo, d = civil_from_days(days)
    local wd = (days + 3) % 7 + 1                  -- 1=周一 … 7=周日
    local week = math.floor((days - SEM_DAYS) / 7) + 1
    local phase, phase_key = phase_of(now_min)

    draw_clock(hh, mm)
    draw_date(y, mo, d, wd, phase_key)
    draw_week(week)

    local list = courses_at(wd, week, phase)
    if #list == 0 then
        paint(card_obj[1], "empty_" .. phase .. ".png", L.card_x, L.card1_y)
        show(card_obj[2], false)
    else
        draw_cards(list, now_min)
    end
    return { y = y, m = mo, d = d, wd = wd, week = week,
             phase = phase, hh = hh, mm = mm, n = #list, list = list }
end

-- ---------------------------------------------------------------- 定时器
local timer = lvgl.Timer {
    period = 60000,                                -- 精度到分钟就够，60 秒一次比 20 秒省 3 倍
    cb = function() pcall(render, os.time()) end,
}

pageOnPause = function() timer:pause() end
pageOnResume = function()
    timer:resume()
    pcall(render, os.time())
end

pcall(render, os.time())

-- 给测试用（手表上没人调用）
WF = { render = render, courses_at = courses_at, civil_from_days = civil_from_days,
       days_of = days_of, phase_of = phase_of, D = D }
