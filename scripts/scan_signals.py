"""
scan_signals.py — quick scanner: on which days there was a gap-up at all.

This is an independent tool, separate from a full backtest: it does not calculate
entries/exits/P&L, but simply shows how many times, in principle,
the pattern we are interested in occurred (a pre-market gap above yesterday’s post-market close).
It’s useful BEFORE running a full backtest — if the pattern occurs
only once every six months, there’s no point in backtesting it on a month’s worth of data.

To run:
    python -m scripts.scan_signals
"""

from datetime import time

import pandas as pd

from config.settings import SYMBOL
from data.loader import get_bars, prev_trading_day
from engine.backtester import trading_days_in_range, BATCH_DAYS

START_DATE = "2025-12-01"
END_DATE = "2025-12-31"
TIMEFRAME = "5"  


def _gap_stats_for_day(df: pd.DataFrame, today) -> dict | None:
    yesterday = prev_trading_day(today)

    pm_mask = (df.index.date == yesterday) & (df.index.time >= time(16, 0)) & (df.index.time <= time(19, 59))
    pre_mask = (df.index.date == today) & (df.index.time >= time(4, 0)) & (df.index.time <= time(9, 29))

    pm_df, pre_df = df[pm_mask], df[pre_mask]
    if pm_df.empty or pre_df.empty:
        return None

    postmarket_high = float(pm_df[["open", "close"]].max(axis=1).max())
    premarket_open = float(pre_df["open"].iloc[0])

    return {
        "postmarket_high": postmarket_high,
        "premarket_open": premarket_open,
        "gap_usd": premarket_open - postmarket_high,
        "gap_pct": (premarket_open / postmarket_high - 1) * 100,
    }


def scan(symbol: str, start: str, end: str) -> pd.DataFrame:
    all_days = trading_days_in_range(start, end)
    hits = []

    print(f"\nScanning {symbol} {start} → {end} ({len(all_days)} days, {TIMEFRAME}m)\n")

    i = 0
    while i < len(all_days):
        batch = all_days[i : i + BATCH_DAYS]
        load_from = prev_trading_day(batch[0]).strftime("%Y-%m-%d")
        load_to = batch[-1].strftime("%Y-%m-%d")

        df = get_bars(symbol, load_from, load_to, TIMEFRAME)
        if df is None:
            i += BATCH_DAYS
            continue

        for day in batch:
            stats = _gap_stats_for_day(df, day)
            if stats and stats["premarket_open"] > stats["postmarket_high"]:
                hits.append({"date": day.strftime("%Y-%m-%d"), **stats})

        i += BATCH_DAYS

    result = pd.DataFrame(hits)
    print(f"Found gap-up days: {len(hits)} from {len(all_days)}\n")
    if not result.empty:
        print(result.to_string(index=False))
    return result


if __name__ == "__main__":
    scan(SYMBOL, START_DATE, END_DATE)
