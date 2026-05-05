# ============================================================
#  main.py — Asosiy bot logikasi
#  aiogram 3.7.0 | Python 3.11
# ============================================================

import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, PollAnswer,
    ReplyKeyboardRemove, FSInputFile,
    InlineKeyboardButton,
)

import database as db
from buttons import (
    main_menu_kb, quiz_menu_kb, back_kb,
    buy_menu_kb, after_quiz_kb,
    admin_main_kb, admin_back_kb, admin_payment_kb,
    stats_refresh_kb, broadcast_confirm_kb,
    lang_kb, payment_method_kb,
    test_set_detail_kb, test_part_kb,
)
from locales import _
from parser import parse_file, shuffle_options, parse_questions_from_text
from config import (
    BOT_TOKEN, ADMIN_IDS,
    UZCARD_NUMBER_1, UZCARD_HOLDER_1,
    HUMO_NUMBER_1, HUMO_HOLDER_1,
    FREE_USES, WEEKLY_PRICE, MONTHLY_PRICE, PREMIUM_PRICE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s -- %(message)s",
)
log = logging.getLogger(__name__)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
)

router = Router()

# ── Tugma textlari (Filtrlar uchun) ──────────────────
def btns(key: str):
    return [_ (key, "uz"), _(key, "ru"), _(key, "en")]

# Reklama rasmi URL (botning start rasmi)
START_PHOTO_PATH = "start_photo.jpg"  # o'zingizning kanalingiz linkiga o'zgartiring


# ============================================================
#  FSM
# ============================================================
class UserState(StatesGroup):
    waiting_file          = State()
    waiting_screenshot    = State()
    waiting_quiz_name     = State()
    waiting_time_limit    = State()
    waiting_split_count   = State()
    waiting_payment_method = State()


class AdminState(StatesGroup):
    waiting_broadcast = State()
    confirm_broadcast = State()


# ============================================================
#  Yordamchi funksiyalar
# ============================================================
def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def plan_name(plan: str) -> str:
    if plan == "weekly":
        return "1 haftalik 📅"
    elif plan == "monthly":
        return "1 oylik 📆"
    elif plan == "premium":
        return "Cheksiz Premium 👑"
    else:
        return "Noma'lum tarif"


def days_left(expires_at: str) -> int:
    try:
        exp = datetime.strptime(expires_at[:19], "%Y-%m-%d %H:%M:%S")
        delta = exp - datetime.now()
        return max(0, delta.days)
    except Exception:
        return 0


async def get_bot_link(user_id: int) -> str:
    me = await bot.get_me()
    return f"https://t.me/{me.username}?start=ref_{user_id}"


async def send_quiz_poll(chat_id: int, question: dict, idx: int, total: int, time_limit: int) -> Message:
    q_text  = f"[{idx}/{total}] {question['question']}"
    options = [str(o)[:100] for o in question["options"]]
    me = await bot.get_me()
    return await bot.send_poll(
        chat_id=chat_id,
        question=q_text[:300],
        options=options,
        type="quiz",
        correct_option_id=int(question["correct_option_id"]),
        is_anonymous=False,
        explanation=f"🤖 Asosiy botga qaytish: @{me.username}",
        open_period=time_limit,
    )


async def auto_advance_if_unanswered(user_id: int, chat_id: int, current_index: int, time_limit: int):
    await asyncio.sleep(time_limit + 2)
    session = await db.get_quiz_session(user_id)
    if session and session["current_index"] == current_index:
        count = await db.increment_unanswered_count(user_id)
        if count >= 3:
            lang = await db.get_user_lang(user_id)
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            from aiogram.types import InlineKeyboardButton
            b = InlineKeyboardBuilder()
            b.row(InlineKeyboardButton(text=_("btn_resume", lang), callback_data="resume_test"))
            await bot.send_message(chat_id, _("pause_msg", lang), reply_markup=b.as_markup())
            return
        await db.update_quiz_progress(user_id, current_index + 1, session["score"])
        await send_next_question(user_id, chat_id)


async def send_next_question(user_id: int, chat_id: int):
    session = await db.get_quiz_session(user_id)
    if not session:
        return
    questions = session["questions"]
    idx       = session["current_index"]
    total     = len(questions)
    
    # Birinchi savol bo'lsa, test nomi ko'rsatish
    if idx == 0:
        part_id = session.get("part_id", 0)
        if part_id:
            part = await db.get_quiz_part_by_id(part_id)
            if part:
                await bot.send_message(
                    chat_id,
                    f"▶️ *{part['part_name']}* boshlanmoqda...\n📝 {total} ta savol",
                    reply_markup=ReplyKeyboardRemove(),
                )
    
    if idx >= total:
        part_id = session.get("part_id", 0)
        next_part_id = 0
        if part_id:
            part = await db.get_quiz_part_by_id(part_id)
            if part:
                parts = await db.get_quiz_parts(part["set_id"])
                parts.sort(key=lambda x: x["id"])
                for i, p in enumerate(parts):
                    if p["id"] == part_id and i + 1 < len(parts):
                        next_part_id = parts[i+1]["id"]
                        break
        await finish_quiz(user_id, chat_id, session["score"], total, next_part_id)
        return
    q = questions[idx]
    time_limit = q.get("time_limit", 30)
    try:
        msg = await send_quiz_poll(chat_id, q, idx + 1, total, time_limit)
        await db.update_quiz_progress(user_id, idx, session["score"], msg.poll.id)
        asyncio.create_task(auto_advance_if_unanswered(user_id, chat_id, idx, time_limit))
    except Exception as e:
        log.error(f"Poll yuborishda xatolik: {e}")


async def finish_quiz(user_id: int, chat_id: int, score: int, total: int, next_part_id: int = 0):
    pct = int(score / total * 100) if total else 0
    if pct >= 90:
        grade = "🏆 A'lo!"
        bar   = "🟩🟩🟩🟩🟩"
    elif pct >= 70:
        grade = "🎉 Yaxshi!"
        bar   = "🟩🟩🟩🟩⬜"
    elif pct >= 50:
        grade = "👍 Qoniqarli"
        bar   = "🟩🟩🟩⬜⬜"
    else:
        grade = "📚 Ko'proq o'qing!"
        bar   = "🟩⬜⬜⬜⬜"

    text = (
        f"🎓 *Quiz yakunlandi!*\n"
        f"{'━' * 20}\n\n"
        f"✅ *To'g'ri javoblar:*  {score}/{total}\n"
        f"📊 *Natija:*  {pct}%\n"
        f"📶 {bar}\n"
        f"⭐ *Baho:*  {grade}\n\n"
        f"{'━' * 20}"
    )
    
    # Foydalanuvchi bepul bo'lsa, premium taklif qil
    has_sub = await db.has_active_subscription(user_id)
    free_uses = await db.get_free_uses(user_id)
    lang = await db.get_user_lang(user_id)
    
    if not has_sub and free_uses >= FREE_USES:
        text = (
            text + 
            f"\n\n🎁 PREMIUM OBUNANI SINAB KO'RING\n\n"
            f"✨ Cheksiz quizlar yarating\n"
            f"✨ Vaqt chegarasiz testlar\n"
            f"✨ Rasmlardan avtomatik quiz yaratish\n\n"
            f"Narxlar:\n"
            f"• Haftalik: 13 990 so'm 📅\n"
            f"• Oylik: 20 990 so'm 📆"
        )
        await bot.send_message(chat_id, text, reply_markup=buy_menu_kb(lang))
    else:
        await bot.send_message(chat_id, text, reply_markup=after_quiz_kb(next_part_id, lang))


