#!/usr/bin/env bash
# 一条命令跑完：体检 → 出今日图 → 导日历
# 用法：./run.sh [主题]     主题：card（默认）/ line / bar
set -euo pipefail
cd "$(dirname "$0")"
THEME="${1:-card}"

echo "① 课表体检"
if ! python3 check.py; then
  echo
  echo "× 数据有问题，先按上面的提示改 config/timetable.json"
  exit 1
fi

echo
echo "② 出今天的图（上午/下午/晚上各一张 + 当前时段那张）"
python3 make_watchface.py --today --all-phases --theme "$THEME" >/dev/null
python3 make_watchface.py --today --auto-phase --theme "$THEME" --mock

echo
echo "③ 导出日历（-20 分钟，响 1 分钟）"
python3 export_ics.py

cat <<EOF

④ 剩下两步要手动（一步是选图，一步是授权）
   传图：./push_to_phone.sh $THEME
         （或微信发给自己）
   装表盘：小米运动健康 → 设备 → 表盘市场 → 相册表盘 → 选 out/today.png
           （或按时间选 today_morning / today_afternoon / today_evening）
   装日历：把 out/课表.ics 发到手机 → 用「日历」打开 → 添加
           再给小米运动健康开「日历」通知权限，手环才会震

   要让电脑也跟着响：python3 remind.py
EOF
