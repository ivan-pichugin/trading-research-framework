"""
report.py — displays backtest results: a table of trades, statistics, charts, and a CSV file.

It doesn’t perform any calculations itself — it takes the ready-made TradeResult and BacktestStats
and simply displays and saves them in a clear and organised way.
"""

from dataclasses import asdict

import matplotlib.pyplot as plt
import pandas as pd

from analytics.metrics import BacktestStats
from engine.portfolio import TradeResult


def print_trades_table(trades: list[TradeResult]) -> None:
    """Displays the list of trades in the console — easy to check at a glance."""
    print(
        f"\n{'Date':<12} {'Entry':>8} {'T.Entry':>6} {'Stop':>8} "
        f"{'TP':>8} {'Shares':>6} {'Exit':>8} {'T.Exit':>7} "
        f"{'Reason':>10} {'Net P&L':>9} {'%':>7}"
    )
    print("─" * 100)
    for tr in trades:
        mark = "✅" if tr.net_pnl > 0 else "❌"
        tp_display = f"{tr.take_profit:>8.2f}" if tr.take_profit else f"{'—':>8}"
        print(
            f"{mark} {tr.date:<10} {tr.entry_price:>8.2f} {tr.entry_time:>6} "
            f"{tr.stop_price:>8.2f} {tp_display} {tr.shares:>6} "
            f"{tr.exit_price:>8.2f} {tr.exit_time:>7} {tr.exit_reason:>10} "
            f"{tr.net_pnl:>+9.2f} {tr.net_pnl_pct:>+6.2f}%"
        )
    print()


def print_stats(stats: BacktestStats) -> None:
    """Prints summary statistics in blocks: return / edge / parameters."""
    if stats is None:
        print("No trade activity for the period — statistics cannot be calculated.")
        return

    width = 44

    def row(label: str, value: str) -> None:
        print(f"  {label:<28}{value:>{width - 30}}")

    print("\n" + "═" * width)
    print(f"{'PERFORMANCE':^{width}}")
    print("─" * width)
    row("Total Net P&L ($):", f"{stats.total_pnl_usd:+.2f}")
    row("Total Return:", f"{stats.total_return_pct:+.2f}%")
    row("Annual Return:", f"{stats.annual_return_pct:+.2f}%")
    row("Max Drawdown:", f"{stats.max_drawdown_pct:.2f}%")
    row("Sharpe:", f"{stats.sharpe:.2f}")
    row("Sortino:", f"{stats.sortino:.2f}" if isinstance(stats.sortino, float) else str(stats.sortino))
    row("Calmar:", f"{stats.calmar:.2f}" if isinstance(stats.calmar, float) else str(stats.calmar))
    print("─" * width)
    print(f"{'EDGE':^{width}}")
    print("─" * width)
    row("Win Rate:", f"{stats.win_rate_pct:.0f}%")
    row("Profit Factor:", f"{stats.profit_factor:.2f}" if isinstance(stats.profit_factor, float) else str(stats.profit_factor))
    row("Avg Win / Avg Loss:", f"{stats.avg_win_pct:.2f}% / {stats.avg_loss_pct:.2f}%")
    row("Wins / Losses:", f"{stats.n_wins} / {stats.n_losses}")
    print("─" * width)
    print(f"{'PARAMETERS':^{width}}")
    print("─" * width)
    row("# Trades:", f"{stats.n_trades}")
    row("Trades / Month:", f"{stats.trades_per_month:.1f}")
    row("Avg Hold:", f"{stats.avg_hold_minutes:.1f} min")
    print("═" * width + "\n")


def export_trades_csv(trades: list[TradeResult], path: str = "results/backtest_results.csv") -> None:
    """Saves trades in CSV format — handy for further analysis in Excel, pandas or a notebook."""
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)

    df = pd.DataFrame([asdict(tr) for tr in trades])
    df.to_csv(path, index=False)
    print(f"Saved → {path}")


