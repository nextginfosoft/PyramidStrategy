"""
Gamification Quotes Registry
────────────────────────────
Maps trading events to motivational quotes from renowned traders.
Each event type has a pool of quotes; one is selected randomly per trigger.
"""

import random
from typing import Optional

# Event types that trigger quotes
ENTRY_L1 = "ENTRY_L1"
ENTRY_L2 = "ENTRY_L2"  
ENTRY_L3 = "ENTRY_L3"
TARGET_HIT = "TARGET_HIT"
SL_HIT = "SL_HIT"
SQUAREOFF = "SQUAREOFF"
ENGINE_START = "ENGINE_START"
ENGINE_STOP = "ENGINE_STOP"
LEVEL_BLOCKED = "LEVEL_BLOCKED"
POST_EXIT_FOMO = "POST_EXIT_FOMO"

# Quote format: (quote_text, author)
QUOTES: dict[str, list[tuple[str, str]]] = {
    ENTRY_L1: [
        ("The secret to being successful from a trading perspective is to have an indefatigable and undying thirst for information and knowledge.", "Paul Tudor Jones"),
        ("Every battle is won before it is fought.", "Sun Tzu"),
        ("It's not about being right or wrong. It's about how much you make when you're right and how much you lose when you're wrong.", "George Soros"),
        ("The goal of a successful trader is to make the best trades. Money is secondary.", "Alexander Elder"),
        ("In investing, what is comfortable is rarely profitable.", "Robert Arnott"),
        ("Opportunities come infrequently. When it rains gold, put out the bucket, not the thimble.", "Warren Buffett"),
    ],
    ENTRY_L2: [
        ("The trend is your friend until the end when it bends.", "Ed Seykota"),
        ("Compound interest is the eighth wonder of the world. He who understands it, earns it; he who doesn't, pays it.", "Albert Einstein"),
        ("The biggest risk is not taking any risk.", "Mark Zuckerberg"),
        ("Do not be embarrassed by your failures, learn from them and start again.", "Richard Branson"),
        ("Markets can remain irrational longer than you can remain solvent.", "John Maynard Keynes"),
        ("Add to your winners, not your losers. Cut your losses short and let your profits run.", "Jesse Livermore"),
    ],
    ENTRY_L3: [
        ("Rule No. 1: Never lose money. Rule No. 2: Never forget Rule No. 1.", "Warren Buffett"),
        ("The elements of good trading are: cutting losses, cutting losses, and cutting losses.", "Ed Seykota"),
        ("Risk comes from not knowing what you're doing.", "Warren Buffett"),
        ("It is not the strongest of the species that survives, nor the most intelligent, but the one most responsive to change.", "Charles Darwin"),
        ("You can be free. You can live and work anywhere in the world. But you need to protect your capital — it's the foundation of everything.", "Alexander Elder"),
        ("Pyramiding instructions appear on every dollar bill. Add to your winners, cut your losers.", "Jesse Livermore"),
    ],
    TARGET_HIT: [
        ("Profits are like eels — slippery. Grab them while you can.", "Henry Clews"),
        ("The stock market is filled with individuals who know the price of everything, but the value of nothing.", "Philip Fisher"),
        ("I made my money by selling too soon.", "Bernard Baruch"),
        ("Bulls make money, bears make money, pigs get slaughtered.", "Wall Street Proverb"),
        ("After a big win, the hardest thing to do is stay disciplined. That's what separates professionals.", "Mark Douglas"),
        ("Winners don't celebrate by entering another trade. They celebrate by reviewing.", "Trading Wisdom"),
        ("Well done is better than well said.", "Benjamin Franklin"),
    ],
    SL_HIT: [
        ("Losing money is the least of my troubles. A loss never bothers me after I take it. But being wrong — not taking the loss — that damages the pocketbook and the soul.", "Jesse Livermore"),
        ("The market is a device for transferring money from the impatient to the patient.", "Warren Buffett"),
        ("You must learn to lose; it is more important than learning to win.", "Mark Douglas"),
        ("In trading, you have to be defensive and aggressive at the same time. If you are not aggressive, you are not going to make money, and if you are not defensive, you are not going to keep money.", "Ray Dalio"),
        ("A loss is only a loss when you refuse to learn from it. Otherwise, it's tuition.", "Trading Wisdom"),
        ("Discipline is the bridge between goals and accomplishment.", "Jim Rohn"),
        ("The best loser is the long-term winner.", "Mark Douglas"),
        ("Take a deep breath. The market will be here tomorrow. Your capital must be too.", "Trading Wisdom"),
    ],
    SQUAREOFF: [
        ("It's not how much money you make, but how much money you keep, how hard it works for you, and how many generations you keep it for.", "Robert Kiyosaki"),
        ("Success is the sum of small efforts, repeated day in and day out.", "Robert Collier"),
        ("Review your trades like a surgeon reviews surgery. Clinically, without emotion.", "Trading Wisdom"),
        ("The single most important thing you can do at the end of a trading session is to write down what you learned.", "Brett Steenbarger"),
        ("Don't focus on making money; focus on protecting what you have.", "Paul Tudor Jones"),
    ],
    ENGINE_START: [
        ("Plan your trade, trade your plan.", "Trading Proverb"),
        ("Give me six hours to chop down a tree and I will spend the first four sharpening the axe.", "Abraham Lincoln"),
        ("What seems too high and risky to the majority generally goes higher and what seems low and cheap generally goes lower.", "William O'Neil"),
        ("Courage is resistance to fear, mastery of fear — not absence of fear.", "Mark Twain"),
        ("The market rewards patience and punishes desperation. Focus. Execute. Trust the system.", "Trading Wisdom"),
    ],
    ENGINE_STOP: [
        ("Know when to walk away. The market will always be there tomorrow.", "Trading Wisdom"),
        ("Rest is not idleness. It is the foundation of tomorrow's performance.", "John Lubbock"),
        ("Time away from the screens is not wasted time. It's an investment in your edge.", "Trading Wisdom"),
    ],
    LEVEL_BLOCKED: [
        ("There are old traders and there are bold traders, but there are very few old, bold traders.", "Ed Seykota"),
        ("The desire for constant action irrespective of underlying conditions is responsible for many losses.", "Jesse Livermore"),
        ("Patience is the key. The blocked level is protecting you from revenge trading.", "Trading Wisdom"),
        ("Not trading IS a valid trade. Sometimes the best position is no position.", "Trading Wisdom"),
    ],
    POST_EXIT_FOMO: [
        ("I never buy at the bottom and I always sell too soon.", "Baron Rothschild"),
        ("Don't try to catch the last eighth — or the first. These two are the most expensive eighths in the world.", "Jesse Livermore"),
        ("Comparison is the thief of joy — and the enemy of consistent trading.", "Trading Wisdom"),
        ("You captured your edge. The market owes you nothing more. Move on.", "Trading Wisdom"),
    ],
}


