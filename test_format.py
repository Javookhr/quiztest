from parser import parse_questions_from_text

# Foydalanuvchi yuborgan HAQIQIY format (++++dan oldin ====li blok bor, savol yo'q)
test = """====
konvertizatsiya
====
integratsiya
====
#inflyatsiya
====
emissiya
++++
O'zbekiston Konstitutsiyasining kirish qismi qanday nomlanadi?
====
So'z boshi
====
# Muqaddima
====
Asosnoma
====
Referendum
++++
Inson xuquqlari va erkinligini kim ta'minlashi lozim:
====
#Davlat
====
Prezident
====
Bosh prokuror
====
Oliy sud
++++
Senat a'zolaridan nechchi nafardan senaator saylanadi?
====
16nafar
====
6 nafar
====
7 nafar
====
# 4 nafar
"""

qs = parse_questions_from_text(test)
print(f"JAMI: {len(qs)} savol")
print("=" * 40)
for i, q in enumerate(qs, 1):
    cid = q['correct_option_id']
    correct = q['options'][cid]
    print(f"\n{i}. {q['question']}")
    print(f"   Togri javob: {correct}")
    print(f"   Barcha variantlar: {q['options']}")