def plot_equity_curve(trades: list[TradeResult], stats: BacktestStats, symbol: str) -> None:
    """
    Plots two separate panels sharing the same x-axis (one column per trade):
      - top:    equity curve, as a percentage of starting capital
      - bottom: per-trade P&L bars (green = win, red = loss)

    Two panels instead of one dual-axis chart, because equity moves in
    single-digit percentage points while individual trades move in
    fractions of a percent -- overlaying them on one axis made small
    trades invisible next to the equity line.
    """
    if not trades:
        return

    dates = [tr.date for tr in trades]

    # per_trade_pct[i] = equity right after trade i minus equity right before trade i,
    # i.e. exactly how much that single trade moved the curve.
    equity_before = stats.equity_curve_pct[:-1]
    equity_after = stats.equity_curve_pct[1:]
    per_trade_pct = [equity_after[i] - equity_before[i] for i in range(len(trades))]
    colors = ["#26a69a" if p > 0 else "#ef5350" for p in per_trade_pct]

    fig, (ax_equity, ax_pnl) = plt.subplots(
        2, 1, figsize=(14, 7), sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1]},
    )
    fig.patch.set_facecolor("#0d0d0d")

    # ── Top panel: equity curve ──
    ax_equity.set_facecolor("#0d0d0d")
    x_equity = range(len(stats.equity_curve_pct))  # n_trades + 1 points (includes the starting 100%)
    ax_equity.plot(x_equity, stats.equity_curve_pct, color="#f0c040", linewidth=2, zorder=5)
    ax_equity.fill_between(x_equity, stats.equity_curve_pct, 100.0, alpha=0.15, color="#f0c040", zorder=4)
    ax_equity.axhline(100, color="#555555", linewidth=0.8, linestyle="--")

    # Zoom the y-axis to the actual range of values instead of matplotlib's default
    # padding -- otherwise a realistic +0.5% move over a handful of trades looks
    # like a flat line against a 0-100+ scale.
    curve_min, curve_max = min(stats.equity_curve_pct), max(stats.equity_curve_pct)
    curve_span = max(curve_max - curve_min, 0.5)  # avoid a zero-height range if equity never moved
    pad = curve_span * 0.25
    ax_equity.set_ylim(curve_min - pad, curve_max + pad)

    ax_equity.set_ylabel("Equity (% of start)", color="#f0c040", fontsize=9)
    ax_equity.tick_params(colors="#aaaaaa")
    ax_equity.set_title(f"{symbol} — Equity Curve & Per-Trade P&L ({len(trades)} trades)",
                         color="#dddddd", fontsize=12)
    ax_equity.grid(True, color="#1e1e1e", linewidth=0.5)

    # ── Bottom panel: P&L per trade ──
    ax_pnl.set_facecolor("#0d0d0d")
    x_trades = range(len(trades))  # n_trades points, one bar per closed trade
    ax_pnl.bar(x_trades, per_trade_pct, color=colors, width=0.6)
    ax_pnl.axhline(0, color="#555555", linewidth=0.8)
    ax_pnl.set_ylabel("P&L per trade (%)", color="#aaaaaa", fontsize=9)
    ax_pnl.tick_params(colors="#aaaaaa")
    ax_pnl.grid(True, color="#1e1e1e", linewidth=0.5, axis="y")

    # Shared x-axis: equity has one extra point at the start (the "100% before
    # any trade" point), so trade dates are set on the bottom panel and line up
    # with the last n_trades points of the equity curve.
    ax_pnl.set_xticks(x_trades)
    ax_pnl.set_xticklabels(dates, rotation=45, ha="right", fontsize=7, color="#aaaaaa")

    for ax in (ax_equity, ax_pnl):
        for spine in ax.spines.values():
            spine.set_edgecolor("#2a2a2a")

    plt.tight_layout()
    plt.savefig("results/equity_curve.png", dpi=150, facecolor="#0d0d0d")
    print("Plot saved → results/equity_curve.png")
    plt.show()