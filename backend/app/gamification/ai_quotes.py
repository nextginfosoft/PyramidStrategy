"""
AI-Powered Daily Gamification Quotes
─────────────────────────────────────
Pre-fetches daily fresh motivational quotes from AI (OpenAI / Anthropic / Gemini)
and caches them for zero-latency event response during trading hours.
Falls back gracefully to the hardcoded quote registry if AI is unavailable.
"""

import json
import random
from typing import Optional
from loguru import logger

from app.gamification.quotes import (
    ENTRY_L1, ENTRY_L2, ENTRY_L3, TARGET_HIT, SL_HIT,
    SQUAREOFF, ENGINE_START, ENGINE_STOP, LEVEL_BLOCKED, POST_EXIT_FOMO
)

# Daily in-memory cache for AI-generated quotes: { event_type: [(quote, author), ...] }
_DAILY_AI_QUOTES: dict[str, list[tuple[str, str]]] = {}


def get_daily_ai_quote(event_type: str) -> Optional[tuple[str, str]]:
    """Return a randomly chosen AI quote for today if available."""
    pool = _DAILY_AI_QUOTES.get(event_type, [])
    if pool:
        return random.choice(pool)
    return None


async def generate_daily_ai_quotes(user_id: int = 1) -> bool:
    """
    Calls configured AI provider (OpenAI, Anthropic, or Gemini) to generate
    fresh share market motivational quotes for today's trading session.
    """
    global _DAILY_AI_QUOTES
    from app.services.ai_service import get_user_ai_service

    ai_service = get_user_ai_service(user_id)
    if not ai_service.is_enabled():
        logger.info(f"User {user_id}: AI Service disabled or not configured. Using static quote registry.")
        return False

    prompt = (
        "You are a master quantitative trading mentor and market wisdom curator.\n"
        "Generate a JSON object containing unique, highly motivational, and context-specific share market quotes for a day trader.\n"
        "The quotes should draw inspiration from renowned traders (e.g. Warren Buffett, Jesse Livermore, Paul Tudor Jones, Ray Dalio, Mark Douglas, Ed Seykota, etc.) or modern trading wisdom.\n\n"
        "Generate 1-2 quotes for EACH of the following event keys:\n"
        "- ENTRY_L1: Initial position entered at key level (focus: execution, research, starting strong)\n"
        "- ENTRY_L2: Pyramiding into winning position (focus: discipline, compounding, adding to winners)\n"
        "- ENTRY_L3: Maximum position loaded (focus: risk management, conviction, protecting capital)\n"
        "- TARGET_HIT: Take-profit target achieved (focus: locking profits, discipline over greed)\n"
        "- SL_HIT: Stop loss triggered (focus: capital preservation, resilience, tuition paid, next opportunity)\n"
        "- SQUAREOFF: Day session end / square off (focus: review, peace of mind, consistency)\n"
        "- ENGINE_START: Trading engine initiated (focus: preparation, strategy execution, focus)\n"
        "- LEVEL_BLOCKED: Level blocked to prevent overtrading (focus: patience, avoiding FOMO, protecting gains)\n"
        "- POST_EXIT_FOMO: Price kept moving after exit (focus: no regret, sticking to plan, edge captured)\n\n"
        "Return ONLY a valid raw JSON object (no markdown, no ```json wrapper) with this exact schema:\n"
        "{\n"
        '  "ENTRY_L1": [["quote text", "Author Name"]],\n'
        '  "ENTRY_L2": [["quote text", "Author Name"]],\n'
        '  "ENTRY_L3": [["quote text", "Author Name"]],\n'
        '  "TARGET_HIT": [["quote text", "Author Name"]],\n'
        '  "SL_HIT": [["quote text", "Author Name"]],\n'
        '  "SQUAREOFF": [["quote text", "Author Name"]],\n'
        '  "ENGINE_START": [["quote text", "Author Name"]],\n'
        '  "LEVEL_BLOCKED": [["quote text", "Author Name"]],\n'
        '  "POST_EXIT_FOMO": [["quote text", "Author Name"]]\n'
        "}"
    )

    try:
        raw_resp = await ai_service.call_llm(prompt)
        if not raw_resp:
            logger.warning(f"User {user_id}: AI returned empty response for daily quotes generation.")
            return False

        # Clean potential markdown formatting
        cleaned_resp = raw_resp.strip()
        if cleaned_resp.startswith("```json"):
            cleaned_resp = cleaned_resp[7:]
        if cleaned_resp.startswith("```"):
            cleaned_resp = cleaned_resp[3:]
        if cleaned_resp.endswith("```"):
            cleaned_resp = cleaned_resp[:-3]
        cleaned_resp = cleaned_resp.strip()

        data = json.loads(cleaned_resp)
        new_quotes: dict[str, list[tuple[str, str]]] = {}

        for key, quotes_list in data.items():
            if isinstance(quotes_list, list):
                parsed_list = []
                for item in quotes_list:
                    if isinstance(item, list) and len(item) >= 2:
                        parsed_list.append((str(item[0]), str(item[1])))
                if parsed_list:
                    new_quotes[key] = parsed_list

        if new_quotes:
            _DAILY_AI_QUOTES = new_quotes
            logger.info(f"✨ Successfully generated and loaded {sum(len(v) for v in new_quotes.values())} AI quotes for user {user_id}!")
            return True

    except Exception as e:
        logger.error(f"Failed to generate daily AI quotes for user {user_id}: {e}")

    return False
