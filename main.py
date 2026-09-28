from telegram.ext import ApplicationBuilder,CommandHandler,CallbackQueryHandler,MessageHandler,filters
import asyncio, threading, provisioner
import config,database as db,handlers

def main():
    if not config.BOT_TOKEN: raise SystemExit("LANDING_BOT_TOKEN is missing")
    if not config.ADMIN_ID: raise SystemExit("LANDING_ADMIN_ID is missing")
    db.init_db()
    provisioner.resume_running()
    threading.Thread(target=provisioner.monitor_running,daemon=True).start()
    app=ApplicationBuilder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",handlers.start))
    app.add_handler(CommandHandler("admin",handlers.admin))
    app.add_handler(CommandHandler("create_token",handlers.create_token_cmd))
    app.add_handler(CommandHandler("bots",handlers.bots_cmd))
    app.add_handler(CommandHandler("revoke",handlers.revoke))
    app.add_handler(CommandHandler("help",handlers.help_cmd))
    app.add_handler(CallbackQueryHandler(handlers.buy,pattern="^buy$"))
    app.add_handler(CallbackQueryHandler(handlers.mybots,pattern="^mybots$"))
    app.add_handler(CallbackQueryHandler(handlers.revoke_help,pattern="^revoke_help$"))
    app.add_handler(CallbackQueryHandler(handlers.admin_cb,pattern="^a_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handlers.text_input))
    # Admin input is handled by the same text handler.
    print("Landing bot running...")
    app.run_polling()
if __name__=="__main__": main()
