#!/usr/bin/env bash
# 扫描附近的蓝牙设备，看看能不能发现手环
# 用法：./ble_probe.sh [扫描秒数，默认 15]
set -uo pipefail
SECS="${1:-15}"
WORK="$(cd "$(dirname "$0")" && pwd)"
LOG="$WORK/re/ble_scan_$(date +%H%M%S).log"

command -v bluetoothctl >/dev/null || { echo "没装 bluetoothctl：sudo apt install bluez"; exit 1; }

if ! bluetoothctl list 2>/dev/null | grep -q Controller; then
  echo "× 没有可用的蓝牙控制器。检查：rfkill list / 是否被硬件开关关掉"
  exit 1
fi

echo "蓝牙控制器："
bluetoothctl list | sed 's/^/  /'
echo
echo "扫描 ${SECS} 秒……（手环要处于「未连接手机」状态才会广播）"
bluetoothctl --timeout "$SECS" scan on > "$LOG" 2>&1
echo "  → 原始日志：$LOG"

# 解析发现到的设备
# 只取「Device MAC 名称」这种首行，排除 RSSI/ManufacturerData 之类的属性续行
mapfile -t DEVS < <(grep -oE 'Device [0-9A-F:]{17}[^:]*' "$LOG" \
  | grep -vE 'RSSI|Manufacturer|ServiceData|UUID|TxPower|Name:|Alias' | sort -u)
if [ "${#DEVS[@]}" -eq 0 ]; then
  echo
  echo "一个设备都没扫到。可能原因："
  echo "  1. 蓝牙被关了（rfkill list 看看）"
  echo "  2. 手环还连着手机 —— 先在手机蓝牙里「断开连接」或关掉手机蓝牙"
  echo "  3. 手环离电脑太远（放到 30cm 内再试）"
  exit 1
fi

echo
echo "发现的设备（共 ${#DEVS[@]} 个）："
HIT=0
for line in "${DEVS[@]}"; do
  mac=$(echo "$line" | awk '{print $2}')
  name=$(echo "$line" | cut -d' ' -f3- | sed 's/^ *//')
  [ -z "$name" ] || [ "$name" = "$mac" ] && name="（无名称）"
  # 小米手环常见的名称/前缀特征
  if echo "$name" | grep -qiE 'mi band|smart band|xiaomi|redmi|小米|手环'; then
    echo "  ★ $mac  $name   ← 像手环"
    HIT=1
    bluetoothctl info "$mac" 2>/dev/null | grep -E 'Name|Alias|RSSI|Paired|Services' | sed 's/^/      /'
  else
    echo "    $mac  $name"
  fi
done

echo
if [ "$HIT" = "1" ]; then
  cat <<'EOF'
发现疑似手环。但请注意：能看见 ≠ 能控制。
手环接受连接后要求 auth key 认证，没有 key 会被踢下线。
要真连上，得先从小米运动健康导出 auth key（或重配对时抓包），
然后用 Gadgetbridge 或自己实现 protobuf 协议。
EOF
else
  cat <<'EOF'
没发现手环。排查顺序：
 1. 手环从手机断开：手机蓝牙设置里点手环 → 断开连接
 2. 手环放到电脑旁 30cm 内，抬腕亮屏
 3. 重跑：./ble_probe.sh 25
EOF
fi
