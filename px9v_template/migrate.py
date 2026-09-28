import sqlite3
from config import DB_NAME

# Database connect kar rahe hain
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# Sabhi users ko wapas 'live' (1) set kar rahe hain
# Agar aapke table ka naam ya column ka naam alag hai, to yahan update kar lein.
# (Assume kar raha hu table ka naam 'user_status' ya 'users' hai. Agar 'users' hai to "UPDATE users SET is_live = 1 WHERE is_live = 0" use karein)
try:
    cursor.execute("UPDATE users SET is_live = 1 WHERE is_live = 0")
except sqlite3.OperationalError:
    # Fallback in case the table is named differently in your schema
    cursor.execute("UPDATE user_status SET is_live = 1 WHERE is_live = 0")

conn.commit()
conn.close()

print("✅ Migration Complete: All users are revived and ready for broadcast.")
