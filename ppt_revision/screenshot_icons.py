# -*- coding: utf-8 -*-
"""用 Playwright 截取每个图标元素"""
from playwright.sync_api import sync_playwright
import os

BASE = r"D:\AI\14 - 数据治理\ppt_revision\ui_mockups"
OUT = r"D:\AI\14 - 数据治理\ppt_revision\new_images\icons"
os.makedirs(OUT, exist_ok=True)

icons = [
    ("i1", "icon_multimodal.png"),
    ("i2", "icon_dedup.png"),
    ("i3", "icon_formassist.png"),
    ("i4", "icon_llm.png"),
    ("i5", "icon_domain.png"),
    ("i6", "icon_datamodel.png"),
    ("i7", "icon_ontology.png"),
    ("i8", "icon_knowledge.png"),
    ("i9", "icon_whitebox.png"),
    ("i10", "icon_humanloop.png"),
    ("i11", "icon_shield.png"),
]

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 120, "height": 120}, device_scale_factor=3)
    page.goto("file:///" + os.path.join(BASE, "icons.html").replace("\\", "/"))
    page.wait_for_timeout(300)
    for el_id, fname in icons:
        el = page.query_selector(f"#{el_id}")
        out_path = os.path.join(OUT, fname)
        el.screenshot(path=out_path)
        print(f"saved {fname} ({os.path.getsize(out_path)} bytes)")
    browser.close()
print("done")
