import sqlite3

db_path = "quiz_bot.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT telegram_id, username, full_name, last_active FROM users ORDER BY last_active DESC LIMIT 1")
row = cur.fetchone()
print(row)
conn.close()
