import sqlite3, os, hashlib, secrets, datetime
import config

def conn():
    c=sqlite3.connect(config.DB_PATH)
    c.row_factory=sqlite3.Row
    return c

def init_db():
    c=conn(); x=c.cursor()
    x.execute("""CREATE TABLE IF NOT EXISTS access_keys(
      id INTEGER PRIMARY KEY AUTOINCREMENT, key_hash TEXT UNIQUE NOT NULL,
      key_hint TEXT NOT NULL, max_uses INTEGER NOT NULL DEFAULT 1, used_count INTEGER NOT NULL DEFAULT 0,
      premium_enabled INTEGER NOT NULL DEFAULT 0, premium_user_limit INTEGER,
      premium_revenue_limit INTEGER, premium_days INTEGER,
      created_by INTEGER NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'ACTIVE'
    )""")
    x.execute("""CREATE TABLE IF NOT EXISTS bots(
      id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER NOT NULL,
      bot_user_id INTEGER, bot_username TEXT, bot_token_enc TEXT NOT NULL,
      access_key_id INTEGER NOT NULL, admin_id INTEGER NOT NULL,
      premium_key TEXT, premium_user_limit INTEGER, premium_revenue_limit INTEGER, premium_days INTEGER,
      instance_path TEXT NOT NULL, pid INTEGER, status TEXT DEFAULT 'RUNNING',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP, revoked_at TEXT
    )""")
    c.commit(); c.close()

def _hash(s): return hashlib.sha256(s.encode()).hexdigest()

def make_access_key(created_by, max_uses, p_user=None, p_rev=None, p_days=None):
    raw="PX9V-ACCESS-"+secrets.token_urlsafe(22).upper().replace("-","_")
    c=conn(); c.execute("""INSERT INTO access_keys
      (key_hash,key_hint,max_uses,premium_enabled,premium_user_limit,premium_revenue_limit,premium_days,created_by)
      VALUES(?,?,?,?,?,?,?,?)""",(_hash(raw),raw[-8:],int(max_uses),int(p_user is not None),p_user,p_rev,p_days,int(created_by)))
    c.commit(); c.close(); return raw

def get_key(raw):
    c=conn(); r=c.execute("SELECT * FROM access_keys WHERE key_hash=?",(_hash(raw.strip()),)).fetchone(); c.close(); return r

def consume_key(raw):
    c=conn()
    r=c.execute("SELECT * FROM access_keys WHERE key_hash=?",(_hash(raw.strip()),)).fetchone()
    if not r: c.close(); return False,"INVALID",None
    if r["status"]!="ACTIVE": c.close(); return False,"REVOKED",r
    if r["used_count"]>=r["max_uses"]: c.close(); return False,"USED",r
    cur=c.execute("UPDATE access_keys SET used_count=used_count+1 WHERE id=? AND used_count<max_uses",(r["id"],))
    ok=cur.rowcount==1; c.commit()
    r=c.execute("SELECT * FROM access_keys WHERE id=?",(r["id"],)).fetchone(); c.close()
    return ok,"OK" if ok else "USED",r


def release_key(raw):
    c=conn(); c.execute("UPDATE access_keys SET used_count=CASE WHEN used_count>0 THEN used_count-1 ELSE 0 END WHERE key_hash=? AND status='ACTIVE'",(_hash(raw.strip()),)); c.commit(); c.close()

def list_bots(owner_id=None):
    c=conn()
    if owner_id is None: rows=c.execute("SELECT * FROM bots ORDER BY id DESC").fetchall()
    else: rows=c.execute("SELECT * FROM bots WHERE owner_id=? ORDER BY id DESC",(int(owner_id),)).fetchall()
    c.close(); return rows

def add_bot(data):
    c=conn()
    cur=c.execute("""INSERT INTO bots(owner_id,bot_user_id,bot_username,bot_token_enc,access_key_id,admin_id,premium_key,premium_user_limit,premium_revenue_limit,premium_days,instance_path,pid,status)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",data)
    c.commit(); bid=cur.lastrowid; c.close(); return bid

def get_bot_by_id(bid):
    c=conn(); r=c.execute("SELECT * FROM bots WHERE id=?",(int(bid),)).fetchone(); c.close(); return r

def find_bot(value):
    value=value.strip().lstrip("@")
    c=conn()
    if value.isdigit(): r=c.execute("SELECT * FROM bots WHERE id=? OR bot_user_id=?",(int(value),int(value))).fetchone()
    else: r=c.execute("SELECT * FROM bots WHERE lower(bot_username)=lower(?)",(value,)).fetchone()
    c.close(); return r

def revoke_bot(bid):
    c=conn(); cur=c.execute("UPDATE bots SET status='REVOKED',revoked_at=CURRENT_TIMESTAMP WHERE id=? AND status!='REVOKED'",(int(bid),)); ok=cur.rowcount==1; c.commit(); c.close(); return ok
