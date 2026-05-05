# ============================================================
#  database.py — Barcha ma'lumotlar bazasi operatsiyalari
# ============================================================

import aiosqlite
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from config import DB_PATH, FREE_USES

REFERRAL_BONUS_THRESHOLD = 5   # Nechta referal = 1 ta bepul urinish


# ──────────────────────────────────────────────────────────
#  Jadvallar
# ──────────────────────────────────────────────────────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id  INTEGER PRIMARY KEY,
                username     TEXT,
                full_name    TEXT,
                created_at   TEXT DEFAULT (datetime('now','localtime')),
                last_active  TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

        try:
            await db.execute("ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'uz'")
        except:
            pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                plan        TEXT    NOT NULL,
                started_at  TEXT    NOT NULL,
                expires_at  TEXT    NOT NULL,
                created_at  TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id             INTEGER NOT NULL,
                plan                TEXT    NOT NULL,
                amount              INTEGER NOT NULL,
                screenshot_file_id  TEXT,
                status              TEXT DEFAULT 'pending',
                created_at          TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS free_uses (
                user_id  INTEGER PRIMARY KEY,
                count    INTEGER DEFAULT 0
            )
        """)

        # Referral tizimi
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id  INTEGER NOT NULL,
                referred_id  INTEGER NOT NULL UNIQUE,
                created_at   TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

        # Referral bonus (nechta bonus berilgan)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referral_bonuses (
                user_id          INTEGER PRIMARY KEY,
                bonuses_given    INTEGER DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS quiz_sessions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER UNIQUE,
                questions        TEXT    NOT NULL,
                original_qs      TEXT    NOT NULL,
                current_index    INTEGER DEFAULT 0,
                score            INTEGER DEFAULT 0,
                current_poll_id  TEXT,
                created_at       TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

        # Test to'plamlari (saqlangan quiz setlar)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quiz_sets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                name        TEXT    NOT NULL,
                questions   TEXT    NOT NULL,
                time_limit  INTEGER DEFAULT 30,
                use_count   INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

        # Test to'plam bo'laklari (split qilingan qismlar)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quiz_parts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                set_id      INTEGER NOT NULL,
                part_name   TEXT    NOT NULL,
                questions   TEXT    NOT NULL,
                time_limit  INTEGER DEFAULT 30,
                FOREIGN KEY (set_id) REFERENCES quiz_sets(id) ON DELETE CASCADE
            )
        """)

        try:
            await db.execute("ALTER TABLE quiz_sessions ADD COLUMN part_id INTEGER DEFAULT 0")
        except:
            pass
            
        try:
            await db.execute("ALTER TABLE quiz_sessions ADD COLUMN unanswered_count INTEGER DEFAULT 0")
        except:
            pass

        await db.commit()


# ──────────────────────────────────────────────────────────
#  Foydalanuvchi
# ──────────────────────────────────────────────────────────
async def get_or_create_user(telegram_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (telegram_id, username, full_name)
            VALUES (?, ?, ?)
        """, (telegram_id, username or "", full_name or ""))
        await db.execute("""
            UPDATE users
               SET last_active = datetime('now','localtime'),
                   username    = ?,
                   full_name   = ?
             WHERE telegram_id = ?
        """, (username or "", full_name or "", telegram_id))
        await db.commit()


async def get_user(telegram_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                return dict(zip([c[0] for c in cur.description], row))
    return None


async def get_all_user_ids() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT telegram_id FROM users") as cur:
            return [r[0] for r in await cur.fetchall()]


# ──────────────────────────────────────────────────────────
#  Bepul urinishlar
# ──────────────────────────────────────────────────────────
async def get_free_uses(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT count FROM free_uses WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def increment_free_uses(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO free_uses (user_id, count) VALUES (?, 1)
            ON CONFLICT(user_id) DO UPDATE SET count = count + 1
        """, (user_id,))
        await db.commit()


async def add_free_uses(user_id: int, amount: int):
    """Bonus bepul urinish qo'shish (referral uchun)"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO free_uses (user_id, count) VALUES (?, 0)
            ON CONFLICT(user_id) DO NOTHING
        """, (user_id,))
        await db.execute("""
            UPDATE free_uses SET count = MAX(0, count - ?) WHERE user_id = ?
        """, (amount, user_id))
        await db.commit()


