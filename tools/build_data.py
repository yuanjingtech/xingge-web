#!/usr/bin/env python3
"""从 xingge-app-kuikly 生成落地页：数据 + 页面区块，并回填 index.html。

设计原则（spec §3）：
  - 单一真源：16 型文案 / 配色 / 六维分数 / 题库统计全部从源仓库读，本仓库不二次抄写。
  - 只读源仓库，绝不写入。
  - 结构不符就报错退出，不静默降级（否则页面会「看起来正常但内容是空的」）。

产物：
  assets/data/personalities.js   —— 数据（file:// 下不能用 fetch，所以是 JS 而非 JSON）
  assets/img/poster-qr.png      —— 小程序码
  index.html                    —— 回填 GALLERY / REPORT 两个区块

派生色说明：16 型主色里有 #22223B 这类极深色，直接当浅底文字色对比度不够。
所以每型额外算两个派生色：
  text  —— 用于浅底上的文字/描边，对 #FFFFFF 对比度 >= 4.5:1
  tint  —— 用于卡片底色/色块，浅色化后仍保留色相

用法：
    python3 tools/build_data.py            # 生成
    python3 tools/build_data.py --check    # 校验产物与源一致（verify.py 调用）
"""
import html
import json
import math
import os
import re
import sys

WEB_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(WEB_ROOT)
APP_ROOT = os.path.join(REPO_ROOT, "xingge-app-kuikly")

RESULT_JSON = os.path.join(APP_ROOT, "shared/src/commonMain/assets/common/result.json")
TIKU_JSON = os.path.join(APP_ROOT, "shared/src/commonMain/assets/common/tiku.json")
PROFILE_KT = os.path.join(
    APP_ROOT,
    "shared/src/commonMain/kotlin/com/yuanjingtech/xingge/app/mbti/data/json/ProfileData.kt",
)
QR_PNG = os.path.join(APP_ROOT, "shared/src/commonMain/assets/common/mbti/poster-qr.png")
# 小程序构建产物里的 window.navigationBarTitleText 就是已注册的正式名
MINIAPP_APP_JSON = os.path.join(APP_ROOT, "miniApp/dist/app.json")

OUT_JS = os.path.join(WEB_ROOT, "assets/data/personalities.js")
OUT_QR = os.path.join(WEB_ROOT, "assets/img/poster-qr.png")
OUT_INDEX = os.path.join(WEB_ROOT, "index.html")

GALLERY_START = "<!-- GALLERY:START · 由 tools/build_data.py 生成 -->"
GALLERY_END = "<!-- GALLERY:END -->"
REPORT_START = "<!-- REPORT:START · 由 tools/build_data.py 生成 -->"
REPORT_END = "<!-- REPORT:END -->"

# 站点品牌名 = 小程序正式名「我的MBTI人格」（人类 2026-10-26 确认）。
# 优先从源仓库已注册的 navigationBarTitleText 读取，读不到再用下面的常量兜底，
# 避免品牌名在两边漂移。改品牌名 = 改小程序配置，不是改这里。
BRAND_FALLBACK = "我的MBTI人格"
BRAND_EN = "MyMBTI"

GROUPS = [
    ("分析家", "NT", "直觉 + 思考", "INTJ INTP ENTJ ENTP"),
    ("外交官", "NF", "直觉 + 情感", "INFJ INFP ENFJ ENFP"),
    ("守护者", "SJ", "实感 + 判断", "ISTJ ISFJ ESTJ ESFJ"),
    ("探险家", "SP", "实感 + 知觉", "ISTP ISFP ESTP ESFP"),
]

DIMS = [
    ("EI", "能量从哪里来", "外向 E / 内向 I", "跟人待在一起回血，还是独处回血"),
    ("SN", "信息怎么收", "实感 S / 直觉 N", "看眼前的事实，还是看背后的可能"),
    ("TF", "决定怎么下", "思考 T / 情感 F", "先讲道理，还是先讲感受"),
    ("JP", "日子怎么过", "判断 J / 知觉 P", "按计划走，还是走一步看一步"),
]

