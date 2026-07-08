"""
test_strategy.py -- checks strategies/gap_up_break.py against synthetic data.

Data is built by hand instead of loaded from Polygon -- tests must be
fast, deterministic, and not depend on network/API keys.
"""

import pandas as pd

from strategies.gap_up_break import find_entry_signal, check_exit


def _make_bars(rows: list[tuple], freq: str = "1min", start: str = "2026-01-05 09:30") -> pd.DataFrame:
    """Helper: builds an OHLCV DataFrame from a list of (open, high, low, close, volume) tuples."""
    index = pd.date_range(start=start, periods=len(rows), freq=freq, tz="America/New_York")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=index)


def _make_regular_session(candle_1: tuple, candle_5: tuple, candle_6: tuple) -> pd.DataFrame:
    """Helper: assembles 6 regular-session bars where only candles 1, 5, 6 matter.
    Candles 2, 3, 4 are filled with neutral values -- the strategy doesn't read them."""
    filler = (100, 100.5, 99.5, 100, 500)
    return _make_bars([candle_1, filler, filler, filler, candle_5, candle_6])


def test_no_gap_returns_no_signal():
    """If open of candle 1 is NOT above the postmarket high -- no signal should fire."""
    prev_pm = _make_bars([(100, 100.5, 99.5, 100, 1000)])
    reg_1m = _make_regular_session(
        candle_1=(99, 99.5, 98.5, 99, 500),   # open 99 < postmarket_high 100.5
        candle_5=(100, 101, 99.5, 100.5, 1000),
        candle_6=(100.5, 101.5, 100, 101, 2000),
    )

    day_data = {"prev_postmarket": prev_pm, "regular_1m": reg_1m}

    assert find_entry_signal(day_data) is None


def test_volume_not_confirming_is_filtered_out():
    """Gap exists, but volume of candle 6 is NOT greater than volume of candle 5 -- no signal."""
    prev_pm = _make_bars([(100, 100.5, 99.5, 100, 1000)])
    reg_1m = _make_regular_session(
        candle_1=(102, 103, 101.5, 102.5, 500),   # open 102 > postmarket_high 100.5 -- gap exists
        candle_5=(103, 104, 102.5, 103.5, 2000),  # volume 2000
        candle_6=(103.5, 104.5, 103, 104, 1500),  # volume 1500 < 2000 -- doesn't confirm
    )

    day_data = {"prev_postmarket": prev_pm, "regular_1m": reg_1m}

    assert find_entry_signal(day_data) is None


def test_close_not_breaking_high1_is_filtered_out():
    """Gap + volume are fine, but close of candle 6 is NOT above high of candle 1 -- no signal."""
    prev_pm = _make_bars([(100, 100.5, 99.5, 100, 1000)])
    reg_1m = _make_regular_session(
        candle_1=(102, 103, 101.5, 102.5, 500),   # high of candle 1 = 103
        candle_5=(102, 102.5, 101, 102, 1000),
        candle_6=(102, 102.8, 101.5, 102.5, 1500),  # close 102.5 < high1 103
    )

    day_data = {"prev_postmarket": prev_pm, "regular_1m": reg_1m}

    assert find_entry_signal(day_data) is None


def test_valid_setup_generates_signal_with_correct_entry_and_stop():
    """All three conditions are met -- signal should fire with correct entry/stop/take."""
    prev_pm = _make_bars([(100, 100.5, 99.5, 100, 1000)])
    reg_1m = _make_regular_session(
        candle_1=(102, 103, 101.5, 102.5, 500),   # open 102 > pm_high 100.5; high1 = 103; low1 = 101.5
        candle_5=(103, 103.5, 102.5, 103, 1000),  # volume 1000
        candle_6=(103, 104, 102.8, 103.8, 1500),  # volume 1500 > 1000; close 103.8 > high1 103
    )

    day_data = {"prev_postmarket": prev_pm, "regular_1m": reg_1m}

    signal = find_entry_signal(day_data)

    assert signal is not None
    assert signal["entry_price"] == 103.8   # close of candle 6
    assert signal["stop_price"] == 101.5    # low of candle 1
    assert signal["take_profit"] > signal["entry_price"]


def test_stop_above_entry_is_rejected():
    """
    Safety check against an invalid signal: if low of candle 1 were above
    or equal to the entry price, no signal should be created.
    """
    prev_pm = _make_bars([(100, 100.5, 99.5, 100, 1000)])
    reg_1m = _make_regular_session(
        candle_1=(102, 103, 104, 102.5, 500),     # low (104) above close of candle 6 -- unrealistic in real data, but checks the safety guard
        candle_5=(103, 103.5, 102.5, 103, 1000),
        candle_6=(103, 104, 102.8, 103.8, 1500),
    )

    day_data = {"prev_postmarket": prev_pm, "regular_1m": reg_1m}

    assert find_entry_signal(day_data) is None


def test_check_exit_triggers_stop_before_take_profit_when_both_hit():
    """If both stop and take-profit are hit within the same bar -- stop should win (conservative)."""
    signal = {"entry_price": 100.0, "stop_price": 99.0, "take_profit": 101.7}
    bar = pd.Series({"open": 100.5, "high": 102, "low": 98.5, "close": 101})  # hits both levels

    exit_info = check_exit(bar, signal)

    assert exit_info is not None
    assert exit_info["reason"] == "stop"
    assert exit_info["exit_price"] == 99.0


def test_check_exit_returns_none_when_neither_level_hit():
    """If the bar doesn't touch stop or take-profit -- keep holding the position (None)."""
    signal = {"entry_price": 100.0, "stop_price": 99.0, "take_profit": 101.7}
    bar = pd.Series({"open": 100.2, "high": 100.8, "low": 99.5, "close": 100.5})

    assert check_exit(bar, signal) is None