"""
strategies/gap_up_break.py -- "gap-up + volume confirmation" strategy.

Logic (all candles are 1-minute, counted from regular session start 09:30):
  1. Open of candle #1 (09:30) must be ABOVE yesterday's postmarket high.
  2. Volume of candle #6 (09:35) must be GREATER than volume of candle #5 (09:34).
  3. Close of candle #6 must be ABOVE the high of candle #1.
  If all three conditions hold -- enter Long at the close price of candle #6.

Stop -- low of candle #1 (the most obvious structural level for this
strategy). Take-profit = 2R (risk multiple, same convention as the rest
of the project), set via the constant below -- adjust to your risk profile.

Function interface intentionally matches what engine/backtester.py expects:
  - find_entry_signal(day_data) -> dict | None
  - check_exit(bar, signal) -> dict | None
"""

import pandas as pd

TAKE_PROFIT_R_MULTIPLE = 2  # take_profit = entry + (entry - stop) * this multiple


def find_entry_signal(day_data: dict) -> dict | None:
    """
    day_data must contain:
      - "prev_postmarket": DataFrame, yesterday's postmarket bars
      - "regular_1m": DataFrame, today's 1-minute regular session bars

    Returns a signal dict, or None if entry conditions are not met.
    """
    prev_postmarket = day_data["prev_postmarket"]
    regular_1m = day_data["regular_1m"]

    if prev_postmarket.empty or len(regular_1m) < 6:
        return None

    postmarket_high = float(prev_postmarket["high"].max())

    candle_1 = regular_1m.iloc[0]  # 09:30
    candle_5 = regular_1m.iloc[4]  # 09:34
    candle_6 = regular_1m.iloc[5]  # 09:35

    gap_up = candle_1["open"] > postmarket_high
    volume_confirms = candle_6["volume"] > candle_5["volume"]
    breaks_high = candle_6["close"] > candle_1["high"]

    if not (gap_up and volume_confirms and breaks_high):
        return None

    entry_price = float(candle_6["close"])
    stop_price = float(candle_1["low"])

    if stop_price >= entry_price:
        return None  # safety check: stop can't be above/equal to entry

    risk = entry_price - stop_price
    take_profit = entry_price + risk * TAKE_PROFIT_R_MULTIPLE

    return {
        "entry_price": entry_price,
        "entry_time": candle_6.name,  # Timestamp -- backtester needs this to find bars AFTER entry
        "stop_price": stop_price,
        "take_profit": take_profit,
    }


def check_exit(bar: pd.Series, signal: dict) -> dict | None:
    """
    Checks a single bar after entry: did it hit stop or take-profit.
    If both levels are hit within the same bar -- conservatively assume
    the stop triggered first (we don't know the real intra-bar price path).
    """
    hit_stop = bar["low"] <= signal["stop_price"]
    hit_take_profit = bar["high"] >= signal["take_profit"]

    if hit_stop:
        return {"exit_price": signal["stop_price"], "reason": "stop"}
    if hit_take_profit:
        return {"exit_price": signal["take_profit"], "reason": "take_profit"}
    return None