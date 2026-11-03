#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课表表盘 · 可视化面板
=====================
不用敲命令，浏览器里改课表、出包、推手机。

    python3 app.py          # 然后浏览器打开 http://127.0.0.1:8765

左边改课表，右边看效果，底下两个按钮：生成表盘 / 推到手机。
只用 Python 标准库，不需要装任何东西。
"""

import base64
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(ROOT, "config", "timetable.json")
PORT = 8765
HOST = "0.0.0.0"
FACE = os.path.join(ROOT, "out", "kebiao.face")
IMPORT_TMP = os.path.join(ROOT, "import_tmp")      # 局域网可访问，手机浏览器能打开

BUILD_LOG = {"text": "还没跑过", "running": False}
LOCK = threading.Lock()


# ------------------------------------------------------------------ 工具
def load_cfg():
    with open(CFG, encoding="utf-8") as f:
        return json.load(f)


def save_cfg(data):
    """只接受 courses / meta 的改动，periods 保留原样"""
    cfg = load_cfg()
    courses = []
    for c in data.get("courses", []):
        try:
            name = str(c.get("name", "")).strip()
            if not name:
                continue
            wd = int(c.get("weekday", 1))
            ps = sorted({int(x) for x in c.get("periods", [])})
            if not ps or not 1 <= wd <= 7:
                continue
            item = {"name": name, "weekday": wd, "periods": ps,
                    "weeks": str(c.get("weeks") or "1-16")}
            room = str(c.get("room", "")).strip()
            if room:
                item["room"] = room
            courses.append(item)
        except (TypeError, ValueError):
            continue
    cfg["courses"] = courses
    cfg.setdefault("meta", {})["sample_data"] = False
    if data.get("current_week"):
        cfg["meta"]["current_week"] = int(data["current_week"])
    with open(CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


def run(cmd, timeout=300):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       timeout=timeout, errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def build():
    with LOCK:
        BUILD_LOG["running"] = True
        BUILD_LOG["text"] = "编译中…"
    try:
        rc1, out1 = run([sys.executable, "wf/gen_assets.py"])
        rc2, out2 = run([sys.executable, "wf/preview.py"])
        rc3, out3 = run(["bash", "wf/build.sh"])
        ok = rc3 == 0 and os.path.exists(os.path.join(ROOT, "out", "kebiao.face"))
        text = out1 + "\n" + out2 + "\n" + out3
        size = os.path.getsize(os.path.join(ROOT, "out", "kebiao.face")) // 1024
        with LOCK:
            BUILD_LOG["text"] = f"{'✓ 成功' if ok else '✗ 失败'}  kebiao.face {size} KB\n\n" + text
            BUILD_LOG["at"] = time.strftime("%H:%M:%S")
        BUILD_LOG["running"] = False
    except Exception as e:
        with LOCK:
            BUILD_LOG["text"] = f"✗ 出错: {e}"
            BUILD_LOG["running"] = False


def adb(*args):
    try:
        return run(["adb"] + list(args), timeout=120)
    except FileNotFoundError:
        return 1, "没装 adb"
    except subprocess.TimeoutExpired:
        return 1, "adb 超时"


def device():
    rc, out = adb("devices")
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    return None


def status():
    dev = device()
    face = os.path.join(ROOT, "out", "kebiao.face")
    return {"device": dev,
            "face_kb": os.path.getsize(face) // 1024 if os.path.exists(face) else 0,
            "built_at": BUILD_LOG.get("at", "")}


def push():
    """推到手机 + 自动唤起「打开方式」，选 Gadgetbridge 就能装"""
    dev = device()
    if not dev:
        return 1, ("没检测到手机。检查：\n"
                   "  1. 数据线是不是只能充电那种\n"
                   "  2. 手机「开发者选项 → USB 调试」开了没\n"
                   "  3. 手机弹出「允许 USB 调试」时点了允许没")
    face = os.path.join(ROOT, "out", "kebiao.face")
    if not os.path.exists(face):
        return 1, "还没生成表盘，先点「保存并生成」"
    rc, out = adb("-s", dev, "push", face, "/sdcard/Download/")
    msgs = [out.strip()]
    rc2, out2 = adb("-s", dev, "shell", "am", "start", "-a", "android.intent.action.VIEW",
                    "-d", "file:///sdcard/Download/kebiao.face",
                    "-t", "application/octet-stream")
    if "Error" not in out2 and "Exception" not in out2:
        msgs.append("已在手机上打开这个文件 → 选 Gadgetbridge → Install")
    else:
        msgs.append("请手动打开：文件管理 → Download → kebiao.face → 用 Gadgetbridge 打开")
    return (0 if rc == 0 else 1), "\n".join(msgs)


def do_import(filename, content_b64):
    """导入 .ics / .xlsx / .csv / .txt，覆盖 config/timetable.json"""
    os.makedirs(IMPORT_TMP, exist_ok=True)
    safe = re.sub(r"[^\w.\-\u4e00-\u9fa5]", "_", os.path.basename(filename)) or "import"
    path = os.path.join(IMPORT_TMP, safe)
    with open(path, "wb") as f:
        f.write(base64.b64decode(content_b64))
    rc, out = run([sys.executable, "import_kebiao.py", path, "--config", CFG, "--out", CFG])
    return rc == 0, out


# ------------------------------------------------------------------ 页面
PAGE = r"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>课表表盘</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:dark;--bg:#000;--sf:#101317;--sf2:#171B20;--ln:#20242A;
 --ink:#F4F6FA;--ink2:#8E949E;--ink3:#5A606B;--ac:#5B8CFF;--bad:#FF6B81}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.55 system-ui,-apple-system,"PingFang SC","Noto Sans SC",sans-serif;
 font-variant-numeric:tabular-nums;padding:28px 20px 60px}
.wrap{max-width:1180px;margin:0 auto}
h1{margin:0 0 4px;font-size:24px;font-weight:600}
.sub{margin:0 0 26px;color:var(--ink2);font-size:13px}
.cols{display:grid;grid-template-columns:1fr 300px;gap:32px;align-items:start}
@media(max-width:820px){.cols{grid-template-columns:1fr}}
h2{margin:0 0 12px;font-size:13px;font-weight:500;color:var(--ink3);letter-spacing:.02em}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;color:var(--ink3);font-weight:500;font-size:12px;padding:0 8px 8px}
td{padding:5px 8px;border-top:1px solid var(--ln)}
tr:hover td{background:var(--sf)}
input,select{font:inherit;color:var(--ink);background:var(--sf2);border:1px solid var(--ln);
 border-radius:7px;height:36px;padding:0 9px;width:100%}
input:focus,select:focus{outline:2px solid var(--ac);outline-offset:-1px;border-color:transparent}
.w60{width:60px}.w80{width:80px}.w100{width:100px}
.state{display:flex;gap:16px;flex-wrap:wrap;margin:0 0 20px;font-size:12.5px;color:var(--ink3)}
.state b{color:var(--ink2);font-weight:500}
button.sm{height:30px;font-size:12.5px;padding:0 8px;color:var(--ink2)}
.wkbox{display:flex;gap:4px;align-items:center}
button{font:inherit;color:inherit;background:var(--sf2);border:0;border-radius:9px;
 height:40px;padding:0 16px;cursor:pointer}
button:active{transform:scale(.985)}
button.pri{background:var(--ac);color:#fff;font-weight:500}
button.del{background:none;color:var(--ink3);padding:0 8px;height:32px}
button.del:hover{color:var(--bad)}
.bar{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}
.stage{background:var(--sf);border-radius:14px;padding:14px}
.stage img{display:block;width:100%;border-radius:18px;background:#000}
.tabs{display:flex;gap:6px;margin-bottom:10px}
.tabs button{height:32px;font-size:13px;padding:0 12px;color:var(--ink2)}
.tabs button.on{background:var(--sf2);color:var(--ink)}
pre{margin:14px 0 0;background:var(--sf);border-radius:12px;padding:14px;
 color:var(--ink2);font-size:12px;line-height:1.5;max-height:260px;overflow:auto;white-space:pre-wrap}
.hint{color:var(--ink3);font-size:12.5px;margin-top:10px}
</style></head><body><div class="wrap">
<h1>课表表盘</h1>
<p class="sub">导入 → 改 → 生成 → 推手机，四步都在这页</p>
<div class="state">
 <span>手机：<b id="stDev">检查中…</b></span>
 <span>表盘包：<b id="stFace">—</b></span>
 <span>上次生成：<b id="stAt">—</b></span>
</div>
<div class="cols">
 <div>
  <h2>课程（共 <span id="n">0</span> 门）</h2>
  <table><thead><tr>
    <th style="width:34%">课程</th><th style="width:16%">教室</th><th style="width:12%">星期</th>
    <th style="width:16%">节次</th><th style="width:14%">周次</th><th></th>
  </tr></thead><tbody id="rows"></tbody></table>
  <div class="bar">
    <button onclick="addRow()">+ 加一门</button>
    <button onclick="picker()">导入 .ics / Excel</button>
    <button class="pri" onclick="save(true)">保存并生成</button>
    <button onclick="save(false)">只保存</button>
  </div>
  <input type="file" id="file" accept=".ics,.csv,.xlsx,.txt,.json" hidden>
  <div class="hint" id="msg"></div>
  <pre id="log">还没跑过</pre>
 </div>
 <div>
  <h2>效果预览</h2>
  <div class="stage">
    <div class="tabs">
      <button class="on" data-p="morning">上午</button>
      <button data-p="afternoon">下午</button>
      <button data-p="evening">晚上</button>
    </div>
    <img id="pv" src="/preview?phase=morning&t=0" alt="预览">
  </div>
  <div class="bar"><button onclick="push()">推到手机</button></div>
  <div class="hint">预览是服务器按当前课表渲染的，改完保存就会更新</div>
 </div>
</div></div>
<script>
const WD=['一','二','三','四','五','六','日'];
let data=null;
fetch('/api/data').then(r=>r.json()).then(d=>{data=d;render();refreshState()});

function render(){
  const tb=document.getElementById('rows');
  tb.innerHTML=data.courses.map((c,i)=>`
   <tr>
    <td><input value="${esc(c.name)}" oninput="set(${i},'name',this.value)"></td>
    <td><input value="${esc(c.room||'')}" oninput="set(${i},'room',this.value)"></td>
    <td><select onchange="set(${i},'weekday',+this.value)">
      ${WD.map((w,j)=>`<option value="${j+1}" ${c.weekday==j+1?'selected':''}>周${w}</option>`).join('')}
    </select></td>
    <td><input class="w80" value="${c.periods.join('-')}" oninput="set(${i},'periods',this.value)"></td>
    <td><div class="wkbox">
      <input value="${esc(c.weeks||'1-16')}" oninput="set(${i},'weeks',this.value)">
      <button class="sm" onclick="wk(${i},'all')" title="全学期">全</button>
      <button class="sm" onclick="wk(${i},'odd')" title="单周">单</button>
      <button class="sm" onclick="wk(${i},'even')" title="双周">双</button>
    </div></td>
    <td><button class="del" onclick="del(${i})">删</button></td>
   </tr>`).join('');
  document.getElementById('n').textContent=data.courses.length;
}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function set(i,k,v){
  if(k==='periods'){v=String(v).split(/[^0-9]+/).filter(Boolean).map(Number);
    if(v.length>1&&v.length===2){const a=v[0],b=v[1];v=[];for(let x=Math.min(a,b);x<=Math.max(a,b);x++)v.push(x);}
    if(!v.length)v=[1];}
  data.courses[i][k]=v;
}
function wk(i, kind){
  const max = 17; let s;
  if(kind === 'all') s = `1-${max}`;
  else { const start = kind === 'odd' ? 1 : 2, a = [];
    for(let x = start; x <= max; x += 2) a.push(x); s = a.join(','); }
  data.courses[i].weeks = s; render();
}
function picker(){ document.getElementById('file').click(); }
document.getElementById('file').onchange = async e => {
  const f = e.target.files[0]; if(!f) return;
  document.getElementById('log').textContent = '导入中…';
  const b64 = await new Promise(res => {
    const fr = new FileReader();
    fr.onload = () => res(String(fr.result).split(',')[1]);
    fr.readAsDataURL(f);
  });
  const r = await fetch('/api/import', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({filename: f.name, b64})});
  const j = await r.json();
  document.getElementById('log').textContent = j.log;
  if(j.ok){ data = await (await fetch('/api/data')).json(); render();
    document.getElementById('msg').textContent = '导入成功'; }
  e.target.value = '';
};
async function refreshState(){
  const st = await (await fetch('/api/status')).json();
  const d = document.getElementById('stDev');
  d.textContent = st.device ? ('已连接 ' + st.device) : '未连接';
  d.style.color = st.device ? 'var(--ok)' : 'var(--bad)';
  document.getElementById('stFace').textContent = st.face_kb ? (st.face_kb + ' KB') : '未生成';
  document.getElementById('stAt').textContent = st.built_at || '—';
}
function addRow(){data.courses.push({name:'',room:'',weekday:1,periods:[1,2],weeks:'1-16'});render()}
function del(i){data.courses.splice(i,1);render()}
async function save(build_){
  const r=await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(data)});
  const j=await r.json();
  document.getElementById('msg').textContent=j.msg||'已保存';
  if(build_) startBuild();
  refreshPreview();
}
async function startBuild(){
  document.getElementById('log').textContent='编译中…（约 5 秒）';
  const r=await fetch('/api/build',{method:'POST'});const j=await r.json();
  document.getElementById('log').textContent=j.log;
  refreshPreview(); refreshState();
}
async function push(){
  const r=await fetch('/api/push',{method:'POST'});const j=await r.json();
  document.getElementById('log').textContent=j.log;
}
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on');refreshPreview();
});
function refreshPreview(){
  const p=document.querySelector('.tabs button.on').dataset.p;
  document.getElementById('pv').src='/preview?phase='+p+'&t='+Date.now();
}
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if u.path == "/api/data":
            return self._send(200, json.dumps(load_cfg(), ensure_ascii=False))
        if u.path == "/preview":
            q = parse_qs(u.query)
            ph = (q.get("phase") or ["morning"])[0]
            p = os.path.join(ROOT, "wf", f"preview_{ph}.png")
            if not os.path.exists(p):
                p = os.path.join(ROOT, "wf", "preview_morning.png")
            if not os.path.exists(p):
                return self._send(404, b"no preview", "text/plain")
            return self._send(200, open(p, "rb").read(), "image/png")
        if u.path == "/api/status":
            return self._send(200, json.dumps(status(), ensure_ascii=False))
        if u.path == "/api/log":
            return self._send(200, json.dumps(BUILD_LOG, ensure_ascii=False))
        return self._send(404, "{}")

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b"{}"
        if u.path == "/api/save":
            try:
                data = json.loads(raw.decode("utf-8"))
                cfg = save_cfg(data)
                return self._send(200, json.dumps(
                    {"ok": True, "msg": f"已保存 {len(cfg['courses'])} 门课"}, ensure_ascii=False))
            except Exception as e:
                return self._send(200, json.dumps({"ok": False, "msg": f"保存失败：{e}"},
                                                  ensure_ascii=False))
        if u.path == "/api/build":
            build()
            return self._send(200, json.dumps(BUILD_LOG, ensure_ascii=False))
        if u.path == "/api/import":
            try:
                payload = json.loads(raw.decode("utf-8"))
                ok, out = do_import(payload.get("filename", "x.ics"), payload.get("b64", ""))
                return self._send(200, json.dumps({"ok": ok, "log": out}, ensure_ascii=False))
            except Exception as e:
                return self._send(200, json.dumps({"ok": False, "log": f"导入失败：{e}"},
                                                  ensure_ascii=False))
        if u.path == "/api/push":
            try:
                rc, out = push()
                return self._send(200, json.dumps(
                    {"ok": rc == 0, "log": ("推送成功\n" if rc == 0 else "推送失败\n") + out},
                    ensure_ascii=False))
            except Exception as e:
                return self._send(200, json.dumps({"ok": False, "log": str(e)}, ensure_ascii=False))
        return self._send(404, "{}")


def lan_ips():
    """列出本机局域网 IP，手机要用这个地址访问"""
    out = []
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        out.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        import subprocess as sp
        r = sp.run(["hostname", "-I"], capture_output=True, text=True, timeout=3)
        for ip in r.stdout.split():
            if ip.count(".") == 3 and not ip.startswith("127.") and ip not in out:
                out.append(ip)
    except Exception:
        pass
    return out


def main():
    if not os.path.exists(CFG):
        sys.exit(f"找不到 {CFG}")
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print("=" * 52, flush=True)
    print(f"课表表盘面板已启动", flush=True)
    print(f"  本机：   http://127.0.0.1:{PORT}", flush=True)
    ips = lan_ips()
    if ips:
        print(f"  手机上开：http://{ips[0]}:{PORT}   ← 手机和电脑连同一个 WiFi", flush=True)
    else:
        print("  （没检测到局域网 IP，手机可能连不上）", flush=True)
    print("-" * 52, flush=True)
    print("流程：改课表 → 保存并生成 → 推到手机 → 手机上 Gadgetbridge 安装", flush=True)
    print("=" * 52, flush=True)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已退出")


if __name__ == "__main__":
    main()
