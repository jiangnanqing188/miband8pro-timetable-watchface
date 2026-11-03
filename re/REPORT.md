# 逆向调查：课表内容怎么"传"到手环

调查日期 2026-11-03。目标：确认有没有可能把课表内容通过蓝牙写进小米手环 8 Pro。

---

## 结论先说

| 路线 | 能不能传 | 依据 |
|---|---|---|
| **A. 相册表盘**（现在这套） | ✅ 能，唯一现成可用 | 官方 App 功能，图直接传到手环当表盘 |
| **B. Gadgetbridge 刷表盘** | ⚠️ 理论能，8 Pro 官方标注 **untested** | Gadgetbridge 文档明确实现了 `Flashing (watchface, firmware, rpk)` |
| **C. 自己写 BLE 协议** | ⚠️ 能做但风险高 | 需要 Xiaomi protobuf + auth key，工作量大且无真机验证 |

**关键事实：手环表盘只接受"打包好的表盘文件"，不接受"课表数据"。**
所以不管走哪条路，课表都是**先变成一张图 / 一个表盘包**，再整体传过去 —— 不存在"传一条课表数据、手环自己排版"这种事。

---

## 一、关于"逆向超级课程表"

**观察**：超级课程表是课表 App，没有蓝牙、没有手环模块。逆它只能逆出它的数据格式和教务系统解析逻辑，逆不出任何"传手环"的东西。

**阻塞**（为什么这次没做）：
- 本机没有任何 apk：`find ~ -iname "*.apk"` → 0 个结果
- 应用商店拿不到：`d.apkpure.com` → HTTP 403，`apkpure.com` → 403
- 源码仓库不可达：`raw.githubusercontent.com` → 404，`codeberg.org/api` → 连接失败

**REA 需要"已发布的安装包"作为分析对象**，没有产物就只能靠猜 —— 猜出来的协议我不会写进交付物。

---

## 二、开源实现里的真实证据

小米手环 8 Pro 走的是 Xiaomi **protobuf** 协议族（不是老 Mi Band 的 Huami 协议）。

**证据 1** — Gadgetbridge 设备页把 Mi Band 8 Pro 列为未验证：
> Mi Band 8 Pro ¶ Unknown support … It is supported by … has_flag__pair_xiaomi has_flag__experimental
> Also known as the Xiaomi Smart Band 8 Pro. **Untested**, added based on feedback from issue #3471.

来源：<https://gadgetbridge.org/gadgets/wearables/xiaomi/>

**证据 2** — 该协议族已实现的功能里，正好包含我们要的两件事：
> List of features supported by Gadgetbridge
> - Authentication / Encryption
> - Set time (date, time, timezone offset, dst offset, 12h/24h)
> - **Flashing (watchface, firmware, rpk)**
> - **Watchface and app management**
> - **Alarm clock alerts** (a notification is shown on the watch when a phone alarm rings…)
> - **Vibration patterns (experimental)**
> - Apps, calls, custom icons…

来源：<https://gadgetbridge.org/basics/topics/xiaomi-protobuf/>

**证据 2.5** — auth key 拿得到（8 Pro 明确在列）：
> Newer Mi Bands (Mi Band 7 Pro, 8, 8 Active, **8 Pro**, 9, 9 Active, 9 Pro, 10, 10 Pro, 11), Xiaomi and Redmi watches
> The authentication key is stored on Huami servers or in the original Mi Fit / Mi Fitness / Xiaomi Wear / Zepp app's database.

即：8 Pro 的 key 存在官方 App 后端，能用 Zepp 账号 token 取出来（文档给了具体取法）。
所以"连不上"不是卡在 key，是卡在**协议实现**和**设备未验证**。

来源：<https://gadgetbridge.org/basics/pairing/huami-xiaomi-server/>

**证据 3** — 表盘是当固件刷的：
> Watchfaces are uploaded the same way as is a firmware update.

来源：<https://gadgetbridge.org/internals/features/installer/>

### 这三条说明什么

1. **"用蓝牙传表盘"在开源实现里是现成功能**（Flashing watchface），不是天方夜谭。
2. 但 Gadgetbridge 只认**它支持的 .bin 表盘包格式**，它不会读我的 PNG。
3. 8 Pro 在这套实现里是 **untested** —— 没人验证过，包括表盘刷入。

---

## 三、三条路的真实代价

### A. 相册表盘（已交付，今天能用）
- 传的是 PNG，走官方 App，零风险
- 缺点：一张图 = 一天，静态

### B. Gadgetbridge 刷自定义表盘
需要凑齐：
1. 手机装 Gadgetbridge（F-Droid / Codeberg）
2. 用 auth key 配对（从小米运动健康里导出，或重新配对拿 key）
3. **一个 8 Pro 认的 .bin 表盘包** ← 这是卡点，格式在 Gadgetbridge 的 Java 源码里
4. 运气：8 Pro 是 untested，可能直接报错或刷不进去

