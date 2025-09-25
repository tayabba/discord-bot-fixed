import threading
import time
from datetime import datetime, UTC
import tls_client

from core.state import DiscordAPI, CaptchaSolver, TokenKeepAlive
from core.token_manager import token_manager
from core.log import Logger

from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from colorama import Fore
import base64
import os
import random
import yaml
import uuid
import requests
import re
import json

try:
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
        SETTINGS = config.get('SETTINGS', {
            "enable_proxy": True,
            "max_boost_retries": 3,
            "proxy_format": "http://username:password@host:port",
            "keep_online": True,
            "enable_captcha": False,
            "captcha_api_key": "f9434194-3844-481e-a30b-1dd442aaebe9",
        })
        WATERMARK = config.get('WATERMARK', {
            "default_bio": "**https://discord.gg/quickboost**",
            "default_nickname": "Quick Boosts",
            "enable_avatar": False,
            "enable_banner": False,
            "enable_bio": True,
            "enable_nickname": True,
            "enable_watermark": True
        })
except Exception as e:
    Logger.error(f"Failed To Load Config.Yaml | Error : {str(e)}")
    SETTINGS = {
        "enable_proxy": True,
        "max_boost_retries": 3,
        "max_threads": 15,
        "proxy_format": "http://username:password@host:port",
        "keep_online": True,
        "enable_captcha": False,
        "captcha_api_key": "f9434194-3844-481e-a30b-1dd442aaebe9",
    }
    WATERMARK = {
        "default_bio": "**https://discord.gg/quickboost**",
        "default_nickname": "Quick Boosts",
        "enable_avatar": False,
        "enable_banner": False,
        "enable_bio": True,
        "enable_nickname": True,
        "enable_watermark": True
    }

