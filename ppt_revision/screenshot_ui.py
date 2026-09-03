# -*- coding: utf-8 -*-
"""用 Playwright 把 HTML UI 稿截成高分辨率 PNG"""
from playwright.sync_api import sync_playwright
import os

BASE = r"D:\AI\14 - 数据治理\ppt_revision\ui_mockups"
OUT = r"D:\AI\14 - 数据治理\ppt_revision\new_images"
os.makedirs(OUT, exist_ok=True)

pages = [
    ("chat.html",   "p15_chat.png",   640, 520),
    ("form.html",   "p15_form.png",   520, 520),
    ("alerts.html", "p16_alerts.png", 760, 500),
]

with sync_playwright() as p:
    browser = p.chromium.launch()
    for html, png, w, h in pages:
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
        page.goto("file:///" + os.path.join(BASE, html).replace("\\", "/"))
        page.wait_for_timeout(300)
        out_path = os.path.join(OUT, png)
        page.screenshot(path=out_path)
        print(f"saved {out_path} ({os.path.getsize(out_path)} bytes)")
        page.close()
    browser.close()
print("done")
