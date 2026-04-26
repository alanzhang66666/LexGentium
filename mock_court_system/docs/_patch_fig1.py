# -*- coding: utf-8 -*-
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt

doc = Document(Path(__file__).with_name("申请书正文.docx"))
exact = (
    "[图1 LegalFlow系统架构：数据输入→扩展式博弈驱动的多智能体协同管道（CD→DD→CI）→评测输出。"
    "核心引擎基于SPNE建模序贯策略决策，辅以演化动力学模拟群体策略稳定性验证，底层由P-RAG渐进式法条检索增强判决质量]"
)
for p in doc.paragraphs:
    if p.text and "[图1" in p.text:
        p.text = exact
        for r in p.runs:
            r.font.name = "Times New Roman"
            r._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
            r.font.size = Pt(10.5)
        break
else:
    raise SystemExit("fig1 para not found")
doc.save(Path(__file__).with_name("申请书正文.docx"))
print("ok")
