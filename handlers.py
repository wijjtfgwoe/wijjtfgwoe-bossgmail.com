from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import config, database as db, provisioner
import os, asyncio

states={}

def is_admin(uid): return int(uid)==config.ADMIN_ID

async def start(update, context):
    u=update.effective_user
    kb=[[InlineKeyboardButton("🤖 BUY NEW BOT",callback_data="buy")],
        [InlineKeyboardButton("📦 MY BOTS",callback_data="mybots")],
        [InlineKeyboardButton("❌ REVOKE BOT",callback_data="revoke_help")]]
    await update.message.reply_text(
        f"✨ <b>PX9V BOT STORE</b>\n\nWelcome <b>{u.first_name}</b>!\n\n"
        "Create your own PX9V bot using an access key. Your bot token and admin ID are collected securely during setup.\n\n"
        "Choose an option below.",
        parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb))

async def buy(update,context):
    q=update.callback_query; await q.answer()
    states[q.from_user.id]={"step":"access"}
    await q.message.reply_text("🔐 <b>CREATE KEY</b>\n\nSend your <b>access key</b> to start bot creation.",parse_mode="HTML")

async def mybots(update,context):
    q=update.callback_query; await q.answer()
    rows=db.list_bots(q.from_user.id)
    if not rows: await q.message.reply_text("No bots found."); return
    lines=["📦 <b>YOUR BOTS</b>"]
    for r in rows:
        lines.append(f"\n• #{r['id']} — @{r['bot_username']}\n  Status: <b>{r['status']}</b>")
    await q.message.reply_text("\n".join(lines),parse_mode="HTML")

async def revoke_help(update,context):
    q=update.callback_query; await q.answer()
    await q.message.reply_text("Use:\n<code>/revoke @botusername</code>\nor\n<code>/revoke ACCESS_KEY</code>",parse_mode="HTML")

async def text_input(update,context):
    uid=update.effective_user.id
    st=states.get(uid)
    if st and is_admin(uid) and st.get("step","").startswith("ak_"):
        return await admin_text(update,context)
    if not st: return
    val=update.message.text.strip()
    if st["step"]=="access":
        row=db.get_key(val)
        if not row:
            await update.message.reply_text("❌ Invalid access key."); return
        if row["status"]!="ACTIVE":
            await update.message.reply_text("🔒 This access key is revoked."); return
        if row["used_count"]>=row["max_uses"]:
            await update.message.reply_text("⚠️ This access key has reached its usage limit."); return
        st.update({"step":"token","key":row,"access_raw":val})
        await update.message.reply_text("🤖 <b>Send your bot Access Token</b>\n\nGet it from @BotFather.",parse_mode="HTML"); return
    if st["step"]=="token":
        me=provisioner.validate_token(val)
        if not me:
            await update.message.reply_text("❌ Invalid bot token. Send a valid token from @BotFather."); return
        st.update({"step":"admin","token":val,"me":me})
        await update.message.reply_text("👤 <b>Send your Admin ID</b>\n\nThis ID will become the Permanent Admin of the new PX9V bot.",parse_mode="HTML"); return
    if st["step"]=="admin":
        try: admin_id=int(val)
        except:
            await update.message.reply_text("❌ Admin ID must be a numeric Telegram user ID."); return
        key=st["key"]
        await update.message.reply_text("⚙️ Creating your PX9V bot...\n\nPlease wait.")
        try:
            # Reserve one activation immediately before provisioning.
            ok,reason,live_key=db.consume_key(st["access_raw"])
            if not ok:
                raise RuntimeError({"INVALID":"Access key is invalid.","REVOKED":"Access key was revoked.","USED":"Access key usage limit reached."}.get(reason,"Access denied."))
            bid,username,premium=await asyncio.to_thread(provisioner.provision,uid,admin_id,st["token"],live_key)
            states.pop(uid,None)
            msg=f"✅ <b>BOT CREATED SUCCESSFULLY</b>\n\n🤖 Bot: @{username}\n🆔 Bot ID: <code>{bid}</code>\n👤 Admin ID: <code>{admin_id}</code>\n\nYour PX9V bot is now running."
            if premium:
                msg+=f"\n\n💎 <b>PREMIUM TOKEN</b>\n<code>{premium}</code>\n\nUse /premiumkey in your new bot to activate it."
            await update.message.reply_text(msg,parse_mode="HTML")
        except Exception as e:
            # A failed provisioning attempt should not consume the customer's access slot.
            try: db.release_key(st["access_raw"])
            except Exception: pass
            states.pop(uid,None)
            await update.message.reply_text(f"❌ <b>Creation failed</b>\n\n<code>{str(e)[:900]}</code>",parse_mode="HTML")

