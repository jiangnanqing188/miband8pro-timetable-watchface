#!/usr/bin/env bash
# 一条命令做完所有"能用命令做"的事，剩下的手机上的点击由你完成
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APK="$HERE/gadgetbridge-2026.11.0.apk"
FACE="$(cd "$HERE/.." && pwd)/out/kebiao.face"

echo "① 检查手机连接"
DEV=$(adb devices | awk 'NR>1 && $2=="device"{print $1; exit}')
if [ -z "${DEV:-}" ]; then
  ST=$(adb devices | awk 'NR>1{print $2; exit}')
  if [ "${ST:-}" = "unauthorized" ]; then
    echo "  手机没授权：看手机屏幕，点「允许 USB 调试」→ 再跑一次"
  else
    echo "  没检测到手机：检查数据线（要能传文件那种，不是纯充电线）"
  fi
  exit 1
fi
echo "  ✓ $DEV"
echo "  型号: $(adb -s "$DEV" shell getprop ro.product.model 2>/dev/null | tr -d '\r')"

echo "② 装 Gadgetbridge"
if adb -s "$DEV" shell pm list packages 2>/dev/null | grep -q "nodomain.freeyourgadget.gadgetbridge"; then
  echo "  已安装，跳过"
else
  adb -s "$DEV" install -r "$APK" | tail -1
fi

echo "③ 推表盘文件"
adb -s "$DEV" push "$FACE" /sdcard/Download/ | tail -1

echo "④ 打开 Gadgetbridge"
adb -s "$DEV" shell monkey -p nodomain.freeyourgadget.gadgetbridge -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 \
  && echo "  已启动"

cat <<'EOF'

────────────────────────────────────────
下面这几步只能你在手机上点（我这里碰不到手机屏幕）：

1. 点右下 + ，允许「蓝牙」和「定位」权限
2. 扫描列表里找 <你的手环MAC>（你的手环 MAC）
3. 长按它（不是点）→ 弹出框里粘 Auth Key → 返回
4. 点手环 → 配对 → 手环上确认
5. 配对成功后：文件管理 → Download → kebiao.face
   → 打开方式选 Gadgetbridge → Install
6. Watchfaces 里点「课表」→ Set

装完出问题就把日志导出来：
Gadgetbridge → 设置 → 调试 → 导出日志
────────────────────────────────────────
EOF
