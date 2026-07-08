"""
portfolio.py — everything with $$: position size, commissions, P&L.

This has been kept separate from the strategy and the backtester:
the logic behind ‘how many shares to buy for a given risk’ and ‘how much we paid
in commissions’ should not depend on which specific strategy generated the signal.
"""

import math
from dataclasses import dataclass

from config.settings import RISK_PER_TRADE_USD, COMMISSION_PER_SHARE


@dataclass
class TradeResult:
    """The result of a single off-market trade — everything you need for statistics and reports."""
    date: str
    entry_price: float
    entry_time: str
    stop_price: float
    take_profit: float | None
    shares: int
    exit_price: float
    exit_time: str
    exit_reason: str
    gross_pnl: float
    commission: float
    net_pnl: float
    net_pnl_pct: float


def position_size(entry_price: float, stop_price: float) -> int:
    """
    Calculates the number of shares so that, should the stop be triggered,
    the loss amounts to exactly RISK_PER_TRADE_USD (this is what is known as ‘1R’).

    We round down and guarantee a minimum of 1 share, so a very wide
    stop-loss does not result in 0 shares"""

    stop_distance = entry_price - stop_price
    if stop_distance <= 0:
        raise ValueError("stop_price must be lower than entry_price for LONG")

    return max(1, math.floor(RISK_PER_TRADE_USD / stop_distance))


def calculate_pnl(entry_price: float, exit_price: float, shares: int) -> tuple[float, float, float]:
    """
    Returns (gross_pnl, commission, net_pnl) in dollars.
    Commission is calculated for both sides of the trade (opening + closing).
    """
    gross_pnl = (exit_price - entry_price) * shares
    commission = COMMISSION_PER_SHARE * shares * 2  # round-trip
    net_pnl = gross_pnl - commission
    return round(gross_pnl, 2), round(commission, 2), round(net_pnl, 2)
