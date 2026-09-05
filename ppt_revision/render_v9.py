# -*- coding: utf-8 -*-
import win32com.client, os
pptx_path = r"D:\AI\14 - 数据治理\ppt_revision\AI_主数据治理_v9.pptx"
out_dir = r"D:\AI\14 - 数据治理\ppt_revision\render_v9"
os.makedirs(out_dir, exist_ok=True)
ppt = win32com.client.Dispatch("PowerPoint.Application")
try: ppt.Visible = False
except: pass
pres = ppt.Presentations.Open(pptx_path, WithWindow=False)
pres.SaveAs(out_dir, 17)
pres.Close()
ppt.Quit()
print("rendered")
