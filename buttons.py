# ============================================================
#  buttons.py — Barcha tugmalar (emoji bilan chiroyli)
#  MUHIM: button text va F.text == bir xil bo'lishi shart!
# ============================================================

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from locales import _

# ============================================================
#  Foydalanuvchi — ReplyKeyboard
# ============================================================

def main_menu_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=_("menu_test", lang)))
    b.row(
        KeyboardButton(text=_("menu_buy", lang)),
        KeyboardButton(text=_("menu_share", lang)),
    )
    return b.as_markup(resize_keyboard=True)


def quiz_menu_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=_("menu_new_quiz", lang)))
    b.row(KeyboardButton(text=_("menu_my_quizzes", lang)))
    b.row(KeyboardButton(text=_("menu_back", lang)))
    return b.as_markup(resize_keyboard=True)


def back_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=_("menu_back", lang)))
    return b.as_markup(resize_keyboard=True)


def payment_method_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """To'lov usulini tanlash tugmalari"""
    # Switched to inline keyboard to avoid reply-keyboard echoes
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=_("uzcard", lang), callback_data="pay_uzcard"))
    b.row(InlineKeyboardButton(text=_("humo", lang), callback_data="pay_humo"))
    b.row(InlineKeyboardButton(text=_("menu_back", lang), callback_data="cb_back_main"))
    return b.as_markup()


# ============================================================
#  Foydalanuvchi — InlineKeyboard
# ============================================================

def lang_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    """Til tanlash tugmalari"""
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🇺🇸 English",  callback_data="lang_en"))
    b.row(InlineKeyboardButton(text="🇷🇺 Русский",  callback_data="lang_ru"))
    b.row(InlineKeyboardButton(text="🇺🇿 O'zbek",   callback_data="lang_uz"))
    return b.as_markup()


def buy_menu_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text=_("btn_buy_weekly", lang),
        callback_data="buy_weekly",
    ))
    b.row(InlineKeyboardButton(
        text=_("btn_buy_monthly", lang),
        callback_data="buy_monthly",
    ))
    b.row(InlineKeyboardButton(
        text=_("menu_back", lang),
        callback_data="cb_back_main",
    ))
    return b.as_markup()


def split_prompt_kb(set_id: int, lang: str = "uz") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=_("btn_no_split", lang), callback_data=f"view_set_{set_id}"))
    return b.as_markup()


def after_quiz_kb(next_part_id: int = 0, lang: str = "uz") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if next_part_id > 0:
        b.row(InlineKeyboardButton(text=_("btn_next_part", lang), callback_data=f"next_part_{next_part_id}"))
    b.row(InlineKeyboardButton(text=_("btn_retake", lang),  callback_data="retake_quiz"))
    b.row(InlineKeyboardButton(text=_("menu_new_quiz", lang),     callback_data="new_quiz"))
    b.row(InlineKeyboardButton(text=_("btn_main_menu", lang),   callback_data="cb_main_menu"))
    return b.as_markup()


def test_set_detail_kb(set_id: int, parts: list, lang: str = "uz") -> InlineKeyboardMarkup:
    """Test to'plam tafsilotlari — bo'laklar va amallar"""
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text=_("btn_start_test", lang),
        callback_data=f"run_set_{set_id}",
    ))
    b.row(InlineKeyboardButton(
        text=_("btn_split", lang),
        callback_data=f"split_set_{set_id}",
    ))
    # Har bir bo'lak uchun tugma
    for part_name in parts:
        b.row(InlineKeyboardButton(
            text=part_name,
            callback_data=f"view_part_{set_id}_{part_name}",
        ))
    b.row(
        InlineKeyboardButton(
            text=_("btn_share_inline", lang),
            callback_data=f"share_set_{set_id}",
        ),
        InlineKeyboardButton(
            text=_("btn_delete", lang),
            callback_data=f"delete_set_{set_id}",
        )
    )
    b.row(InlineKeyboardButton(
        text=_("menu_back", lang),
        callback_data="cb_quiz_menu",
    ))
    return b.as_markup()


def test_part_kb(set_id: int, part_name: str, lang: str = "uz") -> InlineKeyboardMarkup:
    """Test bo'lagi tafsilotlari"""
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text=_("btn_start_test", lang),
        callback_data=f"run_part_{set_id}_{part_name}",
    ))
    b.row(InlineKeyboardButton(
        text=_("btn_share_inline", lang),
        callback_data=f"share_part_{set_id}_{part_name}",
    ))
    b.row(InlineKeyboardButton(
        text=_("btn_delete", lang),
        callback_data=f"delete_part_{set_id}_{part_name}",
    ))
    b.row(InlineKeyboardButton(
        text=_("menu_back", lang),
        callback_data=f"view_set_{set_id}",
    ))
    return b.as_markup()


# ============================================================
#  Admin — ReplyKeyboard
# ============================================================

def admin_main_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=_("menu_stats", lang)))
    b.row(KeyboardButton(text=_("menu_checks", lang)))
    b.row(KeyboardButton(text=_("menu_broadcast", lang)))
    return b.as_markup(resize_keyboard=True)


def admin_back_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=_("menu_admin_back", lang)))
    return b.as_markup(resize_keyboard=True)


# ============================================================
#  Admin — InlineKeyboard
# ============================================================

def admin_payment_kb(payment_id: int, lang: str = "uz") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=_("btn_approve", lang), callback_data=f"approve_{payment_id}"),
        InlineKeyboardButton(text=_("btn_reject", lang),  callback_data=f"reject_{payment_id}"),
    )
    return b.as_markup()


def stats_refresh_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=_("btn_refresh", lang), callback_data="refresh_stats"))
    return b.as_markup()


def broadcast_confirm_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=_("btn_send", lang),      callback_data="confirm_broadcast"),
        InlineKeyboardButton(text=_("btn_cancel_b", lang),  callback_data="cancel_broadcast"),
    )
    return b.as_markup()
