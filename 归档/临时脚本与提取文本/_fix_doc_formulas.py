# -*- coding: utf-8 -*-
"""
将 .doc 用 Microsoft Word 打开并另存为 .docx，同时更新域、嵌入 TrueType 字体，
以修复多数公式/符号在旧版二进制 .doc 中的显示异常。
"""
import os
import sys
import time

try:
    import win32com.client as win32
except ImportError:
    print("需要安装 pywin32: pip install pywin32", file=sys.stderr)
    sys.exit(1)

# 路径
SRC = r"E:\25-26-1\模拟法庭世纪杯\启研计划申请书（申请人信息）.doc"
DST = r"E:\25-26-1\模拟法庭世纪杯\启研计划申请书（申请人信息）_公式修复.docx"

# wdFormatXMLDocument: Word 2007+ 标准 .docx（无宏）
WD_FORMAT_XML_DOCUMENT = 12


def main():
    if not os.path.isfile(SRC):
        print("找不到源文件:", SRC, file=sys.stderr)
        sys.exit(2)

    word = win32.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = None
    try:
        doc = word.Documents.Open(
            os.path.abspath(SRC),
            ReadOnly=False,
            AddToRecentFiles=False,
        )
        # 嵌入字体，避免公式符号在其他机器上变方框
        try:
            doc.EmbedTrueTypeFonts = True
        except Exception:
            pass
        try:
            doc.SaveSubsetFonts = True
        except Exception:
            pass
        # 更新域（部分公式以域代码形式存在）
        try:
            doc.Fields.Update()
        except Exception:
            pass
        try:
            doc.Content.Fields.Update()
        except Exception:
            pass
        # 另存为 .docx（Office Math 以 oMath 存储，显示更稳定）
        out = os.path.abspath(DST)
        if os.path.isfile(out):
            os.remove(out)
        doc.SaveAs2(out, FileFormat=WD_FORMAT_XML_DOCUMENT)
        doc.Close(SaveChanges=False)
        doc = None
        print("已生成:", out)
    finally:
        try:
            if doc is not None:
                doc.Close(SaveChanges=False)
        except Exception:
            pass
        word.Quit()
        time.sleep(0.5)


if __name__ == "__main__":
    main()
