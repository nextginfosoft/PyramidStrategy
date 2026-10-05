"""Option pricing model, minute alignment, option-history capture, and how the
backtest workflow labels its data sources (real recorded Kite prices vs the
Black-Scholes model). All ported modules (minute_series, option_pricing,
option_history) are byte-identical to DestinyAutoPilot's, so these tests
mirror its coverage for them."""
import math
from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.backtest import router
from app.api.routes.session import require_auth
from app.core.time_rules import IST, get_expiry_date
from app.db.database import Base, get_db
from app.models.models import OptionMinutePrices, User
from app.services import option_history
from app.services.backtesting import run_backtest_workflow
from app.services.minute_series import (
    MINUTES_PER_DAY,
    NIFTY_SPOT_TOKEN,
    align_minute_closes,
    trim_to_data,
)
from app.services.option_history import (
    backfill_range,
    candidate_contracts,
    capture_day,
    load_option_prices,
    recorded_symbol_counts,
    weekdays_between,
)
from app.services.option_pricing import (
    RISK_FREE_RATE,
    bs_price,
    model_premium,
    years_to_expiry,
)

MONDAY = date(2026, 9, 21)


def _candle(day: date, hhmm: str, close: float):
    h, m = map(int, hhmm.split(":"))
    return {"date": IST.localize(datetime(day.year, day.month, day.day, h, m)), "close": close}


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class FakeKite:
    """Just enough of KiteService for the history/backtest code."""

    def __init__(self, nifty=None, options=None, tokens=None, authenticated=True):
        self.nifty = nifty if nifty is not None else []
        self.options = options or {}  # token -> candles (or an Exception to raise)
        self.tokens = tokens or {}    # symbol -> token
        self.authenticated = authenticated
        self._kite = self
        self.history_calls = []

    def is_authenticated(self):
        return self.authenticated

    def validate_token(self):
        return True

    def get_instrument_token(self, symbol):
        return self.tokens.get(symbol)

    def historical_data(self, instrument_token, from_date, to_date, interval):
        self.history_calls.append(instrument_token)
        if instrument_token == NIFTY_SPOT_TOKEN:
            return self.nifty
        result = self.options.get(instrument_token, [])
        if isinstance(result, Exception):
            raise result
        return result


class TestOptionPricingModel:
    def test_put_call_parity_holds(self):
        spot, strike, t, iv = 24100.0, 24150.0, 0.02, 0.14
        call = bs_price("CE", spot, strike, t, iv)
        put = bs_price("PE", spot, strike, t, iv)

        assert call - put == pytest.approx(spot - strike * math.exp(-RISK_FREE_RATE * t), abs=1e-6)

    def test_price_rises_with_volatility(self):
        assert bs_price("PE", 24100, 24150, 0.02, 0.25) > bs_price("PE", 24100, 24150, 0.02, 0.10)

    def test_a_put_gains_as_spot_falls_and_a_call_as_it_rises(self):
        assert bs_price("PE", 24000, 24150, 0.02, 0.14) > bs_price("PE", 24100, 24150, 0.02, 0.14)
        assert bs_price("CE", 24200, 23850, 0.02, 0.14) > bs_price("CE", 24100, 23850, 0.02, 0.14)

    def test_an_option_is_worth_at_least_its_intrinsic_value(self):
        assert bs_price("PE", 24000, 24150, 0.02, 0.14) >= 150 - 1e-6
        assert bs_price("CE", 24200, 23850, 0.02, 0.14) >= 350 - 1e-6

    def test_at_expiry_only_intrinsic_value_is_left(self):
        assert bs_price("PE", 24000, 24150, 0.0, 0.14) == 150
        assert bs_price("CE", 24000, 24150, 0.0, 0.14) == 0

    def test_time_decay_makes_the_same_option_cheaper_later_in_the_day(self):
        expiry = date(2026, 9, 22)
        morning = model_premium("PE", 24100, 24150, expiry, MONDAY, 10)
        afternoon = model_premium("PE", 24100, 24150, expiry, MONDAY, 300)

        assert afternoon < morning

    def test_years_to_expiry_counts_from_the_bar_to_the_1530_expiry(self):
        # Monday 9:15 -> Tuesday 15:30 is 30h15m
        assert years_to_expiry(date(2026, 9, 22), MONDAY, 0) == pytest.approx(30.25 / (24 * 365))

    def test_premium_is_on_the_exchange_tick_and_never_zero(self):
        deep_otm = model_premium("PE", 24500, 24150, date(2026, 9, 22), MONDAY, 370)
        assert deep_otm >= 0.05
        assert round(deep_otm / 0.05) * 0.05 == pytest.approx(deep_otm)