def get_quote(event_type: str) -> Optional[tuple[str, str]]:
    """Get a random quote for the given event type. Tries daily AI quotes first, falls back to static pool."""
    try:
        from app.gamification.ai_quotes import get_daily_ai_quote
        ai_quote = get_daily_ai_quote(event_type)
        if ai_quote:
            return ai_quote
    except Exception:
        pass

    pool = QUOTES.get(event_type)
    if not pool:
        return None
    return random.choice(pool)


def get_event_type_for_entry(level: str) -> str:
    """Map state machine level (L1/L2/L3) to quote event type."""
    mapping = {"L1": ENTRY_L1, "L2": ENTRY_L2, "L3": ENTRY_L3}
    return mapping.get(level, ENTRY_L1)


def get_event_emoji(event_type: str) -> str:
    """Get the emoji for a gamification event."""
    emojis = {
        ENTRY_L1: "🟢",
        ENTRY_L2: "📈",
        ENTRY_L3: "🔥",
        TARGET_HIT: "🎯",
        SL_HIT: "🛑",
        SQUAREOFF: "⏰",
        ENGINE_START: "▶️",
        ENGINE_STOP: "⏹",
        LEVEL_BLOCKED: "🚫",
        POST_EXIT_FOMO: "📊",
    }
    return emojis.get(event_type, "💡")


def get_event_label(event_type: str) -> str:
    """Get a human-readable label for the event."""
    labels = {
        ENTRY_L1: "Level 1 Entry — First Position",
        ENTRY_L2: "Level 2 Added — Pyramiding Up",
        ENTRY_L3: "Level 3 Full — Maximum Conviction",
        TARGET_HIT: "Target Hit — Profit Booked!",
        SL_HIT: "Stop Loss Hit — Loss Absorbed",
        SQUAREOFF: "Session Square-Off",
        ENGINE_START: "Engine Started — Battle Begins",
        ENGINE_STOP: "Engine Stopped — Stand Down",
        LEVEL_BLOCKED: "Level Blocked — Re-entry Denied",
        POST_EXIT_FOMO: "Post-Exit Update",
    }
    return labels.get(event_type, event_type)