# ============================================================
#  /start — referral qo'llab-quvvatlash bilan
# ============================================================
@router.message(Command("start"))
async def cmd_start(msg: Message, state: FSMContext, command: CommandObject):
    await state.clear()
    u = msg.from_user
    await db.get_or_create_user(u.id, u.username or "", u.full_name or "")
    lang = await db.get_user_lang(u.id)

    # Referral parametrini tekshirish
    args = command.args or ""
    if args.startswith("part_"):
        try:
            part_id = int(args.split("_")[1])
            part = await db.get_quiz_part_by_id(part_id)
            if part:
                q_count = len(part["questions"])
                info = (
                    f"🎲 \"{part['part_name']}\" testiga tayyorlaning\n"
                    f"👥 0 kishi 🖋 0 marta ishlatildi\n"
                    f"📊 {q_count} ta savol ⏱ Har bir savol uchun {part['time_limit']} soniya"
                )
                if not await db.can_use_quiz(u.id):
                    info += f"\n💳 Testni boshlash uchun premium obuna kerak"
                await msg.answer(info, reply_markup=test_part_kb(part["set_id"], part["part_name"], lang))
                return
        except Exception:
            pass
    elif args.startswith("ref_"):
        try:
            referrer_id = int(args.split("_")[1])
            if referrer_id != u.id:
                added = await db.add_referral(referrer_id, u.id)
                if added:
                    bonus = await db.check_and_give_referral_bonus(referrer_id)
                    if bonus:
                        try:
                            await bot.send_message(
                                referrer_id,
                                "🎁 *Tabriklaymiz!*\n\n"
                                "5 ta do'stingiz botga qo'shildi!\n"
                                "Sizga *1 ta bepul quiz* berildi! 🎉"
                            )
                        except Exception:
                            pass
                    else:
                        ref_count = await db.get_referral_count(referrer_id)
                        remaining = 5 - (ref_count % 5)
                        try:
                            await bot.send_message(
                                referrer_id,
                                f"👤 Yangi do'stingiz botga qo'shildi!\n\n"
                                f"Bonus olish uchun yana *{remaining} ta* taklif qiling 🔗"
                            )
                        except Exception:
                            pass
        except (ValueError, IndexError):
            pass

    # Admin bo'lsa
    if is_admin(u.id):
        await msg.answer(
            "👨‍💼 *Admin paneliga xush kelibsiz!*\n\n"
            "Quyidagi bo'limlardan birini tanlang 👇",
            reply_markup=admin_main_kb(lang)
        )
        return

    # Obuna holati
    has_sub = await db.has_active_subscription(u.id)
    if has_sub:
        sub    = await db.get_subscription_info(u.id)
        d_left = days_left(sub["expires_at"])
        status = f"✅ *Obuna faol* — {d_left} kun qoldi"
    else:
        used      = await db.get_free_uses(u.id)
        remaining = max(0, FREE_USES - used)
        status    = f"🆓 Bepul urinishlar: *{remaining}/{FREE_USES}*"

    # Reklama rasmi bilan start xabari
    start_text = (
        f"📚 *Sessiya testlarida Quiz Universty sizga yordam beradi!*\n"
        f"📄 *Quiz Universty* bilan endi bir soniyada quiz yaratishingiz mumkin!\n\n"
        f"Shunchaki *Hemis* Word formatidagi testni yuboring, va bir zumda quiz tayyor bo'ladi!\n\n"
        f"{'━' * 22}\n"
        f"{status}\n"
        f"{'━' * 22}"
    )

    try:
        photo = FSInputFile(START_PHOTO_PATH)
        await msg.answer_photo(photo=photo, caption=start_text, reply_markup=main_menu_kb(lang))
    except Exception:
        await msg.answer(start_text, reply_markup=main_menu_kb(lang))


