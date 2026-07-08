"""
backtester.py -- engine that runs a strategy over historical data.

Idea: this file does not contain the strategy logic itself (gap, breakout,
etc.) -- that lives in strategies/gap_up_break.py. This file only handles
the general mechanics:
  1. Slice raw 1-minute bars into sessions (postmarket/premarket/regular)
  2. Pass these slices to find_entry_signal()
  3. If there's a signal -- walk bars after entry and ask check_exit()
     whether stop/take-profit triggered
  4. Calculate P&L via portfolio.py

To test a different strategy, swap the find_entry_signal/check_exit
import for functions from your new file.
"""

from datetime import date, time, timedelta

import pandas as pd

from data.loader import get_bars, prev_trading_day, resample_ohlcv
from engine.portfolio import position_size, calculate_pnl, TradeResult
from strategies.gap_up_break import find_entry_signal, check_exit

BATCH_DAYS = 50  # how many trading days to load per Polygon request


def trading_days_in_range(start: str, end: str) -> list[date]:
    """List of weekdays between start and end (does not account for exchange holidays)."""
    days = []
    current = pd.Timestamp(start).date()
    end_date = pd.Timestamp(end).date()
    while current <= end_date:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _slice_day_sessions(df_1m: pd.DataFrame, today: date) -> dict | None:
    """
    Slices minute bars into sessions:
      - prev_postmarket: yesterday 16:00-19:59 (postmarket)
      - premarket:        today 04:00-09:29
      - regular_1m:       today 09:30-15:55, raw 1-minute bars
      - regular_5m:       same, resampled to 5 minutes

    Returns None if any of the slices is empty (no trading/no data).
    """
    yesterday = prev_trading_day(today)

    prev_pm_mask = (
        (df_1m.index.date == yesterday)
        & (df_1m.index.time >= time(16, 0))
        & (df_1m.index.time <= time(19, 59))
    )
    pre_mask = (
        (df_1m.index.date == today)
        & (df_1m.index.time >= time(4, 0))
        & (df_1m.index.time <= time(9, 29))
    )
    reg_mask = (
        (df_1m.index.date == today)
        & (df_1m.index.time >= time(9, 30))
        & (df_1m.index.time <= time(15, 55))
    )

    prev_pm_df = df_1m[prev_pm_mask]
    pre_df = df_1m[pre_mask]
    reg_df = df_1m[reg_mask]

    if prev_pm_df.empty or pre_df.empty or reg_df.empty:
        return None

    reg_5m = resample_ohlcv(reg_df, 5)
    if reg_5m.empty:
        return None

    return {
        "prev_postmarket": prev_pm_df,
        "premarket": pre_df,
        "regular_1m": reg_df,
        "regular_5m": reg_5m,
    }


def _simulate_exit(reg_1m: pd.DataFrame, signal: dict) -> tuple[float, pd.Timestamp, str]:
    """
    Walks bars AFTER entry and asks check_exit() on each one.
    If neither stop nor take-profit triggered by session end -- close the
    position at the last bar's price (end of day, "eod").
    """
    bars_after_entry = reg_1m[reg_1m.index > signal["entry_time"]]

    for ts, bar in bars_after_entry.iterrows():
        exit_info = check_exit(bar, signal)
        if exit_info is not None:
            return exit_info["exit_price"], ts, exit_info["reason"]

    return float(reg_1m["close"].iloc[-1]), reg_1m.index[-1], "eod"


def analyze_day(df_1m: pd.DataFrame, today: date) -> TradeResult | None:
    """Runs the strategy on a single day's data. Returns a trade or None."""
    day_data = _slice_day_sessions(df_1m, today)
    if day_data is None:
        return None

    signal = find_entry_signal(day_data)
    if signal is None:
        return None

    shares = position_size(signal["entry_price"], signal["stop_price"])
    exit_price, exit_time, exit_reason = _simulate_exit(day_data["regular_1m"], signal)
    gross_pnl, commission, net_pnl = calculate_pnl(signal["entry_price"], exit_price, shares)
    net_pnl_pct = round((exit_price / signal["entry_price"] - 1) * 100, 4)

    return TradeResult(
        date=today.strftime("%Y-%m-%d"),
        entry_price=round(signal["entry_price"], 4),
        entry_time=signal["entry_time"].strftime("%H:%M"),
        stop_price=round(signal["stop_price"], 4),
        take_profit=round(signal["take_profit"], 4),
        shares=shares,
        exit_price=round(exit_price, 4),
        exit_time=exit_time.strftime("%H:%M"),
        exit_reason=exit_reason,
        gross_pnl=gross_pnl,
        commission=commission,
        net_pnl=net_pnl,
        net_pnl_pct=net_pnl_pct,
    )


def run_backtest(symbol: str, start: str, end: str) -> list[TradeResult]:
    """
    Main entry point: runs the gap-up strategy on symbol over [start, end].

    Data is loaded in batches of BATCH_DAYS days to avoid hitting Polygon
    API limits in a single request for the whole period.
    """
    all_days = trading_days_in_range(start, end)
    trades: list[TradeResult] = []

    print(f"\nBacktesting {symbol}: {start} -> {end} ({len(all_days)} trading days)\n")

    i = 0
    while i < len(all_days):
        batch = all_days[i : i + BATCH_DAYS]
        load_from = prev_trading_day(batch[0]).strftime("%Y-%m-%d")
        load_to = batch[-1].strftime("%Y-%m-%d")

        print(f"  Loading {load_from} -> {load_to} ...", end="\r", flush=True)
        df_1m = get_bars(symbol, load_from, load_to, timeframe="1")

        if df_1m is None:
            print(f"  No data {load_from} -> {load_to}" + " " * 20)
            i += BATCH_DAYS
            continue

        for day in batch:
            try:
                result = analyze_day(df_1m, day)
            except Exception as e:
                print(f"  Error on {day}: {e}" + " " * 20)
                continue
            if result:
                trades.append(result)

        i += BATCH_DAYS

    print(" " * 60)
    return trades