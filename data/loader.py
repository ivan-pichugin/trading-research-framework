"""
`loader.py` is the only place in the project where interaction with Polygon.io takes place.
The idea is that neither the strategies/ nor the engine/ directories should need to know where 
the data comes from or in what format Polygon returns it. 
They receive a standard pandas.DataFrame object with columns [open, high, low, close, volume] 
and a time index in the New York time zone. 
If we want to change the data source, we’ll only need to change this file.
"""

import time
from datetime import date, timedelta

import pandas as pd
import requests

from config.settings import POLYGON_API_KEY

BASE_URL = "https://api.polygon.io/v2/aggs/ticker"


def get_bars(symbol: str, start_date: str, end_date: str, timeframe: str = "1") -> pd.DataFrame | None:
    """
    Loads one-minute bars over the period [start_date, end_date].
    timeframe: 1m, 5m, 15m bars.
    Returns a DataFrame indexed by America/New_York or None if no data is available.

    Polygon returns results page by page (next_url) — we fetch all pages,
    and handle the rate limit (status code 429) by simply waiting and retrying.
    """
    url = f"{BASE_URL}/{symbol}/range/{timeframe}/minute/{start_date}/{end_date}"
    params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": POLYGON_API_KEY}

    all_results = []
    while url:
        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 429:
            print("  Rate limit — waiting 12s...", end="\r")
            time.sleep(12)
            continue

        if response.status_code != 200:
            print(f"  Polygon error {response.status_code}: {response.text[:200]}")
            return None

        payload = response.json()
        if payload.get("status") not in ("OK", "DELAYED"):
            print(f"  Polygon status: {payload.get('status')} — {payload.get('error', '')}")
            return None

        all_results.extend(payload.get("results", []))
        url = payload.get("next_url")
        params = {"apiKey": POLYGON_API_KEY}  # next_url already contains the remaining parameters

    if not all_results:
        return None

    df = pd.DataFrame(all_results)
    df.index = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_convert("America/New_York")
    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    return df[["open", "high", "low", "close", "volume"]]


def prev_trading_day(d: date) -> date:
    """Returns the previous working day. 
    Does not take market holidays into account.
    (this is an acceptable simplification)"""
    prev = d - timedelta(days=1)
    while prev.weekday() >= 5:
        prev -= timedelta(days=1)
    return prev


def resample_ohlcv(df: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Aggregates one-minute bars into N-minute candlesticks (OHLCV)"""
    return df.resample(f"{minutes}min").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).dropna()
