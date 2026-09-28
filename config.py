import os
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN=os.getenv("LANDING_BOT_TOKEN","").strip()
ADMIN_ID=int(os.getenv("LANDING_ADMIN_ID","0") or 0)
DB_PATH=os.getenv("LANDING_DB_PATH","landing_bot.db")
INSTANCE_ROOT=os.getenv("INSTANCE_ROOT","instances")
TEMPLATE_ROOT=os.getenv("TEMPLATE_ROOT","px9v_template")
MASTER_INSTANCE_KEY=os.getenv("MASTER_INSTANCE_KEY","CHANGE_THIS_TO_A_LONG_RANDOM_SECRET")
REVOKE_DELETE_FILES=os.getenv("REVOKE_DELETE_FILES","true").lower() in ("1","true","yes")