收益：能做出真正的表盘（不再是一张图的相册表盘），并且能用它的 `Alarm clock alerts` + `Vibration patterns` 做提醒。

### C. 自己实现 BLE 协议
要复刻：连接 → auth 握手（ECDH + token）→ protobuf 帧 → 文件分块传输 + 校验。
没有真机、没有抓到过一包真实流量，做出来 100% 是"看起来对"的代码。**不推荐，我也不交付这种东西。**

---

## 四、要继续往下走，需要什么

| 需要 | 用途 | 怎么给 |
|---|---|---|
| **手机型号 + 是否愿意装 Gadgetbridge** | 决定 B 路线可行性 | 一句话 |
| **auth key**（32 位 hex） | Gadgetbridge 配对手环 | 小米运动健康 → 我的 → 关于（老版本可导出）；或重配对时抓 |
| **一个 8 Pro 的现成 .bin 表盘**（从社区下的任意一个） | 作为逆向样本，比对格式 | 你下载一个丢给我 |
| **超级课程表 APK**（如果你还想逆它） | 看它怎么存课表，做导入适配 | 手机里 `adb pull` 或直接给我文件路径 |

其中**第 3 项最关键**：有一个真实 .bin 样本，我就能把它的结构拆出来（包头 / 资源表 / 图片编码），
再决定能不能按同样的格式生成 —— 这比盲猜协议靠谱一百倍。

---

## 四·五、本机蓝牙实测（2026-11-03 04:25）

```
Controller E8:65:38:EC:64:26 jnq-Legion-R9000P-ARX8
扫描 12 秒 → 发现 8 个设备，无手环
（TWS 耳机、邻居的手机/笔电、"LAPTOP-28U48HT4" 等）
```

结论：笔记本蓝牙可用，但**手环当时不在广播状态**（正常——它正连着手机）。
诊断脚本：`./ble_probe.sh 25`（手环需先从手机断开、放到电脑旁）。

## 五、当前状态一句话

课表 → 图 → 手环：**通了**（相册表盘）。
提醒 -20 分钟振动 1 分钟：**通了**（日历重复提醒，通知镜像）。
课表内容直传手环：**卡在"没有 8 Pro 的 .bin 样本 + 没有真机"**，不是卡在思路。


---

# 追加调查：课简（CurSimple）能不能"二次开发"

2026-11-03。线索来源：<https://cursimple.github.io/cursimple-app/>

## 对象确认

课简 = **CurSimple**，开源安卓 App，仓库 <https://github.com/cursimple/cursimple-app>，
当前版本 v0.8.1，五种 ABI 的 APK。

## REA 没能跑起来（两条都断了）

| 尝试 | 结果 |
|---|---|
| 下载 APK（gh-proxy / 直连 releases） | **0 字节**，下载被挡 |
| 注册 REA MCP server（`open_binary` / `inspect_android_package`） | 工具集里**没有** REA 服务 |

没有产物、没有分析引擎，REA 无从下手——这一步如实记下，不猜。

## 但读到了更好的东西：官方插件文档

`docs/plugin-system.md`（原文在仓库里，可直接拉）：

> Plugins are independent ZIP bundles executed through a restricted WebView.
> The host owns installation, permissions, persistence and scheduling;
> **each bundle owns its school or service protocol.**

也就是说课简的插件是"**导入器**"：从教务系统网页抓课表，走 `ctx.web.queryAll` →
`ctx.schedule.addCourse` → `ctx.schedule.commit`；或者做 extension 组件订阅通知/内容。

**关键负面结论**：把整份 API 表翻完，插件拿不到"读现有课表"的接口——
`ctx.schedule` 只有写入草稿，没有读取；owned page 的命令表里也没有 schedule 读操作。
所以「写个课简插件，读课表 → 画表盘 → 存图」这条路**不成立**，不是我不会写，是没这个 API。

（API 12 的 "component-provided app layouts drawn natively by the host" 是给 feed 内容排版用的，
不是课表。）

## 真正的答案在 README 第 98 行

> 课表支持二维码、分享字符、图片、系统日历写入和 **`.ics` 导出**

课简自己就能把课表导成 `.ics`。于是链路变成：

```
课简导课 → 导出 .ics → import_kebiao.py 解析 → config/timetable.json → 出表盘
```

`import_kebiao.py` 已加上 `.ics` 解析：

- `DTSTART` / `DTEND` 的时间 → 第几节（按作息表就近匹配，差 30 分钟内算命中）
- 事件日期 → 第几教学周（配 `meta.semester_start`；没有就按最早一门课那周算第 1 周并警告）
- `RRULE COUNT=16` → `1-16`；`UNTIL` → 截止周
- `SUMMARY:高等数学 A（教三-201）` → 课名 + 教室
- 折行（续行空格）、`VALARM` 嵌套块、转义字符都按 RFC 5545 处理

