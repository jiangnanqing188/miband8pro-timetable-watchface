#!/usr/bin/env bash
# 把表盘图片和日历推到手机上（USB 数据线 + 开发者模式）
# 用法：./push_to_phone.sh [主题]     默认 card
set -euo pipefail

THEME="${1:-card}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/out/theme_$THEME"
[ -d "$SRC" ] || { echo "没有这个主题：$SRC"; exit 1; }

command -v adb >/dev/null || { echo "没装 adb：sudo apt install android-tools-adb"; exit 1; }
DEV=$( { adb devices 2>/dev/null || true; } | awk 'NR>1 && $2=="device" {print $1; exit}' )
if [ -z "${DEV:-}" ]; then
  cat <<'EOF'
没检测到手机。要做三件事：
  1. 手机「设置 → 关于手机 → 连点版本号 7 次」打开开发者模式
  2. 「开发者选项 → USB 调试」打开
  3. 数据线连电脑，手机上点「允许调试」

看不到设备时先跑： adb kill-server && adb devices
EOF
  exit 1
fi

DEST="/sdcard/Download/课表表盘"
adb -s "$DEV" shell mkdir -p "$DEST"
FILES=("$HERE/out/today.png" "$HERE"/out/today_*.png "$HERE/out/课表.ics" "$SRC"/watchface_*.png)
for f in "${FILES[@]}"; do
  [ -f "$f" ] && adb -s "$DEV" push "$f" "$DEST/" >/dev/null && echo "  → $(basename "$f")"
done

cat <<EOF

已推到手机：$DEST
接下来（这一步真的走蓝牙，由小米运动健康完成传输）：
  小米运动健康 → 设备 → 表盘市场 → 相册表盘 → 选刚推过去的那张图 → 同步
日历：手机「文件管理」找到 课表.ics → 用日历打开 → 添加到日历
EOF
