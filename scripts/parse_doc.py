# -*- coding: utf-8 -*-
"""深度解析 .doc 答题纸结构 - 提取文本"""
import olefile
import sys

path = sys.argv[1]

ole = olefile.OleFileIO(path)
wd = ole.openstream('WordDocument').read()

def extract_all_strings(data, min_len=2):
    """提取 UTF-16LE 字符串"""
    strings = []
    current = []
    i = 0
    while i < len(data) - 1:
        high = data[i+1]
        low = data[i]
        if high == 0 and 32 <= low <= 126:
            current.append(chr(low))
            i += 2
        elif high > 0:
            if current and len(''.join(current)) >= min_len:
                strings.append(''.join(current))
            current = []
            try:
                char = data[i:i+2].decode('utf-16-le')
                if char.isprintable() or char in '\n\r\t':
                    current.append(char)
                else:
                    if current and len(''.join(current)) >= min_len:
                        strings.append(''.join(current))
                    current = []
            except:
                if current and len(''.join(current)) >= min_len:
                    strings.append(''.join(current))
                current = []
            i += 2
        else:
            if current and len(''.join(current)) >= min_len:
                strings.append(''.join(current))
            current = []
            i += 2
    if current and len(''.join(current)) >= min_len:
        strings.append(''.join(current))
    return strings

strings = extract_all_strings(wd, min_len=2)

print("=== 提取的有意义文本 ===")
seen = set()
for s in strings:
    s = s.strip()
    if not s:
        continue
    has_content = any(ord(c) > 0x4e00 for c in s) or any(c.isalpha() for c in s)
    if has_content and len(s) > 1 and s not in seen:
        seen.add(s)
        print(repr(s))

ole.close()
