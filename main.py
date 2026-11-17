import os
import glob
import importlib
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============ CONFIGURATION ============
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHECKERS_FOLDER = "checkers"

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found! Set it in Heroku Config Vars or .env file.")
# =======================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

loaded_checkers = {}

def load_checkers():
    """Yeh function automatically checkers folder se saari .py files utha lega"""
    checkers = {}
    for filepath in glob.glob(f"{CHECKERS_FOLDER}/*.py"):
        filename = os.path.basename(filepath)
        if filename == "__init__.py":
            continue
            
        module_name = filename[:-3]
        try:
            module = importlib.import_module(f"{CHECKERS_FOLDER}.{module_name}")
            if hasattr(module, "Checker"):
                checker_instance = module.Checker()
                if hasattr(checker_instance, "command") and hasattr(checker_instance, "name"):
                    checkers[checker_instance.command] = checker_instance
                    print(f"✅ Loaded: /{checker_instance.command} -> {checker_instance.name}")
        except Exception as e:
            print(f"❌ Error loading {filename}: {e}")
    return checkers

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start message jo saare available commands dikhayega"""
    message = "🤖 <b>Welcome to Multi-Checker Bot!</b>\n\n📋 <b>Available Commands:</b>\n\n"
    
    for cmd, checker in loaded_checkers.items():
        message += f"➡️ /{cmd} - <b>{checker.name}</b>\n"
    
    message += "\n💡 <b>Kaise use karein:</b>\n"
    message += "1. Upar diye gaye kisi bhi command ko type karein (e.g., <code>/stkida</code> ya <code>/olive</code>).\n"
    message += "2. Bot file mangega, aap apna <code>.txt</code> combo file bhej dein.\n"
    message += "3. Beech mein rokna ho toh <code>/stop</code> type karein."
    
    await update.message.reply_text(message, parse_mode="HTML")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kisi bhi chalte hue checker ko rokne ke liye"""
    is_running = any(context.user_data.get(f'stats_{cmd}') for cmd in loaded_checkers.keys())
    
    if is_running:
        context.user_data['stop_checking'] = True
        await update.message.reply_text("🛑 <b>Stop Command Received!</b>\nCurrent checking process ko safely roka ja raha hai...", parse_mode="HTML")
    else:
        await update.message.reply_text("ℹ️ Koi checking process currently run nahi ho raha hai.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jab user .txt file bhejega"""
    awaiting = context.user_data.get('awaiting_file_for')
    
    if awaiting and awaiting in loaded_checkers:
        await loaded_checkers[awaiting].handle_document(update, context)
    else:
        await update.message.reply_text("❌ Pehle koi checker command (jaise <code>/stkida</code> ya <code>/olive</code>) type karo, fir file bhejo.", parse_mode="HTML")

def main():
    print("\n🚀 Bot Starting...\n")
    global loaded_checkers
    loaded_checkers = load_checkers()
    print(f"✅ Total {len(loaded_checkers)} checkers loaded.\n")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    
    # Saare loaded checkers ke commands auto-register honge
    for cmd, checker in loaded_checkers.items():
        app.add_handler(CommandHandler(cmd, checker.handle_command))
        
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    print("🤖 Bot is running... Press Ctrl+C to stop.\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