SECTION_LABEL = {
    "scene": "像不像你身边这个人",
    "core": "核心特质",
    "pros": "天然优势",
    "cons": "容易踩的坑",
    "jobs": "适合的工作",
    "advice": "真心建议",
}


def fail(msg):
    print(f"build_data.py: {msg}", file=sys.stderr)
    sys.exit(1)


def read_text(path):
    if not os.path.exists(path):
        fail(f"源文件不存在：{path}")
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------- 颜色 ----------

def hex_to_rgb(h):
    h = h.lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        fail(f"颜色格式非法：{h}")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(v))):02X}" for v in rgb)


def rel_luminance(rgb):
    def chan(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_with_white(rgb):
    return 1.05 / (rel_luminance(rgb) + 0.05)


def mix(rgb, target, amount):
    return tuple(v + (t - v) * amount for v, t in zip(rgb, target))


def derive_colors(hexcolor):
    """返回 (text, tint)。text 白底对比度 >= 4.5:1；tint 为浅色卡片底。"""
    base = hex_to_rgb(hexcolor)
    text = base
    for _ in range(40):
        if contrast_with_white(text) >= 4.5:
            break
        text = mix(text, (0, 0, 0), 0.12)
    else:
        text = (0, 0, 0)
    tint = mix(base, (255, 255, 255), 0.86)
    return rgb_to_hex(text), rgb_to_hex(tint)


# ---------- 文本解析 ----------

HEADER_RULES = [
    ("quote", ("一句话总结",)),
    # 少数型（INTJ/INTP）没有「核心特质（人话版）」小节，用的是「他们的思维方式是这样的」，
    # 结构等价，归到 core，渲染时用原文标题。
    ("core", ("核心特质（人话版）", "核心特质：", "他们的思维方式")),
    ("scene", ("想象一下", "特点鲜明")),
    ("pros", ("他们的优点",)),
    ("cons", ("容易踩的坑", "容易遇到的烦恼")),
    ("jobs", ("适合的工作",)),
    ("advice", ("真心建议",)),
]

# 收尾段落（"总而言之，XXX 是……"）不属于建议清单，单独存，页面用作卡片结语。
CLOSING_MARK = "总而言之"


def header_key(line):
    s = line.strip()
    if not s:
        return None
    for key, marks in HEADER_RULES:
        if any(m in s for m in marks):
            return key
    return None


def clean(line):
    return line.strip().strip("　 ").lstrip("·•")


def parse_description(desc):
    """把整段 description 切成结构化小节。

    各型原文的小节标题写法不完全一致（"他们的优点：" / "他们的优点（为啥他们这么牛）："），
    所以按关键词归并，而不是按精确标题匹配。
    """
    lines = desc.split("\n")
    out = {"feature": "", "metaphor": "", "quote": "", "closing": "", "sections": []}

    for line in lines:
        s = line.strip()
        if s.startswith("特点："):
            out["feature"] = s[len("特点："):].strip()
        elif s.startswith("角色比喻："):
            out["metaphor"] = s[len("角色比喻："):].strip()
        elif s.startswith(CLOSING_MARK):
            out["closing"] = s

    current = None
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith(CLOSING_MARK):
            current = None
            continue
        key = header_key(s)
        if key:
            if key == "quote":
                # 引子话术在下一行，交给后续普通行处理
                current = "quote"
            else:
                current = key
                if key not in [x["key"] for x in out["sections"]]:
                    out["sections"].append({"key": key, "title": s.rstrip("：:"), "items": []})
            continue
        if s.startswith("特点：") or s.startswith("角色比喻："):
            continue
        if current == "quote":
            out["quote"] = s.strip().strip("“”\"")
            current = None
            continue
        if current is None:
            continue
        # 建议类里"1. xxx"要保留序号；其它条目去掉列表符号
        item = s if re.match(r"^\d+[.、]", s) else clean(s)
        if not item:
            continue
        for sec in out["sections"]:
            if sec["key"] == current:
                sec["items"].append(item)
                break
    return out


def split_summary(summary, nickname):
    """summary 形如 '建筑师紫老头 - 战略家/大师'，返回 (role, aliases)。"""
    head = summary.split(" - ")[0]
    role = head.replace(nickname, "", 1) if nickname and nickname in head else head
    alias = summary.split(" - ", 1)[1] if " - " in summary else ""
    return role.strip(), [a.strip() for a in alias.split("/") if a.strip()]


# ---------- 数据装配 ----------

def load_sources():
    result = json.loads(read_text(RESULT_JSON))
    tiku = json.loads(read_text(TIKU_JSON))

    kt = read_text(PROFILE_KT)
    m = re.search(r'"""\s*(\{.*?\})\s*"""', kt, re.S)
    if not m:
        fail(f"ProfileData.kt 里找不到内嵌 JSON：{PROFILE_KT}")
    profile = json.loads(m.group(1))

    if not os.path.exists(QR_PNG):
        fail(f"小程序码不存在：{QR_PNG}")

    # 品牌名：优先取小程序已注册的正式名
    brand = BRAND_FALLBACK
    if os.path.exists(MINIAPP_APP_JSON):
        try:
            app_json = json.loads(read_text(MINIAPP_APP_JSON))
            title = (app_json.get("window") or {}).get("navigationBarTitleText")
            if title:
                brand = title.strip()
        except json.JSONDecodeError:
            print("build_data.py: 警告：app.json 解析失败，用兜底品牌名", file=sys.stderr)

    personalities = result.get("personalities") or []
    if len(personalities) != 16:
        fail(f"result.json 期望 16 型，实际 {len(personalities)}")
    if len(profile.get("profiles") or {}) != 16:
        fail("ProfileData 期望 16 型")

    return personalities, profile, tiku, brand


def build_personality(item, prof, dims):
    code = item["type"]
    p = (prof.get("profiles") or {}).get(code)
    if not p:
        fail(f"ProfileData 缺少 {code}")

    nickname = p["nick"]
    role, aliases = split_summary(item["summary"], nickname)
    parsed = parse_description(item["description"])
    text_color, tint_color = derive_colors(item["color"])

    scores = p["scores"]
    if len(scores) != 6:
        fail(f"{code} 六维分数应为 6 个，实际 {len(scores)}")
    if any(not isinstance(s, (int, float)) or s < 0 or s > 100 for s in scores):
        fail(f"{code} 六维分数越界：{scores}")

    group = next((g for g, _, _, members in GROUPS if code in members.split()), None)
    if not group:
        fail(f"{code} 不在任何分组里")

    return {
        "code": code,
        "role": role,
        "nickname": nickname,
        "aliases": aliases,
        "group": group,
        "color": item["color"],
        "text": text_color,
        "tint": tint_color,
        "word": item["impressionSoft"],
        "wordLine": item["impressionSoftLine"],
        "spicy": item["impressionSpicy"],
        "spicyLine": item["impressionSpicyLine"],
        "quote": parsed["quote"],
        "closing": parsed["closing"],
        "feature": parsed["feature"],
        "metaphor": parsed["metaphor"],
        "sections": parsed["sections"],
        "dims": dict(zip(dims, scores)),
        "rank": p["rank"],
        "overall": p["overall"],
        "top": p["top"],
        "low": p["low"],
    }


def build():
    personalities, profile, tiku, brand = load_sources()
    dims = profile["dims"]

    items = [build_personality(x, profile, dims) for x in personalities]

    ranks = sorted(x["rank"] for x in items)
    if ranks != list(range(1, 17)):
        fail(f"rank 应为 1..16 且唯一，实际 {ranks}")

    codes = {x["code"] for x in items}
    for group, code2, label, members in GROUPS:
        got = {c for c in members.split() if c in codes}
        if len(got) != 4:
            fail(f"分组 {group} 应含 4 型，实际 {sorted(got)}")

    counts = {}
    for q in tiku["questions"]:
        counts[q["dimension"]] = counts.get(q["dimension"], 0) + 1
    total = len(tiku["questions"])

    return {
        "brand": brand,
        "brandEn": BRAND_EN,
        "totalQuestions": total,
        "dimensionCounts": counts,
        "dims": dims,
        "dimHints": profile["hints"],
        "profileSource": profile["source"],
        "groups": [{"name": g, "code": c, "label": l, "members": m.split()}
                   for g, c, l, m in GROUPS],
        "dimIntro": [{"code": c, "title": t, "pair": p, "line": l} for c, t, p, l in DIMS],
        "personalities": sorted(items, key=lambda x: x["rank"]),
    }


def render_js(data):
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    return (
        "/* 由 tools/build_data.py 从 xingge-app-kuikly 生成，请勿手改。\n"
        "   源：shared/.../assets/common/result.json、tiku.json、ProfileData.kt\n"
        "   重跑：python3 tools/build_data.py */\n"
        f"window.XINGGE_DATA = {payload};\n"
    )


# ---------- 页面区块渲染 ----------

def esc(s):
    return html.escape(str(s), quote=True)


def section_of(item, key):
    for sec in item["sections"]:
        if sec["key"] == key:
            return sec
    return None


def render_items(items, ordered=False):
    tag = "ol" if ordered else "ul"
    rows = "".join(f"<li>{esc(x)}</li>" for x in items)
    return f'<{tag} class="list">{rows}</{tag}>'


def render_gallery(data):
    items = data["personalities"]
    out = []

    chips = ['<button type="button" class="chip is-on" data-filter="all" aria-pressed="true">全部 16 型</button>']
    for g in data["groups"]:
        chips.append(
            f'<button type="button" class="chip" data-filter="{esc(g["name"])}" '
            f'aria-pressed="false">{esc(g["name"])} <span>{esc(g["code"])}</span></button>'
        )

    out.append('<div class="chips" role="group" aria-label="按组筛选">')
    out.append("".join(chips))
    out.append("</div>")
    out.append('<div class="gallery" id="gallery">')

    for p in items:
        pros = section_of(p, "pros")
        cons = section_of(p, "cons")
        jobs = section_of(p, "jobs")
        advice = section_of(p, "advice")
        scene = section_of(p, "scene")
        core = section_of(p, "core")

        style = (f'--c:{p["color"]};--c-text:{p["text"]};--c-tint:{p["tint"]}')
        out.append(
            f'<details class="card" id="t-{esc(p["code"])}" data-group="{esc(p["group"])}" '
            f'data-type="{esc(p["code"])}" style="{style}">'
        )
        out.append(
            '<summary class="card__face">'
            f'<span class="card__word" aria-hidden="true">{esc(p["word"])}</span>'
            '<span class="card__meta">'
            f'<span class="card__code">{esc(p["code"])}</span>'
            f'<span class="card__role">{esc(p["role"])}</span>'
            f'<span class="card__nick">{esc(p["nickname"])}</span>'
            '</span>'
            f'<span class="card__line">{esc(p["wordLine"])}</span>'
            '<span class="card__hint" aria-hidden="true"></span>'
            '</summary>'
        )

        out.append('<div class="card__body">')
        if p["quote"]:
            out.append(f'<blockquote class="card__quote">“{esc(p["quote"])}”</blockquote>')
        if p["feature"]:
            out.append(f'<p class="card__feature">{esc(p["feature"])}</p>')

        out.append('<div class="card__words">')
        out.append(
            '<div class="card__word-pair is-soft">'
            f'<b>{esc(p["word"])}</b><span>{esc(p["wordLine"])}</span>'
            '<em>温柔版</em></div>'
        )
        out.append(
            '<div class="card__word-pair is-spicy">'
            f'<b>{esc(p["spicy"])}</b><span>{esc(p["spicyLine"])}</span>'
            '<em>网友调侃</em></div>'
        )
        out.append("</div>")

        for key, sec in (("scene", scene), ("core", core), ("pros", pros), ("cons", cons)):
            if not sec:
                continue
            out.append('<section class="card__sec">')
            out.append(f'<h4>{esc(SECTION_LABEL[key])}</h4>')
            out.append(render_items(sec["items"]))
            out.append("</section>")

        if jobs:
            out.append('<section class="card__sec">')
            out.append('<h4>适合的工作</h4>')
            out.append(f'<p class="card__jobs">{esc(" ".join(jobs["items"]))}</p>')
            out.append("</section>")

        if advice:
            out.append('<section class="card__sec">')
            out.append('<h4>真心建议</h4>')
            out.append(render_items(advice["items"], ordered=True))
            out.append("</section>")

        if p["closing"]:
            out.append(f'<p class="card__closing">{esc(p["closing"])}</p>')

        # 六维摘要（真实数据，来自 ProfileData）
        bars = []
        for dim in data["dims"]:
            v = p["dims"][dim]
            bars.append(
                f'<li><span>{esc(dim)}</span>'
                f'<i class="bar" style="--v:{v}%"></i><b>{v}</b></li>'
            )
        out.append('<section class="card__sec card__dims">')
        out.append(
            f'<h4>六维工作画像 <a href="#report" class="inline-link" '
            f'data-pick="{esc(p["code"])}">看雷达图</a></h4>'
        )
        out.append(f'<ul class="bars">{"".join(bars)}</ul>')
        out.append(
            f'<p class="card__note">综合 {p["overall"]} · 全站第 {p["rank"]} 名 · '
            f'最强 {esc(p["top"])} {p["dims"][p["top"]]} · 最弱 {esc(p["low"])} {p["dims"][p["low"]]}</p>'
        )
        out.append("</section>")

        out.append("</div></details>")

    out.append("</div>")
    return "\n".join(out)


RADAR_LABEL_R = 88
RADAR_MAX_R = 60
RADAR_CX = 130
RADAR_CY = 130


def radar_points(scores, radius):
    n = len(scores)
    pts = []
    for i, v in enumerate(scores):
        a = -math.pi / 2 + 2 * math.pi * i / n
        r = radius * v / 100.0
        pts.append((RADAR_CX + r * math.cos(a), RADAR_CY + r * math.sin(a)))
    return pts


def render_radar(p, dims):
    n = len(dims)
    scores = [p["dims"][d] for d in dims]

    rings = []
    for frac in (0.25, 0.5, 0.75, 1.0):
        pts = radar_points([100] * n, RADAR_MAX_R * frac)
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        rings.append(f'<polygon class="r-ring" points="{path}"/>')

    axes = []
    for i in range(n):
        a = -math.pi / 2 + 2 * math.pi * i / n
        axes.append(
            f'<line class="r-axis" x1="{RADAR_CX}" y1="{RADAR_CY}" '
            f'x2="{RADAR_CX + RADAR_MAX_R * math.cos(a):.1f}" '
            f'y2="{RADAR_CY + RADAR_MAX_R * math.sin(a):.1f}"/>'
        )

    shape = " ".join(f"{x:.1f},{y:.1f}" for x, y in radar_points(scores, RADAR_MAX_R))

    labels = []
    for i, d in enumerate(dims):
        a = -math.pi / 2 + 2 * math.pi * i / n
        x = RADAR_CX + RADAR_LABEL_R * math.cos(a)
        y = RADAR_CY + RADAR_LABEL_R * math.sin(a)
        dx = math.cos(a)
        anchor = "start" if dx > 0.3 else ("end" if dx < -0.3 else "middle")
        labels.append(
            f'<text class="r-label" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
            f'dominant-baseline="middle">{esc(d)}</text>'
            f'<text class="r-value" x="{x:.1f}" y="{y + 14:.1f}" text-anchor="{anchor}" '
            f'dominant-baseline="middle">{scores[i]}</text>'
        )

    aria = "，".join(f"{d} {p['dims'][d]}" for d in dims)
    return (
        f'<svg class="radar" viewBox="0 0 260 260" role="img" '
        f'aria-label="{esc(p["code"])} 六维工作画像：{esc(aria)}">'
        f'<g>{"".join(rings)}{"".join(axes)}</g>'
        f'<polygon class="r-shape" points="{shape}"/>'
        f'<g>{"".join(labels)}</g>'
        '</svg>'
    )


def render_report(data):
    items = data["personalities"]
    out = []

    chips = []
    for i, p in enumerate(items):
        style = f'--c:{p["color"]};--c-text:{p["text"]}'
        chips.append(
            f'<button type="button" class="chip chip--type{" is-on" if i == 0 else ""}" '
            f'data-type="{esc(p["code"])}" aria-pressed="{"true" if i == 0 else "false"}" '
            f'style="{style}">{esc(p["code"])}</button>'
        )
    out.append('<div class="chips chips--types" role="group" aria-label="选择类型">')
    out.append("".join(chips))
    out.append("</div>")

    out.append('<div class="pf-stage" id="report-stage">')
    for i, p in enumerate(items):
        style = f'--c:{p["color"]};--c-text:{p["text"]};--c-tint:{p["tint"]}'
        cls = "pf-figure is-active" if i == 0 else "pf-figure"
        out.append(f'<figure class="{cls}" data-type="{esc(p["code"])}" style="{style}">')
        out.append(
            '<div class="pf-head">'
            f'<span class="pf-code">{esc(p["code"])}</span>'
            '<div class="pf-title">'
            f'<h3>{esc(p["role"])} · {esc(p["nickname"])}</h3>'
            f'<p>综合 {p["overall"]} · 全站第 {p["rank"]} 名</p>'
            '</div></div>'
        )
        out.append(render_radar(p, data["dims"]))
        bars = []
        for dim in data["dims"]:
            v = p["dims"][dim]
            bars.append(
                f'<li><span>{esc(dim)}</span><i class="bar" style="--v:{v}%"></i><b>{v}</b></li>'
            )
        out.append(f'<ul class="bars bars--lg">{"".join(bars)}</ul>')
        out.append(
            f'<figcaption class="pf-note">最强 {esc(p["top"])} {p["dims"][p["top"]]}，'
            f'最弱 {esc(p["low"])} {p["dims"][p["low"]]}。没有全能选手，只有长板放没放对位置。</figcaption>'
        )
        out.append("</figure>")
    out.append("</div>")
    return "\n".join(out)


def patch_index(index_html, gallery, report):
    if GALLERY_START not in index_html or GALLERY_END not in index_html:
        fail("index.html 缺少 GALLERY 标记")
    if REPORT_START not in index_html or REPORT_END not in index_html:
        fail("index.html 缺少 REPORT 标记")

    def repl(text, start, end, body):
        head, rest = text.split(start, 1)
        _, tail = rest.split(end, 1)
        return f"{head}{start}\n{body}\n{end}{tail}"

    text = repl(index_html, GALLERY_START, GALLERY_END, gallery)
    text = repl(text, REPORT_START, REPORT_END, report)
    return text


def main():
    check = "--check" in sys.argv
    data = build()
    js = render_js(data)
    gallery = render_gallery(data)
    report = render_report(data)

    index_html = read_text(OUT_INDEX)
    patched = patch_index(index_html, gallery, report)

    if check:
        if not os.path.exists(OUT_JS):
            fail(f"产物不存在：{OUT_JS}，请先跑 build_data.py")
        with open(OUT_JS, encoding="utf-8") as f:
            if f.read() != js:
                fail("产物 JS 与源仓库不一致，请重跑 python3 tools/build_data.py")
        if patched != index_html:
            fail("index.html 区块与源仓库不一致，请重跑 python3 tools/build_data.py")
        print("build_data.py --check: 产物与源一致")
        return

    os.makedirs(os.path.dirname(OUT_JS), exist_ok=True)
    os.makedirs(os.path.dirname(OUT_QR), exist_ok=True)
    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write(js)
    with open(QR_PNG, "rb") as src, open(OUT_QR, "wb") as dst:
        dst.write(src.read())
    with open(OUT_INDEX, "w", encoding="utf-8") as f:
        f.write(patched)

    print(f"生成 {os.path.relpath(OUT_JS, WEB_ROOT)}（{len(js)} 字节，16 型）")
    print(f"复制 {os.path.relpath(OUT_QR, WEB_ROOT)}")
    print(f"回填 {os.path.relpath(OUT_INDEX, WEB_ROOT)}（图鉴 {len(data['personalities'])} 卡 + 报告 {len(data['personalities'])} 图）")
    print(f"题库：{data['totalQuestions']} 题 / {len(data['dimIntro'])} 维度")


if __name__ == "__main__":
    main()
