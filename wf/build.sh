#!/usr/bin/env bash
# 编译成 .face（用 Mi8WfBinTool，纯 Java，Linux 可跑）
# 用法：./wf/build.sh
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
TOOL="$ROOT/re/Mi8WfBinTool.java"
OUT="$ROOT/out"

echo "① 生成素材与数据表"
python3 wf/gen_assets.py || exit 1

echo "② 组装工程（数据内联成单文件）"
python3 wf/make_project.py || exit 1

echo "③ 准备打包源"
python3 - <<'PY'
import json, os, shutil
src = "wf/build/face/app/lua"
dst = "wf/build/pack"
shutil.rmtree(dst, ignore_errors=True)
os.makedirs(dst + "/images/lua", exist_ok=True)
shutil.copy("wf/preview_morning.png", dst + "/images/preview.png")
pngs = []
for f in sorted(os.listdir(src)):
    if f.endswith(".png"):
        shutil.copy(os.path.join(src, f), dst + "/images/lua/" + f)
        pngs.append("lua/" + f)
shutil.copy(os.path.join(src, "main.lua"), dst + "/images/lua/main.lua")
wf = {
    "name": "课表", "id": "167200916", "previewImg": "preview", "faceStyleCount": 1,
    "elementsNormal": [{"type": "type_element_lua", "x": 0, "y": 0,
                        "jsFileName": "lua/main.lua", "jsImgList": pngs}],
    "elementsAod": [],
}
json.dump(wf, open(dst + "/wfDef.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"   素材 {len(pngs)} 张 + main.lua")
PY

echo "④ 打包"
if [ ! -f "$TOOL.class" ] && [ ! -f "re/Mi8WfBinTool.class" ]; then
  JAVAC=$(command -v javac || echo /snap/pycharm-community/672/jbr/bin/javac)
  (cd re && "$JAVAC" -encoding UTF-8 Mi8WfBinTool.java) || exit 1
fi
mkdir -p "$OUT"
(cd re && java Mi8WfBinTool pack ../wf/build/pack ../out/kebiao.face mi8pro) || exit 1

echo "⑤ 校验"
python3 - <<'PY'
import struct, sys
p = "out/kebiao.face"
d = open(p, "rb").read()
ok = True
def chk(name, cond, val=""):
    global ok
    print(f"   {'✓' if cond else '✗'} {name} {val}")
    ok = ok and cond
chk("magic 5aa53412", d[:4] == bytes.fromhex("5aa53412"), d[:4].hex())
chk("设备标志 0x800", struct.unpack("<I", d[0x10:0x14])[0] == 0x800)
chk("表盘数 1", struct.unpack("<H", d[0x1C:0x1E])[0] == 1)
chk("ID", d[0x28:0x31].rstrip(b"\0").decode(errors="replace") == "167200916",
    d[0x28:0x31].rstrip(b"\0").decode(errors="replace"))
chk("名称=课表", d[0x68:0xa4].split(b"\0")[0].decode("utf-8", "replace") == "课表")
n = d.count(b"\x89PNG\r\n\x1a\n")
chk("图片数量", n >= 70, f"{n} 张")
chk("体积合理", len(d) > 300_000, f"{len(d)//1024} KB")
sys.exit(0 if ok else 1)
PY
