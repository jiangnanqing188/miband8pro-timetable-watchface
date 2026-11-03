# 小米手环 8 Pro · 课表表盘

两条实现路线，都在这个目录里：

| 路线 | 产物 | 状态 |
|---|---|---|
| **A. 相册表盘**（静态图） | `out/today*.png` | ✅ 可用，零风险 |
| **B. Lua 表盘**（真程序） | `out/kebiao.face` | ✅ 已在小米手环 8 Pro 真机跑通 |

B 更强：时间、日期、教学周都是 `os.time()` 现算，能高亮"正在上的那节课"，
7/12/18 点自动切上午/下午/晚上。A 是保底方案，今天就能戴。

---

## 三分钟上手

```bash
python3 app.py        # 或双击 启动面板.sh，浏览器自动打开
```

面板里做四件事：**导入课表（.ics / Excel）→ 改 → 保存并生成 → 推到手机**。
手机上会自动调起「打开方式」，选 Gadgetbridge 就能装。

命令行党也可以：

```bash
python3 add_class.py add "高等数学" -d 1 -p 1-2 -r 教三201   # 加课
python3 import_kebiao.py 课表.ics                            # 导入
./wf/build.sh                                                # 打包
adb push out/kebiao.face /sdcard/Download/                   # 推手机
```

---

## B. Lua 表盘（推荐）

```bash
./wf/build.sh          # 素材 → 工程 → 打包 → 校验，一条命令
```

产物 `out/kebiao.face`（约 900 KB），装法：

1. 传到手机
2. 用 **Gadgetbridge** 打开这个文件 → Install
3. 手环上长按表盘 → 滑到新的那张 → 点一下

```bash
node wf/test/run_test.mjs           # 34 项逻辑测试（真 Lua VM）
node wf/test/run_test.mjs --built   # 测打进包里的那个版本
python3 wf/preview.py               # 合成预览图 wf/preview_*.png
```

**结构**：`wf/gen_assets.py`（素材）→ `wf/app/lua/main.lua`（逻辑）→
`wf/make_project.py`（内联数据、组装）→ `wf/build.sh`（调 Mi8WfBinTool 打包）。

---


抬手看课表。屏幕上只有三样东西：**手环自己画的时间**、**日期**、**今天的课**。
步数、心率、卡路里、老师、节次角标 —— 全不画。

```
┌──────────────────┐
│                  │
│     10:24        │  ← 手环画的，永远准，我留了 104px 空白给它
│                  │
│  2026年11月4日 周三 │  ← 我画的
│ ───────────────  │
│ ▌08:00 大学物理    │  ← 我画的：时间 / 课名 / 教室
│ ▌10:00 数据结构实验 │
│ ▌14:00 马克思主义…  │
│ ▌16:00 体育        │
└──────────────────┘
```

---

## 一、先挑界面（三套都做好了）

| 方案 | 命令 | 风格 |
|---|---|---|
| **卡片** | `--theme card` | 深色卡片 + 左侧色条，层次最清楚 |
| **极简** | `--theme line` | 纯黑底 + 只靠细线分隔，最省电、最像系统原生 |
| **时间轴** | `--theme bar` | 一条竖线串起今天的课，圆点是节点 |

**→ 打开 `out/index.html` 对比三套**（带"装到手表上长什么样"的模拟图）。

```bash
python3 make_watchface.py --theme card --preview        # 生成你所选的那套
```

其他参数：

```bash
--week 10        第几周（默认读 config 里的 current_week）
--clock bottom   手环把时间画在底部时用
--clock-h 120    时间被压到日期了，就把留白调大
--day 3          只生成周三
--mock           额外输出 mock_*.png（模拟手环时间叠上去的效果）
```

**为什么图里没有时间**：时间必须由手环自己画，图是死的、时间是活的。
图上留白，手环把 `10:24` 叠上去 —— 时间永远准，还省得每天换图。

---

## 二、装到手表上

```bash
# 1. 生成（以卡片风格为例）
python3 make_watchface.py --theme card --preview

# 2. 传到手机（USB 数据线 + USB 调试打开）
./push_to_phone.sh card
#    或者手动：把 out/theme_card/watchface_周X.png 用微信发给自己

# 3. 手机上：小米运动健康 → 设备 → 表盘市场 → 相册表盘 → 选图 → 同步
```

到第 3 步才真正走蓝牙 —— 是小米运动健康用蓝牙把图传到手环的。第三方 App 没法绕过它。

**建议**：主表盘用 `watchface_week.png`（一周五天全在图上，装一次不用再管），
哪天课特别满，把当天那张换上，看完再换回来。

---

## 三、数据从哪来（课简 → .ics → 一键导入）

**课简（CurSimple）原生支持导出 `.ics`**，这是最顺的一条路：

