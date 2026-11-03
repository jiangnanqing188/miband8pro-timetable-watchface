# 装 Lua 表盘到小米手环 8 Pro（社区标准流程）

产物：`out/kebiao.face`（724 KB）

> 依据：社区开源表盘集 [band-face-pack](https://github.com/hassan-xsf/band-face-pack) 的
> [INSTALL.md](https://github.com/hassan-xsf/band-face-pack/blob/main/INSTALL.md)，
> 原文在 `re/INSTALL-pack.md`。它自己的说法是：
> "uses Gadgetbridge: free and open source, with no modded Mi Fitness and no cracked apps"

需要：安卓手机 + 手环 auth key + 这个 `.face` 文件。

---

## 一、先和官方 App 配对一次

装小米运动健康（Mi Fitness），登录小米账号，正常配对。

**这一步是必须的**：它把你的手环注册到小米账号下，auth key 就是这时生成的。
**每次重新配对，key 都会变** —— 所以后面取 key 必须在最后一次配对之后。

---

## 二、取 auth key（在电脑上跑，Linux 一行）

用 [Xiaomi Cloud Tokens Extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor)（★4.9k）：

**Linux（你这台机器就能跑）：**
```bash
bash <(curl -L https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor/raw/master/run.sh)
```

**Windows：** 下 [token_extractor.exe](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor/releases/latest/download/token_extractor.exe)

用法：
1. 输入小米账号（邮箱）和密码，或者选二维码登录
2. 选服务器区域：国行填 `cn`，不确定就留空让它全试
3. 列表里找你的手环（形如 `Xiaomi Smart Band 8 Pro`）
4. **`TOKEN` 就是 auth key**，32 位十六进制

> ⚠️ 这个 key 等于手环的钥匙，谁拿到都能连你的手环，别外传。

---

## 三、把官方 App 断开

手机上：设置 → 应用 → 小米运动健康 → **强行停止**（卸载最保险）。

**同一时间只能有一个 App 连着**，不停止的话 Gadgetbridge 连不上。

---

## 四、Gadgetbridge 配对

1. 装 [Gadgetbridge](https://f-droid.org/packages/nodomain.freeyourgadget.gadgetbridge/)
2. 打开，点 **+**，给蓝牙和定位权限
3. 扫到手环后 **长按** 它（不是点）
4. 在 **Auth Key** 里粘贴第二步拿到的 key，返回
5. 点手环配对，手环上让确认就确认

连上能看到电量/步数 = 成功。

---

## 五、装表盘

1. `out/kebiao.face` 传到手机
2. **方式 A**：文件管理器点它 → 打开方式选 Gadgetbridge → **Install**
   **方式 B**：Gadgetbridge → 点手环 → **Watchfaces** → **+** → 选文件
3. 等进度条（小表盘几秒，图多的约 20 秒）
4. 选中它：Watchfaces 里点它 → **Set**，或手环上长按表盘 → 滑到新的 → 点一下

---

## 六、出问题怎么办（社区手册原话整理）

| 现象 | 处理 |
|---|---|
| 配对失败 / authentication failed | key 错或过期。**在最后一次配 Mi Fitness 之后**重跑提取器；确认 Mi Fitness 已停 |
| 扫描找不到手环 | 手机蓝牙关开一次；手机蓝牙设置里把手环取消配对；手环放近 |
| 右键菜单里没有 Gadgetbridge | 改用 Gadgetbridge → Watchfaces → **+** |
| 安装开始后失败 | 重连一次再试；表盘太大可能超时（我的 724KB，不算大） |
| **装上后黑屏** | 是 Lua 启动报错。用 [Band Face Viewer](https://hassan-xsf.github.io/band-face-viewer/) 打开同一个 `.face`，看 Console 的报错 |
| 表盘卡住、点不动 | **不用手环屏幕也能救**：Gadgetbridge → Watchfaces → 点另一张 → Set |
| 出现两张一样的 | ID 不同（那是不同版本），删掉旧的 |

---

## 我的包已经自检的项

```
✓ magic 5aa53412 / 设备 0x800 / faceCount 1 / styleCount 0   （与社区可用表盘逐字节一致）
✓ ID 167200916 / 名称「课表」
✓ JS 资源 74 个 = 73 张图 + main.lua
✓ 回读解包 76 个文件，文件名全保留
✓ Lua 逻辑 34/34（真 Lua VM，测的就是包内那份代码）
```

**没验证的**：8 Pro 在 Gadgetbridge 里是 `untested`，这版固件认不认只有装上去知道。
