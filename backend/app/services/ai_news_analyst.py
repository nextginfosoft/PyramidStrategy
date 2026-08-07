import json
import hashlib
from typing import Dict, Any, Optional
from loguru import logger
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.models import MarketNewsAnalysis
from app.services.ai_service import ai_service
from app.services.telegram_bot import telegram_bot_service

SENIOR_ANALYST_SYSTEM_PROMPT = """You are a senior financial market analyst monitoring news for its potential impact on the Indian Nifty 50 index.

For each news item (headline + summary) you receive:
1. First determine if it is genuinely relevant to Nifty 50 — meaning it touches RBI monetary policy or interest rates, Union Budget/fiscal or tax policy, global central bank decisions (US Fed, ECB), crude oil or USD/INR moves, geopolitical events affecting India or global trade, earnings or guidance from a Nifty 50 constituent company, SEBI regulatory changes, India credit rating actions, major FII/DII flow data, or elections/systemic shocks — and ignore routine PR, opinion pieces, or previously covered news with nothing new.
2. If it is NOT relevant, output ONLY a JSON object: {"relevant": false}
3. If it IS relevant, analyze it like a senior equity analyst:
   - Explain the mechanism by which it would move Nifty 50.
   - Judge whether the market has likely already priced it in.
   - Commit to a directional call (bullish/bearish/mixed/uncertain) with a confidence score rather than hedging.
   - Rate the impact magnitude conservatively (negligible/low/moderate/high/severe — reserve high/severe for genuinely exceptional events like a rate shock or war escalation).
   - Identify affected sectors and specific Nifty 50 stocks involved.
   - State the level target direction ("towards_resistance", "towards_support", or "range_bound").
   - State the time horizon ("immediate/intraday", "next session", "multi-day", or "structural").
   - State what evidence would prove your call wrong (invalidation_trigger).

Return STRICTLY a raw JSON object with NO markdown block or extra text.
JSON Schema:
{
  "relevant": true,
  "category": string,
  "impact_magnitude": "negligible" | "low" | "moderate" | "high" | "severe",
  "direction": "bullish" | "bearish" | "mixed" | "uncertain",
  "confidence": float (0.0 to 1.0),
  "level_target": "towards_resistance" | "towards_support" | "range_bound",
  "time_horizon": "immediate/intraday" | "next session" | "multi-day" | "structural",
  "affected_sectors": [string],
  "affected_stocks": [string],
  "mechanism": string,
  "invalidation_trigger": string,
  "already_priced_in": boolean,
  "recommended_action": "monitor" | "alert_low" | "alert_high" | "alert_urgent",
  "trader_summary": string (1 sentence),
  "level_advice": string (1 clear sentence on what to do at Support/Resistance levels)
}
"""

