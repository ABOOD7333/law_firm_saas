"""
Smart mojibake fix for base.html:
- The file has BOTH correct Arabic (U+0600-U+06FF) and mojibake (U+00C0-U+00FF)
- Mojibake sequences: runs of chars in U+00C0-U+00FF that, when encoded as latin-1
  and decoded as UTF-8, produce valid Arabic text
- We ONLY fix the mojibake sequences, leaving real Arabic chars untouched
"""
import shutil

def fix_smart_mojibake(text):
    result = []
    i = 0
    chars = list(text)
    n = len(chars)
    
    while i < n:
        c = chars[i]
        code = ord(c)
        
        # Mojibake Arabic pattern: chars in U+00C0-U+00FF range
        # (These are latin-1 byte values 0xC0-0xFF misread as unicode codepoints)
        if 0x00C0 <= code <= 0x00FF:
            # Collect a run of these chars
            run = []
            while i < n and 0x0080 <= ord(chars[i]) <= 0x00FF:
                run.append(chars[i])
                i += 1
            # Try to fix: encode as latin-1, decode as UTF-8
            try:
                raw_bytes = "".join(run).encode("latin-1")
                fixed = raw_bytes.decode("utf-8")
                result.append(fixed)
            except Exception:
                # Can't fix - keep original
                result.extend(run)
        else:
            result.append(c)
            i += 1
    
    return "".join(result)

# Work from the restored backup
with open("templates/base.html", "r", encoding="utf-8") as f:
    content = f.read()

fixed = fix_smart_mojibake(content)

# Verification
print("=== Verification of key lines ===")
lines = fixed.split("\n")
for i, line in enumerate(lines):
    stripped = line.strip()
    if "knowledge-admin" in stripped or "ai-assistant" in stripped or "dashboard" in stripped[:50]:
        if i > 170 and i < 200:
            print(f"Line {i}: {stripped[:100]}")
    if "calendar" in stripped and "href" in stripped:
        if i > 180 and i < 200:
            print(f"Line {i}: {stripped[:100]}")
    if "search" in stripped and "href" in stripped:
        if i > 185 and i < 200:
            print(f"Line {i}: {stripped[:100]}")

# Save
with open("templates/base.html", "w", encoding="utf-8") as f:
    f.write(fixed)

print("\n✅ base.html has been fixed successfully!")

# Count remaining issues
remaining_mojibake = sum(1 for c in fixed if 0x00C0 <= ord(c) <= 0x00FF)
real_arabic = sum(1 for c in fixed if 0x0600 <= ord(c) <= 0x06FF)
print(f"Remaining mojibake chars: {remaining_mojibake}")
print(f"Real Arabic chars: {real_arabic}")
