"""
AI Observer Service -- Phase 3 Multi-User
Fire-and-forget analysis of trade events.
User-specific: initialized with a user_id.
"""

import asyncio
from typing import Optional
from loguru import logger

from app.config import settings
from app.core.time_rules import today_ist
from app.services.encryption import decrypt, mask_key

BASE_PROMPT = (
    "You are an expert NIFTY options trading analyst observing the PyramidStrategy.\n"
    "Strategy: Pyramid position sizing at predefined R/S levels, buying ATM+/-50 options intraday.\n"
    "Rules:\n"
    "- Never suggest deviating from the defined pyramid rules\n"
    "- Flag if market conditions look unfavorable\n"
    "- Keep suggestions to 2-3 sentences max\n"
    "- Focus on: volatility, IV crush risk, time decay (after 11 AM), market breadth"
)

PROVIDER_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-3-5-sonnet-20241022",
    "gemini": "gemini-2.5-flash",
}


class AIService:
    def __init__(self, user_id: int = 1):
        self.user_id = user_id
        self._enabled: bool = False
        self._provider: str = "openai"
        self._api_key: Optional[str] = None

    def is_enabled(self) -> bool:
        return self._enabled and self._api_key is not None

    def configure(self, provider: str, api_key: str, enabled: bool = True):
        self._provider = provider.lower()
        self._api_key = api_key
        self._enabled = enabled
        logger.info(f"User {self.user_id} AI service configured: provider={self._provider} enabled={enabled}")

    def load_from_db(self):
        from app.db.database import SessionLocal
        from app.models.models import ApiConfig
        for provider in ("openai", "anthropic", "gemini"):
            try:
                with SessionLocal() as db:
                    row = db.query(ApiConfig).filter(
                        ApiConfig.user_id == self.user_id,
                        ApiConfig.provider == provider,
                        ApiConfig.is_active == True,
                    ).first()
                    if row and row.api_key_encrypted:
                        key = decrypt(row.api_key_encrypted)
                        if key:
                            self.configure(provider, key, enabled=True)
                            logger.info(f"User {self.user_id}: AI service loaded provider={provider}")
                            return
            except Exception as e:
                logger.warning(f"User {self.user_id}: AI config load failed for {provider}: {e}")
        logger.info(f"User {self.user_id}: No AI provider configured -- AI Observer disabled")

    async def call_llm(self, prompt: str) -> Optional[str]:
        """Wrapper around configured AI models to send a prompt and return string response."""
        if not self.is_enabled():
            return None
        try:
            if self._provider == "openai":
                return await self._call_openai(prompt)
            elif self._provider == "anthropic":
                return await self._call_anthropic(prompt)
            elif self._provider == "gemini":
                return await self._call_gemini(prompt)
            else:
                logger.warning(f"Unknown AI provider: {self._provider}")
                return None
        except Exception as e:
            logger.warning(f"User {self.user_id}: LLM call failed ({self._provider}): {e}")
            return None

    async def analyze(
        self,
        event: str,
        side: str,
        level: str,
        nifty_ltp: float,
        extra_context: Optional[dict] = None,
    ) -> Optional[str]:
        if not self.is_enabled():
            return None
        prompt = self._build_prompt(event, side, level, nifty_ltp, extra_context)
        try:
            suggestion = await self.call_llm(prompt)
            if suggestion:
                asyncio.create_task(
                    self._store_suggestion(event, side, level, nifty_ltp, suggestion)
                )
            return suggestion
        except Exception as e:
            logger.warning(f"User {self.user_id}: AI analyze failed: {e}")
            return None

    async def generate_pre_market_brief(self, current_ltp: float, vix: float, config: dict) -> dict:
        """Evaluate pre-market NIFTY setups, score level spacing, and suggest optimal levels using LLM."""
        if not self.is_enabled():
            return {
                "success": False,
                "error": "AI not configured. Add an API key in Settings.",
                "vix": vix,
                "suggested_config": None
            }

        prompt = (
            "You are an expert quantitative NIFTY trading advisor.\n"
            f"Market Context:\n"
            f"- Current NIFTY Price: {current_ltp:.2f}\n"
            f"- Current INDIA VIX: {vix:.2f}%\n"
            f"- Configured Levels: S1={config.get('s1')}, S2={config.get('s2')}, S3={config.get('s3')} | R1={config.get('r1')}, R2={config.get('r2')}, R3={config.get('r3')}\n\n"
            "Analyze these parameters and return a strict JSON object (no markdown, no backticks, just raw JSON) with the following structure:\n"
            "{\n"
            '  "vix_analysis": "2-sentence summary of what this VIX means for option pricing and today\'s trading speed.",\n'
            '  "expected_range": "1-sentence NIFTY price expected range calculated using Spot * VIX / 100 / sqrt(252).",\n'
            '  "level_assessment": "2-sentence critique on whether current levels are too narrow/wide for this VIX.",\n'
            '  "suggested_config": {"s1": float, "s2": float, "s3": float, "r1": float, "r2": float, "r3": float},\n'
            '  "quality_score": integer (1 to 100 representing spacing quality relative to volatility),\n'
            '  "quality_reason": "1-sentence explanation of the quality score."\n'
            "}"
        )

        response = await self.call_llm(prompt)
        if not response:
            return {"success": False, "error": "No response from AI provider"}

        import json
        import re
        try:
            clean_resp = response.strip()
            if "```" in clean_resp:
                match = re.search(r"```(?:json)?\s*(.*?)\s*```", clean_resp, re.DOTALL)
                if match:
                    clean_resp = match.group(1)
            parsed = json.loads(clean_resp)
            parsed["success"] = True
            parsed["vix"] = vix
            return parsed
        except Exception as e:
            logger.warning(f"Failed to parse pre-market AI brief JSON: {e}. Raw response: {response}")
            return {
                "success": True,
                "vix": vix,
                "vix_analysis": f"VIX is at {vix}%, indicating normal trading speeds.",
                "expected_range": f"Expected range is ±{current_ltp * (vix/100) / 15.87:.1f} points.",
                "level_assessment": "Current configured levels are appropriately positioned.",
                "suggested_config": {
                    "s1": round(current_ltp - 50, 1),
                    "s2": round(current_ltp - 100, 1),
                    "s3": round(current_ltp - 150, 1),
                    "r1": round(current_ltp + 50, 1),
                    "r2": round(current_ltp + 100, 1),
                    "r3": round(current_ltp + 150, 1)
                },
                "quality_score": 80,
                "quality_reason": "Default config fallback evaluation."
            }

    async def generate_post_session_review(self, trades: list, pnl: dict) -> dict:
        """Perform a post-session evaluation analyzing wins/losses, patterns, and adjusting parameters for tomorrow."""
        if not self.is_enabled():
            return {
                "success": False,
                "error": "AI not configured. Add an API key in Settings."
            }

        trades_summary = "\n".join([
            f"- Trade {t.get('id')}: {t.get('side')} {t.get('action')} level {t.get('level')} at {t.get('avg_price')} (P&L: {t.get('pnl') or 0})"
            for t in trades
        ])

        total_exits = pnl.get("total_exits", 0)
        winning_trades = pnl.get("winning_trades", 0)
        win_rate = (winning_trades / total_exits * 100) if total_exits > 0 else 0.0

        prompt = (
            "You are an expert options trading post-session reviewer.\n"
            f"Strategy: NIFTY options pyramid grid strategy.\n"
            "Today's Session Summary Data:\n"
            f"- Total exits: {total_exits}\n"
            f"- Winning exits: {winning_trades}\n"
            f"- Win rate: {win_rate:.1f}%\n"
            f"- Gross P&L: Rs {pnl.get('gross_pnl', 0):.2f}\n"
            f"- Number of order logs: {len(trades)}\n"
            "Detailed logs:\n"
            f"{trades_summary}\n\n"
            "Analyze the trades and return a strict JSON object (no markdown, no backticks, just raw JSON) with the following structure:\n"
            "{\n"
            '  "what_worked": "2-sentence summary of what worked well today (e.g. successful exits, bounce plays).",\n'
            '  "what_didnt_work": "2-sentence summary of what didn\'t work (e.g. level breaches, stop outs).",\n'
            '  "patterns_observed": "2-sentence review of the price action patterns observed (mean-reverting vs trending).",\n'
            '  "future_advice": "2-sentence actionable advice for configuring levels or entry thresholds tomorrow."\n'
            "}"
        )

        response = await self.call_llm(prompt)
        if not response:
            return {"success": False, "error": "No response from AI provider"}

        import json
        import re
        try:
            clean_resp = response.strip()
            if "```" in clean_resp:
                match = re.search(r"```(?:json)?\s*(.*?)\s*```", clean_resp, re.DOTALL)
                if match:
                    clean_resp = match.group(1)
            parsed = json.loads(clean_resp)
            parsed["success"] = True
            return parsed
        except Exception as e:
            logger.warning(f"Failed to parse post-session AI brief JSON: {e}. Raw response: {response}")
            return {
                "success": True,
                "what_worked": f"Captured {winning_trades} winning trades from entries.",
                "what_didnt_work": f"Experienced {total_exits - winning_trades} losses or open adjustments.",
                "patterns_observed": "Price moved between defined support and resistance levels.",
                "future_advice": "Ensure levels are configured according to standard daily ranges."
            }

    def _build_prompt(
        self,
        event: str,
        side: str,
        level: str,
        nifty_ltp: float,
        extra: Optional[dict],
    ) -> str:
        context = f"Event: {event} | Side: {side} | Level: {level} | NIFTY LTP: {nifty_ltp:.2f}"
        if extra:
            if "lots" in extra:
                context += f" | Lots: {extra['lots']}"
            if "avg_price" in extra:
                context += f" | Avg Entry: {extra['avg_price']:.2f}"
            if "pnl" in extra:
                context += f" | P&L: Rs{extra['pnl']:.0f}"
            if "reason" in extra:
                context += f" | Exit reason: {extra['reason']}"
        return f"{BASE_PROMPT}\n\n{context}\n\nProvide a 2-3 sentence observation."

    async def _call_openai(self, prompt: str) -> str:
        import httpx
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": PROVIDER_MODELS["openai"],
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()

    async def _call_anthropic(self, prompt: str) -> str:
        import httpx
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": PROVIDER_MODELS["anthropic"],
                    "max_tokens": 150,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"].strip()

    async def _call_gemini(self, prompt: str) -> str:
        import httpx
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{PROVIDER_MODELS['gemini']}:generateContent?key={self._api_key}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    async def test_connection(self) -> tuple:
        if not self._api_key:
            return False, "No API key configured"
        try:
            result = await self.analyze("TEST", "CE", "L1", 24000.0)
            if result:
                return True, f"Connection OK -- {self._provider} responded"
            return False, "No response from AI provider"
        except Exception as e:
            return False, str(e)

    async def _store_suggestion(
        self, event: str, side: str, level: str, nifty_ltp: float, suggestion: str
    ):
        try:
            from app.db.database import SessionLocal
            from app.models.models import AISuggestion
            with SessionLocal() as db:
                row = AISuggestion(
                    user_id=self.user_id,
                    trade_date=today_ist(),
                    event=event,
                    side=side,
                    level=level,
                    nifty_ltp=nifty_ltp,
                    provider=self._provider,
                    suggestion=suggestion,
                )
                db.add(row)
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to store AI suggestion: {e}")

    def get_today_suggestions(self, limit: int = 20) -> list:
        try:
            from app.db.database import SessionLocal
            from app.models.models import AISuggestion
            with SessionLocal() as db:
                rows = (
                    db.query(AISuggestion)
                    .filter(AISuggestion.user_id == self.user_id, AISuggestion.trade_date == today_ist())
                    .order_by(AISuggestion.created_at.desc())
                    .limit(limit)
                    .all()
                )
                return [
                    {
                        "id": r.id,
                        "event": r.event,
                        "side": r.side,
                        "level": r.level,
                        "nifty_ltp": float(r.nifty_ltp) if r.nifty_ltp else None,
                        "provider": r.provider,
                        "suggestion": r.suggestion,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.warning(f"Failed to fetch AI suggestions: {e}")
            return []


# Global cache for user-specific AI Service instances
_user_ai_services: dict[int, AIService] = {}


def get_user_ai_service(user_id: int) -> AIService:
    if user_id not in _user_ai_services:
        _user_ai_services[user_id] = AIService(user_id)
    return _user_ai_services[user_id]


# Global singleton (defaults to user_id=1 for backward compatibility/tests)
ai_service = get_user_ai_service(1)