class AINewsAnalyst:
    async def analyze_and_process(
        self,
        headline: str,
        summary: str = "",
        chat_id: Optional[str] = None,
        message_id: Optional[int] = None,
        chat_username: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Evaluates news item, stores evaluation in DB, and sends simplified Telegram alert."""
        if not ai_service.is_enabled():
            logger.info("AINewsAnalyst: AI Service disabled. Skipping analysis.")
            return None

        # Build Telegram Link if chat info provided
        msg_link = None
        if chat_id and message_id:
            if chat_username:
                msg_link = f"https://t.me/{chat_username}/{message_id}"
            else:
                clean_id = str(chat_id).replace("-100", "")
                msg_link = f"https://t.me/c/{clean_id}/{message_id}"

        # Deduplication Hash
        news_key = f"{headline.strip()}:{summary.strip()}"
        news_hash = hashlib.sha256(news_key.encode("utf-8")).hexdigest()

        with SessionLocal() as db:
            existing = db.query(MarketNewsAnalysis).filter(MarketNewsAnalysis.news_hash == news_hash).first()
            if existing:
                logger.info("AINewsAnalyst: News item already processed. Skipping duplicate.")
                return None

        # Call AI LLM Service (Gemini / OpenAI / Anthropic)
        user_prompt = f"{SENIOR_ANALYST_SYSTEM_PROMPT}\n\n[NEWS ITEM TO ANALYZE]\nHeadline: {headline}\nSummary: {summary}"
        raw_resp = await ai_service.call_llm(user_prompt)

        if not raw_resp:
            logger.warning("AINewsAnalyst: LLM call returned empty response.")
            return None

        try:
            # Clean JSON formatting if wrapped in code blocks
            clean_json_str = raw_resp.strip()
            if clean_json_str.startswith("```"):
                clean_json_str = clean_json_str.split("```")[1]
                if clean_json_str.startswith("json"):
                    clean_json_str = clean_json_str[4:]
            clean_json_str = clean_json_str.strip()
            
            data = json.loads(clean_json_str)
        except Exception as e:
            logger.error(f"AINewsAnalyst: Failed to parse LLM JSON output: {e}. Raw: {raw_resp}")
            return None

        is_relevant = bool(data.get("relevant", False))

        # Save to DB
        with SessionLocal() as db:
            record = MarketNewsAnalysis(
                news_hash=news_hash,
                headline=headline,
                summary=summary,
                telegram_message_link=msg_link,
                relevant=is_relevant,
                category=data.get("category"),
                impact_magnitude=data.get("impact_magnitude"),
                direction=data.get("direction"),
                confidence=data.get("confidence"),
                level_target=data.get("level_target"),
                time_horizon=data.get("time_horizon"),
                affected_sectors=data.get("affected_sectors"),
                affected_stocks=data.get("affected_stocks"),
                mechanism=data.get("mechanism"),
                invalidation_trigger=data.get("invalidation_trigger"),
                already_priced_in=data.get("already_priced_in"),
                recommended_action=data.get("recommended_action"),
                trader_summary=data.get("trader_summary")
            )
            db.add(record)
            db.commit()

        if not is_relevant:
            logger.info("AINewsAnalyst: News item deemed irrelevant to Nifty 50.")
            return {"relevant": False}

        data["telegram_message_link"] = msg_link

        # Send Telegram Alert
        target_chat = chat_id or telegram_bot_service._chat_id
        if target_chat:
            await self._send_simple_telegram_alert(target_chat, data)

        return data

    async def _send_simple_telegram_alert(self, chat_id: str, data: Dict[str, Any]):
        """Format and dispatch simple, high-clarity Telegram alert."""
        direction = (data.get("direction") or "uncertain").lower()
        level_target = (data.get("level_target") or "range_bound").lower()

        if direction == "bullish" or level_target == "towards_resistance":
            header = "🟢 *NIFTY 50 NEWS ALERT*"
            move_text = "Moving **UP towards Resistance (R)**"
        elif direction == "bearish" or level_target == "towards_support":
            header = "🔴 *NIFTY 50 NEWS ALERT*"
            move_text = "Moving **DOWN towards Support (S)**"
        else:
            header = "🟡 *NIFTY 50 NEWS ALERT*"
            move_text = "**Range-Bound (Bouncing between S & R)**"

        bias_str = direction.upper()
        confidence_pct = int((data.get("confidence") or 0.5) * 100)
        impact = (data.get("impact_magnitude") or "moderate").upper()
        
        sectors = ", ".join(data.get("affected_sectors") or ["General Nifty 50"])
        stocks = ", ".join(data.get("affected_stocks") or [])
        stocks_str = f" ({stocks})" if stocks else ""

        what_happened = data.get("trader_summary") or data.get("mechanism") or "Significant market development."
        level_advice = data.get("level_advice") or "Monitor price action carefully at S/R levels."
        
        link_str = f"\n\n🔗 [View News Source]({data['telegram_message_link']})" if data.get("telegram_message_link") else ""

        message = (
            f"{header}\n\n"
            f"🎯 *EXPECTED MOVE*: {move_text}\n"
            f"📊 *BIAS*: **{bias_str}** (Confidence: {confidence_pct}%)\n"
            f"⚡ *IMPACT*: **{impact}**\n\n"
            f"🏭 *Target Sectors*: {sectors}{stocks_str}\n\n"
            f"💡 *WHAT HAPPENED*:\n{what_happened}\n\n"
            f"⚠️ *LEVEL TRADING ADVICE*:\n{level_advice}"
            f"{link_str}"
        )

        await telegram_bot_service._send_message(chat_id, message)

    async def fetch_and_evaluate_realtime_news(self):
        """Periodically queries Gemini Google Search Grounding for breaking Nifty 50 news."""
        if not ai_service.is_enabled():
            return

        search_prompt = (
            "Search Google for breaking market news in India published in the last 15 minutes that impacts the Nifty 50 index, "
            "RBI interest rates, Union budget, crude oil, USD/INR, or Nifty 50 constituent earnings (HDFC Bank, Reliance, ICICI, TCS, Infosys). "
            "If breaking news is found, summarize the headline and main body text. "
            "If NO breaking news is found in the last 15 minutes, output EXACTLY: NO_BREAKING_NEWS"
        )

        raw_news = await ai_service.call_llm(search_prompt)
        if not raw_news or "NO_BREAKING_NEWS" in raw_news:
            return

        headline = raw_news.split("\n")[0]
        summary = "\n".join(raw_news.split("\n")[1:]) if "\n" in raw_news else ""

        await self.analyze_and_process(headline=headline, summary=summary)


ai_news_analyst = AINewsAnalyst()

