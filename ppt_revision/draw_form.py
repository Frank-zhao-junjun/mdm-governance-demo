# -*- coding: utf-8 -*-
"""用 Pillow 精确绘制物料表单 UI 图（文字 100% 准确）"""
from PIL import Image, ImageDraw, ImageFont

W, H = 2048, 781
BG = (245, 247, 250)
CARD_BG = (255, 255, 255)
HEADER_BG = (31, 56, 100)       # 深蓝
HEADER_TEXT = (255, 255, 255)
LABEL = (120, 120, 120)
VALUE = (26, 26, 26)
BORDER = (225, 228, 232)
ROW_LINE = (235, 238, 242)

FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

def f(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# 卡片
card_x, card_y, card_w, card_h = 40, 30, W - 80, H - 60
radius = 18
d.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h],
                    radius=radius, fill=CARD_BG, outline=BORDER, width=2)

# 顶部深蓝条（只在卡片顶部圆角内）
header_h = 95
# 画一个覆盖顶部的圆角矩形，再把下两角盖住
d.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + header_h + radius],
                    radius=radius, fill=HEADER_BG)
d.rectangle([card_x, card_y + header_h, card_x + card_w, card_y + header_h + radius],
            fill=HEADER_BG)
header_font = f(40, bold=True)
title = "AI已根据铭牌自动填充，请核对确认"
bbox = d.textbbox((0, 0), title, font=header_font)
tw = bbox[2] - bbox[0]
d.text((card_x + (card_w - tw) // 2, card_y + 22), title, font=header_font, fill=HEADER_TEXT)

# 表格
table_top = card_y + header_h
row_h = (card_h - header_h) // 4
col_x = [card_x + 70, card_x + 470, card_x + 1080, card_x + 1430]
label_font = f(34)
value_font = f(38, bold=True)

rows = [
    ("物料编码", "10-y-088", "物料名称", "六角头螺栓"),
    ("规格型号", "M10×20",   "材质",     "碳钢"),
    ("表面处理", "发黑",      "计量单位", "PC"),
    ("性能等级", "8.8级",    "执行标准", "GB5783"),
]

for i, (l1, v1, l2, v2) in enumerate(rows):
    y = table_top + i * row_h
    # 行分隔线
    if i > 0:
        d.line([card_x + 30, y, card_x + card_w - 30, y], fill=ROW_LINE, width=2)
    cy = y + row_h // 2 - 24
    d.text((col_x[0], cy), l1, font=label_font, fill=LABEL)
    d.text((col_x[1], cy - 2), v1, font=value_font, fill=VALUE)
    d.text((col_x[2], cy), l2, font=label_font, fill=LABEL)
    d.text((col_x[3], cy - 2), v2, font=value_font, fill=VALUE)

out = r"D:\AI\14 - 数据治理\ppt_revision\new_images\p15_form.png"
img.save(out, "PNG")
print("saved", out)
