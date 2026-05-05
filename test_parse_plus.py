from parser import parse_questions_from_text
import json

# Sample inputs to test different plus variants
samples = {
    "three_plus": """+++
Savol
====
# to'g'ri javob
====
javob
====
javob
====
javob
""",
    "four_plus": """++++
Savol
====
# to'g'ri javob
====
javob
====
javob
====
javob
""",
}

for name, text in samples.items():
    qs = parse_questions_from_text(text)
    print(f"=== {name} ===")
    print(json.dumps(qs, ensure_ascii=False, indent=2))
    print()
