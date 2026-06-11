"""
AI Observer Service
────────────────────
Async, non-blocking AI analysis of trade events.
NEVER delays or blocks order execution.

Supported providers: OpenAI, Anthropic, Google Gemini
"""

import httpx
from loguru import logger
from app.config import settings
from app.db.database import SessionLocal
from app.models.models import ApiConfig


BASE_PROMPT = """You are an expert NIFTY options trading analyst observing the PyramidStrategy.
Strategy: Pyramid position sizing at predefined R/S levels, buying ATM±50 options.
Your job: Observe live trades and provide concise, actionable insights.
Rules you must follow:
- Never suggest deviating from the defined pyramid rules
- Flag if market conditions look unfavorable for the strategy
- Provide post-trade analysis after each exit
- Keep suggestions to 2-3 sentences max
- Focus on: volatility, IV crush risk, time decay (after 11 AM), market breadth"""


class AIService:
    def __init__(self):
        self._enabled = False
        self._provider = "openai"
        self._api_key = None

    def is_enabled(self) -> bool:
        return self._enabled and self._api_key is not None

    def configure(self, provider: str, api_key: str, enabled: bool = True):
        self._provider = provider
        self._api_key = api_key
        self._enabled = enabled
        logger.info(f"AI service configured: provider={provider}, enabled={enabled}")

    def load_from_db(self):
        """Load AI config from database."""
        try:
            with SessionLocal() as db:
                cfg = db.query(ApiConfig).filter(
                    ApiConfig.provider == self._provider,
                    ApiConfig.is_active == True
                ).first()
                if cfg and cfg.api_key_encrypted:
                    from app.services.encryption import decrypt
                    self._api_key = decrypt(cfg.api_key_encrypted)
                    self._enabled = True
        except Exception as e:
            logger.warning(f"Could not load AI config from DB: {e}")

    async def analyze(self, event: str, side: str, level: str, nifty_ltp: float) -> str | None:
        """
        Analyze a trade event and return a suggestion string.
        Called AFTER trade execution — never blocks it.
        """
        if not self.is_enabled():
            return None

        prompt = self._build_prompt(event, side, level, nifty_ltp)

        try:
            if self._provider == "openai":
                return await self._call_openai(prompt)
            elif self._provider == "anthropic":
                return await self._call_anthropic(prompt)
            elif self._provider == "gemini":
                return await self._call_gemini(prompt)
        except Exception as e:
            logger.warning(f"AI call failed: {e}")
            return None

    def _build_prompt(self, event: str, side: str, level: str, nifty_ltp: float) -> str:
        return f"""{BASE_PROMPT}

Current event: {event} on {side} side at {level}
NIFTY LTP: {nifty_ltp:.2f}

Provide a brief 2-3 sentence observation about this trade event."""

    async def _call_openai(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()

    async def _call_anthropic(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 150,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"].strip()

    async def _call_gemini(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={self._api_key}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


# Global singleton
ai_service = AIService()
