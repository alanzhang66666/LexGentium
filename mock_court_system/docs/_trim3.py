# -*- coding: utf-8 -*-
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt

doc = Document(Path(__file__).with_name("申请书正文.docx"))
for p in doc.paragraphs:
    if p.text and "确立扩展式博弈建模主线" in p.text:
        p.text = p.text.replace("确立扩展式博弈建模主线。", "确立扩展式博弈主线。", 1)
        for r in p.runs:
            r.font.name = "Times New Roman"
            r._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
            r.font.size = Pt(10.5)
        break
doc.save(Path(__file__).with_name("申请书正文.docx"))
