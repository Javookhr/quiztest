# 🔧 Bot Fixes Summary

## ✅ Payment Flow - Fixed

### 1️⃣ **User clicks "Sotib olish" (Buy)**
   - Shows inline keyboard with **Humo** and **Uzcard** buttons
   - User selects payment method

### 2️⃣ **User clicks Humo or Uzcard**
   - Shows **Humo card details** OR **Uzcard card details**
   - Shows message: "⏱️ To'lovni *5 daqiqa* ichida amalga oshirib, chek (screenshot) yuboring!"
   - Shows inline keyboard with plan options (Weekly/Monthly)

### 3️⃣ **User selects plan (Weekly or Monthly)**
   - Payment record created in database
   - Single message shows:
     - 📅 Tarif (Plan name)
     - 💰 Summa (Amount)
     - 🏦 Selected card details (only Humo OR Uzcard, not both)
     - 🔎 To'lov ID (Payment ID)
     - 3 action buttons:
       - ✅ Chek yuborish (Upload screenshot)
       - ❌ Bekor qilish (Cancel payment)
       - 🔁 Boshqa karta (Change card)

### 4️⃣ **User uploads screenshot (photo/document)**
   - Database updated with screenshot
   - User sees: "✅ Chek adminga yuborildi.\n⏳ To'lov 5 daqiqa ichida tekshiriladi.\n\nIltimos kuting — sizga xabar beriladi."
   - Admin receives screenshot with payment details and approve/reject buttons

### 5️⃣ **Timeout (5 minutes)**
   - If no screenshot uploaded in 5 minutes:
     - Payment automatically cancelled
     - User notified: "❌ To'lov bekor qilindi — iltimos yana urinib ko'ring."
     - User can click "🔁 Sotib olish" to restart

## 📝 Code Changes

### `main.py`
1. **`on_uzcard_payment` handler** - Rewritten to show Uzcard card details with 5-minute message
2. **`on_humo_payment` handler** - Rewritten to show Humo card details with 5-minute message
3. **`on_buy` handler** - Rewritten to:
   - Create payment record
   - Show only selected card (Humo or Uzcard)
   - Include Payment ID in message
   - Start 5-minute timeout watcher
   - Add action buttons (Upload/Cancel/Change card)

4. **`handle_screenshot` handler** - Updated to:
   - Show concise user confirmation
   - Notify admin with screenshot and controls

5. **New `paid_hint` handler** - User clicked upload button (info only)
6. **New `cancel_payment_user` handler** - User clicked cancel → removes payment & goes to menu

### `database.py`
- `cancel_payment(payment_id)` - Already implemented to set status to 'cancelled'

### `buttons.py`
- `payment_method_kb()` - Already uses inline keyboard with Humo/Uzcard/Back buttons

## 🚀 Flow Summary

```
User clicks "Sotib olish"
    ↓
Shows inline: [Humo] [Uzcard] [Orqaga]
    ↓ (User clicks Humo or Uzcard)
Shows card details + "5 daqiqada to'lov qil"
Shows inline: [1 Haftalik] [1 Oylik] [Orqaga]
    ↓ (User selects plan)
Shows payment details with:
  - Only selected card
  - Payment ID
  - [✅ Chek yuborish] [❌ Bekor qilish] [🔁 Boshqa karta]
    ↓ (User uploads screenshot)
User: "✅ Chek adminga yuborildi. 5 daqiqa ichida tekshiriladi."
Admin: Gets screenshot with approve/reject buttons
    ↓ (5 minutes timeout OR admin approves/rejects)
✅ Success OR ❌ Try again
```

## ✨ Key Features

✅ No duplicate messages  
✅ Only selected card shown (not both)  
✅ Payment ID included  
✅ 5-minute timeout with automatic cancellation  
✅ Admin notifications  
✅ User confirmations clear and concise  
✅ Option to change card or cancel anytime  

---

**Testing:** Run `python main.py` to start the bot.