```
课简里导好课  →  导出课表 .ics  →  python3 import_kebiao.py 课简.ics  →  ./run.sh
```

```bash
python3 import_kebiao.py 课表.ics        # 读 SUMMARY/DTSTART/RRULE，自动映射成节次和周次
```

`.ics` 解析覆盖了真实导出的各种写法（`tests/ics_test.py` 有 8 个场景，全过）：

| 情况 | 处理 |
|---|---|
| `DTSTART;TZID=Asia/Shanghai:` | 按墙上时间用 |
| `DTSTART:...Z`（UTC） | 自动换算成 +8，否则每节课都会错到凌晨 |
| `RRULE COUNT=16` | → 1-16 周 |
| `RRULE INTERVAL=2`（**单双周**） | → 1,3,5,7… 不是连着 8 周 |
| `RRULE UNTIL=` | → 到那一周为止 |
| 一节课一个 VEVENT（逐次导出） | 16 条自动合并成"1-16 周" |
| `EXDATE`（停课） | 从周次里扣掉 |
| `SUMMARY:高等数学（教三-201）` | 括号拆成教室；有 `LOCATION` 以它为准 |
| 折行、`\,` 转义、`VALARM` 嵌套 | 按 RFC 5545 处理 |

往返测试（自己导出再读回）17 门课全部一致。

其他格式也都认：



```bash
python3 import_kebiao.py 课简导出.json       # 或 .csv / .xlsx / .txt / .ics
```

自动认这些列名：课程/课程名称/name、星期/周几/weekday、节次/period/periods、
周次/weeks、教室/地点/room、老师/teacher。节次写 `1-2`、`第3-4节`、`1,2` 都行，
周次写 `1-16`、`1-8,10-16`、`[1,2,3]` 都行。

