"""
AI Observer Service -- Phase 3
Fire-and-forget analysis of trade events.
NEVER delays or blocks order execution -- always called via asyncio.create_task().

Supported providers: OpenAI (gpt-4o), Anthropic (claude-3-5-sonnet), Google (gemini-1.5-pro)
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
    "gemini": "gemini-1.5-pro",
}


class AIService:
    def __init__(self):
        self._enabled: bool = False
        self._provider: str = "openai"
        self._api_key: Optional[str] = None

    def is_enabled(self) -> bool:
        return self._enabled and self._api_key is not None

    def configure(self, provider: str, api_key: str, enabled: bool = True):
        self._provider = provider.lower()
        self._api_key = api_key
        self._enabled = enabled
        logger.info(f"AI service configured: provider={self._provider} enabled={enabled}")

    def load_from_db(self):
        from app.db.database import SessionLocal
        from app.models.models import ApiConfig
        for provider in ("openai", "anthropic", "gemini"):
            try:
                with SessionLocal() as db:
                    row = db.query(ApiConfig).filter(
                        ApiConfig.provider == provider,
                        ApiConfig.is_active == True,
                    ).first()
                    if row and row.api_key_encrypted:
                        key = decrypt(row.api_key_encrypted)
                        if key:
                            self.configure(provider, key, enabled=True)
                            logger.info(f"AI service loaded: provider={provider}")
                            return
            except Exception as e:
                logger.warning(f"AI config load failed for {provider}: {e}")
        logger.info("No AI provider configured -- AI Observer disabled")

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
            if self._provider == "openai":
                suggestion = await self._call_openai(prompt)
            elif self._provider == "anthropic":
                suggestion = await self._call_anthropic(prompt)
            elif self._provider == "gemini":
                suggestion = await self._call_gemini(prompt)
            else:
                logger.warning(f"Unknown AI provider: {self._provider}")
                return None
            if suggestion:
                asyncio.create_task(
                    self._store_suggestion(event, side, level, nifty_ltp, suggestion)
                )
            return suggestion
        except Exception as e:
            logger.warning(f"AI call failed ({self._provider}): {e}")
            return None

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
                    .filter(AISuggestion.trade_date == today_ist())
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


# Global singleton
ai_service = AIService()