**验证**：拿自己导出的 `.ics` 再读回来，17 门课的课名/星期/节次/周次/教室
**17/17 完全一致**（往返测试）。

## 这条路 vs 逆 APK

| | 逆 APK / 改插件 | 官方 .ics |
|---|---|---|
| 可行性 | APK 拿不到；插件无读取 API | ✅ 现成功能 |
| 维护成本 | 课简一升级就可能废 | 稳定（iCalendar 标准） |
| 需要手机权限 | 可能要 root / 抓包 | 无 |

结论：**数据源这条线用 `.ics` 打通了**；剩下的"传表盘"仍受第 3 节的三层限制。


---

# 重大更正：8 Pro 表盘是 Lua 程序，有开源打包工具

2026-11-03 复查。**修正前面"私有二进制格式、社区工具覆盖不到、无法验证"的判断——那是错的。**

## 事实（都有出处）

**1. 8 Pro 的表盘是"Lua 脚本 + 资源"，不是不可解析的二进制黑盒**

`zhy8388608/Mi8WfBinTool`（Java，命令行，解包/打包 `.bin`）的支持表里明确写了：

| 设备 | 代号 | 参数 | 格式 |
|---|---|---|---|
| 小米手环 8 Pro | `lchz.watch.m67` | `mi8pro` | 二进制，头部偏移 `0xA8`，RLE V2.0 索引色压缩 |

同一工具还覆盖 8/9/10、红米手表 4/5/6、手表 S3/S4/S5。

**2. 表盘里跑的是 Lua，能在浏览器里完整模拟**

`hassan-xsf/band-face-viewer`：把 `.face` 解包，`main.lua` 跑在 fengari（JS 写的 Lua VM）上，
`lvgl_shim.lua` 提供手环的 `lvgl` / `dataman` API，映射到 canvas。
**8 Pro 明确支持，屏幕 336×480**（和我出图的尺寸一致）。
它能喂假数据（时间/日期/电量/步数/心率/天气），能看 Lua 报错行号，能导出 PNG 当预览图。

**3. 安装靠 Gadgetbridge，不用 root、不用改官方 App**

`hassan-xsf/band-face-pack` README 原文：

> **Install with Gadgetbridge: no root, no modded apps.**

步骤：下载 `.face` → 手机上用 Gadgetbridge 打开 → Install → 手环上长按表盘切过去。
配 Gadgetbridge 的官方文档同样写着 Xiaomi protobuf 设备支持 `Flashing (watchface, firmware, rpk)`。

**4. 另一条老路（针对旧设备）**

`Mino260806/mi-watchface-uploader`：LSPosed 模块，hook 小米运动健康，
把 `Android/data/<pkg>/files/WatchFace/custom_watchface` 顶替成要下载的表盘包。
实测过 Redmi Watch 2 Lite；**Smart Band 7 Pro 明确"not working yet"**，8 Pro 未提及。★23，2023 年后没更新。
这条对 8 Pro 不可靠，仅作背景。

## 关于"上传到官方"

据我看到的资料，**普通人的自定义表盘并不是"上传到官方表盘市场"**——官方商店只有官方/合作设计师的内容。
社区的实际做法就是上面第 3 条：**本地打包成 `.face`，用 Gadgetbridge 直接推进手环**。
（这一条我没有拿到小米的官方文档原文，是综合社区项目的描述，你查的时候可以重点核这个点。）

## 对项目的意义

之前走"相册表盘 + 静态 PNG"是因为以为只能这样。现在知道表盘是 Lua 程序，意味着：

- 表盘**能读设备时间** → 可以高亮"现在上的是哪节"、显示"距离下课 12 分钟"
- 表盘**是程序** → 课表数据可以写进 Lua 变量，打包时生成，不依赖手机
- **验证不需要真机** → band-face-viewer 能跑，我可以先在这里把逻辑调通，再让你装

## 下一步（等我做）

1. 按 `.face` 结构做一个"课表表盘"：Lua 里带课表数组，按当前时间渲染今天的课
2. 用 band-face-viewer 本地跑通（`python serve.py` → 127.0.0.1:8770）
3. 你那边：手机装 Gadgetbridge、配对 8 Pro（要 auth key），我去把 `.face` 调通


---

# 落地：Lua 表盘做出来了（含打包，已解决）

## 已完成的验证链