> **关于"基于课简二次开发"**：课简（[cursimple/cursimple-app](https://github.com/cursimple/cursimple-app)
> ，Apache 开源）确实有插件系统——插件是 ZIP 包、跑在受限 WebView 里。
> 但我读了它的插件 API 文档：插件只干两件事——**从教务系统网页抓课表**（`ctx.schedule.addCourse`）
> 和**订阅内容/通知**（extension 组件）。**没有"读取现有课表交给页面渲染"的接口**，
> 所以"写个课简插件直接出表盘图"这条路走不通，见 [`re/REPORT.md`](re/REPORT.md)。
>
> 真正能用的是它自带的 `.ics` 导出——数据出来，我这边接住，一样是闭环。

---

## 四、上课前 20 分钟提醒

### ① 手上/电脑上（立刻能用）

```bash
python3 remind.py --dry-run     # 先看今天几点会提醒
python3 remind.py --test        # 试响一次，确认声音+弹窗正常
python3 remind.py               # 常驻，到点就响
```

到点前 20 分钟开始：弹窗 + 双音提示音，**每 5 秒一次、连续 60 秒**（共 12 次），
不点掉就一直吵。可以改：

```bash
python3 remind.py --lead 20 --duration 60     # 提前 20 分钟，响 60 秒
```

> 注意：桌面弹窗走 D-Bus，我这边在沙箱里跑会被系统拒（`Could not connect: Permission denied`），
> 你在自己的终端里跑就正常。声音走 PulseAudio/ALSA，不受影响。

### ② 手环上（真能震的那个）

```bash
python3 export_ics.py            # 生成 out/课表.ics
```

每节课一条每周重复日程，VALARM 写成：

```
TRIGGER:-PT20M      ← 提前 20 分钟
REPEAT:11
DURATION:PT60S      ← 60 秒内响 12 次，约每 5 秒一次
```

手机日历每次响 → 小米运动健康把通知镜像到手环 → 手环震一次，
1 分钟内震十来次，这就是"振动一分钟"能做到的最好效果。

1. `out/课表.ics` 发到手机 → 用「日历」打开 → 添加到日历
2. 小米运动健康 → 设备 → 消息通知 → 允许「日历」

> **能力边界，说明白**：手环不能被第三方 App 直接写。写通知、设闹钟都得走
> 厂商协议（还要账号 auth key），振动时长由固件决定，单次最长两三秒。
> 想靠反复触发凑时长，就只能走日历通知这条路 —— 上面的写法是它能支持的极限。

---

## 4.5、只要当天的：一条命令出一张

```bash
python3 make_watchface.py --today --theme card    # → out/today.png
python3 make_watchface.py --date 2026-11-05       # 也可以指定某天
python3 make_watchface.py --cron                  # 打印每天自动出图的 crontab
```

`--today` 会自动从日期算出**周几 + 第几周**，导出的图直接叫 `today.png`，
传手机时永远传这一个文件，不用在相册里找。

配合每天定时跑，就变成"每天早上自动生成今天的课表"：

```
30 6 * * *  cd "~/桌面/小米手环表盘" && python3 make_watchface.py --today --theme card
```

**注意**：生成完还是要手动传一次（相册表盘只能人工选图），所以建议
`--today` 出图后再让 `remind.py` 早上提一嘴"今天的图好了，去换一下"。

---

## 4.5.5、时间显示不对？先标定

手环把时间画多大、画在哪，固件说了算，我只能留白。留错了会压到日期：

```bash
python3 make_watchface.py --calibrate      # 出 5 张不同留白的样张
```

打开 `out/calibrate/index.html`，5 张一起传到手机、逐张试，
看哪个**灰框刚好框住系统时间**，然后：

```bash
python3 make_watchface.py --today --clock-h 112    # 换成那个值
```

### 按时段出图：上午 / 下午 / 晚上

课多的时候一张图塞不下（8 门课挤在一起，时间会被裁掉），拆成三个时段就好了：

```bash
python3 make_watchface.py --today --all-phases     # 三张 + 挑选页 out/phases.html
python3 make_watchface.py --today --phase afternoon  # 只要下午那张
python3 make_watchface.py --today --auto-phase       # 按现在几点自动选
```

| 时段 | 时间范围 | 文件 |
|---|---|---|
| 上午 | 07:00 – 12:00 | `today_morning.png` |
| 下午 | 12:00 – 18:00 | `today_afternoon.png` |
| 晚上 | 18:00 – 23:59 | `today_evening.png` |

日期行会标出来："2026年11月3日 周二 · 上午"。**每张只画这个时段的课**，
所以字能放大、教室也不再被挤掉。没课就写"晚上没课"。

每个时段只有 1–2 节课时，走**大字版**：课名 28px、时间 20px、教室 14px，
内容块垂直居中，抬手一眼就能读完。三节课以上自动缩到 19px 并保留全部信息，
八节课也能看清（只是会砍掉结束时间和教室）。

**自动跟着时间换**（推荐）：`remind.py` 已经内置了。
它每 15 秒看一次表，到 7 点 / 12 点 / 18 点会自动重新出一张当段的图，
并弹窗提醒你去换表盘：

```bash
python3 remind.py        # 一个进程同时管：换时段出图 + 课前 20 分钟提醒
```

只想换图不提醒，就挂 crontab：

```
*/30 6-23 * * *  cd "~/桌面/小米手环表盘" && python3 make_watchface.py --today --auto-phase
```

---

## 4.6、"能不能直接把课表传进手环"—— 有调查结论

见 [`re/REPORT.md`](re/REPORT.md)。一句话：

- **能传的只有"表盘文件"，不是"课表数据"** —— 课表必须先变成图或 .bin 包
- 开源实现 Gadgetbridge 确实实现了 `Flashing (watchface)`，但它只认自己的 .bin 格式，
  而且 8 Pro 在那套实现里官方标注 **untested**
- 想走这条路，我需要一个**现成的 8 Pro .bin 表盘**当样本去拆格式，以及一台能连上的真机

---

## 五、命令速查

| 想干什么 | 命令 |
|---|---|
| 出图 | `python3 make_watchface.py --theme card --preview` |
| 换周 | `python3 make_watchface.py --week 10` |
| 导入课表 | `python3 import_kebiao.py 课表.csv` |
| 传到手机 | `./push_to_phone.sh card` |
| 电脑端提醒 | `python3 remind.py`（`--test` 试响，`--dry-run` 预览） |
| 手环端提醒 | `python3 export_ics.py` → 导入手机日历 |
| 只出当天 | `python3 make_watchface.py --today` → `out/today.png` |
| 一键跑完 | `./run.sh card`（体检 → 出图 → 导日历） |
| 时段图 | `python3 make_watchface.py --today --all-phases` |
| 自动跟时间换 | `python3 remind.py`（7/12/18 点自动换图并提醒） |
| 课表体检 | `python3 check.py`（查冲突/错节次/超长课名） |
| 标定时间留白 | `python3 make_watchface.py --calibrate` → `out/calibrate/index.html` |
| **全部自检** | `./tests/run_all.sh`（39 项：逻辑 + ICS + 图规格） |
| 每天自动出图 | `python3 make_watchface.py --cron` → 复制那行到 crontab |
| 三套对比页 | `python3 preview_all.py` → `out/index.html` |

---

## 六、文件

```
小米手环表盘/
├── config/timetable.json     课表数据（也可以由 import_kebiao.py 生成）
├── make_watchface.py         出图：三套主题 / 时钟留白 / 模拟预览
├── import_kebiao.py          导入：json / csv / xlsx / txt
├── export_ics.py             课表 → .ics（-20 分钟，响 1 分钟）
├── remind.py                 电脑端提醒引擎
├── check.py                  课表体检：冲突 / 错节次 / 超长课名 / PNG 规格
├── add_class.py              加课/改课/删课（索引稳定，可按键名操作）
├── editor.html               手机浏览器里加课 + 出图（单文件）
├── ble_probe.sh              扫附近蓝牙，看电脑能不能发现手环
├── tests/                    自检：run_all.sh · logic_test.mjs · ics_test.py
├── run.sh                    一条命令：体检 → 出今日图 → 导日历
├── make_calibrate_page.py    时钟留白标定页
├── preview_all.py            三套界面 + 一周总览的对比页
├── push_to_phone.sh          adb 推到手机
├── re/REPORT.md              逆向调查：课表到底能不能蓝牙传进手环
├── samples/                  三种格式的课表样例，照着填
└── out/
    ├── index.html            ★ 先看这个：三套方案对比
    ├── theme_card|line|bar/  三套主题的图
    ├── watchface_*.png       card 主题的主输出
    └── 课表.ics
```

---

## 七、已知限制

- 图是**静态**的，不会高亮"现在上的是哪节"，也不显示倒计时 —— 那是原生表盘的事，做不了
- 一周总览里格子小，课名会压缩（"大学英语（三）"→"大学英语"），详情图是全名
- 日历的"响 12 次"要靠手机日历支持 `REPEAT`/`DURATION`（Google 日历、小米日历都支持），
  有的第三方日历只响一次
- 手环上时间的大小、位置由固件决定，位置不对就调 `--clock-h` / `--clock bottom`


---

## 目录结构

```
app.py                  可视化面板（浏览器操作，标准库实现）
add_class.py            命令行加课/改课/删课
import_kebiao.py        课表导入：.ics / .csv / .xlsx / .json / .txt
check.py                课表体检（撞课、错节次、超长课名）
export_ics.py           课表 → 日历（-20 分钟提醒，共 1 分钟）
remind.py               桌面提醒（课前 20 分钟响 60 秒）
make_watchface.py       静态表盘出图（相册表盘路线）
editor.html             手机浏览器里手改课表 + 出图
wf/                     Lua 表盘：素材生成 → 打包 → 测试
  gen_assets.py         把课表渲染成图元 + 数据表
  app/lua/main.lua      表盘逻辑（时间/周次/当前课，全用 os.time 现算）
  build.sh              调 Mi8WfBinTool 打包成 .face
  test/run_test.mjs     Lua 逻辑测试（fkengari 真跑）
tests/                  自检脚本（./tests/run_all.sh）
re/                     调研记录：表盘格式、课简插件 API、手环协议
```

## 依赖

- Python 3.9+，`Pillow`
- Java（打包用）：[Mi8WfBinTool](https://github.com/zhy8388608/Mi8WfBinTool) —— 需自行下载到 `re/`，并改两处（详见 [re/REPORT.md](re/REPORT.md)）：
  1. `readFace` 里单表盘不该读第 2 个 AOD 面 → `if (namedFaces ? hasAnyAod : (faceCount > 1))`
  2. `writeHeader` 单表盘 `styleCount` 应为 0 → `aod ? faceCount + 2 : 0`
- Node（测试用）：`npm i fengari` 到 `wf/`
- 安卓端：[Gadgetbridge](https://gadgetbridge.org/)（不需要 root）

## License

MIT


---

## 关于上课提醒：能做到什么，做不到什么

**能做的**（两条路，都验证过）：

1. **写进手机日历**，课前弹通知 → Gadgetbridge 镜像到手环 → 手环振动

   ```bash
   python3 tools/push_calendar.py --dry-run   # 先看会写什么
   python3 tools/push_calendar.py             # 直接写进手机日历（走 adb，不用点屏幕）
   python3 tools/push_calendar.py --clear     # 删掉之前写的（标题带 [课表] 前缀）
   ```

   每条日程带 5 个提醒（提前 20~16 分钟，每分钟一次），
   也就是 5 分钟内连续振 5 下。

2. **电脑端提醒**：`python3 remind.py`，课前 20 分钟弹窗 + 响铃 60 秒。

**做不到的**：让手环一次连续振动 60 秒。

手环单次振动只有 2-3 秒，**时长由固件写死**，任何 App 都改不了；
日历提醒的最小粒度是 1 分钟，所以最多做到"每分钟振一下"。
真要长振动，只能用**手环自带的闹钟**（会一直振到你按掉），
但那是每节课手动设一个，不适合每天 5 门课。

写这篇不是为了免责，是因为网上很多"手环振动一分钟"的教程其实是
把通知连发几次当成"一直振"，实机上就是几下短振。
