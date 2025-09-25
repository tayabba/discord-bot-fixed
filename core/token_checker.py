
import aiohttp
import asyncio
from datetime import datetime, timezone
import pytz
import os
from typing import List, Dict, Any, Tuple, Union
import time
import json
from dataclasses import dataclass, asdict

@dataclass
class TokenStats:
    total_tokens: int = 0
    invalid_tokens: int = 0
    valid_tokens: int = 0
    valid_no_nitro: int = 0
    valid_with_nitro: int = 0
    one_month_nitro: int = 0
    three_month_nitro: int = 0
    tokens_with_boosts: int = 0
    available_boosts: int = 0
    used_boosts: int = 0
    reusable_boosts: int = 0
    tokens_with_reusable: int = 0
    time_taken: float = 0
    tokens_per_second: float = 0
    valid_with_nitro_1_month: int = 0
    valid_with_nitro_3_months: int = 0

class TokenChecker:
    def __init__(self, chunk_size: int = 100, max_concurrent: int = 50):
        self.chunk_size = chunk_size
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    def clean_tokens(self, tokens_input: str) -> List[str]:
        if isinstance(tokens_input, str):
            tokens = tokens_input.strip().split('\n')
        else:
            tokens = tokens_input
        cleaned = []
        for token in tokens:
            token = token.strip().strip('",\'').strip()
            if token:
                if ':' in token:
                    cleaned.append(token.split(':')[-1])
                else:
                    cleaned.append(token)
        return cleaned
    def calculate_days_remaining(self, end_date: datetime) -> int:
        today = datetime.now(timezone.utc)
        days_remaining = (end_date - today).days
        return max(0, days_remaining)

    async def check_boost_slots(self, session: aiohttp.ClientSession, token: str) -> Dict[str, Any]:
        headers = {"Authorization": token}
        try:
            async with session.get(
                "https://discord.com/api/v9/users/@me/guilds/premium/subscription-slots",
                headers=headers
            ) as response:
                if response.status == 200:
                    slots = await response.json()
                    total_slots = len(slots)
                    used_slots = sum(1 for slot in slots if slot.get('subscription_id'))
                    reusable_slots = sum(1 for slot in slots if not slot.get('subscription_id') 
                                       and not slot.get('cooldown_ends_at'))
                    
                    return {
                        "total": total_slots,
                        "used": used_slots,
                        "free": total_slots - used_slots,
                        "reusable": reusable_slots,
                        "has_reusable": reusable_slots > 0,
                        "slots_data": slots,
                        "status": f"Using {used_slots}/{total_slots} boosts | Reusable {reusable_slots}/{total_slots}"
                    }
                return {
                    "status": f"Failed to fetch boost status ({response.status})",
                    "has_reusable": False,
                    "total": 0,
                    "used": 0,
                    "free": 0,
                    "reusable": 0
                }
        except Exception as e:
            return {
                "status": f"Error checking boosts: {str(e)}",
                "has_reusable": False,
                "total": 0,
                "used": 0,
                "free": 0,
                "reusable": 0
            }

    async def check_single_token(self, session: aiohttp.ClientSession, token: str) -> Dict[str, Any]:
        async with self.semaphore:
            headers = {"Authorization": token}
            try:
                async with session.get("https://discord.com/api/v9/users/@me", headers=headers) as response:
                    if response.status != 200:
                        return {"token": token, "valid": False, "error": f"Invalid token ({response.status})", "category": "invalid"}
                    
                    profile_data = await response.json()
                    premium_type = profile_data.get('premium_type', 0)

                    if premium_type == 0:
                        return {"token": token, "valid": True, "nitro": False, "category": "valid_no_nitro", "boost_status": "No Nitro"}
                    
                    async with session.get("https://discord.com/api/v9/users/@me/billing/subscriptions", headers=headers) as response:
                        subscription_data = await response.json()
                        
                        start_date = datetime.now(timezone.utc)
                        end_date = start_date
                        
                        if subscription_data and len(subscription_data) > 0:
                            sub = subscription_data[0]
                            start_date = datetime.fromisoformat(sub['current_period_start'].replace('Z', '+00:00'))
                            end_date = datetime.fromisoformat(sub['current_period_end'].replace('Z', '+00:00'))

                    duration = "1 Month" if premium_type == 1 else ("1 Month" if (end_date - start_date).days < 45 else "3 Months")
                    boost_info = await self.check_boost_slots(session, token)
                    
                    return {"token": token, "valid": True, "nitro": True, "category": "valid_with_nitro", "type": duration, 
                            "premium_type": premium_type, "start_date": start_date.strftime('%Y-%m-%d'), 
                            "expires": end_date.strftime('%Y-%m-%d'), "days_remaining": self.calculate_days_remaining(end_date),
                            "boost_status": boost_info["status"], "boost_details": boost_info}

            except Exception as e:
                return {"token": token, "valid": False, "category": "invalid", "error": f"Error: {str(e)}"}

    async def process_tokens(self, tokens: List[str]) -> Tuple[List[Dict[str, Any]], TokenStats]:
        start_time = time.time()
        
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=None),
            timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            chunks = [tokens[i:i + self.chunk_size] 
                     for i in range(0, len(tokens), self.chunk_size)]
            
            all_results = []
            for chunk in chunks:
                tasks = [self.check_single_token(session, token) for token in chunk]
                results = await asyncio.gather(*tasks)
                all_results.extend(results)

        time_taken = time.time() - start_time
        
        stats = TokenStats(
            total_tokens=len(all_results),
            time_taken=time_taken,
            tokens_per_second=len(all_results)/time_taken
        )
        
        for result in all_results:
            if not result["valid"]:
                stats.invalid_tokens += 1
                continue
                
            stats.valid_tokens += 1
            
            if not result.get("nitro"):
                stats.valid_no_nitro += 1
                continue
                
            stats.valid_with_nitro += 1
            
            if result["type"] == "1 Month":
                stats.one_month_nitro += 1
                stats.valid_with_nitro_1_month += 1
            else:
                stats.three_month_nitro += 1
                stats.valid_with_nitro_3_months += 1
                
            boost_details = result.get("boost_details", {})
            if boost_details.get("total", 0) > 0:
                stats.tokens_with_boosts += 1
                stats.available_boosts += boost_details.get("free", 0)
                stats.used_boosts += boost_details.get("used", 0)
                stats.reusable_boosts += boost_details.get("reusable", 0)
                if boost_details.get("reusable", 0) > 0:
                    stats.tokens_with_reusable += 1
        
        return all_results, stats

    async def checker_(self, tokens_input: str) -> Dict[str, Any]:
        """Simple token check with basic metrics"""
        tokens = self.clean_tokens(tokens_input)
        results, stats = await self.process_tokens(tokens)
        
        categorized = {
            "invalid": [],
            "valid_no_nitro": [],
            "valid_with_nitro": [],
            "valid_nitro_with_boosts": [],
            "valid_nitro_with_reusable": []
        }
        
        for result in results:
            if not result["valid"]:
                categorized["invalid"].append(result["token"])
            elif not result.get("nitro"):
                categorized["valid_no_nitro"].append(result["token"])
            else:
                categorized["valid_with_nitro"].append(result["token"])
                boost_details = result.get("boost_details", {})
                if boost_details.get("free", 0) > 0:
                    categorized["valid_nitro_with_boosts"].append(result["token"])
                if boost_details.get("reusable", 0) > 0:
                    categorized["valid_nitro_with_reusable"].append(result["token"])

        report_lines = [
            "\n=== Basic Token Check Results ===",
            f"Time taken: {stats.time_taken:.2f}s",
            f"Speed: {stats.tokens_per_second:.0f} tokens/s",
            f"\nKey Metrics:",
            f"Total Tokens: {stats.total_tokens}",
            f"Valid Tokens: {stats.valid_tokens}",
            f"Invalid Tokens: {stats.invalid_tokens}",
            f"Valid No Nitro: {stats.valid_no_nitro}",
            f"Valid With Nitro: {stats.valid_with_nitro}",
            f"Valid Nitro with Available Boosts: {stats.tokens_with_boosts}",
            f"Valid Nitro with Reusable Boosts: {stats.tokens_with_reusable}"
        ]
        
        return {
            "stats": asdict(stats),
            "results": results,
            "categorized": categorized,
            "report": "\n".join(report_lines)
        }
        
    def format_token_result(self, result: Dict[str, Any]) -> str:
        if not result.get("valid"):
            return f"{result['token']} | Invalid | {result.get('error', 'Unknown error')}"
            
        if not result.get("nitro"):
            return f"{result['token']} | Valid (No Nitro)"
            
        return (f"{result['token']} | Valid (With Nitro) | {result['type']} | "
                f"Start: {result['start_date']} | "
                f"Expires: {result['expires']} ({result['days_remaining']} days left) | "
                f"{result['boost_status']}")

    async def checker_detailed(self, tokens_input: str) -> Dict[str, Any]:
        """Detailed token check with comprehensive report"""
        tokens = self.clean_tokens(tokens_input)
        results, stats = await self.process_tokens(tokens)
        
        categorized = {
            "invalid": [],
            "valid_no_nitro": [],
            "valid_with_nitro": [],
            "valid_with_nitro_available": [],
            "valid_with_nitro_reusable": []
        }
        
        for result in results:
            category = result.get("category", "invalid")
            categorized[category].append(result)

        report_lines = [
            "\n=== Detailed Token Check Results ===",
            f"Time taken: {stats.time_taken:.2f}s",
            f"Speed: {stats.tokens_per_second:.0f} tokens/s",
            f"\nStatistics:",
            f"Total Tokens: {stats.total_tokens}",
            f"Invalid Tokens: {stats.invalid_tokens}",
            f"Valid Tokens: {stats.valid_tokens}",
            f"Valid (No Nitro): {stats.valid_no_nitro}",
            f"Valid (With Nitro): {stats.valid_with_nitro}",
            f"1 Month Nitro: {stats.one_month_nitro}",
            f"3 Month Nitro: {stats.three_month_nitro}",
            f"Tokens with Boosts: {stats.tokens_with_boosts}",
            f"Available Boosts: {stats.available_boosts}",
            f"Used Boosts: {stats.used_boosts}",
            f"Reusable Boosts: {stats.reusable_boosts}",
            f"Tokens with Reusable: {stats.tokens_with_reusable}",
            "\nDetailed Results:"
        ]
        
        report_lines.extend(self.format_token_result(result) for result in results)
        
        return {
            "stats": asdict(stats),
            "results": results,
            "categorized": categorized,
            "report": "\n".join(report_lines)
        }

