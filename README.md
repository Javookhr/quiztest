# 🎓 Docuiz Quiz Bot

Telegram quiz bot — fayldan savollarni avtomatik quizga aylantiradi.

## 📁 Fayl tuzilmasi

```
quiz_bot/
├── config.py        ← Bot token, admin ID, narxlar
├── database.py      ← SQLite ma'lumotlar bazasi
├── buttons.py       ← Barcha tugmalar
├── parser.py        ← Fayl parsing (txt, docx, pptx, xlsx, pdf, rasm)
├── main.py          ← Asosiy bot logikasi
└── requirements.txt ← Kutubxonalar
```

## ⚙️ O'rnatish

### 1. Kutubxonalarni o'rnatish
```bash
pip install -r requirements.txt
```

### 2. Tesseract OCR o'rnatish (rasm uchun)
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-uzb tesseract-ocr-rus

# Windows
# https://github.com/UB-Mannheim/tesseract/wiki dan yuklab o'rnating
```

### 3. config.py ni sozlash
```python
BOT_TOKEN  = "1234567890:AAF..."   # @BotFather dan token
ADMIN_IDS  = [123456789]           # Sizning Telegram ID
CARD_NUMBER = "8600 xxxx xxxx xxxx"
CARD_HOLDER = "Ism Familiya"
```

### 4. Botni ishga tushirish
```bash
python main.py
```

---

## 🗂 Qo'llab-quvvatlanadigan fayl formatlari

| Format | Tavsif |
|--------|--------|
| `.txt` | Oddiy matn fayl |
| `.docx` | Microsoft Word |
| `.pptx` | PowerPoint slayd |
| `.xlsx` | Excel jadval |
| `.pdf` | PDF hujjat |
| 📷 Rasm | JPG, PNG, BMP — OCR orqali o'qiladi |

---

## 📝 Test fayl formati (.txt, .docx)

```
1. Qaysi dasturlash tili eng mashhur?
A) Java
B) Python
C) C++
D) JavaScript
Javob: B

2. HTML nima?
A) Dasturlash tili
B) Belgilash tili
C) Ma'lumotlar bazasi
D) Operatsion tizim
Javob: B
```

## 📊 Excel fayl formati (.xlsx)

| A (Savol) | B (Variant 1) | C (Variant 2) | D (Variant 3) | E (Variant 4) | F (To'g'ri) |
|-----------|---------------|---------------|---------------|---------------|-------------|
| Savol matni? | Variant A | Variant B | To'g'ri | Variant D | C |

---

## 💰 To'lov tizimi

- **1 haftalik** — 15 000 UZS
- **1 oylik** — 25 000 UZS
- Foydalanuvchi karta raqamiga pul o'tkazadi → chek yuboradi → admin tasdiqlaydi

## 👑 Admin imkoniyatlari

- 📊 **Statistika** — foydalanuvchilar va daromad (⟳ yangilanadi)
- ✅ **Chek tekshirish** — to'lovlarni tasdiqlash/rad etish
- 📢 **Reklama yuborish** — barcha foydalanuvchilarga xabar

## ✅ Bot imkoniyatlari

- Fayl yuklash → avtomatik quiz
- Variantlar har safar aralashtirilib chiqadi
- Quizda vaqt chegarasi yo'q
- Natija + 3 ta tugma: qayta ishlash / yangi test / asosiy menyu
- Bepul: **3 ta urinish**
- Obuna: **1 haftalik / 1 oylik**
