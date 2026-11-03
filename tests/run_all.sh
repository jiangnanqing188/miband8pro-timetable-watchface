#!/usr/bin/env bash
# 全部自检：课表逻辑 + ICS 解析 + 生成的图
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
echo "① 网页版逻辑测试"; node tests/logic_test.mjs 2>/dev/null || fail=1
echo; echo "② .ics 真实场景测试"; python3 tests/ics_test.py 2>/dev/null | grep -v "^从" || fail=1
echo; echo "③ 课表体检"; python3 check.py 2>&1 | tail -3 || fail=1
echo; echo "④ 出图 + 规格校验"
python3 make_watchface.py --today --all-phases >/dev/null 2>&1 || fail=1
python3 - <<'PY'
from PIL import Image
import glob, os
bad=0
for f in sorted(glob.glob("out/today*.png")):
    im=Image.open(f)
    ok = im.size==(336,480) and im.mode=="RGB"
    if not ok: bad+=1
    print(f"  {'✓' if ok else '✗'} {os.path.basename(f)}  {im.size[0]}×{im.size[1]} {im.mode}")
raise SystemExit(1 if bad else 0)
PY
[ $? -ne 0 ] && fail=1
echo
[ $fail -eq 0 ] && echo "全部通过" || echo "有失败项"
exit $fail
