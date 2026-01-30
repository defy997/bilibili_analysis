# 调试 emoji_pattern
import re

# 创建 emoji_pattern
emoji_pattern = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # 表情符号
    "\U0001F300-\U0001F5FF"  # 符号和图标
    "\U0001F680-\U0001F6FF"  # 交通和地图符号
    "\U0001F1E0-\U0001F1FF"  # 旗帜
    "\U00002702-\U000027B0"  # 装饰符号
    "\U000024C2-\U0001F251"  # 其他符号
    "\U0001F900-\U0001F9FF"  # 补充符号和图标
    "\U0001FA70-\U0001FAFF"  # 扩展符号
    "]+",
    flags=re.UNICODE
)

# 检查正则的字符范围
print("=== 检查 emoji_pattern 的范围 ===")
test_chars = ['我', '了', '笑', '哈', 'a', '1', '😋', '[']
for char in test_chars:
    match = emoji_pattern.search(char)
    print(f"'{char}' (U+{ord(char):04X}): 匹配={bool(match)}")

# 检查具体是哪个范围匹配了中文
print("\n=== 逐个范围测试 ===")
text = "我不行了"
for name, pattern in [
    ("F600-64F", "\U0001F600-\U0001F64F"),
    ("F300-5FF", "\U0001F300-\U0001F5FF"),
    ("F680-6FF", "\U0001F680-\U0001F6FF"),
    ("F1E0-1FF", "\U0001F1E0-\U0001F1FF"),
    ("2702-27B0", "\U00002702-\U000027B0"),
    ("24C2-F251", "\U000024C2-\U0001F251"),
    ("F900-9FF", "\U0001F900-\U0001F9FF"),
    ("FA70-FAFF", "\U0001FA70-\U0001FAFF"),
]:
    p = re.compile("[" + pattern + "]+", flags=re.UNICODE)
    match = p.search(text)
    print(f"{name}: {text!r} -> 匹配={bool(match)}")

# 直接检查原始字符串
print("\n=== 检查 services.py 中的实际内容 ===")
with open('analysis/services.py', 'r', encoding='utf-8') as f:
    content = f.read()
# 找到 remove_emoji 函数
start = content.find('def remove_emoji')
end = content.find('def compress_repeated_chars')
emoji_func = content[start:end]
# 打印 emoji_pattern 那几行
for i, line in enumerate(emoji_func.split('\n')[6:12], start=7):
    print(f"Line {start//100 + i}: {line!r}")
