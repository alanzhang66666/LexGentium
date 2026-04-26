# -*- coding: utf-8 -*-
import re
from pathlib import Path
from docx import Document

doc = Document(Path(__file__).with_name("申请书正文.docx"))
buf = []
rec = False
for p in doc.paragraphs:
    t = p.text or ""
    if "（二）前期工作" in t:
        rec = True
    if rec:
        buf.append(t)
    if "（三）研究内容" in t:
        buf.pop()
        break
s = "".join(buf)
print(len(re.sub(r"\s+", "", s)))