# ============================================================
#  /stop — Quizni to'xtatish
# ============================================================
@router.message(Command("stop"))
async def cmd_stop(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    lang = await db.get_user_lang(uid)
    await state.clear()
    session = await db.get_quiz_session(uid)
    if session:
        await db.delete_quiz_session(uid)
        await msg.answer(_("stop_msg", lang), reply_markup=main_menu_kb(lang))
    else:
        await msg.answer(_("stop_err", lang), reply_markup=main_menu_kb(lang))


# ============================================================
#  /lang — Til tanlash
# ============================================================
@router.message(Command("lang"))
async def cmd_lang(msg: Message):
    lang = await db.get_user_lang(msg.from_user.id)
    await msg.answer(
        "🌐 *Tilni tanlang:*",
        reply_markup=lang_kb(lang)
    )


@router.callback_query(F.data.startswith("lang_"))
async def on_lang_select(cb: CallbackQuery):
    lang = cb.data.split("_")[1]
    await db.set_user_lang(cb.from_user.id, lang)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer(_("lang_chosen", lang), reply_markup=main_menu_kb(lang))
    await cb.answer()


# ============================================================
#  /cancel — Amalni bekor qilish
# ============================================================
@router.message(Command("cancel"))
async def cmd_cancel(msg: Message, state: FSMContext):
    lang = await db.get_user_lang(msg.from_user.id)
    await state.clear()
    await msg.answer(_("cancel_msg", lang), reply_markup=main_menu_kb(lang))


# ============================================================
#  ADMIN — Statistika
# ============================================================
def _stats_text(s: dict) -> str:
    return (
        f"📊 *Statistika paneli*\n"
        f"{'━' * 22}\n\n"
        f"👤 Bugun faol:        *{s['today_active']}*\n"
        f"🆕 Bugun yangi:       *{s['today_new']}*\n"
        f"📅 Bu oy faol:        *{s['month_active']}*\n"
        f"👥 Jami foydalanuvchi: *{s['total_users']}*\n"
        f"🔒 Faol obunalar:     *{s['active_subs']}*\n"
        f"🔗 Jami referrallar:  *{s['total_referrals']}*\n\n"
        f"{'━' * 22}\n"
        f"💰 Bu oy daromad:  *{s['month_revenue']:,} UZS*\n"
        f"💵 Jami daromad:   *{s['total_revenue']:,} UZS*\n\n"
        f"{'━' * 22}\n"
        f"⏳ Kutilayotgan cheklar: *{s['pending_count']}*\n\n"
        f"🕐 {datetime.now().strftime('%d.%m.%Y  %H:%M:%S')}"
    )


@router.message(F.text.in_(btns("menu_stats")))
async def admin_stats(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    stats = await db.get_stats()
    lang = await db.get_user_lang(msg.from_user.id)
    await msg.answer(_stats_text(stats), reply_markup=stats_refresh_kb(lang))


@router.callback_query(F.data == "refresh_stats")
async def refresh_stats(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer()
        return
    stats = await db.get_stats()
    lang = await db.get_user_lang(cb.from_user.id)
    try:
        await cb.message.edit_text(_stats_text(stats), reply_markup=stats_refresh_kb(lang))
    except Exception:
        pass
    await cb.answer("✅ Yangilandi!")


# ============================================================
#  ADMIN — Chek tekshirish
# ============================================================
@router.message(F.text.in_(btns("menu_checks")))
async def admin_checks(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    payments = await db.get_pending_payments()
    lang = await db.get_user_lang(msg.from_user.id)
    if not payments:
        await msg.answer(
            "✅ *Hozirda tekshiriladigan to'lov yo'q.*\n\nHamma cheklar ko'rib chiqilgan!",
            reply_markup=admin_main_kb(lang)
        )
        return

    await msg.answer(
        f"📋 *{len(payments)} ta kutilayotgan to'lov:*",
        reply_markup=admin_main_kb(lang)
    )
    for p in payments:
        uname   = f"@{p['username']}" if p["username"] else (p["full_name"] or "Noma'lum")
        caption = (
            f"💳 *To'lov #{p['id']}*\n"
            f"{'━' * 18}\n"
            f"👤 Foydalanuvchi: {uname}\n"
            f"🆔 ID: `{p['user_id']}`\n"
            f"📅 Tarif: *{plan_name(p['plan'])}*\n"
            f"💰 Summa: *{p['amount']:,} UZS*\n"
            f"🕐 Vaqt: {p['created_at']}"
        )
        kb = admin_payment_kb(p["id"], lang)
        if p["screenshot_file_id"]:
            try:
                await msg.answer_photo(p["screenshot_file_id"], caption=caption, reply_markup=kb)
            except Exception:
                await msg.answer(caption, reply_markup=kb)
        else:
            await msg.answer(caption + "\n\n⚠️ Chek hali yuborilmagan", reply_markup=kb)


@router.callback_query(F.data.startswith("approve_"))
async def approve_payment(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer()
        return
    pid     = int(cb.data.split("_", 1)[1])
    payment = await db.get_payment(pid)
    if not payment:
        await cb.answer("To'lov topilmadi!", show_alert=True)
        return
    await db.update_payment_status(pid, "approved")
    await db.activate_subscription(payment["user_id"], payment["plan"])
    lang = await db.get_user_lang(payment["user_id"])
    try:
        sub = await db.get_subscription_info(payment["user_id"])
        exp = sub["expires_at"][:10] if sub else "—"
        await bot.send_message(
            payment["user_id"],
            f"🎉 *To'lovingiz tasdiqlandi!*\n\n"
            f"{'━' * 22}\n"
            f"✅ Tarif: *{plan_name(payment['plan'])}*\n"
            f"📅 Tugash sanasi: *{exp}*\n"
            f"{'━' * 22}\n\n"
            f"Cheksiz quizlar yarating! 🚀",
            reply_markup=main_menu_kb(lang),
        )
    except Exception:
        pass
    try:
        suffix = "\n\n✅ *TASDIQLANDI*"
        if cb.message.photo:
            await cb.message.edit_caption(caption=(cb.message.caption or "") + suffix, reply_markup=None)
        else:
            await cb.message.edit_text((cb.message.text or "") + suffix, reply_markup=None)
    except Exception:
        pass
    await cb.answer("✅ Tasdiqlandi!")


@router.callback_query(F.data.startswith("reject_"))
async def reject_payment(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer()
        return
    pid     = int(cb.data.split("_", 1)[1])
    payment = await db.get_payment(pid)
    if not payment:
        await cb.answer("To'lov topilmadi!", show_alert=True)
        return
    await db.update_payment_status(pid, "rejected")
    lang = await db.get_user_lang(payment["user_id"])
    try:
        await bot.send_message(
            payment["user_id"],
            "❌ *To'lovingiz tasdiqlanmadi.*\n\n"
            "Iltimos, to'g'ri miqdorni to'g'ri karta raqamiga\n"
            "o'tkazing va chekni qayta yuboring.",
            reply_markup=main_menu_kb(lang),
        )
    except Exception:
        pass
    try:
        suffix = "\n\n❌ *BEKOR QILINDI*"
        if cb.message.photo:
            await cb.message.edit_caption(caption=(cb.message.caption or "") + suffix, reply_markup=None)
        else:
            await cb.message.edit_text((cb.message.text or "") + suffix, reply_markup=None)
    except Exception:
        pass
    await cb.answer("❌ Bekor qilindi!")


# ============================================================
#  ADMIN — Reklama yuborish
# ============================================================
@router.message(F.text.in_(btns("menu_broadcast")))
async def admin_broadcast_start(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    lang = await db.get_user_lang(msg.from_user.id)
    await state.set_state(AdminState.waiting_broadcast)
    await msg.answer(
        "📢 *Reklama yuborish*\n\n"
        "Barcha foydalanuvchilarga yubormoqchi bo'lgan\n"
        "xabar, rasm, video yoki faylni yuboring 👇",
        reply_markup=admin_back_kb(lang),
    )


@router.message(AdminState.waiting_broadcast)
async def admin_broadcast_content(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    lang = await db.get_user_lang(msg.from_user.id)
    if msg.text in btns("menu_admin_back"):
        await state.clear()
        await msg.answer("Admin menyu", reply_markup=admin_main_kb(lang))
        return
    await state.update_data(bcast_chat_id=msg.chat.id, bcast_msg_id=msg.message_id)
    await state.set_state(AdminState.confirm_broadcast)
    await msg.answer(
        "☝️ *Yuqoridagi xabar* barcha foydalanuvchilarga yuboriladi.\n\n"
        "Tasdiqlaysizmi?",
        reply_markup=broadcast_confirm_kb(lang),
    )


@router.callback_query(F.data == "confirm_broadcast")
async def confirm_broadcast(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer()
        return
    data     = await state.get_data()
    src_chat = data.get("bcast_chat_id")
    src_msg  = data.get("bcast_msg_id")
    await state.clear()
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cb.answer()
    user_ids = await db.get_all_user_ids()
    total    = len(user_ids)
    sent = failed = 0
    status = await cb.message.answer(f"📤 Yuborilmoqda...  0/{total}")
    for uid in user_ids:
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=src_chat, message_id=src_msg)
            sent += 1
        except Exception:
            failed += 1
        if (sent + failed) % 20 == 0:
            try:
                await status.edit_text(f"📤 Yuborilmoqda...  {sent + failed}/{total}")
            except Exception:
                pass
        await asyncio.sleep(0.05)
    await status.edit_text(
        f"✅ *Reklama yuborildi!*\n\n"
        f"📤 Yuborildi: *{sent}*\n"
        f"❌ Yuborilmadi: *{failed}*"
    )


@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await db.get_user_lang(cb.from_user.id)
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cb.message.answer("❌ Reklama bekor qilindi.", reply_markup=admin_main_kb(lang))
    await cb.answer()


@router.message(F.text.in_(btns("menu_admin_back")))
async def admin_back_menu(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    lang = await db.get_user_lang(msg.from_user.id)
    await state.clear()
    await msg.answer("👨‍💼 Admin menyu", reply_markup=admin_main_kb(lang))


# ============================================================
#  FOYDALANUVCHI — Test menyusi
# ============================================================
@router.message(F.text.in_(btns("menu_test")))
async def quiz_menu_handler(msg: Message, state: FSMContext):
    await state.clear()
    lang = await db.get_user_lang(msg.from_user.id)
    # Don't echo the button label back (which was causing duplicate "Test" messages).
    # Send a neutral header instead and show the quiz keyboard.
    await msg.answer(
        "📝 *Test menyusi*",
        reply_markup=quiz_menu_kb(lang),
    )


# ============================================================
#  Yangi test to'plam yaratish
# ============================================================
@router.message(F.text.in_(btns("menu_new_quiz")))
async def start_new_quiz(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    lang = await db.get_user_lang(uid)
    if not await db.can_use_quiz(uid):
        await msg.answer(
            f"⛔ *Bepul urinishlar tugadi!*\n\n"
            f"Siz {FREE_USES} ta bepul quizdan foydalandingiz.\n\n"
            f"Cheksiz quiz uchun obuna xarid qiling 👇",
            reply_markup=buy_menu_kb(lang),
        )
        return

    await state.set_state(UserState.waiting_quiz_name)
    await msg.answer(
        "📝 *Testingizni nomini yuboring*",
        reply_markup=back_kb(lang),
    )


@router.message(UserState.waiting_quiz_name)
async def handle_quiz_name(msg: Message, state: FSMContext):
    lang = await db.get_user_lang(msg.from_user.id)
    if msg.text in btns("menu_back"):
        await state.clear()
        await msg.answer("📝 Test menyusi", reply_markup=quiz_menu_kb(lang))
        return
    quiz_name = msg.text.strip() if msg.text else ""
    if not quiz_name:
        await msg.answer("❌ Iltigos, nom kiriting.")
        return
    await state.update_data(quiz_name=quiz_name)
    await state.set_state(UserState.waiting_time_limit)
    await msg.answer(
        "⏱ *Har bir savol uchun vaqt limitini kiriting* (5–300 soniya)\n\n"
        "`Masalan: 30`",
        reply_markup=back_kb(lang),
    )


@router.message(UserState.waiting_time_limit)
async def handle_time_limit(msg: Message, state: FSMContext):
    lang = await db.get_user_lang(msg.from_user.id)
    if msg.text in btns("menu_back"):
        await state.clear()
        await msg.answer("📝 Test menyusi", reply_markup=quiz_menu_kb(lang))
        return
    text = (msg.text or "").strip()
    if not text.isdigit():
        await msg.answer("❌ Iltimos, son kiriting.")
        return
    seconds = int(text)
    if not (5 <= seconds <= 300):
        await msg.answer("❌ Iltimos, 5 dan 300 gacha son kiriting.")
        return

    await state.update_data(time_limit=seconds)
    await state.set_state(UserState.waiting_file)
    await msg.answer(
        "📎 *Test faylini yuboring*\n\n"
        "📄 txt · 📘 docx · 📊 pptx · 📗 xlsx · 📑 pdf · 🖼 Rasm\n\n"
        "*Format:*\n"
        "Savol matni?\n"
        "====\n"
        "# To'g'ri javob\n"
        "====\n"
        "Variant 2\n"
        "====\n"
        "Variant 3\n"
        "====\n"
        "Variant 4",
        reply_markup=back_kb(lang),
    )


# ============================================================
#  Test to'plamlarini ko'rish
# ============================================================
@router.message(F.text.in_(btns("menu_my_quizzes")))
async def my_quizzes(msg: Message):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    uid  = msg.from_user.id
    lang = await db.get_user_lang(uid)
    sets = await db.get_user_quiz_sets(uid)
    if not sets:
        await msg.answer(
            "📋 *Hozirda hech qanday test to'plam yo'q.*\n\n"
            "Yangi test to'plam yaratish uchun *➕ Yangi test to'plam yaratish* ni bosing.",
            reply_markup=quiz_menu_kb(lang),
        )
        return
    b = InlineKeyboardBuilder()
    for s in sets:
        b.row(InlineKeyboardButton(
            text=f"📚 {s['name']}  ({s['question_count']} ta savol)",
            callback_data=f"view_set_{s['id']}",
        ))
    b.row(InlineKeyboardButton(text=_("menu_back", lang), callback_data="cb_quiz_menu"))
    await msg.answer(
        "📋 *Test to'plamlaringiz:*",
        reply_markup=b.as_markup(),
    )


@router.callback_query(F.data.startswith("view_set_"))
async def view_set(cb: CallbackQuery):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    set_id = int(cb.data.split("_")[2])
    uid    = cb.from_user.id
    lang   = await db.get_user_lang(uid)
    qs     = await db.get_quiz_set(set_id)
    if not qs or qs["user_id"] != uid:
        await cb.answer("Topilmadi!", show_alert=True)
        return
    parts     = await db.get_quiz_parts(set_id)
    part_names = [p["part_name"] for p in parts]
    q_count   = len(qs["questions"])
    info = (
        f"📚 *{qs['name']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 Savollar soni: *{q_count}*\n"
        f"⏱ Vaqt limiti: *{qs['time_limit']} soniya*\n"
        f"🔢 Ishlatilgan: *{qs['use_count']} marta*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    try:
        await cb.message.edit_text(info, reply_markup=test_set_detail_kb(set_id, part_names, lang))
    except Exception:
        pass
    await cb.answer()



# ============================================================
#  Fayl qabul qilish
# ============================================================
@router.message(UserState.waiting_file)
async def handle_file(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    lang = await db.get_user_lang(uid)
    if msg.text in btns("menu_back"):
        await state.clear()
        await msg.answer("📝 Quiz menyusi", reply_markup=quiz_menu_kb(lang))
        return
    file_id   = None
    file_name = "fayl.txt"
    if msg.document:
        file_id   = msg.document.file_id
        file_name = msg.document.file_name or "fayl.bin"
    elif msg.photo:
        file_id   = msg.photo[-1].file_id
        file_name = "rasm.jpg"
    elif msg.text:
        qs = parse_questions_from_text(msg.text)
        if qs:
            await _process_questions(msg, state, qs)
        else:
            await msg.answer(
                "❌ Matndan savollar topilmadi.\n"
                "Iltimos, to'g'ri formatda yozing yoki fayl yuboring."
            )
        return
    else:
        await msg.answer("❌ Iltimos, fayl, rasm yoki matn yuboring.")
        return
    proc = await msg.answer("⏳ *Fayl o'qilmoqda...*")
    try:
        tg_file   = await bot.get_file(file_id)
        bio       = await bot.download_file(tg_file.file_path)
        raw_bytes = bio.read()
        questions, err = await parse_file(raw_bytes, file_name)
        if err:
            await proc.edit_text(err)
            return
        await proc.delete()
        await _process_questions(msg, state, questions)
    except Exception as exc:
        log.exception("Fayl o'qishda xatolik")
        await proc.edit_text(f"❌ Xatolik yuz berdi: {exc}")


async def _process_questions(msg: Message, state: FSMContext, questions: list):
    uid        = msg.from_user.id
    lang       = await db.get_user_lang(uid)
    data       = await state.get_data()
    quiz_name  = data.get("quiz_name", "Nomsiz test")
    time_limit = data.get("time_limit", 30)
    
    for q in questions:
        q["time_limit"] = time_limit

    # Do not increment free uses on upload; increment when the user actually starts the quiz session.

    # To'plamni DB ga saqlash
    set_id = await db.save_quiz_set(uid, quiz_name, questions, time_limit)
    await db.create_quiz_session(uid, questions)

    # Standart bitta butun bo'lak qilib saqlash
    parts = [{
        "name": f"{quiz_name} 1-{len(questions)}",
        "questions": questions
    }]
    await db.save_quiz_parts(set_id, parts)

    await state.update_data(split_set_id=set_id)
    await state.set_state(UserState.waiting_split_count)
    from buttons import split_prompt_kb
    
    text = "✅ *Fayl qabul qilindi!*\n\nIltimos har bir testda savollar sonini kiriting, men test to'plamini shunga qarab bo'laman"
    await msg.answer(
        text,
        reply_markup=split_prompt_kb(set_id, lang),
    )


# ============================================================
#  Test to'plam — Bo'lish (split)
# ============================================================
@router.callback_query(F.data.startswith("split_set_"))
async def split_set_ask(cb: CallbackQuery, state: FSMContext):
    set_id = int(cb.data.split("_")[2])
    await state.update_data(split_set_id=set_id)
    await state.set_state(UserState.waiting_split_count)
    text = "Iltimos har bir testda savollar sonini kiriting, men test to'plamini shunga qarab bo'laman"
    try:
        await cb.message.edit_text(text)
    except Exception:
        await cb.message.answer(text)
    await cb.answer()


@router.message(UserState.waiting_split_count)
async def handle_split_count(msg: Message, state: FSMContext):
    text = (msg.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        await msg.answer("❌ Iltimos, musbat butun son kiriting.")
        return
    
    chunk_size = int(text)
    data = await state.get_data()
    set_id = data.get("split_set_id")
    if not set_id:
        await state.clear()
        return

    uid = msg.from_user.id
    lang = await db.get_user_lang(uid)
    qs  = await db.get_quiz_set(set_id)
    if not qs or qs["user_id"] != uid:
        await msg.answer("Topilmadi!")
        await state.clear()
        return

    questions  = qs["questions"]
    total      = len(questions)
    
    n_parts = (total + chunk_size - 1) // chunk_size
    set_name   = qs["name"]
    time_limit = qs["time_limit"]
    
    parts = []
    for i in range(n_parts):
        chunk = questions[i * chunk_size : (i + 1) * chunk_size]
        if not chunk:
            break
        for q in chunk:
            q["time_limit"] = time_limit
        start = i * chunk_size + 1
        end   = min((i + 1) * chunk_size, total)
        parts.append({
            "name":       f"{set_name} {start}-{end}",
            "questions":  chunk,
            "time_limit": time_limit,
        })
    
    await db.save_quiz_parts(set_id, parts)
    part_names = [p["name"] for p in parts]
    
    await state.clear()
    
    await msg.answer(
        f"✅ *{n_parts} qismga bo'lindi!*\n"
        f"{'━' * 20}\n" +
        "\n".join(f"• {p}" for p in part_names),
        reply_markup=test_set_detail_kb(set_id, part_names, lang),
    )


@router.callback_query(F.data.startswith("view_part_"))
async def view_part_handler(cb: CallbackQuery):
    data      = cb.data[len("view_part_"):]
    set_id    = int(data.split("_")[0])
    part_name = "_".join(data.split("_")[1:])
    uid       = cb.from_user.id
    lang      = await db.get_user_lang(uid)
    part      = await db.get_quiz_part_by_name(set_id, part_name)
    if not part:
        await cb.answer("Topilmadi!", show_alert=True)
        return
    q_count = len(part["questions"])
    info = (
        f"🎲 \"{part_name}\" testiga tayyorlaning\n"
        f"👥 0 kishi 🖋 0 marta ishlatildi\n"
        f"📊 {q_count} ta savol ⏱ Har bir savol uchun {part['time_limit']} soniya"
    )
    if not await db.can_use_quiz(uid):
        info += f"\n💳 Testni boshlash uchun premium obuna kerak"

    try:
        await cb.message.edit_text(info, reply_markup=test_part_kb(set_id, part_name, lang))
    except Exception:
        await cb.message.answer(info, reply_markup=test_part_kb(set_id, part_name, lang))
    await cb.answer()

@router.callback_query(F.data.startswith("run_part_"))
async def run_part(cb: CallbackQuery):
    uid       = cb.from_user.id
    lang      = await db.get_user_lang(uid)
    if not await db.can_use_quiz(uid):
        await cb.answer("⛔ Bepul urinishlar tugadi yoki Premium yakunlandi!", show_alert=True)
        await cb.message.answer("Cheksiz quiz uchun obuna xarid qiling 👇", reply_markup=buy_menu_kb(lang))
        return
    data      = cb.data[len("run_part_"):]
    set_id    = int(data.split("_")[0])
    part_name = "_".join(data.split("_")[1:])
    part      = await db.get_quiz_part_by_name(set_id, part_name)
    if not part:
        await cb.answer("Topilmadi!", show_alert=True)
        return
    questions = part["questions"]
    # Increment free uses only if user has no active subscription
    if not await db.has_active_subscription(uid):
        await db.increment_free_uses(uid)
    await db.create_quiz_session(uid, questions, part_id=part["id"]) 
    await db.increment_set_use_count(set_id)
    await cb.answer()
    await send_next_question(uid, cb.message.chat.id)

@router.callback_query(F.data.startswith("share_set_"))
async def share_set(cb: CallbackQuery):
    import urllib.parse
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    set_id = int(cb.data.split("_")[2])
    uid    = cb.from_user.id
    lang   = await db.get_user_lang(uid)
    qs     = await db.get_quiz_set(set_id)
    if not qs or qs["user_id"] != uid:
        await cb.answer("Topilmadi!", show_alert=True)
        return
    me   = await bot.get_me()
    link = f"https://t.me/{me.username}?start=set_{set_id}"
    share_text = (
        f"{qs['name']} — test to'plami\n"
        f"{len(qs['questions'])} ta savol 📚"
    )
    share_url = (
        "https://t.me/share/url"
        f"?url={urllib.parse.quote(link)}"
        f"&text={urllib.parse.quote(share_text)}"
    )
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📤 Ulashish", url=share_url))
    b.row(InlineKeyboardButton(text=_("menu_back", lang), callback_data=f"view_set_{set_id}"))
    await cb.answer()
    await cb.message.answer(
        f"🔗 *{qs['name']}* uchun havola:\n`{link}`",
        reply_markup=b.as_markup(),
    )


@router.callback_query(F.data.startswith("delete_set_"))
async def delete_set(cb: CallbackQuery):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    set_id = int(cb.data.split("_")[2])
    lang   = await db.get_user_lang(cb.from_user.id)
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ Ha, o'chirish",   callback_data=f"confirm_del_{set_id}"),
        InlineKeyboardButton(text="❌ Yo'q",             callback_data=f"view_set_{set_id}"),
    )
    try:
        await cb.message.edit_text(
            "🗑 *To'plamni o'chirishni tasdiqlaysizmi?*",
            reply_markup=b.as_markup(),
        )
    except Exception:
        await cb.message.answer(
            "🗑 *To'plamni o'chirishni tasdiqlaysizmi?*",
            reply_markup=b.as_markup(),
        )
    await cb.answer()


@router.callback_query(F.data.startswith("confirm_del_"))
async def confirm_delete_set(cb: CallbackQuery):
    set_id = int(cb.data.split("_")[2])
    uid    = cb.from_user.id
    ok     = await db.delete_quiz_set(set_id, uid)
    if ok:
        await cb.answer("✅ O'chirildi!", show_alert=False)
        try:
            await cb.message.edit_text("🗑 To'plam o'chirildi.")
        except Exception:
            pass
    else:
        await cb.answer("❌ O'chirib bo'lmadi!", show_alert=True)



# ============================================================
#  Poll javobi
# ============================================================
@router.poll_answer()
async def on_poll_answer(answer: PollAnswer):
    user_id = answer.user.id
    session = await db.get_quiz_session(user_id)
    if not session:
        return
        
    await db.reset_unanswered_count(user_id)

    questions = session["questions"]
    idx       = session["current_index"]
    score     = session["score"]
    if idx < len(questions):
        q = questions[idx]
        if answer.option_ids and answer.option_ids[0] == int(q["correct_option_id"]):
            score += 1
        await db.update_quiz_progress(user_id, idx + 1, score)
        await asyncio.sleep(1.5)
        await send_next_question(user_id, user_id)


# ============================================================
#  Quiz tugagandan keyin — 3 tugma
# ============================================================
@router.callback_query(F.data.startswith("run_set_"))
async def run_set(cb: CallbackQuery):
    set_id = int(cb.data.split("_")[2])
    parts = await db.get_quiz_parts(set_id)
    if not parts:
        await cb.answer("Test to'plami bo'sh!", show_alert=True)
        return
    part = parts[0]
    uid = cb.from_user.id
    lang = await db.get_user_lang(uid)
    if not await db.can_use_quiz(uid):
        await cb.answer("⛔ Bepul urinishlar tugadi yoki Premium yakunlandi!", show_alert=True)
        await cb.message.answer("Cheksiz quiz uchun obuna xarid qiling 👇", reply_markup=buy_menu_kb(lang))
        return
    questions = part["questions"]
    await db.create_quiz_session(uid, questions, part_id=part["id"])
    await db.increment_set_use_count(set_id)
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cb.answer()
    await cb.message.answer(
        f"▶️ *{part['part_name']}* boshlanmoqda...\n"
        f"📝 {len(questions)} ta savol",
        reply_markup=ReplyKeyboardRemove(),
    )
    await send_next_question(uid, cb.message.chat.id)

@router.callback_query(F.data.startswith("next_part_"))
async def next_part(cb: CallbackQuery):
    part_id = int(cb.data.split("_")[2])
    part = await db.get_quiz_part_by_id(part_id)
    if not part:
        await cb.answer("Topilmadi!", show_alert=True)
        return
    uid = cb.from_user.id
    lang = await db.get_user_lang(uid)
    if not await db.can_use_quiz(uid):
        await cb.answer("⛔ Bepul urinishlar tugadi yoki Premium yakunlandi!", show_alert=True)
        return
    questions = part["questions"]
    # Increment free uses only if user has no active subscription
    if not await db.has_active_subscription(uid):
        await db.increment_free_uses(uid)
    await db.create_quiz_session(uid, questions, part_id=part["id"])
    await db.increment_set_use_count(part["set_id"])
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cb.answer()
    await send_next_question(uid, cb.message.chat.id)

@router.callback_query(F.data.startswith("share_part_"))
async def share_part(cb: CallbackQuery):
    import urllib.parse
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    data      = cb.data[len("share_part_"):]
    set_id    = int(data.split("_")[0])
    part_name = "_".join(data.split("_")[1:])
    uid       = cb.from_user.id
    lang      = await db.get_user_lang(uid)
    part      = await db.get_quiz_part_by_name(set_id, part_name)
    if not part:
        await cb.answer("Topilmadi!", show_alert=True)
        return
    me   = await bot.get_me()
    link = f"https://t.me/{me.username}?start=part_{part['id']}"
    share_text = (
        f"\"{part_name}\" — test to'plami\n"
        f"Testni ishlash uchun quyidagi havolani bosing 👇"
    )
    share_url = (
        "https://t.me/share/url"
        f"?url={urllib.parse.quote(link)}"
        f"&text={urllib.parse.quote(share_text)}"
    )
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📤 Ulashish", url=share_url))
    b.row(InlineKeyboardButton(text=_("menu_back", lang), callback_data=f"view_part_{set_id}_{part_name}"))
    await cb.answer()
    await cb.message.answer(
        f"🔗 *{part_name}* uchun havola:\n`{link}`",
        reply_markup=b.as_markup(),
    )

@router.callback_query(F.data == "resume_test")
async def resume_test_cb(cb: CallbackQuery):
    uid = cb.from_user.id
    session = await db.get_quiz_session(uid)
    if not session:
        await cb.answer("Test topilmadi", show_alert=True)
        return
    await db.reset_unanswered_count(uid)
    await db.update_quiz_progress(uid, session["current_index"] + 1, session["score"])
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cb.answer()
    await send_next_question(uid, cb.message.chat.id)

@router.callback_query(F.data == "retake_quiz")
async def retake_quiz(cb: CallbackQuery):
    uid     = cb.from_user.id
    session = await db.get_quiz_session(uid)
    if not session:
        await cb.answer("Quiz topilmadi!", show_alert=True)
        return
    reshuffled = [shuffle_options(q) for q in session["original_qs"]]
    # Increment free uses only if user has no active subscription
    if not await db.has_active_subscription(uid):
        await db.increment_free_uses(uid)
    await db.create_quiz_session(uid, reshuffled)
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cb.answer()
    await send_next_question(uid, cb.message.chat.id)


@router.callback_query(F.data == "new_quiz")
async def new_quiz(cb: CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    lang = await db.get_user_lang(uid)
    await db.delete_quiz_session(uid)
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cb.answer()
    if not await db.can_use_quiz(uid):
        await cb.message.answer(
            f"⛔ Bepul urinishlar tugadi!\n\nObuna xarid qiling 👇",
            reply_markup=buy_menu_kb(lang),
        )
        return
    await state.set_state(UserState.waiting_quiz_name)
    await cb.message.answer("📝 *Yangi testingizni nomini yuboring:*", reply_markup=back_kb(lang))


@router.callback_query(F.data == "cb_main_menu")
async def cb_main_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await db.get_user_lang(cb.from_user.id)
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cb.answer()
    await cb.message.answer("🏠 *Asosiy menyu*", reply_markup=main_menu_kb(lang))


@router.callback_query(F.data == "cb_quiz_menu")
async def cb_quiz_menu(cb: CallbackQuery):
    lang = await db.get_user_lang(cb.from_user.id)
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cb.answer()
    await cb.message.answer("📝 *Test bo'limi*", reply_markup=quiz_menu_kb(lang))


# ============================================================
#  Sotib olish — Click va Payme
# ============================================================
@router.message(F.text.in_(btns("menu_buy")))
async def buy_section(msg: Message):
    uid     = msg.from_user.id
    lang    = await db.get_user_lang(uid)
    has_sub = await db.has_active_subscription(uid)
    if has_sub:
        sub    = await db.get_subscription_info(uid)
        d_left = days_left(sub["expires_at"])
        await msg.answer(
            f"✅ *Faol obunangiz bor!*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 Tarif: *{plan_name(sub['plan'])}*\n"
            f"📆 Tugash sanasi: *{sub['expires_at'][:10]}*\n"
            f"⏳ Qolgan kunlar: *{d_left} kun*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Cheksiz quizdan bahramand bo'ling! 🎉",
            reply_markup=main_menu_kb(lang),
        )
        return
    used      = await db.get_free_uses(uid)
    remaining = max(0, FREE_USES - used)
    await msg.answer(
        f"✨ *Quiz Universty Premium'ga xush kelibsiz!*\n\n"
        f"🚀 Cheksiz quizlar yarating!\n"
        f"✅ Rasmlardan avtomatik quiz!\n"
        f"⚡ Vaqt chegarasiz testlar!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆓 Qolgan bepul urinishlar: *{remaining}/{FREE_USES}*\n\n"
        f"📅 *Haftalik*      — *{WEEKLY_PRICE:,} UZS*\n"
        f"📆 *Oylik*         — *{MONTHLY_PRICE:,} UZS*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 Har 5 ta referral uchun *1 bepul quiz* oling!\n\n"
        f"To'lov usulini tanlang 👇",
        reply_markup=payment_method_kb(lang),
    )


@router.callback_query(F.data == "pay_uzcard")
async def on_uzcard_payment(cb: CallbackQuery, state: FSMContext):
    """Uzcard tanlandi — show Uzcard card details and plan selection menu"""
    lang = await db.get_user_lang(cb.from_user.id)
    await state.update_data(payment_method="uzcard")
    
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    
    await cb.answer()
    
    # Show Uzcard card details with payment instruction
    uzcard_message = (
        f"💳 *Uzcard orqali to'lov*\n\n"
        f"� *Uzcard:*\n"
        f"`{UZCARD_NUMBER_1}`\n"
        f"👤 {UZCARD_HOLDER_1}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏱️ To'lovni *5 daqiqa* ichida amalga oshirib,\n"
        f"chek \\(screenshot\\) yuboring!\n\n"
        f"Quyidagi tarifni tanlang 👇"
    )
    
    await cb.message.answer(uzcard_message, reply_markup=buy_menu_kb(lang))


@router.callback_query(F.data == "pay_humo")
async def on_humo_payment(cb: CallbackQuery, state: FSMContext):
    """Humo tanlandi — show Humo card details and plan selection menu"""
    lang = await db.get_user_lang(cb.from_user.id)
    await state.update_data(payment_method="humo")
    
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    
    await cb.answer()
    
    # Show Humo card details with payment instruction
    humo_message = (
        f"💳 *Humo orqali to'lov*\n\n"
        f"� *Humo:*\n"
        f"`{HUMO_NUMBER_1}`\n"
        f"👤 {HUMO_HOLDER_1}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏱️ To'lovni *5 daqiqa* ichida amalga oshirib,\n"
        f"chek \\(screenshot\\) yuboring!\n\n"
        f"Quyidagi tarifni tanlang 👇"
    )
    
    await cb.message.answer(humo_message, reply_markup=buy_menu_kb(lang))


@router.callback_query(F.data.startswith("buy_"))
async def on_buy(cb: CallbackQuery, state: FSMContext):
    """User selected a plan (weekly/monthly) — create payment and wait for screenshot"""
    plan   = cb.data.split("_", 1)[1]
    
    if plan == "weekly":
        amount = WEEKLY_PRICE
    elif plan == "monthly":
        amount = MONTHLY_PRICE
    else:
        await cb.answer("❌ Xatolik!")
        return
    
    # Create payment record in DB
    pid    = await db.create_payment(cb.from_user.id, plan, amount)
    await state.update_data(payment_id=pid, plan=plan, amount=amount)
    await state.set_state(UserState.waiting_screenshot)
    
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    
    await cb.answer()
    
    # Get selected payment method (Uzcard or Humo)
    data = await state.get_data()
    method = data.get("payment_method", "uzcard")
    
    if method == "humo":
        card_title = "🏦 *Humo:*"
        card_number = HUMO_NUMBER_1
        card_holder = HUMO_HOLDER_1
    else:
        card_title = "🏦 *Uzcard:*"
        card_number = UZCARD_NUMBER_1
        card_holder = UZCARD_HOLDER_1

    # Compose payment confirmation message with card details
    payment_text = (
        f"💳 *To'lov ma'lumotlari*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Tarif: *{plan_name(plan)}*\n"
        f"💰 Summa: *{amount:,} UZS*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{card_title}\n"
        f"`{card_number}`\n"
        f"👤 {card_holder}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏱️ To'lovni amalga oshirib,\n"
        f"*5 daqiqa* ichida chek \\(screenshot\\) yuboring!\n\n"
        f"🔎 To'lov ID: *{pid}*"
    )

    # Send payment info message WITHOUT any buttons - user just uploads screenshot
    await cb.message.answer(payment_text)

    # Start timeout watcher: if no screenshot uploaded in 5 minutes, cancel payment and notify user
    asyncio.create_task(payment_timeout_watcher(pid, cb.from_user.id))


@router.message(UserState.waiting_screenshot)
async def handle_screenshot(msg: Message, state: FSMContext):
    """User sends screenshot — save it, notify admin, and confirm to user"""
    lang = await db.get_user_lang(msg.from_user.id)
    
    if msg.text in btns("menu_back"):
        await state.clear()
        await msg.answer("🏠 Asosiy menyu", reply_markup=main_menu_kb(lang))
        return
    
    # Accept photo or document as screenshot
    screenshot_fid = None
    if msg.photo:
        screenshot_fid = msg.photo[-1].file_id
    elif msg.document:
        screenshot_fid = msg.document.file_id
    else:
        await msg.answer("❌ Iltimos, to'lov cheki *rasmini* yuboring.")
        return
    
    # Get payment details from FSM state
    data   = await state.get_data()
    pid    = data.get("payment_id")
    plan   = data.get("plan")
    amount = data.get("amount")
    
    if not pid:
        await msg.answer("❌ Xatolik: To'lov ID topilmadi.")
        await state.clear()
        return
    
    # Update payment record with screenshot
    await db.update_payment_screenshot(pid, screenshot_fid)
    await state.clear()
    
    # Send concise confirmation to user
    await msg.answer(
        _("msg_payment_checking", lang),
        reply_markup=main_menu_kb(lang),
    )
    
    # Notify admin with screenshot and admin controls
    u     = msg.from_user
    uname = f"@{u.username}" if u.username else (u.full_name or "Noma'lum")
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                admin_id,
                screenshot_fid,
                caption=(
                    f"💳 *Yangi to'lov #{pid}*\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 {uname}  (ID: `{u.id}`)\n"
                    f"📅 Tarif: *{plan_name(plan)}*\n"
                    f"💰 Summa: *{amount:,} UZS*"
                ),
                reply_markup=admin_payment_kb(pid, lang),
            )
        except Exception as exc:
            log.warning(f"Admin {admin_id} ga xabar yuborib bo'lmadi: {exc}")


async def payment_timeout_watcher(payment_id: int, user_id: int, timeout_seconds: int = 300):
    """Wait timeout_seconds; if payment has no screenshot, cancel and notify user."""
    await asyncio.sleep(timeout_seconds)
    p = await db.get_payment(payment_id)
    if not p:
        return
    # if screenshot not provided and status still pending (DB default), cancel
    if not p.get("screenshot_file_id") and (p.get("status") in (None, "pending", "created")):
        await db.cancel_payment(payment_id)
        log.info(f"Payment {payment_id} cancelled due to timeout")
        lang = await db.get_user_lang(user_id)
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="🔁 Sotib olish", callback_data="open_buy"))
        try:
            await bot.send_message(user_id, "❌ To'lov bekor qilindi — iltimos yana urinib ko'ring.", reply_markup=b.as_markup())
        except Exception:
            pass


@router.callback_query(F.data == "open_buy")
async def open_buy(cb: CallbackQuery):
    lang = await db.get_user_lang(cb.from_user.id)
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cb.answer()
    await cb.message.answer(
        f"✨ *Quiz Universty Premium'ga xush kelibsiz!*",
        reply_markup=payment_method_kb(lang),
    )


@router.callback_query(F.data.startswith("paid_hint_"))
async def paid_hint(cb: CallbackQuery, state: FSMContext):
    """User clicked 'Screenshot upload' button — just close the button and wait"""
    await cb.answer("✅ Chekni yuboring...", show_alert=False)


@router.callback_query(F.data.startswith("cancel_payment_"))
async def cancel_payment_user(cb: CallbackQuery, state: FSMContext):
    """User canceled payment — remove screenshot state and go back to menu"""
    pid = int(cb.data.split("_", 2)[2])
    await db.cancel_payment(pid)
    lang = await db.get_user_lang(cb.from_user.id)
    
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    
    await cb.answer("✅ Bekor qilindi!")
    await state.clear()
    await cb.message.answer("🏠 Asosiy menyu", reply_markup=main_menu_kb(lang))


@router.callback_query(F.data == "cb_back_main")
async def cb_back_main(cb: CallbackQuery):
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    lang = await db.get_user_lang(cb.from_user.id)
    await cb.answer()
    await cb.message.answer("🏠 *Asosiy menyu*", reply_markup=main_menu_kb(lang))


# ============================================================
#  Ulashish — Referral tizimi
# ============================================================
@router.message(F.text.in_(btns("menu_share")))
async def share_bot(msg: Message):
    import urllib.parse
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    uid       = msg.from_user.id
    link      = await get_bot_link(uid)
    ref_count = await db.get_referral_count(uid)
    bonuses   = await db.get_bonuses_given(uid)

    next_milestone      = ((ref_count // 5) + 1) * 5
    remaining_for_bonus = next_milestone - ref_count
    current_in_cycle    = ref_count % 5
    bar = "🟢" * current_in_cycle + "⚪" * (5 - current_in_cycle)

    share_msg  = (
        "🎓 Quiz Universty botini sinab ko'ring!\n"
        "Har qanday fayldan quiz yaratadi 🚀"
    )
    share_url  = (
        "https://t.me/share/url"
        f"?url={urllib.parse.quote(link)}"
        f"&text={urllib.parse.quote(share_msg)}"
    )

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="📤 Do'st taklif qilish",
        url=share_url,
    ))

    await msg.answer(
        f"🔗 *Referral tizimi*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⬆️ *Iltimos, yuqoridagi referal xabarini boshqalar bilan ulashing*\n"
        f"Kimdir shu link orqalik birinchi marta to'liq sotib olganida, sizga *5000 so'm* chegirma hamda xabar yuboriladi\n\n"
        f"Sizning shaxsiy havolangiz:\n"
        f"`{link}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Taklif qilgan do'stlar: *{ref_count}*\n"
        f"🎁 Olgan bonuslar: *{bonuses} ta bepul quiz*\n\n"
        f"📊 Keyingi bonus: {bar}\n"
        f"_{remaining_for_bonus} ta do'st qoldi_\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Har *5 ta* do'st taklif qilsangiz\n"
        f"*1 ta bepul quiz* ishlash imkoni beriladi!",
        reply_markup=kb.as_markup(),
    )


# removed VIP section


# ============================================================
#  Umumiy Orqaga
# ============================================================
@router.message(F.text.in_(btns("menu_back")))
async def back_handler(msg: Message, state: FSMContext):
    lang = await db.get_user_lang(msg.from_user.id)
    await state.clear()
    await msg.answer("🏠 *Asosiy menyu*", reply_markup=main_menu_kb(lang))


# ============================================================
#  Noma'lum xabarlar
# ============================================================
@router.message()
async def unknown_message(msg: Message):
    if is_admin(msg.from_user.id):
        return
    lang = await db.get_user_lang(msg.from_user.id)
    await msg.answer(
        "❓ Quyidagi tugmalardan foydalaning 👇",
        reply_markup=main_menu_kb(lang),
    )


# ============================================================
#  Botni ishga tushirish
# ============================================================
async def main():
    await db.init_db()
    log.info("Ma'lumotlar bazasi tayyor ✅")
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    log.info("Bot ishga tushmoqda... 🚀")
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped gracefully.")
