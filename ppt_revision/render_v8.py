# -*- coding: utf-8 -*-
"""渲染 v8 为 PNG"""
import win32com.client
import os

pptx_path = r"D:\AI\14 - 数据治理\ppt_revision\AI_主数据治理_v8.pptx"
out_dir = r"D:\AI\14 - 数据治理\ppt_revision\render_v8"
os.makedirs(out_dir, exist_ok=True)

ppt = win32com.client.Dispatch("PowerPoint.Application")
try:
    ppt.Visible = False
except Exception:
    pass
pres = ppt.Presentations.Open(pptx_path, WithWindow=False)
pres.SaveAs(out_dir, 17)
pres.Close()
ppt.Quit()
print("rendered to", out_dir)