class TestMinuteSeries:
    def test_candles_land_in_their_minute_slot_and_gaps_carry_forward(self):
        closes = align_minute_closes([
            _candle(MONDAY, "09:15", 100.0),
            _candle(MONDAY, "09:18", 110.0),
        ])

        assert closes[0:4] == [100.0, 100.0, 100.0, 110.0]

    def test_slots_after_the_last_candle_stay_empty(self):
        closes = align_minute_closes([_candle(MONDAY, "09:15", 100.0), _candle(MONDAY, "09:17", 105.0)])

        assert closes[2] == 105.0
        assert closes[3] is None and closes[MINUTES_PER_DAY - 1] is None

    def test_slots_before_the_first_candle_stay_empty_unless_backfilled(self):
        records = [_candle(MONDAY, "09:17", 105.0)]

        assert align_minute_closes(records)[:3] == [None, None, 105.0]
        assert align_minute_closes(records, backfill_leading=True)[:3] == [105.0, 105.0, 105.0]

    def test_timestamps_in_another_timezone_are_read_as_ist(self):
        utc_0345 = {"date": datetime(2026, 9, 21, 3, 45, tzinfo=timezone.utc), "close": 99.0}  # 09:15 IST

        assert align_minute_closes([utc_0345])[0] == 99.0

    def test_candles_outside_the_session_are_ignored(self):
        closes = align_minute_closes([_candle(MONDAY, "09:00", 1.0), _candle(MONDAY, "15:30", 2.0)])

        assert all(c is None for c in closes)

    def test_trim_to_data_drops_the_unfilled_tail(self):
        closes = align_minute_closes([_candle(MONDAY, "09:15", 100.0), _candle(MONDAY, "09:16", 101.0)])

        assert trim_to_data(closes) == [100.0, 101.0]


class TestCandidateContracts:
    def test_covers_every_strike_the_atm_rule_can_pick_across_the_days_range(self):
        contracts = candidate_contracts([24000.0, 24120.0], MONDAY)

        by_side = {s: sorted(c["strike"] for c in contracts if c["side"] == s) for s in ("PE", "CE")}
        # ATM runs 24000..24100: PE = ATM+50, CE = ATM-50
        assert by_side["PE"] == [24050, 24100, 24150]
        assert by_side["CE"] == [23950, 24000, 24050]
        assert {c["expiry"] for c in contracts} == {get_expiry_date(MONDAY)}

    def test_symbols_are_unique_and_capped(self):
        contracts = candidate_contracts([20000.0, 28000.0], MONDAY)  # absurd range

        symbols = [c["symbol"] for c in contracts]
        assert len(symbols) == len(set(symbols)) <= option_history.MAX_SYMBOLS_PER_DAY


