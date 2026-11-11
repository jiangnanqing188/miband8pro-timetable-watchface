#!/usr/bin/env bash
# 手工打 APK（不依赖 gradle）
set -euo pipefail
cd "$(dirname "$0")"

SDK="${SDK:-$(cd .. && pwd)/tools-sdk}"
# 自动挑最新 build-tools：34 的 d8(R8 8.2) 遇到 JDK 21+ 编译出的匿名类/lambda
# 会内部 NPE 崩溃，36.1 起已修复
BT_DIR=$(ls -d "$SDK"/build-tools/*/ 2>/dev/null | sort -V | tail -1)
BT="${BT_DIR%/}"
if [ -z "$BT" ]; then echo "没找到 build-tools，先跑：sdkmanager \"build-tools;36.1.0\""; exit 1; fi
BT_VER=$(basename "$BT")
case "$BT_VER" in
  3[0-5].*) echo "⚠ 用的是 build-tools $BT_VER；它的 d8 处理匿名类会崩，建议装 36.1.0+";;
esac
JAR="$SDK/platforms/android-34/android.jar"
JAVA_HOME="${JAVA_HOME:-/snap/pycharm-community/672/jbr}"
JAVAC="$JAVA_HOME/bin/javac"
KEYTOOL="$JAVA_HOME/bin/keytool"

[ -x "$BT/aapt2" ] || { echo "找不到 $BT/aapt2"; exit 1; }
[ -f "$JAR" ] || { echo "找不到 $JAR"; exit 1; }

rm -rf build && mkdir -p build/classes build/dex

echo "① 编译资源"
"$BT/aapt2" compile --dir res -o build/res.zip

echo "② 链接资源/清单/assets"
"$BT/aapt2" link -o build/base.apk -I "$JAR" \
  --manifest AndroidManifest.xml build/res.zip \
  -A assets --auto-add-overlay

echo "③ 编译 Java"
"$JAVAC" --release 8 -cp "$JAR" -nowarn \
  -d build/classes $(find src -name '*.java') 2>&1 | grep -v "bootstrap class path" || true
ls build/classes/com/kebiao/watchface/*.class >/dev/null

echo "④ dex（build-tools $BT_VER）"
"$BT/d8" --lib "$JAR" --min-api 24 --output build/dex \
  $(find build/classes -name '*.class')

echo "⑤ 打包"
cp build/base.apk build/app-unsigned.apk
(cd build/dex && zip -q -X ../app-unsigned.apk classes.dex)

echo "⑥ zipalign + 签名"
"$BT/zipalign" -f 4 build/app-unsigned.apk build/app-aligned.apk
if [ ! -f build/debug.keystore ]; then
  "$KEYTOOL" -genkeypair -keystore build/debug.keystore -alias kebiao \
    -storepass kebiao123 -keypass kebiao123 -keyalg RSA -keysize 2048 \
    -validity 10000 -dname "CN=Kebiao Watchface, O=Self, C=CN" >/dev/null 2>&1
fi
mkdir -p ../out
"$BT/apksigner" sign --ks build/debug.keystore --ks-pass pass:kebiao123 \
  --key-pass pass:kebiao123 --out ../out/kebiao-app.apk build/app-aligned.apk
"$BT/apksigner" verify --print-certs ../out/kebiao-app.apk | head -3

echo
echo "✓ $(cd .. && pwd)/out/kebiao-app.apk  $(( $(stat -c%s ../out/kebiao-app.apk) / 1024 )) KB"
