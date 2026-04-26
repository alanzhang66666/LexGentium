import re
with open("docs/申请书正文.md", "r", encoding="utf-8") as f:
    text = f.read()
cn = len(re.findall(r'[\u4e00-\u9fff]', text))
imgs = text.count("![")
tables = len(re.findall(r'^\|', text, re.MULTILINE))
formulas = text.count("$$")
lines = len(text.split("\n"))
secs = {}; cur = ""
for line in text.split("\n"):
    if line.startswith("## "):
        cur = line[3:].strip()[:20]
        secs[cur] = 0
    elif cur:
        secs[cur] += len(re.findall(r'[\u4e00-\u9fff]', line))
print(f"CN chars: {cn} | Images: {imgs} | Table rows: {tables} | Formula blocks: {formulas//2} | Lines: {lines}")
est = cn + tables*25 + imgs*40 + (formulas//2)*60
print(f"Est total: ~{est} equiv chars")
for s, c in secs.items():
    print(f"  {s}: {c}")
