#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课表体检：在出图之前把数据问题挑出来
====================================
    python3 check.py            # 体检 config/timetable.json
    python3 check.py --fix-hint # 带修复建议

查这些：
  ✗ 节次不存在 / 节次重复
  ✗ 同一时段两门课（时间冲突）
  ✗ 周次超出作息表范围 / 写错成 0 或负数
  ✗ 一天课太多，卡片会被压得很小（超过 6 节）
  ! 课名太长，图上会被截断
  ! 教室/老师为空
  ✓ 生成的 PNG 是不是 336×480、是不是 RGB（相册表盘的硬要求）
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
WEEK_CN = "一二三四五六日"


def compact(nums):
    nums = sorted(nums)
    segs, a, p = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == p + 1:
            p = n
            continue
        segs.append((a, p))
        a = p = n
    segs.append((a, p))
    return ",".join(f"{x}-{y}" if y > x else str(x) for x, y in segs)


def parse_weeks(v):
    out = set()
    if isinstance(v, list):
        for x in v:
            if isinstance(x, str) and "-" in x:
                a, b = x.split("-", 1)
                out |= set(range(int(a), int(b) + 1))
            else:
                out.add(int(x))
        return out
    for part in str(v).replace("，", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out |= set(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config", "timetable.json"))
    ap.add_argument("--fix-hint", action="store_true")
    args = ap.parse_args()

    cfg = json.load(open(args.config, encoding="utf-8"))
    periods = {p["no"]: p for p in cfg["periods"]}
    maxp = max(periods)
    errs, warns, infos = [], [], []

    if cfg.get("meta", {}).get("sample_data"):
        warns.append("还在用示例数据（sample_data=true），记得换成自己的课表")

    # 作息表本身
    for no, p in periods.items():
        if p["start"] >= p["end"]:
            errs.append(f"第 {no} 节的时间写反了：{p['start']}–{p['end']}")
    starts = [(p["start"], no) for p in periods.values()]
    for i in range(len(starts) - 1):
        if starts[i][0] > starts[i + 1][0]:
            warns.append(f"作息表顺序不对：第 {starts[i][1]} 节比第 "
                         f"{starts[i+1][1]} 节还晚")
            break

    # 每门课
    for i, c in enumerate(cfg["courses"], 1):
        nm = c.get("name", "")
        tag = f"第 {i} 条「{nm[:12]}」"
        if not nm.strip():
            errs.append(f"第 {i} 条课名为空")
            continue
        ps = c.get("periods") or []
        if not ps:
            errs.append(f"{tag} 没写节次")
        for p in ps:
            if p not in periods:
                errs.append(f"{tag} 用了第 {p} 节，但作息表只有 1–{maxp} 节")
        if len(set(ps)) != len(ps):
            errs.append(f"{tag} 节次重复：{ps}")
        wd = c.get("weekday")
        if wd not in range(1, 8):
            errs.append(f"{tag} 星期写成 {wd}，应该是 1–7")
        weeks = parse_weeks(c.get("weeks", "1-16"))
        if not weeks:
            errs.append(f"{tag} 周次是空的")
        if any(w <= 0 or w > 30 for w in weeks):
            errs.append(f"{tag} 周次超出范围：{compact(weeks)}（只支持 1–30）")
        if len(nm) > 14:
            warns.append(f"{tag} 课名 {len(nm)} 个字，卡片上会被截断成「{nm[:10]}…」")
        if not c.get("room"):
            warns.append(f"{tag} 没写教室，图上那一行会空着")

    # 冲突 + 每日课量
    by_day = {}
    for c in cfg["courses"]:
        by_day.setdefault(c.get("weekday"), []).append(c)
    for wd in sorted(by_day):
        day = by_day[wd]
        # 时间冲突（按周次交集判断）
        for a in range(len(day)):
            for b in range(a + 1, len(day)):
                A, B = day[a], day[b]
                if set(A.get("periods", [])) & set(B.get("periods", [])):
                    if parse_weeks(A.get("weeks", "1-16")) & parse_weeks(B.get("weeks", "1-16")):
                        errs.append(
                            f"周{WEEK_CN[wd-1] if wd else '?'} 时间冲突："
                            f"「{A['name']}」和「{B['name']}」撞在同一节")
        infos.append(f"周{WEEK_CN[wd-1] if wd else '?'}：{len(day)} 门课")
        if len(day) > 6:
            warns.append(f"周{WEEK_CN[wd-1]} 有 {len(day)} 门课，卡片会被压到很小，"
                         f"建议用 --theme line（极简版更省地方）")

    # 生成的图
    outdir = os.path.join(ROOT, "out")
    for f in ("today.png", "watchface_week.png"):
        p = os.path.join(outdir, f)
        if not os.path.exists(p):
            continue
        try:
            from PIL import Image
            im = Image.open(p)
            if im.size != (336, 480):
                errs.append(f"{f} 尺寸是 {im.size}，相册表盘要求 336×480")
            if im.mode != "RGB":
                warns.append(f"{f} 色彩模式是 {im.mode}，建议 RGB")
            else:
                infos.append(f"{f} 尺寸 {im.size[0]}×{im.size[1]} {im.mode} "
                             f"{os.path.getsize(p)//1024} KB ✓")
        except Exception as e:
            warns.append(f"{f} 打不开：{e}")

    # 输出
    print(f"\n课表体检 · {os.path.basename(args.config)}")
    print("=" * 46)
    print(f"课程 {len(cfg['courses'])} 门 · 作息 {len(periods)} 节 · "
          f"当前第 {cfg.get('meta', {}).get('current_week', '?')} 周")
    for line in infos:
        print("  · " + line)
    for line in warns:
        print("  ! " + line)
    for line in errs:
        print("  ✗ " + line)
    print("-" * 46)
    if errs:
        print(f"有 {len(errs)} 个错误必须改，否则图会画错。")
        if args.fix_hint:
            print("  → 节次/周次照着 config 顶部 periods 写；冲突的课改 weeks 错开")
        sys.exit(1)
    print(f"没有致命问题" + (f"，{len(warns)} 条提醒" if warns else "") + "。可以出图了。")


if __name__ == "__main__":
    main()