class TestCaptureDay:
    def _kite(self, missing_tokens=(), option_candles=None, nifty=None):
        nifty = nifty if nifty is not None else [
            _candle(MONDAY, "09:15", 24000.0), _candle(MONDAY, "09:16", 24120.0),
        ]
        contracts = candidate_contracts([24000.0, 24120.0], MONDAY)
        tokens = {c["symbol"]: 5000 + i for i, c in enumerate(contracts)}
        for symbol in missing_tokens:
            tokens.pop(symbol)
        candles = option_candles if option_candles is not None else [
            _candle(MONDAY, "09:15", 100.0), _candle(MONDAY, "09:18", 110.0),
        ]
        return FakeKite(nifty=nifty, options={t: candles for t in tokens.values()}, tokens=tokens), contracts

    def test_stores_every_candidate_contract_aligned_to_the_minute(self, session_factory):
        kite, contracts = self._kite()

        result = capture_day(kite, MONDAY, session_factory=session_factory, request_gap=0)

        assert result["status"] == "ok" and result["saved"] == len(contracts) == 6
        with session_factory() as db:
            prices = load_option_prices(db, MONDAY)
            assert set(prices) == {c["symbol"] for c in contracts}
            any_series = next(iter(prices.values()))
            assert any_series[0:4] == [100.0, 100.0, 100.0, 110.0]
            row = db.query(OptionMinutePrices).first()
            assert row.trade_date == MONDAY and row.expiry == get_expiry_date(MONDAY)

    def test_a_second_run_does_not_refetch_what_is_stored(self, session_factory):
        kite, contracts = self._kite()
        capture_day(kite, MONDAY, session_factory=session_factory, request_gap=0)
        calls_after_first = len(kite.history_calls)

        second = capture_day(kite, MONDAY, session_factory=session_factory, request_gap=0)

        assert second["saved"] == 0 and second["skipped"] == len(contracts)
        assert len(kite.history_calls) == calls_after_first + 1  # only the NIFTY spot call

    def test_force_refreshes_stored_rows_in_place(self, session_factory):
        kite, _ = self._kite()
        capture_day(kite, MONDAY, session_factory=session_factory, request_gap=0)
        kite2, _ = self._kite(option_candles=[_candle(MONDAY, "09:15", 200.0)])

        result = capture_day(kite2, MONDAY, session_factory=session_factory, request_gap=0, force=True)

        assert result["saved"] == 6
        with session_factory() as db:
            assert db.query(OptionMinutePrices).count() == 6
            assert next(iter(load_option_prices(db, MONDAY).values()))[0] == 200.0

    def test_contracts_kite_no_longer_lists_are_reported_missing_not_invented(self, session_factory):
        contracts = candidate_contracts([24000.0, 24120.0], MONDAY)
        gone = [contracts[0]["symbol"], contracts[1]["symbol"]]
        kite, _ = self._kite(missing_tokens=gone)

        result = capture_day(kite, MONDAY, session_factory=session_factory, request_gap=0)

        assert result["saved"] == 4 and sorted(result["missing"]) == sorted(gone)
        with session_factory() as db:
            assert not set(gone) & set(load_option_prices(db, MONDAY))

    def test_a_contract_with_no_candles_is_missing(self, session_factory):
        kite, _ = self._kite(option_candles=[])

        result = capture_day(kite, MONDAY, session_factory=session_factory, request_gap=0)

        assert result["saved"] == 0 and len(result["missing"]) == 6

    def test_one_failing_contract_does_not_stop_the_rest(self, session_factory):
        kite, contracts = self._kite()
        kite.options[5000] = RuntimeError("rate limited")

        result = capture_day(kite, MONDAY, session_factory=session_factory, request_gap=0)

        assert result["saved"] == 5 and result["missing"] == [contracts[0]["symbol"]]

    def test_nothing_is_recorded_when_there_is_no_nifty_history(self, session_factory):
        kite, _ = self._kite(nifty=[])

        result = capture_day(kite, MONDAY, session_factory=session_factory, request_gap=0)

        assert result["status"] == "no_nifty_data"
        with session_factory() as db:
            assert db.query(OptionMinutePrices).count() == 0

    def test_a_nifty_history_error_is_reported_not_raised(self, session_factory):
        kite, _ = self._kite()
        kite.options = {}
        kite.historical_data = lambda **kw: (_ for _ in ()).throw(RuntimeError("boom"))

        result = capture_day(kite, MONDAY, session_factory=session_factory, request_gap=0)

        assert result["status"] == "error"

    def test_backfill_walks_the_weekdays_and_counts_per_day(self, session_factory):
        kite, _ = self._kite()
        saturday, monday_after = date(2026, 9, 19), date(2026, 9, 21)

        results = backfill_range(
            kite, saturday, monday_after, session_factory=session_factory, request_gap=0
        )

        assert [r["date"] for r in results] == ["2026-09-21"]
        assert weekdays_between(date(2026, 9, 18), date(2026, 9, 22)) == [
            date(2026, 9, 18), date(2026, 9, 21), date(2026, 9, 22),
        ]
        with session_factory() as db:
            assert recorded_symbol_counts(db, saturday, monday_after) == {MONDAY: 6}


