import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from app.db.database import SessionLocal
from app.models.models import MarketNewsAnalysis
from app.services.ai_news_analyst import AINewsAnalyst

@pytest.fixture(autouse=True)
def clean_news_db():
    with SessionLocal() as db:
        db.query(MarketNewsAnalysis).delete()
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(MarketNewsAnalysis).delete()
        db.commit()

@pytest.mark.asyncio
async def test_ai_news_analyst_irrelevant():
    analyst = AINewsAnalyst()
    with patch("app.services.ai_news_analyst.ai_service") as mock_ai:
        mock_ai.is_enabled.return_value = True
        mock_ai.call_llm = AsyncMock(return_value='{"relevant": false}')
        
        res = await analyst.analyze_and_process("Random company PR release", "Company launches new product line")
        assert res == {"relevant": False}

@pytest.mark.asyncio
async def test_ai_news_analyst_relevant_bullish():
    analyst = AINewsAnalyst()
    mock_resp = '''{
      "relevant": true,
      "category": "Nifty 50 Earnings",
      "impact_magnitude": "high",
      "direction": "bullish",
      "confidence": 0.9,
      "level_target": "towards_resistance",
      "time_horizon": "next session",
      "affected_sectors": ["Banking"],
      "affected_stocks": ["HDFCBANK"],
      "mechanism": "HDFC Bank beat Q3 profit estimates.",
      "invalidation_trigger": "Profit taking at open.",
      "already_priced_in": false,
      "recommended_action": "alert_high",
      "trader_summary": "HDFC Bank Q3 beat drives index higher.",
      "level_advice": "Do not short at Resistance. Expect breakout."
    }'''

    with patch("app.services.ai_news_analyst.ai_service") as mock_ai, \
         patch("app.services.ai_news_analyst.telegram_bot_service") as mock_tg:
        mock_ai.is_enabled.return_value = True
        mock_ai.call_llm = AsyncMock(return_value=mock_resp)
        mock_tg._send_message = AsyncMock()

        res = await analyst.analyze_and_process(
            headline="HDFC Bank Q3 Net Profit jumps 14%",
            summary="NII expands significantly",
            chat_id="12345",
            message_id=99,
            chat_username="nifty_channel"
        )

        assert res["relevant"] is True
        assert res["direction"] == "bullish"
        assert res["level_target"] == "towards_resistance"
        assert res["telegram_message_link"] == "https://t.me/nifty_channel/99"
        
        # Verify simple telegram alert message sent
        assert mock_tg._send_message.called
        sent_text = mock_tg._send_message.call_args[0][1]
        assert "🟢 *NIFTY 50 NEWS ALERT*" in sent_text
        assert "Moving **UP towards Resistance (R)**" in sent_text
        assert "HDFC Bank Q3 beat drives index higher." in sent_text
        assert "https://t.me/nifty_channel/99" in sent_text

