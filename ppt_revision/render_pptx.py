# -*- coding: utf-8 -*-
"""用 PowerPoint COM 导出 v7 全部幻灯片为 PNG"""
import win32com.client
import os, time

pptx_path = r"D:\AI\14 - 数据治理\ppt_revision\AI_主数据治理_v7.pptx"
out_dir = r"D:\AI\14 - 数据治理\ppt_revision\render_v7"
os.makedirs(out_dir, exist_ok=True)

ppt = win32com.client.Dispatch("PowerPoint.Application")
# 不显示窗口
try:
    ppt.Visible = False
except Exception:
    pass

pres = ppt.Presentations.Open(pptx_path, WithWindow=False)
# 17 = ppSaveAsPNG
pres.SaveAs(out_dir, 17)
pres.Close()
ppt.Quit()

# 列出导出的图片
pngs = sorted([f for f in os.listdir(out_dir) if f.lower().endswith('.png')],
              key=lambda x: int(''.join(filter(str.isdigit, x)) or 0))
print(f"exported {len(pngs)} slides")
for f in pngs:
    print(f, os.path.getsize(os.path.join(out_dir, f)))