def _nifty_day(prices, day=MONDAY):
    return [
        _candle(day, f"{(555 + i) // 60:02d}:{(555 + i) % 60:02d}", p) for i, p in enumerate(prices)
    ]


class TestWorkflowDataSources:
    """A day's NIFTY path: 24090 -> 24100 (PE entry at 10:01) -> 24070, then flat."""

    PATH = [24000.0] * 45 + [24090.0, 24100.0, 24070.0] + [24070.0] * (MINUTES_PER_DAY - 48)
    CONFIG = {
        "r1": 24100, "s1": 23900, "target_points": 30, "sl_points": 10,
        "ratchet_step_points": 10, "lot_size": 75, "squareoff_time": "15:20",
        "strategy_type": "DESTINY",
    }
    PE_SYMBOL = next(
        c["symbol"] for c in candidate_contracts([24000.0, 24100.0], MONDAY) if c["strike"] == 24150 and c["side"] == "PE"
    )

    def _store_pe_series(self, session_factory):
        series = [None] * MINUTES_PER_DAY
        for i in range(MINUTES_PER_DAY):
            series[i] = 100.0 - 0.5 * (self.PATH[i] - 24100.0)
        with session_factory() as db:
            db.add(OptionMinutePrices(
                trade_date=MONDAY, symbol=self.PE_SYMBOL, side="PE", strike=24150,
                expiry=get_expiry_date(MONDAY), closes=series,
            ))
            db.commit()

    @pytest.mark.asyncio
    async def test_real_nifty_and_recorded_option_prices_give_real_premiums(self, session_factory):
        self._store_pe_series(session_factory)
        kite = FakeKite(nifty=_nifty_day(self.PATH))

        with session_factory() as db:
            result = await run_backtest_workflow(kite, "2026-09-21", "2026-09-21", self.CONFIG, db=db)

        primary = result["primary"]
        assert [t["premium_source"] for t in primary["trades"]] == ["REAL"]
        assert primary["trades"][0]["entry_price"] == 100.0
        quality = primary["data_quality"]
        assert quality["days"] == [
            {"date": "2026-09-21", "spot_source": "REAL", "option_symbols_recorded": 1}
        ]
        assert quality["mock_spot_days"] == 0
        assert quality["trades_by_premium_source"] == {"REAL": 1, "MODEL": 0}

    @pytest.mark.asyncio
    async def test_real_nifty_without_recorded_options_uses_the_model_and_says_so(self, session_factory):
        kite = FakeKite(nifty=_nifty_day(self.PATH))

        with session_factory() as db:
            result = await run_backtest_workflow(kite, "2026-09-21", "2026-09-21", self.CONFIG, db=db)

        primary = result["primary"]
        assert [t["premium_source"] for t in primary["trades"]] == ["MODEL"]
        assert primary["data_quality"]["trades_by_premium_source"] == {"REAL": 0, "MODEL": 1}
        assert primary["data_quality"]["days"][0]["option_symbols_recorded"] == 0

    @pytest.mark.asyncio
    async def test_simulated_nifty_days_are_flagged_and_never_paired_with_recorded_options(self, session_factory):
        self._store_pe_series(session_factory)
        kite = FakeKite(authenticated=False)  # no Kite: NIFTY falls back to the random walk

        with session_factory() as db:
            result = await run_backtest_workflow(kite, "2026-09-21", "2026-09-21", self.CONFIG, db=db)

        quality = result["primary"]["data_quality"]
        assert quality["mock_spot_days"] == 1
        assert quality["days"][0]["spot_source"] == "MOCK"
        assert quality["days"][0]["option_symbols_recorded"] == 0  # stored prices deliberately not used
        assert all(t["premium_source"] == "MODEL" for t in result["primary"]["trades"])

    @pytest.mark.asyncio
    async def test_a_partly_missing_nifty_day_is_aligned_by_time_not_by_position(self, session_factory):
        # No candles between 09:16 and 09:20: a positional read would shift every later bar.
        candles = [_candle(MONDAY, "09:15", 24000.0), _candle(MONDAY, "09:21", 24000.0)]
        candles += [_candle(MONDAY, "10:00", 24090.0), _candle(MONDAY, "10:01", 24100.0)]
        candles += [_candle(MONDAY, "10:02", 24070.0), _candle(MONDAY, "15:29", 24070.0)]
        kite = FakeKite(nifty=candles)

        with session_factory() as db:
            result = await run_backtest_workflow(kite, "2026-09-21", "2026-09-21", self.CONFIG, db=db)

        assert [t["entry_time"] for t in result["primary"]["trades"]] == ["10:01:00"]

    @pytest.mark.asyncio
    async def test_comparison_configs_are_replayed_with_the_same_data(self, session_factory):
        self._store_pe_series(session_factory)
        kite = FakeKite(nifty=_nifty_day(self.PATH))
        alt = {**self.CONFIG, "name": "Wide SL", "sl_points": 40}

        with session_factory() as db:
            result = await run_backtest_workflow(
                kite, "2026-09-21", "2026-09-21", self.CONFIG, compare_configs=[alt], db=db
            )

        assert result["comparisons"][0]["name"] == "Wide SL"
        assert result["comparisons"][0]["summary"]["total_trades"] == 1


