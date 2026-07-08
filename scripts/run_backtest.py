"""
run_backtest.py — entry point: runs a backtest of the gap-up strategy.

To run:
    python3 -m scripts.run_backtest
"""

from config.settings import SYMBOL
from engine.backtester import run_backtest
from analytics.metrics import calculate_stats
from analytics.report import print_trades_table, print_stats, export_trades_csv, plot_equity_curve

START_DATE = "2026-01-01"
END_DATE = "2026-05-31"


def main() -> None:
    trades = run_backtest(SYMBOL, START_DATE, END_DATE)

    if not trades:
        print("No signals found for specified period.")
        return

    print_trades_table(trades)

    stats = calculate_stats(trades)
    print_stats(stats)

    export_trades_csv(trades)
    plot_equity_curve(trades, stats, SYMBOL)


if __name__ == "__main__":
    main()