| 环节 | 状态 | 证据 |
|---|---|---|
| `.face` 容器格式 | ✅ 已解析 | 主头 `0xA8`：magic `5AA53412`、device、faceCount、previewOffset、id@`0x28`、name@`0x68` |
| Lua 表盘源 | ✅ 写好 | `wf/app/lua/main.lua`，时间/日期/教学周全部 `os.time()` 现算 |
| 逻辑正确性 | ✅ 34/34 | `node wf/test/run_test.mjs`，在真 Lua VM（fengari）里跑 |
| 素材 | ✅ 73 张 | `wf/gen_assets.py`：36 图元 + 37 课程卡（含高亮版）+ 3 没课图 |
| 画面 | ✅ 已合成 | `wf/preview_*.png`，同一套素材同一套坐标 |
| 打包成 `.face` | ⚠️ 半成品 | `out/kebiao.face` 117KB，头正确、Lua 正确，**缺图片资源** |

## 三个卡点，逐个记录

**1. EasyFace Compiler 在 Linux 跑不了**
`Compiler.exe` 是 .NET，但依赖 `Magick.NET-Q16-x64.Native.dll`（Windows 原生 ImageMagick）。
mono 能让它启动、能读 `.fprj`，然后死在图像子系统，报 `images path is not found`
——这个报错是假线索，真因是原生库加载不了。
→ 要 Windows，或 wine。

**2. Mi8WfBinTool 解包有 bug（已修）**
`if (!namedFaces || hasAnyAod)` 会对单表盘也去读第 2 个（AOD）面，直接读到文件尾崩掉。
改成 `if (namedFaces ? hasAnyAod : (faceCount > 1))` 之后，社区表盘能正常解出
`wfDef.json` + 全部图元。**这个补丁是解包任何社区 Lua 表盘的前提。**

**3. 打包器不收 Lua 表盘的图片（未解决）**
`wfDef.json` 里 Lua 表盘只有一个元素：
```json
{"type":"type_element_lua","x":0,"y":0,"jsFileName":"lua/main.lua"}
```
打包器按"元素引用的资源"收集图片 → 我的 73 张卡一张都没进包。
而 EasyFace 的做法是把 `app/lua/` 整个目录当作素材一起打包
（stride 那个表盘 195 张图、定义表里同样只有一个元素）。
→ 要么用 EasyFace 编译，要么给 wfDef 补上"素材清单"字段（格式未公开，需要再逆）。

## 一句话

表盘逻辑和画面都对了，**差一个能正确收素材的打包器**。
最短路径：把 `wf/build/face/` 拷到 Windows，EasyFace 打开 `module.fprj` 编译，2 分钟的事。


---

# 续：打包问题解决了

## 根因

`Mi8WfBinTool` 打包时只收"被元素引用"的图元。
Lua 表盘的 wfDef 里只有一个元素：

```json
{"type":"type_element_lua","jsFileName":"lua/main.lua"}
```

`buildFace()` 里图片来自 `e.get("image")`，Lua 元素没有 image 字段 → 一张都不收。
而 `addUnreferencedFixedResources()` 只收**固定索引**的图（`fixedImageIndex(n) >= 0`），
我这种 `t0.png` / `c0.png` 自定义命名不在其中。

## 解法：元素的 `jsImgList`

翻 `buildFace()` 发现它认这个字段：

```java
for (Object item : arr(e.get("jsImgList"))) {
    String name = str(item);
    JSResourceBytes res = loadJSResource(imgDir, name);
    addSingle(f.js, f.uniqueImages, seen, res.name + "_" + elIndex, -1, jsResource(res.name, res.bytes));
}
```

把 `images/lua/*.png` 全列进 `jsImgList`，打包器就把它们当 Lua 资源块收进包了。

## 附带解决：data.lua 丢文件

`jsImgList` 只列了 png，`data.lua` 不进包。与其再补一个文件，
改成**打包时把数据内联进 main.lua**（`local DATA_INLINE = (function() ... end)()`），
手环上只留一个 .lua —— 少一个文件少一个出错点。测试环境仍可退回 `dofile`。

## 结果

```
$ ./wf/build.sh
① 生成素材与数据表      73 张卡 + 36 个图元
② 组装工程（数据内联）
③ 准备打包源            素材 73 张 + main.lua
④ 打包                  Packed 740922 bytes
⑤ 校验
   ✓ magic 5aa53412      ✓ 设备标志 0x800
   ✓ 表盘数 1            ✓ ID 167200916
   ✓ 名称=课表            ✓ 图片数量 73 张
   ✓ 体积 723 KB
```

产物 `out/kebiao.face`：
- 回读解包 → 76 个文件（73 张图 + main.lua + preview + wfDef）
- 内联版 main.lua 过 34/34 逻辑测试（和源码版同一套断言）

## 仍未验证的

- **没上真机**。结构比对、回读、逻辑测试都过了，但"手环认不认"只有装上去才知道。
- 安装方式：`.face` 传到手机 → Gadgetbridge 打开 → Install → 手环长按表盘切换。
