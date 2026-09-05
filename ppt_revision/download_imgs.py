# -*- coding: utf-8 -*-
"""下载生成的三张 UI 效果图"""
import urllib.request, os

out_dir = r"D:\AI\14 - 数据治理\ppt_revision\new_images"
os.makedirs(out_dir, exist_ok=True)

urls = {
    "p15_chat.png": "https://aka.doubaocdn.com/s/uBfFI42it9",
    "p15_form.png": "https://aka.doubaocdn.com/s/ECM7uNPAUh",
    "p16_alerts.png": "https://aka.doubaocdn.com/s/gtMOUKsH1c",
}
for name, url in urls.items():
    path = os.path.join(out_dir, name)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
        f.write(r.read())
    print(name, os.path.getsize(path))
