"""
settings.py — all the project’s configuration in one place.

Two different types of settings are handled differently:
  1. Secrets (API keys) — read from environment variables (.env),
     never stored in the code and never committed to Git.
  2. Strategy/backtest parameters — standard constants in the code.
     These are not secrets, but part of the logic: they must be visible in the Git history,
     so that it is possible to track how the hypothesis has changed over time.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # picks variables from .env if the file exists

# ──────────────────────────────────────────────
# Secrets
# ──────────────────────────────────────────────

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

if POLYGON_API_KEY is None:
    raise RuntimeError(
        "POLYGON_API_KEY not found."
    )


# ──────────────────────────────────────────────
# Default instrument and period
# ──────────────────────────────────────────────

SYMBOL = "SPY"

# ──────────────────────────────────────────────
# Risk management and trading costs
# ──────────────────────────────────────────────

RISK_PER_TRADE_USD   = 1000.0   # $ amount we lose if the stop is triggered (= 1R)
COMMISSION_PER_SHARE = 0.007   # $/share (one side)
