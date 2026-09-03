#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
import os

OUTPUT_DIR = "/mnt/okcomputer/output/bg"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PAGE_W = 794
PAGE_H = 1123

# 专业商务配色 - 深蓝灰系
COLORS = {
    'primary': '#2C3E50',
    'secondary': '#34495E',
    'accent': '#3498DB',
    'light': '#ECF0F1',
    'warm': '#E8D5B7',
}

COVER_BG_HTML = f'''
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    width: {PAGE_W}px;
    height: {PAGE_H}px;
    background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
    position: relative;
    overflow: hidden;
}}

.top-bar {{
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 12px;
    background: linear-gradient(90deg, {COLORS['primary']} 0%, {COLORS['accent']} 100%);
}}

.left-line {{
    position: absolute;
    top: 80px;
    left: 60px;
    width: 4px;
    height: 200px;
    background: linear-gradient(180deg, {COLORS['accent']} 0%, {COLORS['primary']} 100%);
    border-radius: 2px;
}}

.geo-1 {{
    position: absolute;
    top: 60px;
    right: 60px;
    width: 120px;
    height: 120px;
    border: 3px solid {COLORS['accent']}40;
    border-radius: 50%;
}}

.geo-2 {{
    position: absolute;
    top: 90px;
    right: 90px;
    width: 60px;
    height: 60px;
    background: {COLORS['accent']}15;
    border-radius: 50%;
}}

.bottom-deco {{
    position: absolute;
    bottom: 0;
    left: 0;
    width: 100%;
    height: 180px;
    background: linear-gradient(180deg, transparent 0%, {COLORS['primary']}08 100%);
}}

.bottom-line {{
    position: absolute;
    bottom: 80px;
    left: 60px;
    right: 60px;
    height: 1px;
    background: linear-gradient(90deg, {COLORS['accent']}60, transparent);
}}

.corner-deco {{
    position: absolute;
    bottom: 100px;
    right: 60px;
    width: 80px;
    height: 80px;
    border-right: 2px solid {COLORS['accent']}40;
    border-bottom: 2px solid {COLORS['accent']}40;
}}

.data-dot {{
    position: absolute;
    width: 8px;
    height: 8px;
    background: {COLORS['accent']}50;
    border-radius: 50%;
}}

.dot-1 {{ top: 200px; right: 200px; }}
.dot-2 {{ top: 250px; right: 250px; width: 6px; height: 6px; opacity: 0.6; }}
.dot-3 {{ top: 300px; right: 180px; width: 4px; height: 4px; opacity: 0.4; }}
</style>
</head>
<body>
    <div class="top-bar"></div>
    <div class="left-line"></div>
    <div class="geo-1"></div>
    <div class="geo-2"></div>
    <div class="bottom-deco"></div>
    <div class="bottom-line"></div>
    <div class="corner-deco"></div>
    <div class="data-dot dot-1"></div>
    <div class="data-dot dot-2"></div>
    <div class="data-dot dot-3"></div>
</body>
</html>
'''

BODY_BG_HTML = f'''
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    width: {PAGE_W}px;
    height: {PAGE_H}px;
    background: linear-gradient(180deg, #fafbfc 0%, #f5f7fa 100%);
    position: relative;
    overflow: hidden;
}}

.top-line {{
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 3px;
    background: linear-gradient(90deg, {COLORS['primary']} 0%, {COLORS['accent']} 50%, transparent 100%);
}}

.left-accent {{
    position: absolute;
    top: 100px;
    left: 0;
    width: 3px;
    height: 150px;
    background: linear-gradient(180deg, {COLORS['accent']}30 0%, transparent 100%);
}}

.corner-block {{
    position: absolute;
    bottom: 0;
    right: 0;
    width: 200px;
    height: 200px;
    background: radial-gradient(ellipse at bottom right,
        {COLORS['primary']}05 0%,
        transparent 70%
    );
}}
</style>
</head>
<body>
    <div class="top-line"></div>
    <div class="left-accent"></div>
    <div class="corner-block"></div>
</body>
</html>
'''

BACKCOVER_BG_HTML = f'''
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    width: {PAGE_W}px;
    height: {PAGE_H}px;
    background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
    position: relative;
    overflow: hidden;
}}

.bottom-bar {{
    position: absolute;
    bottom: 0;
    left: 0;
    width: 100%;
    height: 12px;
    background: linear-gradient(90deg, {COLORS['accent']} 0%, {COLORS['primary']} 100%);
}}

.top-area {{
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 200px;
    background: linear-gradient(180deg, {COLORS['primary']}05 0%, transparent 100%);
}}

.center-circle {{
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 300px;
    height: 300px;
    border: 2px solid {COLORS['accent']}15;
    border-radius: 50%;
}}

.center-circle-inner {{
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 200px;
    height: 200px;
    border: 1px solid {COLORS['accent']}10;
    border-radius: 50%;
}}

.corner {{
    position: absolute;
    width: 40px;
    height: 40px;
    border: 2px solid {COLORS['accent']}20;
}}

.corner-tl {{ top: 60px; left: 60px; border-right: none; border-bottom: none; }}
.corner-tr {{ top: 60px; right: 60px; border-left: none; border-bottom: none; }}
.corner-bl {{ bottom: 60px; left: 60px; border-right: none; border-top: none; }}
.corner-br {{ bottom: 60px; right: 60px; border-left: none; border-top: none; }}
</style>
</head>
<body>
    <div class="bottom-bar"></div>
    <div class="top-area"></div>
    <div class="center-circle"></div>
    <div class="center-circle-inner"></div>
    <div class="corner corner-tl"></div>
    <div class="corner corner-tr"></div>
    <div class="corner corner-bl"></div>
    <div class="corner corner-br"></div>
</body>
</html>
'''

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': PAGE_W, 'height': PAGE_H}, device_scale_factor=2)
    
    page.set_content(COVER_BG_HTML)
    page.screenshot(path=os.path.join(OUTPUT_DIR, "cover_bg.png"))
    
    page.set_content(BODY_BG_HTML)
    page.screenshot(path=os.path.join(OUTPUT_DIR, "body_bg.png"))
    
    page.set_content(BACKCOVER_BG_HTML)
    page.screenshot(path=os.path.join(OUTPUT_DIR, "backcover_bg.png"))
    
    browser.close()

print("背景图生成完成！")