async def can_use_quiz(user_id: int) -> bool:
    if await has_active_subscription(user_id):
        return True
    uses = await get_free_uses(user_id)
    return uses < FREE_USES


# ──────────────────────────────────────────────────────────
#  Foydalanuvchi — Til sozlamalari
# ──────────────────────────────────────────────────────────
async def set_user_lang(user_id: int, lang: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET lang = ? WHERE telegram_id = ?", (lang, user_id))
        await db.commit()

async def get_user_lang(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT lang FROM users WHERE telegram_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row and row[0] else 'uz'

async def increment_unanswered_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE quiz_sessions SET unanswered_count = unanswered_count + 1 WHERE user_id = ?", (user_id,))
        await db.commit()
        async with db.execute("SELECT unanswered_count FROM quiz_sessions WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

async def reset_unanswered_count(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE quiz_sessions SET unanswered_count = 0 WHERE user_id = ?", (user_id,))
        await db.commit()


# ──────────────────────────────────────────────────────────
#  Obuna
# ──────────────────────────────────────────────────────────
async def has_active_subscription(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id FROM subscriptions
             WHERE user_id = ?
               AND expires_at > datetime('now','localtime')
             LIMIT 1
        """, (user_id,)) as cur:
            return await cur.fetchone() is not None


async def get_subscription_info(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT plan, started_at, expires_at FROM subscriptions
             WHERE user_id = ?
               AND expires_at > datetime('now','localtime')
             ORDER BY expires_at DESC
             LIMIT 1
        """, (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                return {"plan": row[0], "started_at": row[1], "expires_at": row[2]}
    return None


async def activate_subscription(user_id: int, plan: str):
    now    = datetime.now()
    if plan == "weekly":
        expiry = now + timedelta(weeks=1)
    elif plan == "monthly":
        expiry = now + timedelta(days=30)
    elif plan == "premium":
        # Premium — 10 yil (aslida cheksiz)
        expiry = now + timedelta(days=3650)
    else:
        expiry = now + timedelta(days=30)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO subscriptions (user_id, plan, started_at, expires_at)
            VALUES (?, ?, ?, ?)
        """, (
            user_id, plan,
            now.strftime("%Y-%m-%d %H:%M:%S"),
            expiry.strftime("%Y-%m-%d %H:%M:%S"),
        ))
        await db.commit()


# ──────────────────────────────────────────────────────────
#  To'lovlar
# ──────────────────────────────────────────────────────────
async def create_payment(user_id: int, plan: str, amount: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO payments (user_id, plan, amount) VALUES (?, ?, ?)",
            (user_id, plan, amount)
        )
        await db.commit()
        return cur.lastrowid


async def update_payment_screenshot(payment_id: int, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE payments SET screenshot_file_id = ?, status = 'pending_review'
             WHERE id = ?
        """, (file_id, payment_id))
        await db.commit()


async def cancel_payment(payment_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE payments SET status = 'cancelled' WHERE id = ?
        """, (payment_id,))
        await db.commit()


async def get_payment(payment_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)) as cur:
            row = await cur.fetchone()
            if row:
                return dict(zip([c[0] for c in cur.description], row))
    return None


async def get_pending_payments() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT p.id, p.user_id, p.plan, p.amount,
                   p.screenshot_file_id, p.created_at,
                   u.username, u.full_name
              FROM payments p
              JOIN users u ON p.user_id = u.telegram_id
             WHERE p.status = 'pending_review'
             ORDER BY p.created_at
        """) as cur:
            rows = await cur.fetchall()
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in rows]


async def update_payment_status(payment_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE payments SET status = ? WHERE id = ?", (status, payment_id))
        await db.commit()


# ──────────────────────────────────────────────────────────
#  Referral tizimi
# ──────────────────────────────────────────────────────────
async def add_referral(referrer_id: int, referred_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("""
                INSERT INTO referrals (referrer_id, referred_id)
                VALUES (?, ?)
            """, (referrer_id, referred_id))
            await db.commit()
            return True
        except Exception:
            return False


async def get_referral_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_bonuses_given(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT bonuses_given FROM referral_bonuses WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def check_and_give_referral_bonus(referrer_id: int) -> bool:
    total   = await get_referral_count(referrer_id)
    given   = await get_bonuses_given(referrer_id)
    earned  = total // REFERRAL_BONUS_THRESHOLD
    to_give = earned - given

    if to_give <= 0:
        return False

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO referral_bonuses (user_id, bonuses_given) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET bonuses_given = bonuses_given + ?
        """, (referrer_id, to_give, to_give))
        await db.commit()

    await add_free_uses(referrer_id, to_give)
    return True


# ──────────────────────────────────────────────────────────
#  Quiz sessiyalar (joriy o'yin)
# ──────────────────────────────────────────────────────────
async def create_quiz_session(user_id: int, questions: List[Dict], part_id: int = 0) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM quiz_sessions WHERE user_id = ?", (user_id,))
        qs_json = json.dumps(questions, ensure_ascii=False)
        cur = await db.execute("""
            INSERT INTO quiz_sessions (user_id, questions, original_qs, current_index, score, part_id, unanswered_count)
            VALUES (?, ?, ?, 0, 0, ?, 0)
        """, (user_id, qs_json, qs_json, part_id))
        await db.commit()
        return cur.lastrowid


async def get_quiz_session(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM quiz_sessions WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                data = dict(zip([c[0] for c in cur.description], row))
                data["questions"]   = json.loads(data["questions"])
                data["original_qs"] = json.loads(data["original_qs"])
                return data
    return None


async def get_session_by_poll_id(poll_id: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM quiz_sessions WHERE current_poll_id = ?", (poll_id,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                data = dict(zip([c[0] for c in cur.description], row))
                data["questions"]   = json.loads(data["questions"])
                data["original_qs"] = json.loads(data["original_qs"])
                return data
    return None


async def update_quiz_progress(
    user_id: int,
    current_index: int,
    score: int,
    current_poll_id: Optional[str] = None,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE quiz_sessions
               SET current_index   = ?,
                   score           = ?,
                   current_poll_id = ?
             WHERE user_id = ?
        """, (current_index, score, current_poll_id, user_id))
        await db.commit()


async def delete_quiz_session(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM quiz_sessions WHERE user_id = ?", (user_id,))
        await db.commit()


# ──────────────────────────────────────────────────────────
#  Quiz to'plamlari (saqlangan setlar)
# ──────────────────────────────────────────────────────────
async def save_quiz_set(user_id: int, name: str, questions: List[Dict], time_limit: int = 30) -> int:
    """Yangi quiz to'plam saqlash"""
    async with aiosqlite.connect(DB_PATH) as db:
        qs_json = json.dumps(questions, ensure_ascii=False)
        cur = await db.execute("""
            INSERT INTO quiz_sets (user_id, name, questions, time_limit)
            VALUES (?, ?, ?, ?)
        """, (user_id, name, qs_json, time_limit))
        await db.commit()
        return cur.lastrowid


async def get_user_quiz_sets(user_id: int) -> List[Dict]:
    """Foydalanuvchining barcha quiz to'plamlari"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id, name, time_limit, use_count, created_at, questions,
                   (SELECT COUNT(*) FROM quiz_parts WHERE set_id = quiz_sets.id) as part_count,
                   (SELECT COUNT(DISTINCT user_id) FROM quiz_sessions) as participant_count
              FROM quiz_sets
             WHERE user_id = ?
             ORDER BY created_at DESC
        """, (user_id,)) as cur:
            rows = await cur.fetchall()
            cols = [c[0] for c in cur.description]
            result = []
            for row in rows:
                d = dict(zip(cols, row))
                # Savol sonini hisoblash
                if d.get("questions"):
                    d["question_count"] = len(json.loads(d["questions"]))
                else:
                    d["question_count"] = 0
                result.append(d)
            return result


async def get_quiz_set(set_id: int) -> Optional[Dict]:
    """Bitta quiz to'plamni olish"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM quiz_sets WHERE id = ?", (set_id,)) as cur:
            row = await cur.fetchone()
            if row:
                data = dict(zip([c[0] for c in cur.description], row))
                data["questions"] = json.loads(data["questions"])
                return data
    return None


async def get_quiz_set_by_name(user_id: int, name: str) -> Optional[Dict]:
    """Nom bo'yicha quiz to'plamni topish"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM quiz_sets WHERE user_id = ? AND name = ?", (user_id, name)
        ) as cur:
            row = await cur.fetchone()
            if row:
                data = dict(zip([c[0] for c in cur.description], row))
                data["questions"] = json.loads(data["questions"])
                return data
    return None


async def increment_set_use_count(set_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE quiz_sets SET use_count = use_count + 1 WHERE id = ?", (set_id,)
        )
        await db.commit()


async def delete_quiz_set(set_id: int, user_id: int) -> bool:
    """Quiz to'plamni o'chirish"""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM quiz_sets WHERE id = ? AND user_id = ?", (set_id, user_id)
        )
        await db.execute("DELETE FROM quiz_parts WHERE set_id = ?", (set_id,))
        await db.commit()
        return cur.rowcount > 0


# ──────────────────────────────────────────────────────────
#  Quiz bo'laklari (split)
# ──────────────────────────────────────────────────────────
async def save_quiz_parts(set_id: int, parts: List[Dict]) -> bool:
    """
    Quiz to'plamini bo'laklarga bo'lib saqlash.
    parts = [{"name": "biologiya 1-40", "questions": [...], "time_limit": 30}, ...]
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Oldingi bo'laklarni o'chirish
        await db.execute("DELETE FROM quiz_parts WHERE set_id = ?", (set_id,))
        for part in parts:
            qs_json = json.dumps(part["questions"], ensure_ascii=False)
            await db.execute("""
                INSERT INTO quiz_parts (set_id, part_name, questions, time_limit)
                VALUES (?, ?, ?, ?)
            """, (set_id, part["name"], qs_json, part.get("time_limit", 30)))
        await db.commit()
        return True


async def get_quiz_parts(set_id: int) -> List[Dict]:
    """Quiz to'plamning barcha bo'laklari"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM quiz_parts WHERE set_id = ? ORDER BY id", (set_id,)
        ) as cur:
            rows = await cur.fetchall()
            cols = [c[0] for c in cur.description]
            result = []
            for row in rows:
                d = dict(zip(cols, row))
                d["questions"] = json.loads(d["questions"])
                result.append(d)
            return result


async def get_quiz_part_by_name(set_id: int, part_name: str) -> Optional[Dict]:
    """Nom bo'yicha bo'lakni topish"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM quiz_parts WHERE set_id = ? AND part_name = ?", (set_id, part_name)
        ) as cur:
            row = await cur.fetchone()
            if row:
                d = dict(zip([c[0] for c in cur.description], row))
                d["questions"] = json.loads(d["questions"])
                return d
    return None


async def get_quiz_part_by_id(part_id: int) -> Optional[Dict]:
    """ID bo'yicha bo'lakni topish"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM quiz_parts WHERE id = ?", (part_id,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                d = dict(zip([c[0] for c in cur.description], row))
                d["questions"] = json.loads(d["questions"])
                return d
    return None


async def delete_quiz_part(part_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM quiz_parts WHERE id = ?", (part_id,))
        await db.commit()
        return cur.rowcount > 0


# ──────────────────────────────────────────────────────────
#  Statistika
# ──────────────────────────────────────────────────────────
async def get_stats() -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async def scalar(sql):
            async with db.execute(sql) as cur:
                row = await cur.fetchone()
                return row[0] if row else 0

        return {
            "today_active":  await scalar(
                "SELECT COUNT(*) FROM users WHERE date(last_active) = date('now','localtime')"
            ),
            "today_new":     await scalar(
                "SELECT COUNT(*) FROM users WHERE date(created_at) = date('now','localtime')"
            ),
            "month_active":  await scalar(
                "SELECT COUNT(*) FROM users "
                "WHERE strftime('%Y-%m', last_active) = strftime('%Y-%m', 'now','localtime')"
            ),
            "total_users":   await scalar("SELECT COUNT(*) FROM users"),
            "active_subs":   await scalar(
                "SELECT COUNT(*) FROM subscriptions "
                "WHERE expires_at > datetime('now','localtime')"
            ),
            "month_revenue": await scalar(
                "SELECT COALESCE(SUM(amount),0) FROM payments "
                "WHERE status='approved' "
                "AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now','localtime')"
            ),
            "total_revenue": await scalar(
                "SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='approved'"
            ),
            "pending_count": await scalar(
                "SELECT COUNT(*) FROM payments WHERE status='pending_review'"
            ),
            "total_referrals": await scalar("SELECT COUNT(*) FROM referrals"),
        }
