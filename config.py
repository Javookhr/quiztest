# ============================================================
#  config.py — Bot sozlamalari
# ============================================================

BOT_TOKEN = "8555296457:AAGmg_p-JrgmVYhgA4Zw3paTrSgDdWln4aM"          # @BotFather dan olingan token

ADMIN_IDS = [8534111622]                     # Admin Telegram ID lari (list)

# To'lov ma'lumotlari
# Uzcard kartalar
UZCARD_NUMBER_1  = "5614681873454684"       # Uzcard
UZCARD_HOLDER_1  = "Jamoliddinov Saydullo" # Uzcard egasi

# Humo kartalar
HUMO_NUMBER_1    = "9860160624032688"       # Humo
HUMO_HOLDER_1    = "Islomjon karimov"       # Humo egasi

# Narxlar (UZS)
WEEKLY_PRICE     = 13_990    # Haftalik obuna
MONTHLY_PRICE    = 20_990    # Oylik obuna
PREMIUM_PRICE    = 23_990    # Cheksiz premium (1 martalik to'lov)

# Bepul urinishlar soni
FREE_USES = 1    # Bir marta bepul quiz o'ynash

# To'lov kutish vaqti (soniyalarda) — 5 daqiqa
PAYMENT_TIMEOUT = 300

# Ma'lumotlar bazasi fayli
DB_PATH = "quiz_bot.db"

# ──────────────────────────────────────────────────────────
# OCR — Rasm o'qish uchun Tesseract path (faqat Windows da kerak)
# O'rnating: https://github.com/UB-Mannheim/tesseract/wiki
# ──────────────────────────────────────────────────────────
import pytesseract, os
if os.name == "nt":   # Windows
    pytesseract.pytesseract.tesseract_cmd = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )
