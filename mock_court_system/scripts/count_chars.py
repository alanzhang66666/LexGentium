import re

with open(r'e:\25-26-1\模拟法庭世纪杯\mock_court_system\docs\申请书正文.md', 'r', encoding='utf-8') as f:
    text = f.read()

clean = text
clean = re.sub(r'!\[.*?\]\(.*?\)', '', clean)
clean = re.sub(r'\$\$.*?\$\$', '', clean, flags=re.DOTALL)
clean = re.sub(r'\$[^$]+\$', '', clean)
clean = re.sub(r'^#+ .*$', '', clean, flags=re.MULTILINE)
clean = re.sub(r'^\|.*\|$', '', clean, flags=re.MULTILINE)
clean = re.sub(r'^---+$', '', clean, flags=re.MULTILINE)
clean = re.sub(r'^>.*$', '', clean, flags=re.MULTILINE)
clean = re.sub(r'^\*\*图\d.*$', '', clean, flags=re.MULTILINE)
clean = re.sub(r'\[\d+\]', '', clean)
clean = re.sub(r'^\[\d+\].*$', '', clean, flags=re.MULTILINE)
clean = re.sub(r'\*\*', '', clean)
clean = re.sub(r'`[^`]+`', '', clean)

chinese = len(re.findall(r'[\u4e00-\u9fff]', clean))
english = len(re.findall(r'[a-zA-Z]+', clean))
digits = len(re.findall(r'\d+', clean))
total = chinese + english // 2 + digits // 2
all_chars = len(re.sub(r'\s+', '', clean))

print(f"Chinese chars: {chinese}")
print(f"English words: {english}")
print(f"Digit groups: {digits}")
print(f"Equivalent word count: {total}")
print(f"All non-space chars: {all_chars}")
