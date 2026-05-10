import re

with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

scripts = re.findall(r'<script>(.*?)</script>', content, re.DOTALL)
for i, s in enumerate(scripts):
    print(f"--- Script {i} ---")
    try:
        # Check for basic brace balancing
        open_braces = s.count('{')
        close_braces = s.count('}')
        print(f"Open: {open_braces}, Close: {close_braces}")
        if open_braces != close_braces:
            print("ERROR: Unbalanced braces!")
    except Exception as e:
        print(f"Error analyzing script: {e}")
