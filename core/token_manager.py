import threading
from typing import Set, List, Dict, Optional, Union, Tuple
import random
import os
from core.log import Logger

class TokenManager:
    instance = None
    lock = threading.Lock()
    active_tokens: Dict[str, str] = {}

    def __new__(cls):
        if cls.instance is None:
            with cls.lock:
                if cls.instance is None:
                    cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self):
        self.file_locks = {1: threading.Lock(), 3: threading.Lock()}

    def get_filepath(self, months: int) -> Tuple[bool, str]:
        if months not in [1, 3]:
            return False, "Invalid month duration"
        return True, f"data/{months}m_tokens.txt"

    def load_tokens(self, months: int) -> Tuple[bool, Set[str]]:
        try:
            ok, path = self.get_filepath(months)
            if not ok:
                return False, set()
            if not os.path.exists(path):
                return True, set()
            with open(path, 'r') as f:
                return True, {line.strip() for line in f if line.strip()}
        except:
            return False, set()

    def save_tokens(self, months: int, tokens: Set[str]) -> bool:
        try:
            ok, path = self.get_filepath(months)
            if not ok:
                return False
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                f.write('\n'.join(sorted(tokens)))
            return True
        except:
            return False

    def extract_token(self, token_str: str) -> str:
        if not token_str:
            return ""
            
        token_part = token_str.split('||')[0].strip()
        
        parts = token_part.split(':')
        if len(parts) == 3: 
            return parts[2].strip()
        elif len(parts) == 1: 
            return parts[0].strip()
        else: 
            return parts[-1].strip()

    def match_token(self, search_token: str, stored_token: str) -> bool:
        """Match tokens ignoring format and reason"""
        clean_search = self.extract_token(search_token)
        clean_stored = self.extract_token(stored_token)
        return clean_search == clean_stored

    def stock_info(self, months: Optional[int] = None) -> Tuple[bool, Dict]:
        with self.lock:
            if months:
                if months not in [1, 3]:
                    return False, {"error": "Invalid month duration"}
                ok, tokens = self.load_tokens(months)
                if not ok:
                    return False, {"error": "Failed to load tokens"}
                in_use = sum(1 for v in self.active_tokens.values() if v == str(months))
                return True, {"available": len(tokens), "in_use": in_use, "total": len(tokens) + in_use}
            
            result = {}
            for m in [1, 3]:
                ok, tokens = self.load_tokens(m)
                if not ok:
                    return False, {"error": f"Failed to load {m}m tokens"}
                in_use = sum(1 for v in self.active_tokens.values() if v == str(m))
                result[f"{m}m"] = {"available": len(tokens), "in_use": in_use, "total": len(tokens) + in_use}
            return True, result

    def get_token(self, months: int) -> Tuple[bool, Optional[str]]:
        if months not in [1, 3]:
            return False, "Invalid month duration"
        
        with self.lock, self.file_locks[months]:
            ok, tokens = self.load_tokens(months)
            if not ok:
                return False, "Failed to load tokens"
            
            available_tokens = {
                token for token in tokens 
                if self.extract_token(token) not in self.active_tokens
            }
            if not available_tokens:
                return False, "No tokens available"
            token_line = random.choice(list(available_tokens))
            clean_token = self.extract_token(token_line)
            tokens.remove(token_line)
            
            if not self.save_tokens(months, tokens):
                return False, "Failed to save tokens"
            
            self.active_tokens[clean_token] = str(months)
            return True, clean_token

    def return_token(self, token: str, months: int, reason: str = None) -> Tuple[bool, str]:
        with self.lock, self.file_locks[months]:
            if months not in [1, 3]:
                return False, "Invalid month duration"
            
            clean_token = self.extract_token(token)
            if clean_token in self.active_tokens:
                del self.active_tokens[clean_token]
            
            ok, tokens = self.load_tokens(months)
            if not ok:
                return False, "Failed to load tokens"
            
            original_format = next((t for t in tokens if self.match_token(clean_token, t)), clean_token)
            token_str = f"{original_format} || {reason}" if reason else original_format
            tokens.add(token_str)
            
            if not self.save_tokens(months, tokens):
                return False, "Failed to save tokens"
            return True, "Token returned successfully"
        
    def filter_tokens(self, months: int, filter_results: Dict[str, List[str]]) -> Tuple[bool, Dict]:
        if months not in [1, 3]:
            return False, {"error": "Invalid month duration"}
            
        with self.lock, self.file_locks[months]:
            ok, tokens = self.load_tokens(months)
            if not ok:
                return False, {"error": "Failed to load tokens"}
            
            valid_types = [
                "valid_with_nitro",
                "valid_nitro_with_boosts",
                "valid_nitro_with_reusable"
            ]
            keep_tokens = set()
            for type in valid_types:
                keep_tokens.update(filter_results.get(type, []))
            
            tokens_to_keep = {
                token_line for token_line in tokens
                if self.extract_token(token_line) in keep_tokens
            }
            
            tokens_to_remove = tokens - tokens_to_keep
            
            if not self.save_tokens(months, tokens_to_keep):
                return False, {"error": "Failed to save tokens"}
                
            return True, {
                "kept": len(tokens_to_keep),
                "removed": len(tokens_to_remove),
                "tokens_removed": [self.extract_token(t) for t in tokens_to_remove]
            }
        
    def remove_token(self, token: str, months: int, reason: str = None) -> Tuple[bool, str]:
        with self.lock, self.file_locks[months]:
            if months not in [1, 3]:
                return False, "Invalid month duration"
            
            clean_token = self.extract_token(token)
            ok, tokens = self.load_tokens(months)
            if not ok:
                return False, "Failed to load tokens"
            
            if clean_token in self.active_tokens:
                del self.active_tokens[clean_token]
            
            tokens = {t for t in tokens if not self.match_token(clean_token, t)}
            if reason:
                Logger.debug(f"Token removed: {reason}")
            
            if not self.save_tokens(months, tokens):
                return False, "Failed to save tokens"
            return True, "Token removed successfully"

    def add_token(self, tokens: Union[str, List[str]], months: int) -> Tuple[bool, str]:
        with self.lock, self.file_locks[months]:
            if months not in [1, 3]:
                return False, "Invalid month duration"
            
            if isinstance(tokens, str):
                tokens = [tokens]
            
            ok, current = self.load_tokens(months)
            if not ok:
                return False, "Failed to load tokens"
            
            current.update(tokens)
            if not self.save_tokens(months, current):
                return False, "Failed to save tokens"
            return True, "Tokens added successfully"

    def get_tokens(self, months: int, quantity: int) -> Tuple[bool, Union[List[str], str]]:
        if months not in [1, 3]:
            return False, "Invalid month duration"
        
        ok, tokens = self.load_tokens(months)
        if not ok:
            return False, "Failed to load tokens"
        
        available_tokens = {
            token for token in tokens 
            if self.extract_token(token) not in self.active_tokens
        }
        
        if len(available_tokens) < quantity:
            return False, "Insufficient tokens available"
        
        selected = random.sample(list(available_tokens), quantity)
        
        with self.lock, self.file_locks[months]:
            remaining = tokens - set(selected)
            if not self.save_tokens(months, remaining):
                return False, "Failed to save tokens"
            
            clean_tokens = [self.extract_token(t) for t in selected]
            for token in clean_tokens:
                self.active_tokens[token] = str(months)
        
        return True, clean_tokens
    
    def fetch_tokens(self, duration: str = "all") -> Tuple[bool, Dict]:
        valid_durations = ["all", "1", "3", "in_use"]
        if duration not in valid_durations:
            return False, {"error": "Invalid duration, use 'all', '1', '3', or 'in_use'"}
        
        result = {"status": True, "data": {}}
        
        with self.lock:
            if duration == "in_use":
                active_tokens = {
                    "1m": {t: "1m" for t, m in self.active_tokens.items() if m == "1"},
                    "3m": {t: "3m" for t, m in self.active_tokens.items() if m == "3"}
                }
                
                result["data"] = {
                    "1m": {"count": len(active_tokens["1m"]), "tokens": active_tokens["1m"]},
                    "3m": {"count": len(active_tokens["3m"]), "tokens": active_tokens["3m"]},
                    "total": len(self.active_tokens)
                }
                return True, result
            
            durations_to_check = []
            if duration == "all":
                durations_to_check = [1, 3]
            else:
                durations_to_check = [int(duration)]
            
            for months in durations_to_check:
                ok, tokens = self.load_tokens(months)
                if not ok:
                    return False, {"error": f"Failed to load {months}m tokens"}
                
                in_use = {t: f"{months}m" for t, m in self.active_tokens.items() if m == str(months)}
                
                result["data"][f"{months}m"] = {
                    "available": {self.extract_token(t): t for t in tokens},
                    "available_count": len(tokens),
                    "in_use": in_use,
                    "in_use_count": len(in_use),
                    "total": len(tokens) + len(in_use)
                }
            
            if duration == "all":
                result["data"]["total"] = {
                    "available": sum(result["data"][k]["available_count"] for k in ["1m", "3m"]),
                    "in_use": sum(result["data"][k]["in_use_count"] for k in ["1m", "3m"]),
                    "grand_total": sum(result["data"][k]["total"] for k in ["1m", "3m"])
                }
            
        return True, result

token_manager = TokenManager()