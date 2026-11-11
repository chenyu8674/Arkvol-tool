from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree

FONT = "Microsoft YaHei"

ACCENT = RGBColor(0x25, 0x63, 0xEB)
ACCENT_DARK = RGBColor(0x1E, 0x40, 0xAF)
ACCENT_LIGHT = RGBColor(0xEF, 0xF6, 0xFF)
DARK = RGBColor(0x11, 0x18, 0x27)
BODY = RGBColor(0x37, 0x41, 0x51)
GRAY = RGBColor(0x6B, 0x72, 0x80)
LINE = RGBColor(0xE5, 0xE7, 0xEB)
PANEL = RGBColor(0xF8, 0xFA, 0xFC)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x05, 0x96, 0x69)
GREEN_LIGHT = RGBColor(0xEC, 0xFD, 0xF5)
RED = RGBColor(0xDC, 0x26, 0x26)
RED_LIGHT = RGBColor(0xFE, 0xF2, 0xF2)
ORANGE = RGBColor(0xD9, 0x77, 0x06)
ORANGE_LIGHT = RGBColor(0xFF, 0xFB, 0xEB)

SW = 13.333
SH = 7.5
MX = 0.7

prs = Presentation()
prs.slide_width = Inches(SW)
prs.slide_height = Inches(SH)
BLANK = prs.slide_layouts[6]

state = {"page": 0}


def set_run_font(run, size, color, bold=False):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    rpr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rpr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rpr, qn(tag))
        el.set("typeface", FONT)


def set_bullet(paragraph, char="•", color=ACCENT, indent=0.28):
    ppr = paragraph._p.get_or_add_pPr()
    ppr.set("marL", str(int(Inches(indent))))
    ppr.set("indent", str(-int(Inches(indent))))
    for tag in ("a:buClr", "a:buFont", "a:buChar", "a:buNone"):
        el = ppr.find(qn(tag))
        if el is not None:
            ppr.remove(el)
    clr = etree.SubElement(ppr, qn("a:buClr"))
    srgb = etree.SubElement(clr, qn("a:srgbClr"))
    srgb.set("val", "%02X%02X%02X" % (color[0], color[1], color[2]))
    font = etree.SubElement(ppr, qn("a:buFont"))
    font.set("typeface", "Arial")
    bu = etree.SubElement(ppr, qn("a:buChar"))
    bu.set("char", char)