async def revoke(update,context):
    uid=update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /revoke [access token or bot username]"); return
    value=" ".join(context.args).strip()
    row=db.find_bot(value)
    if row:
        if not is_admin(uid) and row["owner_id"]!=uid:
            await update.message.reply_text("❌ You can revoke only your own bot."); return
    else:
        # Access-key revocation: revoke every active bot tied to this key.
        key=db.get_key(value)
        if not key:
            await update.message.reply_text("❌ Bot/access key not found."); return
        if not is_admin(uid) and key["created_by"]!=uid:
            await update.message.reply_text("❌ You cannot revoke this key."); return
        rows=db.list_bots()
        rows=[r for r in rows if r["access_key_id"]==key["id"] and r["status"]!="REVOKED"]
        if not rows:
            # Still revoke the access key itself so it cannot create future bots.
            c=db.conn(); c.execute("UPDATE access_keys SET status='REVOKED' WHERE id=?",(key["id"],)); c.commit(); c.close()
            await update.message.reply_text("✅ Access key revoked. No active bot was linked to it."); return
        c=db.conn(); c.execute("UPDATE access_keys SET status='REVOKED' WHERE id=?",(key["id"],)); c.commit(); c.close()
        for r in rows:
            provisioner.stop_bot(r)
        await update.message.reply_text(f"✅ Access key revoked and {len(rows)} linked bot(s) stopped.")
        return
    provisioner.stop_bot(row)
    await update.message.reply_text(f"✅ Bot @{row['bot_username']} has been revoked and removed.")

async def admin(update,context):
    if not is_admin(update.effective_user.id): return
    kb=[[InlineKeyboardButton("🔑 CREATE TOKEN",callback_data="a_create")],
        [InlineKeyboardButton("📊 BOT STATISTICS",callback_data="a_stats")],
        [InlineKeyboardButton("🤖 ACTIVE BOTS",callback_data="a_bots")]]
    await update.message.reply_text("🛠 <b>LANDING ADMIN PANEL</b>\n\nManage access keys and customer bot instances.",parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb))

async def create_token_cmd(update,context):
    if not is_admin(update.effective_user.id): return
    states[update.effective_user.id]={"step":"ak_uses"}
    await update.message.reply_text("🔑 CREATE ACCESS TOKEN\n\nHow many bots can this key create? Example: 1")

async def bots_cmd(update,context):
    if not is_admin(update.effective_user.id): return
    rows=db.list_bots()
    text="🤖 ACTIVE/REVOKED BOTS\n\n"+("\n".join(f"#{r['id']} @{r['bot_username']} — {r['status']}" for r in rows[:100]) or "No bots.")
    await update.message.reply_text(text)

async def admin_cb(update,context):
    q=update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    if q.data=="a_create":
        states[q.from_user.id]={"step":"ak_uses"}
        await q.message.reply_text("🔑 <b>CREATE ACCESS TOKEN</b>\n\nHow many bots can this key create?\n\nExample: <code>1</code>",parse_mode="HTML")
    elif q.data=="a_stats":
        rows=db.list_bots()
        active=sum(r["status"]=="RUNNING" for r in rows)
        await q.message.reply_text(f"📊 <b>STATISTICS</b>\n\nTotal bots: <b>{len(rows)}</b>\nRunning: <b>{active}</b>\nRevoked: <b>{len(rows)-active}</b>",parse_mode="HTML")
    elif q.data=="a_bots":
        rows=db.list_bots()
        text="🤖 <b>BOT LIST</b>\n\n" + ("\n".join(f"#{r['id']} @{r['bot_username']} — {r['status']}" for r in rows[:50]) or "No bots.")
        await q.message.reply_text(text,parse_mode="HTML")

async def admin_text(update,context):
    uid=update.effective_user.id
    if not is_admin(uid): return
    st=states.get(uid)
    if not st or not st.get("step","").startswith("ak_"): return
    val=update.message.text.strip()
    step=st["step"]
    if step=="ak_uses":
        try: n=int(val); assert n>0
        except: await update.message.reply_text("Enter a positive number."); return
        st["uses"]=n; st["step"]="ak_premium"
        await update.message.reply_text("💎 Include a premium token after each bot is created?\nSend <code>YES</code> or <code>NO</code>.",parse_mode="HTML"); return
    if step=="ak_premium":
        if val.upper() not in ("YES","NO"): await update.message.reply_text("Send YES or NO."); return
        st["premium"]=val.upper()=="YES"
        if not st["premium"]:
            raw=db.make_access_key(uid,st["uses"])
            states.pop(uid,None)
            await update.message.reply_text(f"✅ <b>ACCESS TOKEN CREATED</b>\n\n<code>{raw}</code>\n\nUses: <b>{st['uses']}</b>",parse_mode="HTML"); return
        st["step"]="ak_puser"; await update.message.reply_text("Premium USER limit (number of end users):"); return
    if step=="ak_puser":
        try: n=int(val); assert n>0
        except: await update.message.reply_text("Enter a positive number."); return
        st["puser"]=n; st["step"]="ak_prev"; await update.message.reply_text("Premium REVENUE limit:"); return
    if step=="ak_prev":
        try: n=int(val); assert n>=0
        except: await update.message.reply_text("Enter 0 or a positive number."); return
        st["prev"]=n; st["step"]="ak_pdays"; await update.message.reply_text("Premium TIME in days:"); return
    if step=="ak_pdays":
        try: n=int(val); assert n>0
        except: await update.message.reply_text("Enter a positive number of days."); return
        raw=db.make_access_key(uid,st["uses"],st["puser"],st["prev"],n)
        states.pop(uid,None)
        await update.message.reply_text(
          f"✅ <b>ACCESS TOKEN CREATED</b>\n\n<code>{raw}</code>\n\n"
          f"Bot uses: <b>{st['uses']}</b>\nPremium user limit: <b>{st['puser']}</b>\nPremium revenue limit: <b>{st['prev']}</b>\nPremium time: <b>{n} days</b>",
          parse_mode="HTML")

async def help_cmd(update,context):
    await update.message.reply_text("/start — Store\n/revoke [access token or @bot] — revoke a bot\n/admin — admin panel")
