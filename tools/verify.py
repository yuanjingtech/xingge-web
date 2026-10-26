#!/usr/bin/env python3
"""落地页自动验证（spec §7）。

检查项：
  1. 数据完整性：16 型齐全、四组各 4 型、六维每型 6 个分数且 0–100、rank 1–16 唯一、颜色合法。
  2. 数据一致性：产物与源仓库保持一致（重生成后无 diff）。
  3. HTML 结构：锚点目标存在、id 唯一、无空 href="#"（CTA 专用锚点除外）。
  4. 资源引用：<img>/<link>/<script> 指向的文件全部存在（仅本地路径，跳过 http/data）。
  5. 文案红线：不出现「诊断」「治疗」「包治」「100%准」「100% 准」等词。
  6. 无障碍基础：每个 <img> 有 alt。

用法：
    python3 tools/verify.py
"""
import html
import os
import re
import subprocess
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
ASSETS = ROOT

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"

PASSED = FAILED = 0
FAILURES = []


def ok(name):
    global PASSED
    PASSED += 1


def fail(name, detail=""):
    global FAILED
    FAILED += 1
    FAILURES.append(f"{name}{' — ' + detail if detail else ''}")


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        fail(name, detail)


def section(title):
    print(f"\n  {YELLOW}{title}{RESET}")


# ---------- 1. 数据完整性 ----------

section("1. 数据完整性")
try:
    js_text = open(os.path.join(ROOT, "assets/data/personalities.js"), encoding="utf-8").read()
    data_str = js_text.split("window.XINGGE_DATA = ", 1)[1].rstrip().rstrip(";")
    DATA = json.loads(data_str)
except Exception as e:
    fail("personalities.js 可解析", str(e))
    DATA = None

if DATA:
    items = DATA.get("personalities") or []
    check("16 型齐全", len(items) == 16, f"实际 {len(items)}")

    codes = {x["code"] for x in items}
    GROUPS = [
        ("分析家", "INTJ INTP ENTJ ENTP"),
        ("外交官", "INFJ INFP ENFJ ENFP"),
        ("守护者", "ISTJ ISFJ ESTJ ESFJ"),
        ("探险家", "ISTP ISFP ESTP ESFP"),
    ]
    for gname, members in GROUPS:
        got = [c for c in members.split() if c in codes]
        check(f"分组 {gname} 含 4 型", len(got) == 4, f"{got}")

    for p in items:
        d = p.get("dims") or {}
        scores = list(d.values())
        check(f"{p['code']} 六维分数数量=6", len(scores) == 6, f"{len(scores)}")
        ok_scores = all(isinstance(v, (int, float)) and 0 <= v <= 100 for v in scores)
        check(f"{p['code']} 六维值在 0–100", ok_scores, f"{scores}")

    ranks = sorted(x["rank"] for x in items)
    check("rank 1–16 唯一", ranks == list(range(1, 17)), f"{ranks}")

    color_re = re.compile(r"^#[0-9a-fA-F]{6}$")
    for p in items:
        check(f"{p['code']} color 格式", bool(color_re.match(p.get("color", ""))), p.get("color"))
        check(f"{p['code']} text 格式", bool(color_re.match(p.get("text", ""))), p.get("text"))
        check(f"{p['code']} tint 格式", bool(color_re.match(p.get("tint", ""))), p.get("tint"))

# ---------- 2. 数据一致性 ----------

section("2. 数据一致性（重生成产物一致）")
try:
    res = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools/build_data.py"), "--check"],
        capture_output=True, text=True
    )
    if res.returncode == 0:
        ok("产物与源一致")
    else:
        fail("产物与源一致", res.stderr.strip() or res.stdout.strip())
except Exception as e:
    fail("build_data.py --check 可运行", str(e))

# ---------- 3. HTML 结构 ----------

section("3. HTML 结构")
try:
    html_text = open(INDEX, encoding="utf-8").read()
except Exception as e:
    fail("index.html 可读", str(e))
    html_text = ""

if html_text:
    # id 唯一性
    ids = re.findall(r'\bid=["\']([^"\']+)["\']', html_text)
    seen = set()
    dups = set()
    for i in ids:
        if i in seen:
            dups.add(i)
        seen.add(i)
    check("id 唯一", not dups, f"重复：{dups}")

    # 锚点目标存在
    ANCHORS = ["main", "top", "dimensions", "gallery-sec", "report", "start", "faq"]
    for a in ANCHORS:
        exists = bool(re.search(r'\bid=["\']' + re.escape(a) + r'["\']', html_text))
        check(f"锚点 #{a} 存在", exists)

    # 无空 href="#"（href="#" 仅允许在 .skip 里）
    bare = re.findall(r'href=["\']\s*#\s*["\']', html_text)
    check("无空 href=\"#\"", len(bare) == 0, f"发现 {len(bare)} 处")

    # 生成标记存在
    check("GALLERY 标记存在", "GALLERY:START" in html_text and "GALLERY:END" in html_text)
    check("REPORT 标记存在", "REPORT:START" in html_text and "REPORT:END" in html_text)

    # 16 张卡
    card_count = len(re.findall(r'class="card"', html_text))
    check(f"图鉴含 16 张卡", card_count == 16, f"实际 {card_count}")

    # 16 个图表
    fig_count = len(re.findall(r'class="pf-figure', html_text))
    check(f"报告含 16 个画像", fig_count == 16, f"实际 {fig_count}")

# ---------- 4. 资源存在 ----------

section("4. 资源引用存在")
if html_text:
    # 收集 src / href 里的本地路径
    patterns = [r'src=["\']([^"\']+)["\']', r'href=["\']([^"\']+\.(?:css|js|png|jpg|svg))["\']']
    refs = []
    for pat in patterns:
        for m in re.finditer(pat, html_text):
            refs.append(m.group(1))
    seen_refs = set()
    for ref in refs:
        if ref.startswith("http") or ref.startswith("data:") or ref in seen_refs:
            continue
        seen_refs.add(ref)
        path = os.path.join(ROOT, ref)
        check(f"资源存在：{ref}", os.path.exists(path))

# ---------- 5. 文案红线 ----------

section("5. 文案红线")
if html_text:
    FORBIDDEN = ["诊断", "治疗", "包治", "100%准", "100% 准", "保证准"]
    visible = re.sub(r"<[^>]+>", "", html_text)
    for word in FORBIDDEN:
        check(f"不含「{word}」", word not in visible, f"在 HTML 文本里发现")

# ---------- 6. 无障碍基础 ----------

section("6. 无障碍基础")
if html_text:
    imgs = re.findall(r"<img[^>]+>", html_text)
    for img in imgs:
        has_alt = "alt=" in img
        src_m = re.search(r'src=["\']([^"\']+)["\']', img)
        src_name = src_m.group(1) if src_m else img[:40]
        check(f"img alt 存在：{src_name}", has_alt)

# ---------- 汇总 ----------

print()
if FAILURES:
    print(f"{RED}失败 {FAILED} 项：{RESET}")
    for f in FAILURES:
        print(f"  {RED}✗{RESET} {f}")
    print(f"\n  通过 {PASSED}，失败 {FAILED}。")
    sys.exit(1)
else:
    print(f"{GREEN}全部通过：{PASSED} 项。{RESET}")