def add_text(
    slide,
    x,
    y,
    w,
    h,
    paras,
    size=16,
    color=BODY,
    bold=False,
    align=PP_ALIGN.LEFT,
    anchor=MSO_ANCHOR.TOP,
    bullet=False,
    spacing=1.2,
    space_after=6,
    bullet_color=ACCENT,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    if isinstance(paras, str):
        paras = [paras]
    for i, item in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        p.space_after = Pt(space_after)
        runs = item if isinstance(item, list) else [(item, {})]
        for text, opts in runs:
            r = p.add_run()
            r.text = text
            set_run_font(
                r,
                opts.get("size", size),
                opts.get("color", color),
                opts.get("bold", bold),
            )
        if bullet:
            set_bullet(p, color=bullet_color)
    return box


def kill_shadow(shp):
    shp.shadow.inherit = False
    style = shp._element.find(qn("p:style"))
    if style is not None:
        ref = style.find(qn("a:effectRef"))
        if ref is not None:
            ref.set("idx", "0")


def add_rect(slide, x, y, w, h, fill=PANEL, line=LINE, radius=0.05, shape=None):
    kind = shape or MSO_SHAPE.ROUNDED_RECTANGLE
    shp = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        shp.adjustments[0] = radius
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(1)
    kill_shadow(shp)
    shp.text_frame.text = ""
    return shp


def footer(slide, dark=False):
    state["page"] += 1
    color = RGBColor(0x93, 0xC5, 0xFD) if dark else GRAY
    add_text(slide, MX, 7.0, 6, 0.25, "AI 编程入门 · 以 Cursor 为例", size=10, color=color)
    add_text(
        slide,
        SW - MX - 1,
        7.0,
        1,
        0.25,
        str(state["page"]),
        size=10,
        color=color,
        align=PP_ALIGN.RIGHT,
    )


def new_slide(title, tag=None, notes=None):
    slide = prs.slides.add_slide(BLANK)
    add_rect(slide, MX, 0.62, 0.09, 0.5, fill=ACCENT, line=None, radius=0.3)
    if tag:
        add_text(slide, MX + 0.28, 0.32, 8, 0.28, tag, size=12, color=ACCENT, bold=True)
    add_text(
        slide,
        MX + 0.28,
        0.6,
        SW - 2 * MX - 0.28,
        0.6,
        title,
        size=30,
        color=DARK,
        bold=True,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    footer(slide)
    if notes:
        slide.notes_slide.notes_text_frame.text = notes
    return slide


def card(slide, x, y, w, h, title, body, size=14, accent=ACCENT, fill=PANEL, bullet=False, title_size=20):
    add_rect(slide, x, y, w, h, fill=fill, line=LINE)
    add_rect(slide, x + 0.25, y + 0.25, 0.45, 0.06, fill=accent, line=None, radius=0.5)
    add_text(slide, x + 0.25, y + 0.42, w - 0.5, 0.45, title, size=title_size, color=DARK, bold=True)
    add_text(
        slide,
        x + 0.25,
        y + 0.95,
        w - 0.5,
        h - 1.1,
        body,
        size=size + 3,
        color=BODY,
        bullet=bullet,
        spacing=1.25,
        bullet_color=accent,
    )


def add_table(slide, x, y, w, col_widths, rows, row_h=0.62, header_h=0.5, size=14, first_col_bold=True):
    size = size + 2
    n_rows = len(rows)
    n_cols = len(rows[0])
    total_h = header_h + row_h * (n_rows - 1)
    shape = slide.shapes.add_table(n_rows, n_cols, Inches(x), Inches(y), Inches(w), Inches(total_h))
    tbl = shape.table
    tblpr = shape._element.graphic.graphicData.tbl.tblPr
    tblpr.set("firstRow", "0")
    tblpr.set("bandRow", "0")
    style = tblpr.find(qn("a:tableStyleId"))
    if style is not None:
        style.text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"
    for i, cw in enumerate(col_widths):
        tbl.columns[i].width = Inches(cw)
    for r in range(n_rows):
        tbl.rows[r].height = Inches(header_h if r == 0 else row_h)
        for c in range(n_cols):
            cell = tbl.cell(r, c)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Inches(0.18)
            cell.margin_right = Inches(0.12)
            cell.margin_top = Inches(0.04)
            cell.margin_bottom = Inches(0.04)
            cell.fill.solid()
            if r == 0:
                cell.fill.fore_color.rgb = ACCENT
            else:
                cell.fill.fore_color.rgb = WHITE if r % 2 == 1 else PANEL
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.line_spacing = 1.1
            run = p.add_run()
            run.text = rows[r][c]
            if r == 0:
                set_run_font(run, size, WHITE, True)
            else:
                is_first = c == 0 and first_col_bold
                set_run_font(run, size, DARK if is_first else BODY, is_first)
            tcpr = cell._tc.get_or_add_tcPr()
            for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
                ln = etree.SubElement(tcpr, qn(tag))
                ln.set("w", "9525")
                fill = etree.SubElement(ln, qn("a:solidFill"))
                clr = etree.SubElement(fill, qn("a:srgbClr"))
                clr.set("val", "E5E7EB")
            # a:ln* must precede fill in schema order
            fills = [e for e in tcpr if e.tag in (qn("a:solidFill"), qn("a:noFill"))]
            for f in fills:
                tcpr.remove(f)
                tcpr.append(f)
    return shape


def arrow(slide, x, y, w=0.32, h=0.3, color=ACCENT):
    shp = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    shp.line.fill.background()
    kill_shadow(shp)
    return shp


def flow(slide, x, y, w, h, steps, size=14, gap=0.4, first_filled=False, fill=ACCENT_LIGHT, text_color=ACCENT_DARK):
    size = size + 2
    n = len(steps)
    bw = (w - gap * (n - 1)) / n
    for i, s in enumerate(steps):
        bx = x + i * (bw + gap)
        filled = first_filled and i == 0
        add_rect(slide, bx, y, bw, h, fill=ACCENT if filled else fill, line=None if filled else RGBColor(0xBF, 0xDB, 0xFE))
        add_text(
            slide,
            bx + 0.1,
            y,
            bw - 0.2,
            h,
            s,
            size=size,
            color=WHITE if filled else text_color,
            bold=True,
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
            spacing=1.1,
            space_after=0,
        )
        if i < n - 1:
            arrow(slide, bx + bw + (gap - 0.24) / 2, y + h / 2 - 0.13, w=0.24, h=0.26)


def section_slide(num, title, goal, notes=None):
    slide = prs.slides.add_slide(BLANK)
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = ACCENT
    add_text(slide, 1.0, 1.9, 4, 1.8, num, size=110, color=RGBColor(0x93, 0xC5, 0xFD), bold=True)
    add_text(slide, 1.0, 3.95, 11, 1.0, title, size=44, color=WHITE, bold=True)
    add_rect(slide, 1.0, 5.0, 0.8, 0.06, fill=WHITE, line=None, radius=0.5)
    add_text(slide, 1.0, 5.3, 10.5, 0.9, [[("学完能做什么：", {"bold": True}), (goal, {})]], size=18, color=RGBColor(0xDB, 0xEA, 0xFE))
    footer(slide, dark=True)
    if notes:
        slide.notes_slide.notes_text_frame.text = notes
    return slide


# ---------------------------------------------------------------- 封面
s = prs.slides.add_slide(BLANK)
add_rect(s, 0, 0, 0.45, SH, fill=ACCENT, line=None, shape=MSO_SHAPE.RECTANGLE)
add_text(s, 1.3, 1.5, 8, 0.4, "AI CODING 101", size=16, color=ACCENT, bold=True)
add_text(s, 1.3, 2.0, 11, 1.3, "AI 编程入门", size=60, color=DARK, bold=True)
add_text(s, 1.3, 3.35, 11, 0.7, "写给有传统开发经验的工程师 · 以 Cursor 为例", size=24, color=BODY)
add_rect(s, 1.3, 4.35, 1.0, 0.06, fill=ACCENT, line=None, radius=0.5)
tags = ["认知", "工具", "上下文", "方法", "扩展", "实践"]
tx = 1.3
for t in tags:
    tw = 0.42 * len(t) + 0.5
    add_rect(s, tx, 4.8, tw, 0.45, fill=ACCENT_LIGHT, line=RGBColor(0xBF, 0xDB, 0xFE), radius=0.5)
    add_text(s, tx, 4.8, tw, 0.45, t, size=14, color=ACCENT_DARK, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, space_after=0)
    tx += tw + 0.2
state["page"] += 1
s.notes_slide.notes_text_frame.text = "开场：说明本次分享面向有传统开发经验、但尚未系统使用 AI 编程的工程师。目标是建立正确认知、掌握 Cursor 基础用法与协作方法。"

# ---------------------------------------------------------------- 目录
s = new_slide("今天聊什么", tag="AGENDA")
items = [
    ("01", "认知篇", "AI 编程是什么、与传统开发的差异"),
    ("02", "工具篇", "认识 Cursor 与核心交互方式"),
    ("03", "上下文篇", "让 AI 看懂你的项目"),
    ("04", "方法篇", "怎么和 AI 高效协作"),
    ("05", "扩展篇", "让 AI 连接外部世界"),
    ("06", "实践篇", "安全、成本与团队落地"),
    ("07", "实验与总结", "动手练习与核心要点"),
]
col_x = [MX, MX + 6.1]
for i, (n, t, d) in enumerate(items):
    cx = col_x[0] if i < 4 else col_x[1]
    cy = 1.75 + (i if i < 4 else i - 4) * 1.2
    add_rect(s, cx, cy, 5.8, 1.0, fill=PANEL, line=LINE)
    add_text(s, cx + 0.25, cy, 0.9, 1.0, n, size=28, color=ACCENT, bold=True, anchor=MSO_ANCHOR.MIDDLE, space_after=0)
    add_text(s, cx + 1.2, cy + 0.17, 4.4, 0.4, t, size=18, color=DARK, bold=True, space_after=0)
    add_text(s, cx + 1.2, cy + 0.57, 4.4, 0.35, d, size=13, color=GRAY, space_after=0)
add_rect(s, col_x[1], 1.75 + 3 * 1.2, 5.8, 1.0, fill=ACCENT, line=None)
add_text(
    s,
    col_x[1] + 0.3,
    1.75 + 3 * 1.2,
    5.2,
    1.0,
    "建议分 3 讲：认知上手 / 上下文方法 / 扩展落地",
    size=14,
    color=WHITE,
    bold=True,
    anchor=MSO_ANCHOR.MIDDLE,
    space_after=0,
)

# ================================================================ 01 认知篇
section_slide("01", "认知篇：AI 编程是什么", "说清 AI 编程的来龙去脉，建立正确的心智模型。")

s = new_slide("AI 编程的演进：从补全到自主 Agent", tag="01 认知篇",
              notes="强调演进的主线是 AI 的自主程度越来越高，人的角色从逐行编写转向定义目标与审查结果。")
stages = [
    ("代码补全", "IntelliSense、早期 Copilot\n按行预测下一段代码"),
    ("对话式辅助", "ChatGPT 复制粘贴\n问答与代码片段"),
    ("IDE 内嵌", "Chat / Edit 直接改代码\n理解当前文件与项目"),
    ("Agent", "自主读代码、改多文件\n运行命令并迭代修正"),
    ("云端 Agent", "后台异步执行任务\n自动创建分支与 PR"),
]
bw = 2.1
gap = (SW - 2 * MX - 5 * bw) / 4
for i, (t, d) in enumerate(stages):
    bx = MX + i * (bw + gap)
    hh = 2.5 + i * 0.3
    yy = 5.0 - hh
    add_rect(s, bx, yy, bw, hh, fill=ACCENT_LIGHT if i < 4 else ACCENT, line=RGBColor(0xBF, 0xDB, 0xFE) if i < 4 else None)
    add_text(s, bx + 0.15, yy + 0.2, bw - 0.3, 0.4, t, size=18, color=ACCENT_DARK if i < 4 else WHITE, bold=True)
    add_text(s, bx + 0.15, yy + 0.75, bw - 0.3, hh - 0.85, d.split("\n"), size=14, color=BODY if i < 4 else WHITE, spacing=1.2)
add_rect(s, MX, 5.3, SW - 2 * MX, 0.06, fill=LINE, line=None, radius=0.5)
add_text(s, MX, 5.5, 4, 0.4, "AI 自主程度：低", size=15, color=GRAY, bold=True)
add_text(s, SW - MX - 4, 5.5, 4, 0.4, "高", size=15, color=ACCENT, bold=True, align=PP_ALIGN.RIGHT)
add_text(
    s,
    MX,
    6.15,
    SW - 2 * MX,
    0.6,
    [[("核心变化：", {"bold": True, "color": ACCENT}), ("人的角色从“逐行编写”转向“定义目标 + 审查结果”", {})]],
    size=17,
    color=DARK,
)

s = new_slide("大模型：开发者必须懂的四个概念", tag="01 认知篇",
              notes="不展开模型原理，只讲会影响日常使用的四点。幻觉是后面强调审查和验证的根本原因。")
cw = (SW - 2 * MX - 3 * 0.3) / 4
cards = [
    ("逐词预测", ["基于上下文预测下一个 token", "不是搜索引擎", "也不是确定性程序"]),
    ("上下文窗口", ["模型的“工作内存”", "容量有上限", "超出或过长会丢信息"]),
    ("Token 与成本", ["输入输出均按 token 计量", "越长越慢、越贵", "精简上下文即省钱提速"]),
    ("幻觉", ["会自信地编造 API 或结论", "听起来对 ≠ 真的对", "必须验证，不能盲信"]),
]
for i, (t, b) in enumerate(cards):
    card(s, MX + i * (cw + 0.3), 1.65, cw, 3.3, t, b, size=14, bullet=True, accent=RED if i == 3 else ACCENT)
add_rect(s, MX, 5.3, SW - 2 * MX, 1.2, fill=ACCENT_LIGHT, line=None)
add_text(
    s,
    MX + 0.35,
    5.3,
    SW - 2 * MX - 0.7,
    1.2,
    [
        [("模型怎么选？", {"bold": True, "color": ACCENT_DARK})],
        "强推理型模型用于复杂任务与设计；快速型模型用于简单修改与补全。按任务选择，不必纠结具体型号。",
    ],
    size=16,
    anchor=MSO_ANCHOR.MIDDLE,
    space_after=4,
)

s = new_slide("与传统开发思维的差异", tag="01 认知篇")
rows = [
    ["维度", "传统开发", "AI 辅助开发"],
    ["输出特性", "确定性：同样输入得到同样结果", "概率性：同样输入可能得到不同结果"],
    ["主要工作", "编写代码", "描述意图 + 审查结果"],
    ["开发者角色", "实现者", "技术负责人 + 评审者"],
    ["质量保障", "编译、测试、评审", "同样需要，而且更依赖自动化验证"],
    ["核心能力", "语法与框架熟练度", "需求拆解、上下文组织、判断力"],
]
add_table(s, MX, 1.75, SW - 2 * MX, [2.2, 4.9, 4.8], rows, row_h=0.78, header_h=0.55, size=15)

s = new_slide("三个常见误区", tag="01 认知篇",
              notes="这一页用来校准预期。尤其强调第三条：责任不会转移给 AI。")
mis = [
    ("“AI 会取代工程师”", "工程基础越扎实，越能用好 AI。AI 放大的是你的能力，不是替代判断。"),
    ("“一句话就能生成完整系统”", "拆小任务、分步迭代、每步验证，成功率远高于一次性大需求。"),
    ("“AI 写的代码可以直接信任”", "你对提交的每一行代码负责。审查和验证永远不能省。"),
]
add_text(s, MX + 0.5, 1.6, 5, 0.4, "误区", size=14, color=RED, bold=True)
add_text(s, MX + 6.5, 1.6, 5, 0.4, "更准确的认识", size=14, color=GREEN, bold=True)
for i, (a, b) in enumerate(mis):
    yy = 2.05 + i * 1.6
    add_rect(s, MX, yy, 5.9, 1.4, fill=RED_LIGHT, line=None)
    add_text(s, MX + 0.3, yy, 5.3, 1.4, a, size=19, color=DARK, bold=True, anchor=MSO_ANCHOR.MIDDLE, space_after=0)
    arrow(s, MX + 6.05, yy + 0.55, w=0.35, h=0.3, color=GRAY)
    add_rect(s, MX + 6.5, yy, SW - 2 * MX - 6.5, 1.4, fill=GREEN_LIGHT, line=None)
    add_text(s, MX + 6.8, yy, SW - 2 * MX - 7.1, 1.4, b, size=17, color=BODY, anchor=MSO_ANCHOR.MIDDLE, space_after=0)

# ================================================================ 02 工具篇
section_slide("02", "工具篇：认识 Cursor", "独立安装配置，并完成第一次 AI 辅助开发。")

s = new_slide("Cursor 是什么", tag="02 工具篇",
              notes="强调 Cursor 基于 VS Code，迁移成本低。产品形态以官方最新信息为准。")
add_rect(s, MX, 1.7, 4.6, 4.9, fill=ACCENT, line=None)
add_text(s, MX + 0.4, 2.0, 3.8, 0.5, "AI 原生 IDE", size=26, color=WHITE, bold=True)
add_text(
    s,
    MX + 0.4,
    2.8,
    3.8,
    3.6,
    [
        "基于 VS Code 构建",
        "插件、快捷键、主题基本可迁移",
        "AI 能力深度融入编辑、搜索、终端与评审流程",
    ],
    size=18,
    color=WHITE,
    bullet=True,
    bullet_color=WHITE,
    spacing=1.35,
    space_after=12,
)
forms = [
    ("桌面 IDE", "日常编码的主战场\nTab、Chat、Agent 等"),
    ("CLI", "在终端中使用 Agent\n适合脚本化与自动化"),
    ("云端 Agent", "在云端环境后台执行\n异步完成任务并提 PR"),
    ("Bugbot", "PR 自动代码审查\n提前发现潜在 bug"),
]
fw = (SW - 2 * MX - 4.6 - 0.3 - 0.3) / 2
for i, (t, d) in enumerate(forms):
    fx = MX + 4.9 + (i % 2) * (fw + 0.3)
    fy = 1.7 + (i // 2) * 2.55
    card(s, fx, fy, fw, 2.35, t, d.split("\n"), size=14)

s = new_slide("安装与初始配置", tag="02 工具篇")
flow(
    s,
    MX,
    1.9,
    SW - 2 * MX,
    1.2,
    ["注册账号", "安装并导入\nVS Code 配置", "了解套餐与用量", "启用隐私模式"],
    size=16,
    gap=0.5,
)
card(
    s,
    MX,
    3.5,
    5.9,
    3.1,
    "上手前先搞清楚",
    ["套餐不同，可用模型与额度不同", "用量按模型与 token 消耗计算", "导入后，原有插件与快捷键可继续使用"],
    size=14,
    bullet=True,
)
card(
    s,
    MX + 6.2,
    3.5,
    SW - 2 * MX - 6.2,
    3.1,
    "企业用户重点关注",
    ["隐私模式：降低代码被存储或用于训练的风险", "团队账号与统一的管理策略", "具体条款以官方最新说明与公司政策为准"],
    size=14,
    bullet=True,
    accent=ORANGE,
)

s = new_slide("核心交互方式：按自主程度由低到高", tag="02 工具篇",
              notes="现场演示建议：Tab 和 Cmd/Ctrl+K 各演示一次，再用 Ask 解释代码，最后用 Agent 完成一个小功能。")
rows = [
    ["功能", "用途", "类比", "自主程度"],
    ["Tab", "智能补全，可预测下一处编辑", "增强版自动补全", "●○○○○"],
    ["Inline Edit\n（Cmd/Ctrl + K）", "选中代码，用自然语言局部修改", "有理解力的重构工具", "●●○○○"],
    ["Ask 模式", "提问、解释代码、探索方案，不改文件", "了解项目的同事", "●●○○○"],
    ["Plan 模式", "先梳理方案与步骤，确认后再执行", "先做设计评审再开工", "●●●○○"],
    ["Agent 模式", "自主多步骤完成任务：搜索、编辑、运行命令", "能独立干活的初级工程师", "●●●●●"],
]
add_table(s, MX, 1.7, SW - 2 * MX, [2.6, 4.6, 3.0, 1.93], rows, row_h=0.82, header_h=0.5, size=14)

s = new_slide("界面速览与安全网", tag="02 工具篇")
cw = (SW - 2 * MX - 3 * 0.3) / 4
cards = [
    ("Chat 面板", ["对话入口", "切换 Ask / Plan / Agent", "选择模型"]),
    ("Diff 审查", ["AI 改动以 diff 呈现", "逐处接受或拒绝", "先看再收，不盲接受"]),
    ("Checkpoint", ["每轮改动自动留存", "不满意可一键回退", "让你敢放手让 AI 试"]),
    ("终端与命令", ["Agent 可执行命令", "危险操作需你确认", "可配置允许范围"]),
]
for i, (t, b) in enumerate(cards):
    card(s, MX + i * (cw + 0.3), 1.7, cw, 3.4, t, b, size=14, bullet=True)
add_rect(s, MX, 5.5, SW - 2 * MX, 1.0, fill=ACCENT_LIGHT, line=None)
add_text(
    s,
    MX + 0.35,
    5.5,
    SW - 2 * MX - 0.7,
    1.0,
    [[("建议习惯：", {"bold": True, "color": ACCENT_DARK}), ("开始大改动前先提交 Git，再让 Agent 动手；Git 与 Checkpoint 是你的双重保险。", {})]],
    size=17,
    anchor=MSO_ANCHOR.MIDDLE,
    space_after=0,
)

# ================================================================ 03 上下文篇
section_slide("03", "上下文篇：让 AI 看懂你的项目", "理解“上下文质量决定输出质量”，掌握喂给 AI 信息的方法。")

s = new_slide("上下文质量决定输出质量", tag="03 上下文篇",
              notes="这是全场最重要的一个观念。同样的模型，给的上下文不同，结果差别巨大。")
add_rect(s, MX, 1.8, SW - 2 * MX, 1.5, fill=ACCENT_LIGHT, line=None)
add_text(
    s,
    MX,
    1.8,
    SW - 2 * MX,
    1.5,
    [[("输出质量  =  模型能力  ×  上下文质量  ×  指令清晰度", {"bold": True})]],
    size=30,
    color=ACCENT_DARK,
    align=PP_ALIGN.CENTER,
    anchor=MSO_ANCHOR.MIDDLE,
    space_after=0,
)
card(
    s,
    MX,
    3.7,
    5.9,
    2.9,
    "Cursor 如何理解项目",
    ["对代码库建立索引，支持语义搜索", "Agent 会自行搜索、阅读相关文件", "你不用手动粘贴整个项目"],
    size=14,
    bullet=True,
)
card(
    s,
    MX + 6.2,
    3.7,
    SW - 2 * MX - 6.2,
    2.9,
    "但你仍然需要",
    ["指出关键文件、规范与参考实现", "补充 AI 无法自行获得的信息", "上下文给得准，结果才稳定"],
    size=14,
    bullet=True,
    accent=ORANGE,
)

s = new_slide("用 @ 引用精准提供上下文", tag="03 上下文篇")
rows = [
    ["引用方式", "适用场景"],
    ["@文件 / @文件夹", "指定要看的代码范围，如“参考 @UserService 的写法”"],
    ["@代码符号", "直接引用某个函数、类或方法"],
    ["@Docs", "引用框架或库的官方文档，减少编造 API"],
    ["@Web", "联网搜索最新资料与解决方案"],
    ["@Git", "引用提交、diff 与分支差异，用于评审或排查"],
    ["图片", "粘贴设计稿、报错截图、架构图"],
]
add_table(s, MX, 1.7, SW - 2 * MX, [3.2, 8.73], rows, row_h=0.64, header_h=0.5, size=15)
add_text(s, MX, 6.5, SW - 2 * MX, 0.3, "注：具体入口与名称随版本更新，以当前 Cursor 界面为准。", size=11, color=GRAY)

s = new_slide("上下文管理四原则", tag="03 上下文篇")
cw = (SW - 2 * MX - 0.3) / 2
ch = 2.35
principles = [
    ("给得准，比给得多更重要", "只提供与任务相关的文件与信息。无关内容会稀释模型的注意力。"),
    ("换任务就开新对话", "一个对话只解决一类问题，避免旧话题干扰新任务。"),
    ("长对话会变“笨”", "早期信息被稀释或遗忘。必要时让 AI 总结要点，再在新对话中继续。"),
    ("避免上下文污染", "错误的尝试与结论留在对话里，会误导后续步骤。回退后重新描述更有效。"),
]
for i, (t, b) in enumerate(principles):
    card(s, MX + (i % 2) * (cw + 0.3), 1.7 + (i // 2) * (ch + 0.25), cw, ch, t, b, size=14.5)

s = new_slide("Rules：项目级的“长期记忆”", tag="03 上下文篇",
              notes="Rules 类似新人入职文档，但是写给 AI 看。建议提交到 Git，团队共享。")
add_rect(s, MX, 1.7, 4.2, 4.9, fill=ACCENT, line=None)
add_text(s, MX + 0.35, 2.0, 3.5, 0.5, "它是什么", size=22, color=WHITE, bold=True)
add_text(
    s,
    MX + 0.35,
    2.7,
    3.5,
    3.8,
    [
        "每次对话自动带上的项目约定",
        [("位置：", {"bold": True}), (".cursor/rules、AGENTS.md", {})],
        "纳入 Git，团队共享",
        "类比：写给 AI 的新人入职文档",
    ],
    size=18,
    color=WHITE,
    bullet=True,
    bullet_color=WHITE,
    spacing=1.3,
    space_after=10,
)
rw = (SW - 2 * MX - 4.2 - 0.6) / 2
card(
    s,
    MX + 4.5,
    1.7,
    rw,
    4.9,
    "适合写进去",
    ["技术栈与版本", "目录结构与分层约定", "编码规范与命名", "构建、测试常用命令", "明确的禁止事项"],
    size=14,
    bullet=True,
    accent=GREEN,
)
card(
    s,
    MX + 4.5 + rw + 0.3,
    1.7,
    rw,
    4.9,
    "不适合写进去",
    ["整份需求文档", "频繁变化的信息", "读代码就能看出的内容", "冗长的大段说明", "与项目无关的个人偏好"],
    size=14,
    bullet=True,
    accent=RED,
)

# ================================================================ 04 方法篇
section_slide("04", "方法篇：怎么和 AI 高效协作", "从“能用”到“用得好”：写好指令、选对流程、做好验证与审查。")

s = new_slide("提示词基本功：目标、背景、约束、验收", tag="04 方法篇",
              notes="现场可以让学员把左边的模糊需求改写成右边的样子，再对比输出差异。")
chips = ["目标", "背景", "约束", "验收标准"]
cx = MX
for c in chips:
    cwid = 1.9
    add_rect(s, cx, 1.65, cwid, 0.5, fill=ACCENT, line=None, radius=0.5)
    add_text(s, cx, 1.65, cwid, 0.5, c, size=15, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, space_after=0)
    cx += cwid + 0.25
add_rect(s, MX, 2.55, 4.4, 3.9, fill=RED_LIGHT, line=None)
add_text(s, MX + 0.3, 2.75, 3.8, 0.4, "模糊的指令", size=16, color=RED, bold=True)
add_text(s, MX + 0.3, 3.4, 3.8, 2.8, "“帮我加个登录功能”", size=22, color=DARK, bold=True, spacing=1.3)
add_text(
    s,
    MX + 0.3,
    4.8,
    3.8,
    1.5,
    ["缺少技术栈与参考实现", "没有边界，容易过度发挥", "无法判断做没做完"],
    size=16,
    color=BODY,
    bullet=True,
    bullet_color=RED,
)
arrow(s, MX + 4.55, 4.25, w=0.4, h=0.35, color=GRAY)
gx = MX + 5.1
add_rect(s, gx, 2.55, SW - MX - gx, 3.9, fill=GREEN_LIGHT, line=None)
add_text(s, gx + 0.3, 2.75, 6, 0.4, "清晰的指令", size=16, color=GREEN, bold=True)
add_text(
    s,
    gx + 0.3,
    3.3,
    SW - MX - gx - 0.6,
    3.1,
    [
        [("目标：", {"bold": True, "color": DARK}), ("新增邮箱 + 密码登录接口", {})],
        [("背景：", {"bold": True, "color": DARK}), ("Spring Boot 项目，写法参考 @UserController", {})],
        [("约束：", {"bold": True, "color": DARK}), ("复用现有 JwtUtil，不引入新依赖", {})],
        [("验收：", {"bold": True, "color": DARK}), ("运行 AuthTests，全部通过", {})],
    ],
    size=18,
    spacing=1.3,
    space_after=12,
)

s = new_slide("典型工作流", tag="04 方法篇")
workflows = [
    ("新功能开发", ["需求描述", "Plan 方案", "Agent 实现", "运行验证"]),
    ("Bug 修复", ["报错 + 复现步骤", "定位原因", "修复", "回归测试"]),
    ("读懂陌生代码", ["Ask 提问全貌", "追问关键模块", "梳理调用链"]),
    ("重构与迁移", ["拆成小步", "逐步替换", "每步跑测试"]),
]
for i, (name, steps) in enumerate(workflows):
    yy = 1.7 + i * 1.18
    add_rect(s, MX, yy, 2.4, 0.95, fill=ACCENT, line=None)
    add_text(s, MX, yy, 2.4, 0.95, name, size=16, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, space_after=0)
    flow(s, MX + 2.65, yy, SW - 2 * MX - 2.65, 0.95, steps, size=14, gap=0.4)
add_text(
    s,
    MX,
    6.45,
    SW - 2 * MX,
    0.4,
    "此外：生成测试、补充文档、撰写 commit message，也是 AI 的高性价比场景。",
    size=15,
    color=GRAY,
)

s = new_slide("让 AI 自我验证：成功率的关键", tag="04 方法篇",
              notes="这是从“能用”到“好用”的关键。给 AI 一个可以自动判断对错的目标，它就能自己迭代。")
flow(
    s,
    MX,
    1.8,
    SW - 2 * MX,
    1.1,
    ["生成改动", "运行测试 / Lint /\n类型检查", "读取失败信息", "自动修正"],
    size=15,
    gap=0.55,
    first_filled=True,
)
add_text(s, MX, 3.05, SW - 2 * MX, 0.4, "↺  循环往复，直到全部通过", size=15, color=ACCENT, bold=True, align=PP_ALIGN.CENTER)
cw = (SW - 2 * MX - 2 * 0.3) / 3
cards = [
    ("可验证的目标", ["“让测试通过”远好于“写得好一点”", "给 AI 明确的判定标准"]),
    ("测试先行", ["TDD 在 AI 时代价值更高", "测试就是写给 AI 的精确规格"]),
    ("把验证写进指令", ["说明用什么命令验证", "写进 Rules，省得每次重复"]),
]
for i, (t, b) in enumerate(cards):
    card(s, MX + i * (cw + 0.3), 3.7, cw, 2.9, t, b, size=14, bullet=True)

s = new_slide("审查与把关：你对每一行提交负责", tag="04 方法篇")
cw = (SW - 2 * MX - 0.3) / 2
card(
    s,
    MX,
    1.7,
    cw,
    3.7,
    "AI 代码的常见问题",
    ["过度设计，多出不必要的抽象", "重复造轮子，忽略已有工具函数", "引入不必要的依赖", "存在安全隐患", "看似正确，实则有隐藏 bug"],
    size=14.5,
    bullet=True,
    accent=RED,
)
card(
    s,
    MX + cw + 0.3,
    1.7,
    cw,
    3.7,
    "Review 清单",
    ["是否满足需求与验收标准", "diff 范围是否超出预期", "是否有测试覆盖", "是否复用了现有代码", "输入校验、密钥、权限是否到位"],
    size=14.5,
    bullet=True,
    accent=GREEN,
)
add_rect(s, MX, 5.75, SW - 2 * MX, 0.85, fill=ACCENT, line=None)
add_text(
    s,
    MX,
    5.75,
    SW - 2 * MX,
    0.85,
    "原则：AI 负责起草，人负责判断与担责",
    size=20,
    color=WHITE,
    bold=True,
    align=PP_ALIGN.CENTER,
    anchor=MSO_ANCHOR.MIDDLE,
    space_after=0,
)

# ================================================================ 05 扩展篇
section_slide("05", "扩展篇：让 AI 连接外部世界", "了解 AI 能力边界如何通过工具、流程与云端协作扩展。")

s = new_slide("扩展能力：MCP、Skills、Hooks、Subagents", tag="05 扩展篇",
              notes="扩展能力不必一次学完。建议先从 Rules 和 MCP 开始，再按需引入其他能力。")
cw = (SW - 2 * MX - 0.3) / 2
ch = 2.4
exts = [
    ("MCP", "Model Context Protocol。标准协议，让 AI 调用外部工具与数据：数据库、Jira、Figma、监控系统等。"),
    ("Skills / Commands", "把团队重复出现的流程封装为可复用能力，一次编写，多人多次使用。"),
    ("Hooks", "在 Agent 的关键节点插入自定义脚本，例如自动格式化、拦截危险操作。"),
    ("Subagents", "把任务分给多个子代理并行处理，各自拥有独立上下文，适合调研与大范围修改。"),
]
for i, (t, b) in enumerate(exts):
    card(s, MX + (i % 2) * (cw + 0.3), 1.7 + (i // 2) * (ch + 0.25), cw, ch, t, b, size=14.5)

s = new_slide("云端 Agent 与 AI 代码审查", tag="05 扩展篇")
add_text(s, MX, 1.6, 6, 0.4, "云端 / 后台 Agent", size=18, color=DARK, bold=True)
flow(
    s,
    MX,
    2.1,
    SW - 2 * MX,
    1.0,
    ["分配任务", "云端环境执行", "提交分支", "创建 PR", "人工评审"],
    size=15,
    gap=0.45,
    first_filled=True,
)
card(
    s,
    MX,
    3.6,
    5.9,
    3.0,
    "适合交给云端 Agent",
    ["边界清晰的小需求与缺陷修复", "批量、重复性的改动", "不需要你盯着的耗时任务"],
    size=16,
    bullet=True,
    accent=GREEN,
)
card(
    s,
    MX + 6.2,
    3.6,
    SW - 2 * MX - 6.2,
    3.0,
    "Bugbot：AI 代码审查",
    ["在 PR 阶段自动审查改动", "提前发现潜在 bug 与安全问题", "是人工评审的补充，不是替代"],
    size=16,
    bullet=True,
)

# ================================================================ 06 实践篇
section_slide("06", "实践篇：落地到真实团队", "知道风险在哪，知道如何在团队中规范地推广。")

s = new_slide("安全与合规", tag="06 实践篇",
              notes="企业落地最常被问到的就是这一页。建议结合公司的实际安全政策补充。")
cw = (SW - 2 * MX - 3 * 0.3) / 4
cards = [
    ("数据隐私", ["了解代码是否离开本地", "启用隐私模式", "核对数据留存与训练政策"]),
    ("密钥与敏感信息", ["不要把密钥贴进对话", "不要提交 .env 与凭证", "用密钥管理服务"]),
    ("命令执行权限", ["谨慎设置自动执行范围", "危险命令必须人工确认", "在隔离环境中验证"]),
    ("依赖与许可证", ["核查新增依赖的来源", "关注开源许可证合规", "警惕 AI 编造的包名"]),
]
for i, (t, b) in enumerate(cards):
    card(s, MX + i * (cw + 0.3), 1.7, cw, 4.2, t, b, size=14, bullet=True, accent=ORANGE)
add_text(
    s,
    MX,
    6.2,
    SW - 2 * MX,
    0.5,
    "原则：对 AI 的授权，不应超过你对一个新入职同事的授权。",
    size=17,
    color=DARK,
    bold=True,
)

s = new_slide("成本、效率与团队规范", tag="06 实践篇")
cw = (SW - 2 * MX - 0.3) / 2
card(
    s,
    MX,
    1.7,
    cw,
    4.0,
    "成本与效率",
    ["简单任务用快速模型，复杂任务再用强模型", "控制上下文长度，既省钱又提质", "衡量真实提效：交付周期、缺陷率、评审耗时", "不要只看“生成了多少行”"],
    size=17,
    bullet=True,
)
card(
    s,
    MX + cw + 0.3,
    1.7,
    cw,
    4.0,
    "团队协作规范",
    ["统一 Rules，并纳入 Git 版本管理", "明确 AI 辅助代码的评审标准", "沉淀常用 Prompt、Skills 与最佳实践", "新人借助 AI 上手，仍需理解核心设计"],
    size=17,
    bullet=True,
)

s = new_slide("常见坑与应对", tag="06 实践篇")
rows = [
    ["现象", "应对方法"],
    ["越改越乱，陷入死循环", "回退到 Checkpoint，换个思路重新描述需求"],
    ["长对话后质量下降", "让 AI 总结要点，新开对话继续"],
    ["一次改动太大，无法审查", "拆成小任务，分步提交"],
    ["AI 编造不存在的 API", "用 @Docs 提供文档，并实际运行验证"],
    ["过度依赖，自身能力退化", "坚持阅读并理解代码，关键设计自己把关"],
]
add_table(s, MX, 1.75, SW - 2 * MX, [4.6, 7.33], rows, row_h=0.78, header_h=0.55, size=15)

# ================================================================ 07 实验与总结
section_slide("07", "动手实验与总结", "通过练习巩固所学，并带走五个核心要点。")

s = new_slide("动手实验：由浅入深", tag="07 实验与总结",
              notes="建议准备一个小型示例项目，所有学员基于同一代码库练习，便于对比结果。")
rows = [
    ["阶段", "练习内容", "目标"],
    ["入门", "用 Tab 和 Cmd/Ctrl+K 修改一个已有的小项目", "熟悉基础交互"],
    ["进阶", "用 Ask 读懂陌生代码库，再用 Agent 加一个小功能", "体会模式差异"],
    ["方法", "同一需求，对比模糊指令与“精确指令 + 验收标准”", "理解指令的作用"],
    ["工程化", "为项目写一份 Rules，观察输出变化", "掌握长期记忆"],
    ["综合", "Plan → Agent → 自动测试，完成并评审一个完整功能", "走通完整流程"],
]
add_table(s, MX, 1.75, SW - 2 * MX, [1.7, 7.4, 2.83], rows, row_h=0.8, header_h=0.55, size=14.5)

s = new_slide("建议的讲授节奏", tag="07 实验与总结")
cw = (SW - 2 * MX - 2 * 0.3) / 3
lectures = [
    ("第 1 讲", "认知 + 上手", ["认知篇", "工具篇", "现场演示 30 到 40 分钟"]),
    ("第 2 讲", "上下文 + 方法", ["上下文篇", "方法篇", "重点：指令与自动验证"]),
    ("第 3 讲", "扩展 + 落地", ["扩展篇", "实践篇", "综合实验与答疑"]),
]
for i, (a, b, c) in enumerate(lectures):
    x0 = MX + i * (cw + 0.3)
    add_rect(s, x0, 1.7, cw, 1.4, fill=ACCENT, line=None)
    add_text(s, x0 + 0.3, 1.85, cw - 0.6, 0.4, a, size=14, color=RGBColor(0xBF, 0xDB, 0xFE), bold=True)
    add_text(s, x0 + 0.3, 2.3, cw - 0.6, 0.6, b, size=22, color=WHITE, bold=True)
    add_rect(s, x0, 3.1, cw, 3.3, fill=PANEL, line=LINE)
    add_text(s, x0 + 0.3, 3.4, cw - 0.6, 2.8, c, size=18, color=BODY, bullet=True, spacing=1.3, space_after=14)

s = new_slide("五个核心要点", tag="07 实验与总结",
              notes="收尾：回顾五点，并强调 AI 是放大器，基础与判断力才是核心。")
points = [
    ("心智", "AI 是概率性的助手，不是确定性的程序，也不会取代你的判断。"),
    ("上下文", "输出质量取决于上下文质量，给得准比给得多更重要。"),
    ("指令", "目标、背景、约束、验收标准，缺一不可。"),
    ("验证", "让 AI 能自动验证，同时人要审查每一行提交。"),
    ("沉淀", "用 Rules、Skills 把经验固化，让团队一起变强。"),
]
for i, (t, b) in enumerate(points):
    yy = 1.7 + i * 1.02
    add_rect(s, MX, yy, SW - 2 * MX, 0.88, fill=PANEL, line=LINE)
    add_rect(s, MX, yy, 0.12, 0.88, fill=ACCENT, line=None, shape=MSO_SHAPE.RECTANGLE)
    add_text(s, MX + 0.4, yy, 0.8, 0.88, str(i + 1), size=26, color=ACCENT, bold=True, anchor=MSO_ANCHOR.MIDDLE, space_after=0)
    add_text(s, MX + 1.1, yy, 1.8, 0.88, t, size=20, color=DARK, bold=True, anchor=MSO_ANCHOR.MIDDLE, space_after=0)
    add_text(s, MX + 3.0, yy, SW - 2 * MX - 3.3, 0.88, b, size=17, color=BODY, anchor=MSO_ANCHOR.MIDDLE, space_after=0)

# ---------------------------------------------------------------- 结束页
s = prs.slides.add_slide(BLANK)
bg = s.background.fill
bg.solid()
bg.fore_color.rgb = ACCENT
add_text(s, 1.0, 2.6, 11, 1.3, "谢谢", size=66, color=WHITE, bold=True)
add_rect(s, 1.0, 4.0, 0.8, 0.06, fill=WHITE, line=None, radius=0.5)
add_text(s, 1.0, 4.3, 11, 0.8, "Q & A · 欢迎提问与交流", size=24, color=RGBColor(0xDB, 0xEA, 0xFE))
footer(s, dark=True)

prs.save("ai-coding-intro/AI编程入门-以Cursor为例.pptx")
print("slides:", len(prs.slides))
