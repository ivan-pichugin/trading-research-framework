"""
metrics.py — calculation of performance metrics based on a list of closed trades.

Everything in this module operates using R-units (a proportion of the risk per trade),
rather than absolute dollar amounts — this provides metrics that are independent of the size
of the deposit and allows strategies with different risk profiles to be compared.

1R = RISK_PER_TRADE_USD, which we conventionally equate to 0.5% of capital.
This is purely a convention for converting P&L into percentages — if your actual
deposit is different, change R_AS_PCT_OF_CAPITAL.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from config.settings import RISK_PER_TRADE_USD
from engine.portfolio import TradeResult

R_AS_PCT_OF_CAPITAL = 0.005 
TRADING_DAYS_PER_YEAR = 252


@dataclass
class BacktestStats:
    n_trades: int
    total_pnl_usd: float
    total_return_pct: float
    annual_return_pct: float
    max_drawdown_pct: float
    sharpe: float
    sortino: float
    calmar: float
    win_rate_pct: float
    profit_factor: float
    avg_win_pct: float
    avg_loss_pct: float
    n_wins: int
    n_losses: int
    trades_per_month: float
    avg_hold_minutes: float
    equity_curve_pct: list[float] = field(default_factory=list)


def _pnl_to_pct_of_capital(trades: list[TradeResult]) -> list[float]:
    """Converts the net_pnl of each trade into a percentage of capital via R_AS_PCT_OF_CAPITAL."""
    return [tr.net_pnl / RISK_PER_TRADE_USD * R_AS_PCT_OF_CAPITAL * 100 for tr in trades]


def _daily_returns(trades: list[TradeResult], pnls_pct: list[float]) -> np.ndarray:
    """
    Calculates a series of daily returns for the ENTIRE backtest period,
    including days with no trades (return = 0). This is important for an accurate
    calculation of the Sharpe and Sortino ratios — otherwise, volatility is underestimated.
    """
    pnl_by_date = {tr.date: pct for tr, pct in zip(trades, pnls_pct)}

    first_date = datetime.strptime(trades[0].date, "%Y-%m-%d")
    last_date = datetime.strptime(trades[-1].date, "%Y-%m-%d")

    all_days = []
    cur = first_date
    while cur <= last_date:
        if cur.weekday() < 5:
            all_days.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)

    return np.array([pnl_by_date.get(d, 0.0) for d in all_days])


def calculate_stats(trades: list[TradeResult]) -> BacktestStats | None:
    """The module’s main function: a list of trades - all metrics at a glance."""
    if not trades:
        return None

    pnls_usd = [tr.net_pnl for tr in trades]
    pnls_pct = _pnl_to_pct_of_capital(trades)

    wins = [p for p in pnls_pct if p > 0]
    losses = [p for p in pnls_pct if p <= 0]

    # ── Equity curve as a percentage of capital (starting point = 100%) ──
    equity_pct = [100.0]
    for p in pnls_pct:
        equity_pct.append(equity_pct[-1] + p)
    total_return_pct = equity_pct[-1] - 100.0

    # ── Max Drawdown ──
    peak = 100.0
    max_dd_pct = 0.0
    for eq in equity_pct[1:]:
        peak = max(peak, eq)
        max_dd_pct = min(max_dd_pct, eq - peak)

    # ── Sharpe / Sortino ratios based on daily returns (including days with zero returns) ──
    daily = _daily_returns(trades, pnls_pct)
    mean_d = daily.mean()
    std_d = daily.std(ddof=1) or 1e-9
    sharpe = (mean_d / std_d) * math.sqrt(TRADING_DAYS_PER_YEAR)

    downside = np.minimum(daily, 0.0)
    downside_std = np.sqrt(np.mean(downside ** 2))
    sortino = (mean_d / downside_std) * math.sqrt(TRADING_DAYS_PER_YEAR) if downside_std > 1e-9 else float("inf")

    # ── Calmar, trade frequency, average holding period ──
    days_span = max((datetime.strptime(trades[-1].date, "%Y-%m-%d")
                      - datetime.strptime(trades[0].date, "%Y-%m-%d")).days, 1)
    annual_return_pct = total_return_pct / days_span * TRADING_DAYS_PER_YEAR
    calmar = abs(annual_return_pct / max_dd_pct) if max_dd_pct != 0 else float("inf")
    trades_per_month = len(trades) / max(days_span / 21, 1)

    hold_minutes = []
    for tr in trades:
        try:
            delta = (datetime.strptime(tr.exit_time, "%H:%M")
                     - datetime.strptime(tr.entry_time, "%H:%M")).seconds / 60
            if delta > 0:
                hold_minutes.append(delta)
        except ValueError:
            continue
    avg_hold = sum(hold_minutes) / len(hold_minutes) if hold_minutes else 0.0

    return BacktestStats(
        n_trades=len(trades),
        total_pnl_usd=round(sum(pnls_usd), 2),
        total_return_pct=round(total_return_pct, 2),
        annual_return_pct=round(annual_return_pct, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
        sharpe=round(sharpe, 2),
        sortino=round(sortino, 2) if sortino != float("inf") else sortino,
        calmar=round(calmar, 2) if calmar != float("inf") else calmar,
        win_rate_pct=round(len(wins) / len(trades) * 100, 1),
        profit_factor=round(abs(sum(wins) / sum(losses)), 2) if sum(losses) != 0 else float("inf"),
        avg_win_pct=round(sum(wins) / len(wins), 3) if wins else 0.0,
        avg_loss_pct=round(abs(sum(losses) / len(losses)), 3) if losses else 0.0,
        n_wins=len(wins),
        n_losses=len(losses),
        trades_per_month=round(trades_per_month, 1),
        avg_hold_minutes=round(avg_hold, 1),
        equity_curve_pct=equity_pct,
    )