MAX_RETRIES = SETTINGS.get('max_boost_retries', 3)
token_keeper = TokenKeepAlive() if SETTINGS.get('keep_online', True) else None
def image_to_b64(image_source):
    try:
        if os.path.exists(image_source) and image_source.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            with open(image_source, 'rb') as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')
                ext = os.path.splitext(image_source)[1].lower()
                mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif'}.get(ext[1:], 'image/png')
                return f"data:{mime};base64,{encoded}"
        
        elif isinstance(image_source, str) and "imgur.com" in image_source.lower():
            try:
                if "/a/" in image_source:
                    image_id = image_source.split("/a/")[1].split("?")[0].split("#")[0]
                else:
                    image_id = image_source.split("imgur.com/")[1].split("?")[0].split("#")[0]
            except:
                return None
            
            req_session = requests.Session()
            req_session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            formats = ['jpg', 'png', 'gif', 'jpeg']
            retry_delay = 2
            
            for attempt in range(3):
                for fmt in formats:
                    try:
                        direct_url = f'https://i.imgur.com/{image_id}.{fmt}'
                        response = req_session.get(direct_url, timeout=10)
                        
                        if response.status_code == 429:
                            time.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                            
                        if response.status_code == 200:
                            base64_data = base64.b64encode(response.content).decode('utf-8')
                            return f"data:image/{fmt};base64,{base64_data}"
                    except:
                        continue
                
                if attempt < 2:
                    time.sleep(retry_delay)
                    retry_delay *= 2
            
            try:
                page_url = f'https://imgur.com/{image_id}'
                response = req_session.get(page_url)
                if response.status_code == 200:
                    match = re.search(r'<link rel="image_src"\s+href="([^"]+)"', response.text)
                    if match:
                        image_url = match.group(1)
                        response = req_session.get(image_url)
                        if response.status_code == 200:
                            base64_data = base64.b64encode(response.content).decode('utf-8')
                            return f"data:image/jpeg;base64,{base64_data}"
            except:
                pass
        
        elif isinstance(image_source, str) and (image_source.startswith(('http://', 'https://')) and 
                                              ("discord" in image_source.lower() or
                                               any(ext in image_source.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif']))):
            try:
                req_session = requests.Session()
                response = req_session.get(image_source, timeout=10)
                if response.status_code == 200:
                    ext = image_source.split('.')[-1].lower() if '.' in image_source else 'png'
                    mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif'}.get(ext, 'image/png')
                    base64_data = base64.b64encode(response.content).decode('utf-8')
                    return f"data:{mime};base64,{base64_data}"
            except:
                pass
                
        return None
    except:
        return None

def get_random_image(directory):
    try:
        if not os.path.exists(directory):
            return None
        files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f)) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        return image_to_b64(os.path.join(directory, random.choice(files))) if files else None
    except:
        return None

def load_proxies() -> List[str]:
    if not SETTINGS.get('enable_proxy', True):
        return []
    try:
        with open('data/proxies.txt', 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        proxy_format = SETTINGS.get('proxy_format', '')
        if proxy_format.startswith('http://'):
            return proxies
        else:
            return [f"http://{proxy}" if not proxy.startswith('http') else proxy for proxy in proxies]
    except FileNotFoundError:
        Logger.error("Proxies.txt Not Found")
        return []
    except Exception as e:
        Logger.error(f"Failed To Load Proxies | Error : {str(e)}")
        return []
    
class BoostClass:
    def __init__(self, order_id: str = None):
        self.discord = DiscordAPI()
        self.solver = None
        self.using_existing_tokens = False
        self.existing_tokens = []  
        self.order_id = order_id or str(uuid.uuid4())[:8]
        self.results = {
            "success": False,
            "total_boosts": 0,
            "expected_boosts": 0,
            "tokens": {},
            "message": "",
            "start_time": None,
            "end_time": None,
            "all_tokens": [],
            "success_tokens": [],
            "failed_tokens": [],
            "captcha_tokens": [],
            "invalid_tokens": [],
            "no_slots_tokens": [],
            "order_id": self.order_id,
            "request": {
                "invite": "",
                "guild_id": "",
                "amount": 0,
                "months": 0,
                "customization": None
            }
        }
        self.state_lock = threading.Lock()
        self.token_lock = threading.Lock()
        self.task_locks = {}
        self.session_locks = {}
        self.remaining_boosts = 0
        self.months = 1
        self.proxies = load_proxies() if SETTINGS.get('enable_proxy', True) else []
        self.proxy = None
        self.useragent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        self.customization = None
        self.raw_proxy = None
        self.thread_stats = {}


    def apply_customization(self, session: Any, guild_id: str, token: str) -> bool:
        if not self.customization and not WATERMARK.get('enable_watermark'): 
            return True
            
        identity = f"{self.order_id}:{token}"
        
        session.headers.update({
            "authority": "discord.com",
            "accept": "*/*",
            "accept-language": "fr-FR,fr;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/json",
            "origin": "https://discord.com",
            "pragma": "no-cache",
            "referer": "https://discord.com/channels/@me",
            "sec-ch-ua": '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin"
        })
        
        try:
            if WATERMARK.get('enable_nickname') or (self.customization and 'nickname' in self.customization):
                nickname = self.customization.get('nickname') if self.customization else WATERMARK.get('default_nickname')
                if nickname:
                    session.patch(f"https://discord.com/api/v9/guilds/{guild_id}/members/@me", json={"nick": nickname})

            if WATERMARK.get('enable_bio') or (self.customization and 'bio' in self.customization):
                bio = self.customization.get('bio') if self.customization else WATERMARK.get('default_bio')
                if bio:
                    session.patch("https://discord.com/api/v9/users/@me/profile", json={"bio": bio})

            if self.customization and 'pronouns' in self.customization:
                session.patch("https://discord.com/api/v9/users/@me", json={"pronouns": self.customization['pronouns']})


            if WATERMARK.get('enable_avatar') or (self.customization and 'avatar' in self.customization):
                avatar_data = None
                if self.customization and isinstance(self.customization.get('avatar'), str):
                    print(self.customization['avatar'])
                    avatar = self.customization['avatar']
                    avatar_data = image_to_b64(avatar)
                if not avatar_data:
                    avatar_data = get_random_image('data/avatars')
                if avatar_data:
                    session.patch(f"https://discord.com/api/v9/guilds/{guild_id}/members/@me", json={"avatar": avatar_data})

            if WATERMARK.get('enable_banner') or (self.customization and 'banner' in self.customization):
                banner_data = None
                if self.customization and isinstance(self.customization.get('banner'), str):
                    banner = self.customization['banner']
                    banner_data = image_to_b64(banner)
                if not banner_data:
                    banner_data = get_random_image('data/banners')
                if banner_data:
                    session.patch(f"https://discord.com/api/v9/guilds/{guild_id}/members/@me", json={"banner": banner_data})
                    
            Logger.debug("WaterMark Applied Successfully", identity)
            return True
        
        except Exception as e:
            Logger.error(f"WaterMark Failed | Error : {str(e)}", identity)
            return False
        
    def check_boost_slots(self, session, identity: str) -> tuple:
        try:
            resp = session.get("https://discord.com/api/v9/users/@me/guilds/premium/subscription-slots")
            if resp.status_code != 200:
                Logger.error(f"Failed To Check Slot's | Error : {resp.status_code} | {resp.text}", identity)
                return False, 0, f"Failed to get slots: {resp.status_code}"
                
            slots = resp.json()
            available_slots = []
            current_time = datetime.now(UTC).isoformat() + "Z"
            
            for slot in slots:
                cooldown = slot.get("cooldown_ends_at")
                premium_sub = slot.get("premium_guild_subscription")
                
                if (cooldown and cooldown < current_time) or (not premium_sub and not slot.get("canceled")):
                    available_slots.append(slot)
                    
            return True, len(available_slots), available_slots
        except Exception as e:
            Logger.error(f"Failed To Check Slot's | Error : {str(e)}", identity)
            return False, 0, f"Slot Check Error: {str(e)}"
   
    def create_session(self, token: str, thread_id: int = None) -> tuple:
        identity = f"{self.order_id}:{token}"
        
        try:
            session = tls_client.Session(
                client_identifier="chrome_124",
                random_tls_extension_order=True
            )
            
            session_id = self.discord.get_session_id(token, self.useragent)
            if session_id == "Invalid token":
                self.handle_token_error(token, "invalid")
                Logger.error("Invalid Token | Removing", identity)
                return None, None, "Invalid Token"

            if SETTINGS.get('enable_proxy', True) and self.proxies:
                proxy = random.choice(self.proxies)
                try:
                    if '@' in proxy:
                        proxy_fmt = proxy if proxy.startswith('http://') else f"http://{proxy}"
                        session.proxies = {"http": proxy_fmt, "https": proxy_fmt}
                    else:
                        parts = proxy.split(':')
                        if len(parts) == 4:
                            formatted_proxy = f"{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
                            proxy_fmt = f"http://{formatted_proxy}"
                            session.proxies = {"http": proxy_fmt, "https": proxy_fmt}
                    self.raw_proxy = proxy.replace('http://', '')
                except Exception as e:
                    Logger.error(f"Proxy Error: {str(e)} | Continuing without proxy", identity)
                    session.proxies = None
                    self.raw_proxy = None

            headers = self.discord.make_headers(token=token, ua=self.useragent, force_new=True)
            session.headers.update(headers)
            
            try:
                session.cookies.update(self.discord.grab_cookies(session))
            except Exception as e:
                Logger.error(f"Cookie grab failed: {e}", identity)

            ok, slot_count, slots = self.check_boost_slots(session, identity)
            if not ok:
                if "captcha" in str(slots).lower():
                    self.handle_token_error(token, "captcha")
                    return None, None, "Captcha required"
                return None, None, slots
                
            if slot_count == 0:
                self.handle_token_error(token, "no_slots")
                return None, None, "No boost slots available"
                
            session.slots = slots
            session.token = token
            
            if thread_id is not None:
                session.thread_id = thread_id

            return session, session_id, headers
        except Exception as e:
            Logger.error(f"Session creation failed: {str(e)}", identity)
            return None, None, f"Session error: {str(e)}"
    

    def handle_token_error(self, token: str, error_type: str):
        identity = f"{self.order_id}:{token}"
        with self.state_lock:
            if error_type == "captcha":
                self.results["captcha_tokens"].append(token)
            elif error_type == "invalid":
                self.results["invalid_tokens"].append(token)
            elif error_type == "no_slots":
                self.results["no_slots_tokens"].append(token)
                self.results["failed_tokens"].append(token)
                Logger.error("No Available Boost Slots | Removing Token", identity)
            if token not in self.results["failed_tokens"]:
                self.results["failed_tokens"].append(token)

    def boost_guild(self, session, guild_id: str, slot_id: str, identity: str) -> dict:
        try:
            response = session.put(
                f"https://discord.com/api/v9/guilds/{guild_id}/premium/subscriptions",
                json={"user_premium_guild_subscription_slot_ids": [slot_id]}
            )
            
            response_data = response.json() if response.text else {}
            
            if response.status_code == 201:
                Logger.debug(f"Successfully Boosted | Guild : {guild_id}", identity)
                return {"success": True, "status_code": response.status_code}
                
            elif response.status_code == 429:
                retry_after = response.headers.get('Retry-After', 5)
                Logger.warning(f"Rate Limited While Boosting {slot_id}, Retry after {retry_after}s", identity)
                return {"success": False, "status_code": 429, "retry_after": retry_after}
                
            else:
                error_msg = response_data.get('message', f"Failed with status {response.status_code}")
                Logger.error(f"Failed To Apply Boost | Error : {error_msg}", identity)
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": error_msg,
                    "response": response_data
                }
                
        except Exception as e:
            error_msg = str(e)
            Logger.error(f"Exception While Boosting | Error : {error_msg}", identity)
            return {
                "success": False,
                "status_code": 0,
                "error": error_msg
            }
        
        
    def join_guild(self, token_id: int, token: str, invite: str, session: Any, session_id: str) -> bool:
        identity = f"{self.order_id}:{token}"
        try:
            if not session.cookies:
                session.cookies.update(self.discord.grab_cookies(session))
            
            resp = session.post(f"https://discord.com/api/v9/invites/{invite}", json={'session_id': session_id})
            if resp.status_code == 200:
                Logger.debug(f"Successfully Joined Guild | {invite}", identity)
                return True
                    
            rep = resp.json()
            if "captcha_key" in rep or "captcha_sitekey" in rep:
                if not hasattr(self, 'solver') or not self.solver:
                    Logger.error("Captcha Detected | No API Key Found, Skipping", identity)
                    self.handle_token_error(token, "captcha")
                    return False
                
                if not self.raw_proxy:
                    Logger.error("Captcha Detected | No Proxy Initialized Skipping", identity)
                    self.handle_token_error(token, "captcha")
                    return False
                
                Logger.info("Captcha Detected | Solving..", identity)
                site_key = rep.get("captcha_sitekey")
                rqdata = rep.get("captcha_rqdata")
                rqtoken = rep.get("captcha_rqtoken")

                print("Site Key", site_key)
                print("Rqdata", rqdata)
                print("Rqtoken", rqtoken)
                solution = self.solver.solve(
                    site_key=site_key,
                    rqdata=rqdata,
                    website_url="discord.com",
                    proxy=self.raw_proxy,
                )
                        
                if not solution:
                    Logger.error("Failed To Get Captcha Solution", identity)
                    self.handle_token_error(token, "captcha")
                    return False
                
                Logger.debug("Captcha Solved Successfully | Solution Received", identity)
                
                # session.headers.update({
                #     "x-captcha-key": solution,
                #     "x-captcha-rqtoken": rqtoken
                # })
                
                retry = session.post(
                    f"https://discord.com/api/v9/invites/{invite}",
                    json={'captcha_key': solution, 'captcha_rqtoken': rqtoken}
                )
                
                if retry.status_code == 200:
                    Logger.success(f"Successfully Joined Guild | {invite} | After Captcha", identity)
                    return True
                
                error_msg = "Captcha validation failed"
                try:
                    error_data = retry.json()
                    error_msg = error_data.get('message', error_msg)
                except:
                    pass
                Logger.error(f"Join Retry Failed: {retry.status_code} | {error_msg}", identity)
                self.handle_token_error(token, "captcha")
                return False
                                
            if "captcha" in str(rep.get('message', '')).lower():
                self.handle_token_error(token, "captcha")
            Logger.error(f"Join Failure : {resp.status_code} | {rep.get('message', '')}", identity)
            return False
                    
        except Exception as e:
            Logger.error(f"Join Failure : {str(e)}", identity)
            return False
        


    def fetch_token(self) -> str:
        with self.token_lock:
            if self.using_existing_tokens and self.existing_tokens:
                return self.existing_tokens.pop(0)
                
            ok, token = token_manager.get_token(self.months)
            return token if ok else None
        
    def process_boost_task(self, task_data: Tuple) -> bool:
        class BoostThread:
            def __init__(self, parent, thread_id, guild_id, invite, boosts_to_do):
                self.parent = parent
                self.thread_id = thread_id
                self.guild_id = guild_id
                self.invite = invite
                self.boosts_to_do = boosts_to_do
                self.boosts_completed = 0
                self.tokens_tried = set()
                self.identity = f"{parent.order_id}:Thread-{thread_id}"
                self.retry_count = 0
                self.max_retries = 1 if parent.using_existing_tokens else MAX_RETRIES
                self.current_token = None
                self.current_session = None
                self.thread_lock = threading.Lock()

            def get_token_identity(self, token):
                return f"{self.identity}:{token[:25]}"
                    
            def execute(self):
                try:
                    while self.boosts_completed < self.boosts_to_do and self.retry_count < self.max_retries:
                        with self.thread_lock:
                            self.current_token = self.parent.fetch_token()
                        
                        if not self.current_token:
                            Logger.error(f"No More Tokens Available | Stopping Thread-{self.thread_id}", self.identity)
                            return False
                        
                        self.tokens_tried.add(self.current_token)
                        token_identity = self.get_token_identity(self.current_token)
                        
                        self.current_session, session_id, error = self.parent.create_session(self.current_token, self.thread_id)
                        if not self.current_session:
                            with self.parent.state_lock:
                                if self.current_token not in self.parent.results["failed_tokens"]:
                                    self.parent.results["failed_tokens"].append(self.current_token)
                            self.retry_count += 1
                            continue
                        
                        if not self.parent.join_guild(self.thread_id, self.current_token, self.invite, self.current_session, session_id):
                            with self.parent.state_lock:
                                if self.current_token not in self.parent.results["failed_tokens"]:
                                    self.parent.results["failed_tokens"].append(self.current_token)
                            self.retry_count += 1
                            continue
                        
                        slots = getattr(self.current_session, 'slots', [])
                        if not slots:
                            with self.parent.state_lock:
                                if self.current_token not in self.parent.results["failed_tokens"]:
                                    self.parent.results["failed_tokens"].append(self.current_token)
                            self.retry_count += 1
                            continue
                        
                        available_boosts = len(slots)
                        boosts_to_use = min(available_boosts, self.boosts_to_do - self.boosts_completed)
                        slot_success = 0
                        
                        for i in range(boosts_to_use):
                            slot = slots[i]
                            boost_result = self.parent.boost_guild(self.current_session, self.guild_id, slot["id"], token_identity)
                            
                            if boost_result["success"]:
                                slot_success += 1
                                with self.parent.state_lock:
                                    self.boosts_completed += 1
                                    self.parent.remaining_boosts -= 1
                                    self.parent.results["total_boosts"] += 1
                                    
                                    if self.current_token not in self.parent.results["success_tokens"]:
                                        self.parent.results["success_tokens"].append(self.current_token)
                            
                        if slot_success > 0:
                            self.parent.apply_customization(self.current_session, self.guild_id, self.current_token)
                            
                            if SETTINGS.get('keep_online', True) and token_keeper:
                                token_keeper.add_token(self.current_token)
                            self.retry_count = 0
                        else:
                            with self.parent.state_lock:
                                if self.current_token not in self.parent.results["failed_tokens"]:
                                    self.parent.results["failed_tokens"].append(self.current_token)
                            self.retry_count += 1
                        
                        remaining_slots = len(slots) - boosts_to_use
                        if remaining_slots > 0:
                            token_manager.return_token(self.current_token, self.parent.months, f"Remaining slots: {remaining_slots}")
                        
                        Logger.success(f"Thread {self.thread_id} Completed {self.boosts_completed}/{self.boosts_to_do} Boosts", self.identity)
                        with self.parent.state_lock:
                            self.parent.results["tokens"][self.thread_id] = {
                                "status": "success" if self.boosts_completed >= self.boosts_to_do else "partial",
                                "boosts": self.boosts_completed,
                                "tokens_used": len(self.tokens_tried)
                            }
                        
                        return self.boosts_completed >= self.boosts_to_do
                        
                    return self.boosts_completed >= self.boosts_to_do
                    
                except Exception as e:
                    Logger.error(f"Thread exception: {str(e)}", self.identity)
                    with self.parent.state_lock:
                        if self.current_token and self.current_token not in self.parent.results["failed_tokens"]:
                            self.parent.results["failed_tokens"].append(self.current_token)
                    return False

        thread = BoostThread(self, *task_data)
        return thread.execute()

    def start_boost(self, amount: int, invite: str, months: int, guild_id: str, custom_tokens: List[str] = None, customization: Dict = None) -> Dict:
        self.results["start_time"] = time.time()
        self.months = months
        self.results["request"].update({
            "amount": amount,
            "months": months,
            "invite": invite.split("/")[-1] if "/" in invite else invite,
            "guild_id": guild_id,
            "customization": customization
        })
        self.results["expected_boosts"] = amount
        self.remaining_boosts = amount
        self.customization = customization

        Logger.info(f"Boost Session Started | Request: {amount} Boosts", self.order_id)
        
        needed_tokens = (amount + 1) // 2
        
        if not self.existing_tokens and custom_tokens:
            self.using_existing_tokens = True
            self.existing_tokens = custom_tokens.copy()
            Logger.debug(f"Using Existing Tokens | {len(self.existing_tokens)} Tokens", self.order_id)
            
        tasks = []
        remaining_boosts = amount
        
        self.thread_stats = {
            "total_threads": needed_tokens,
            "completed_threads": 0,
            "successful_threads": 0,
            "failed_threads": 0
        }
        
        for i in range(needed_tokens):
            self.task_locks[i] = threading.Lock()
            self.session_locks[i] = threading.Lock()
        
        thread_id = 0
        while remaining_boosts > 0:
            boosts_for_thread = min(2, remaining_boosts)
            
            if boosts_for_thread > 0:
                tasks.append((thread_id, guild_id, self.results["request"]["invite"], boosts_for_thread))
                remaining_boosts -= boosts_for_thread
                thread_id += 1
        
        thread_count = min(len(tasks), 30)
        
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = []
            for task in tasks:
                futures.append(executor.submit(self.process_boost_task, task))
            
            for future in futures:
                success = future.result()
                with self.state_lock:
                    self.thread_stats["completed_threads"] += 1
                    if success:
                        self.thread_stats["successful_threads"] += 1
                    else:
                        self.thread_stats["failed_threads"] += 1
                
        Logger.debug(f"Thread Execution Complete: {self.thread_stats['successful_threads']}/{self.thread_stats['total_threads']} Threads Successful", self.order_id)
                
        if self.remaining_boosts > 0:
            return self.finalize_results(f"Failed to complete all boosts ({self.remaining_boosts} remaining)")
        return self.finalize_results()
    

    def finalize_results(self, message: str = None) -> Dict:
        self.results["end_time"] = time.time()
        duration = self.results["end_time"] - self.results["start_time"]
        if message:
            self.results["message"] = message
            Logger.error(f"Failed: {message}", self.order_id)
        else:
            self.results["success"] = self.results["total_boosts"] >= self.results["expected_boosts"]
            status = "success" if self.results["success"] else "error"
            self.results["message"] = f"Added {self.results['total_boosts']}/{self.results['expected_boosts']} Boosts"
            Logger.debug(f"Completed in {duration:.2f}s | {self.results['message']}", self.order_id)
        return self.results
    
async def boost_request(invite: str, months: int, amount: int, customization: Dict = None, tokens: List[str] = None, order_id: str = None) -> Dict:
    order_id = order_id or str(uuid.uuid4())[:8]
    error_details = []
    Logger.debug(f"Boost Request | Invite: {invite} | Months: {months} | Amount: {amount} | Customization: {customization} | Tokens: {tokens} | Order ID: {order_id}")
    if not invite:
        return {"success": False, "message": "No invite provided", "order_id": order_id}
    
    try:
        if not tokens:
            ok, stock = token_manager.stock_info(months)
            
            if not ok:
                Logger.error(f"Stock check failed: {stock.get('error', 'Unknown error')}")
                return {
                    "success": False,
                    "message": "Failed to check token stock",
                    "error": stock.get("error", "Unknown error"),
                    "error_details": ["Failed to check token stock"],
                    "order_id": order_id,
                    "request": {"invite": invite, "amount": amount, "months": months},
                    "tokens": {
                        "success": {"tokens": [], "count": 0},
                        "failed": {"tokens": [], "count": 0},
                        "captcha": {"tokens": [], "count": 0}
                    }
                }
            
            available_tokens = stock.get("available", 0)
            needed_tokens = (amount + 1) // 2  
                        
            if available_tokens < needed_tokens:
                Logger.debug(f"Insufficient stock - Need {amount}x boosts ({needed_tokens} tokens), have {available_tokens} tokens ({available_tokens*2}x boosts)")
                return {
                    "success": False,
                    "message": f"Insufficient stock. Required: {amount}x, Available: {available_tokens*2}x Boosts",
                    "error": f"Insufficient stock. Required: {amount}x, Available: {available_tokens*2}x Boosts",
                    "error_details": [f"Not enough tokens in stock. Need {amount}x, have {available_tokens*2}x Boosts"],
                    "order_id": order_id,
                    "request": {"invite": invite, "amount": amount, "months": months},
                    "tokens": {
                        "success": {"tokens": [], "count": 0},
                        "failed": {"tokens": [], "count": 0},
                        "captcha": {"tokens": [], "count": 0}
                    }
                }

        invite_code = invite.split("/")[-1] if "/" in invite else invite
        guild_data = DiscordAPI.check_invite(invite_code)
        
        if not guild_data:
            return {
                "success": False, "error": "Invalid Discord invite code or server not found", 
                "message": "Invalid Discord invite code or server not found", 
                "order_id": order_id,
                "tokens": {
                    "success": {"tokens": [], "count": 0},
                    "failed": {"tokens": [], "count": 0},
                    "captcha": {"tokens": [], "count": 0}
                },
                "requested": {"months": months, "amount": amount, "invite": invite}}
        
        if months not in [1, 3]:
            error_details.append(f"Invalid boost duration: {months} months. Must be either 1 or 3 months")
            
        if amount < 1:
            error_details.append(f"Invalid boost amount: {amount}. Must be at least 1")
            
        if error_details:
            return {
                "success": False, 
                "message": "Invalid parameters",
                "details": error_details,
                "order_id": order_id,
                "tokens": {
                    "success": {"tokens": [], "count": 0},
                    "failed": {"tokens": [], "count": 0},
                    "captcha": {"tokens": [], "count": 0}
                },
                "requested": {"months": months, "amount": amount, "invite": invite}
            }
        
        booster = BoostClass(order_id)
        
        if tokens:
            booster.using_existing_tokens = True
            booster.existing_tokens = tokens.copy()
            
        if SETTINGS.get('enable_captcha') and SETTINGS.get('captcha_api_key'):
            Logger.debug(f"Initializing Captcha Solver with Service: {SETTINGS.get('captcha_service', 'RazarCaptcha')}")
            booster.solver = CaptchaSolver(SETTINGS['captcha_api_key'])
        
        result = booster.start_boost(amount, invite_code, months, guild_data["guild"]["id"], tokens, customization)
        return {
            "success": result.get("success"),
            "time": result.get("end_time"),
            "timestamp": result.get("end_time"),
            "total_boosts": result.get("total_boosts"),
            "tokens": {
                "captcha": {"tokens": result.get("captcha_tokens", []), "count": len(result.get("captcha_tokens", []))},
                "failed": {
                    "tokens": list(set(result.get("failed_tokens", []) + result.get("no_slots_tokens", []) + result.get("invalid_tokens", []))),
                    "count": len(list(set(result.get("failed_tokens", []) + result.get("no_slots_tokens", []) + result.get("invalid_tokens", []))))
                },
                "success": {"tokens": result.get("success_tokens", []), "count": len(result.get("success_tokens", []))}
            },
            "order_id": result.get("order_id"),
            "request": {
                "invite": result["request"].get("invite"),
                "months": result["request"].get("months"),
                "amount": result["request"].get("amount"),
                "customization": result["request"].get("customization")
            },
            "server_id": result["request"].get("guild_id"),
            'error': result.get('message'),
            'error_details': result.get('message', [])
        }
        
    except Exception as e:
        error_msg = str(e)
        Logger.error(f"Boost Error: {error_msg} for Order: {order_id}")
        return {
            "success": False, 
            "message": "Boost request failed",
            "error": error_msg,
            "order_id": order_id,
            "provided_params": {
                "months": months,
                "amount": amount,
                "invite": invite_code if 'invite_code' in locals() else invite
            }
        }
    

class UnboostManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.results = {"success": [], "failed": []}
        self.useragent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        
    def _create_session(self, token: str):
        session = tls_client.Session(random_tls_extension_order=True, client_identifier="chrome_124")
        session.headers.update({
            'authority': 'discord.com',
            'accept': '*/*',
            'accept-language': 'en-US',
            'authorization': token,
            'origin': 'https://discord.com',
            'referer': 'https://discord.com/channels/@me',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': self.useragent,
            'x-debug-options': 'bugReporterEnabled',
            'x-discord-locale': 'en-US'
        })
        return session

    def _process_token(self, token: str, guild_id: str) -> bool:
        try:
            session = self._create_session(token)
            response = session.delete(f"https://discord.com/api/v9/users/@me/guilds/{guild_id}")
            
            with self.lock:
                if response.status_code in [200, 204]:
                    self.results["success"].append(token)
                    return True
                self.results["failed"].append(token)
            return False
        except:
            with self.lock:
                self.results["failed"].append(token)
            return False

    def unboost_all(self, tokens: List[str], guild_id: str, max_workers: int = 50) -> Dict:
        start = time.time()
        self.results = {"success": [], "failed": [], "time_taken": 0}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(lambda t: self._process_token(t, guild_id), tokens)
            
        self.results["time_taken"] = time.time() - start
        return self.results


async def unboost_server(guild_id: str, tokens: List[str] = None) -> Dict:
    """
    Remove all boosts from a server using UnboostManager
    
    Args:
        guild_id (str): Discord server ID to unboost
        tokens (List[str], optional): Specific tokens to use for unboosting
        
    Returns:
        Dict: Result of the unboost operation
    """
    try:
        unboost_manager = UnboostManager()
        result = unboost_manager.unboost_all(tokens, guild_id)
        
        return {
            "success": True,
            "server_id": guild_id,
            "tokens": {
                "success": {
                    "tokens": result["success"],
                    "count": len(result["success"])
                },
                "failed": {
                    "tokens": result["failed"],
                    "count": len(result["failed"])
                }
            },
            "time_taken": result["time_taken"]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "server_id": guild_id,
            "tokens": {
                "success": {"tokens": [], "count": 0},
                "failed": {"tokens": [], "count": 0}
            },
            "time_taken": 0
        }