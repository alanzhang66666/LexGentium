"""
将申请书正文.md导出为Word文档(.docx)
格式：标题黑体四号、正文宋体五号、图片嵌入
"""
import re
import os
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

PROJECT = Path(__file__).parent.parent
MD_PATH = PROJECT / "docs" / "申请书正文.md"
FIG_DIR = PROJECT / "docs" / "figures"
OUT_PATH = Path(r"E:\25-26-1\模拟法庭世纪杯\申请书正文.docx")


def set_font(run, name_cn="宋体", name_en="Times New Roman", size=10.5, bold=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = name_en
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name_cn)


def add_heading_text(doc, text, level=1):
    """添加标题（黑体四号=14pt）"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    set_font(run, "黑体", "Arial", size=14, bold=True)
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    return p


def add_subheading(doc, text):
    """添加子标题（黑体小四=12pt）"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_font(run, "黑体", "Arial", size=12, bold=True)
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    return p


def add_body_text(doc, text):
    """添加正文段落（宋体五号=10.5pt）"""
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0.74)
    p.paragraph_format.line_spacing = Pt(18)

    # Handle bold markers
    parts = re.split(r'(\*\*[^*]+\*\*)', text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = p.add_run(part[2:-2])
            set_font(run, bold=True)
        else:
            run = p.add_run(part)
            set_font(run)
    return p


def add_image(doc, img_path, caption=""):
    """添加图片和图注"""
    if not os.path.exists(img_path):
        p = doc.add_paragraph()
        run = p.add_run(f"[图片缺失: {img_path}]")
        set_font(run, size=9)
        return

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(str(img_path), width=Cm(14))

    if caption:
        cap_p = doc.add_paragraph()
        cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = cap_p.add_run(caption)
        set_font(run, size=9, bold=True)
        cap_p.paragraph_format.space_after = Pt(8)


def add_table_from_lines(doc, header_line, data_lines):
    """从markdown表格行创建Word表格"""
    def parse_row(line):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        return cells

    headers = parse_row(header_line)
    rows = [parse_row(l) for l in data_lines]

    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"

    for j, h in enumerate(headers):
        cell = table.rows[0].cells[j]
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        set_font(run, "黑体", "Arial", size=9, bold=True)

    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            if j < len(headers):
                cell = table.rows[i + 1].cells[j]
                cell.text = ""
                clean = val.replace("**", "")
                run = cell.paragraphs[0].add_run(clean)
                set_font(run, size=9)

    doc.add_paragraph()


def add_formula(doc, formula_text):
    """添加公式（居中，宋体五号）"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    clean = formula_text.strip().strip("$")
    run = p.add_run(clean)
    set_font(run, "Times New Roman", "Times New Roman", size=10.5)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)


def add_algorithm(doc, lines):
    """添加伪代码块"""
    for line in lines:
        text = line.lstrip("> ").rstrip()
        if not text:
            continue
        p = doc.add_paragraph()
        run = p.add_run(text)
        set_font(run, "Consolas", "Consolas", size=9)
        p.paragraph_format.left_indent = Cm(1)
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)


def main():
    with open(MD_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    doc = Document()

    # Set default font
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    style.font.size = Pt(10.5)
    style.paragraph_format.line_spacing = Pt(18)

    i = 0
    in_table = False
    table_header = ""
    table_rows = []
    in_algorithm = False
    algo_lines = []

    while i < len(lines):
        line = lines[i].rstrip("\n")

        # Skip empty lines
        if not line.strip():
            if in_table and table_rows:
                add_table_from_lines(doc, table_header, table_rows)
                in_table = False
                table_header = ""
                table_rows = []
            if in_algorithm and algo_lines:
                add_algorithm(doc, algo_lines)
                in_algorithm = False
                algo_lines = []
            i += 1
            continue

        # Title (# level 1)
        if line.startswith("# ") and not line.startswith("##"):
            text = line[2:].strip()
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(text)
            set_font(run, "黑体", "Arial", size=16, bold=True)
            p.paragraph_format.space_after = Pt(12)
            i += 1
            continue

        # Section heading (## level 2)
        if line.startswith("## ") and not line.startswith("###"):
            if in_table and table_rows:
                add_table_from_lines(doc, table_header, table_rows)
                in_table = False; table_header = ""; table_rows = []
            text = line[3:].strip()
            add_heading_text(doc, text)
            i += 1
            continue

        # Subsection (### level 3, #### level 4)
        if line.startswith("###"):
            if in_table and table_rows:
                add_table_from_lines(doc, table_header, table_rows)
                in_table = False; table_header = ""; table_rows = []
            hashes = len(line) - len(line.lstrip("#"))
            text = line[hashes:].strip()
            add_subheading(doc, text)
            i += 1
            continue

        # Horizontal rule
        if line.strip() == "---":
            i += 1
            continue

        # Image
        if line.strip().startswith("!["):
            m = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line.strip())
            if m:
                alt = m.group(1)
                path = m.group(2)
                full_path = FIG_DIR.parent / path
                if not full_path.exists():
                    full_path = FIG_DIR / os.path.basename(path)
                add_image(doc, full_path, "")
            i += 1
            continue

        # Block formula ($$...$$)
        if line.strip().startswith("$$"):
            formula = line.strip()
            if not formula.endswith("$$") or formula == "$$":
                i += 1
                while i < len(lines) and not lines[i].strip().endswith("$$"):
                    formula += " " + lines[i].strip()
                    i += 1
                if i < len(lines):
                    formula += " " + lines[i].strip()
            add_formula(doc, formula)
            i += 1
            continue

        # Table
        if line.strip().startswith("|"):
            if not in_table:
                in_table = True
                table_header = line
                i += 1
                if i < len(lines) and re.match(r'\|[\s\-:|]+\|', lines[i]):
                    i += 1
                continue
            else:
                table_rows.append(line)
                i += 1
                continue

        # Algorithm block (> lines)
        if line.startswith("> "):
            if not in_algorithm:
                in_algorithm = True
                algo_lines = []
            algo_lines.append(line)
            i += 1
            continue
        elif in_algorithm:
            add_algorithm(doc, algo_lines)
            in_algorithm = False
            algo_lines = []

        # Keywords line
        if line.startswith("**关键词"):
            p = doc.add_paragraph()
            clean = line.replace("**", "")
            run = p.add_run(clean)
            set_font(run, bold=True)
            i += 1
            continue

        # Figure caption (bold line starting with **)
        if line.startswith("**图") or line.startswith("**表"):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            clean = line.replace("**", "").replace("\\*", "*")
            run = p.add_run(clean)
            set_font(run, size=9, bold=True)
            p.paragraph_format.space_after = Pt(8)
            i += 1
            continue

        # Annotation line (starting with *)
        if line.startswith("*注：") or line.startswith("*注:"):
            p = doc.add_paragraph()
            clean = line.strip("*").strip()
            run = p.add_run(clean)
            set_font(run, size=9)
            i += 1
            continue

        # Reference lines
        if re.match(r'^\[\d+\]', line.strip()):
            p = doc.add_paragraph()
            run = p.add_run(line.strip())
            set_font(run, size=9)
            p.paragraph_format.first_line_indent = Cm(0)
            i += 1
            continue

        # Regular paragraph
        if in_table and table_rows:
            add_table_from_lines(doc, table_header, table_rows)
            in_table = False; table_header = ""; table_rows = []

        add_body_text(doc, line.strip())
        i += 1

    # Flush remaining
    if in_table and table_rows:
        add_table_from_lines(doc, table_header, table_rows)
    if in_algorithm and algo_lines:
        add_algorithm(doc, algo_lines)

    doc.save(str(OUT_PATH))
    print(f"Saved to {OUT_PATH}")
    print(f"File size: {OUT_PATH.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
