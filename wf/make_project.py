#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把素材 + Lua 组装成 EasyFace 能编译的工程目录（python3 wf/make_project.py）"""
import os, re, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, "wf")
BUILD = os.path.join(WF, "build", "face")

def main():
    if os.path.exists(BUILD):
        shutil.rmtree(BUILD)
    lua_dir = os.path.join(BUILD, "app", "lua")
    img_dir = os.path.join(BUILD, "images")
    os.makedirs(lua_dir, exist_ok=True)
    os.makedirs(img_dir, exist_ok=True)

    # 把 data.lua 内联进 main.lua：手环上只留一个文件，少一个出错点
    data_src = open(os.path.join(WF, "app", "lua", "data.lua"), encoding="utf-8").read()
    main_src = open(os.path.join(WF, "app", "lua", "main.lua"), encoding="utf-8").read()
    inlined = ("-- 由 wf/make_project.py 组装：数据内联 + 表盘逻辑\n"
               "local DATA_INLINE = (function()\n" + data_src + "\nend)()\n\n" + main_src)
    open(os.path.join(lua_dir, "main.lua"), "w", encoding="utf-8").write(inlined)
    # EasyFace 的约定（照社区工程）：素材和 main.lua 放一起 app/lua/，
    # images/ 里只放 preview.png
    n_img = 0
    for f in os.listdir(os.path.join(WF, "images")):
        p = os.path.join(WF, "images", f)
        if os.path.isfile(p):
            shutil.copy(p, lua_dir)
            n_img += 1
    shutil.copy(os.path.join(WF, "preview_morning.png"),
                os.path.join(img_dir, "preview.png"))   # images/ 只放预览图
    shutil.copy(os.path.join(WF, "preview_morning.png"), os.path.join(BUILD, "preview.png"))

    fprj = '''<?xml version="1.0" encoding="utf-16" ?>
<FaceProject DeviceType="567">
    <Screen Title="\u8bfe\u8868" Bitmap="preview.png">
        <Widget Shape="34" Name="app_lua%2Fmain.lua" X="0" Y="0" Width="336" Height="480" Alpha="0" Visible_Src="0" />
    </Screen>
</FaceProject>
'''
    open(os.path.join(BUILD, "module.fprj"), "w", encoding="utf-16").write(fprj)
    n_g = len([f for f in os.listdir(img_dir) if re.match(r"^(t|d|y|mo|dd|wk|w\d|dot|p_)", f)])
    print(f"✓ 工程已组装：wf/build/face/")
    print(f"   module.fprj（DeviceType=567, 336×480）")
    print(f"   app/lua/main.lua + data.lua")
    print(f"   images/ {n_img} 张图（{n_g} 个文字图元 + 课程卡 + 没课图）")

if __name__ == "__main__":
    main()