class TestOptionHistoryRoutes:
    @pytest.fixture
    def db_session(self, session_factory):
        db = session_factory()
        yield db
        db.close()

    @pytest.fixture
    def client(self, db_session):
        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[require_auth] = lambda: User(id=1, username="t@example.com")
        return TestClient(app)

    def test_coverage_lists_each_weekday_with_its_recorded_contract_count(self, client, db_session):
        db_session.add(OptionMinutePrices(
            trade_date=MONDAY, symbol="X", side="PE", strike=24150,
            expiry=date(2026, 9, 22), closes=[1.0] * MINUTES_PER_DAY,
        ))
        db_session.commit()

        resp = client.get("/api/backtest/option-history", params={"start_date": "2026-09-18", "end_date": "2026-09-22"})

        assert resp.status_code == 200
        assert resp.json()["days"] == [
            {"date": "2026-09-18", "symbols": 0},
            {"date": "2026-09-21", "symbols": 1},
            {"date": "2026-09-22", "symbols": 0},
        ]

    def test_backfill_requires_a_logged_in_kite_session(self, client, monkeypatch):
        monkeypatch.setattr(
            "app.api.routes.backtest.get_user_kite_service", lambda uid: FakeKite(authenticated=False)
        )

        resp = client.post("/api/backtest/option-history/backfill", json={"start_date": "2026-09-21", "end_date": "2026-09-21"})

        assert resp.status_code == 400
        assert "Kite" in resp.json()["detail"]

    def test_backfill_refuses_a_range_longer_than_a_week_of_trading_days(self, client, monkeypatch):
        monkeypatch.setattr("app.api.routes.backtest.get_user_kite_service", lambda uid: FakeKite())

        resp = client.post("/api/backtest/option-history/backfill", json={"start_date": "2026-09-01", "end_date": "2026-09-30"})

        assert resp.status_code == 400

    def test_backfill_returns_the_per_day_results(self, client, monkeypatch):
        seen = {}

        def fake_backfill(kite, start, end):
            seen["range"] = (start, end)
            return [{"date": "2026-09-21", "status": "ok", "saved": 6, "skipped": 0, "missing": []}]

        monkeypatch.setattr("app.api.routes.backtest.get_user_kite_service", lambda uid: FakeKite())
        monkeypatch.setattr("app.api.routes.backtest.backfill_range", fake_backfill)

        resp = client.post("/api/backtest/option-history/backfill", json={"start_date": "2026-09-21", "end_date": "2026-09-21"})

        assert resp.status_code == 200
        assert resp.json()["days"][0]["saved"] == 6
        assert seen["range"] == (MONDAY, MONDAY)

    def test_bad_dates_are_a_400_not_a_crash(self, client):
        resp = client.get("/api/backtest/option-history", params={"start_date": "nope", "end_date": "2026-09-22"})
        assert resp.status_code == 400
        resp = client.get("/api/backtest/option-history", params={"start_date": "2026-09-22", "end_date": "2026-09-21"})
        assert resp.status_code == 400
