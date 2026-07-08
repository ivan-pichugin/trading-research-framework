# Trading Research Framework

A small framework for testing trading hypotheses on historical intraday data: loading bars, generating signals, simulating trades, calculating risk/return metrics.

This is a **research tool**, not a ready-made trading system. The goal of the project is to show how to test an idea honestly: without look-ahead bias, with explicit assumptions and clear limitations.

## Why this exists

I was curious whether a simple intraday pattern (premarket gap-up + level breakout) could form a workable hypothesis, and what an honest process of testing such an idea actually looks like — from loading data to computing statistics. This repository is the result of that process, structured so it can be reused for other hypotheses.

## Architecture

config/       — settings; secrets (API keys) are read from .env, never stored in code
data/         — loads bars from Polygon.io, resamples timeframes
strategies/   — trading hypothesis logic: signal detection and exit rules
engine/       — backtester (day-by-day loop) and portfolio (position sizing, commissions, P&L)
analytics/    — metrics (Sharpe, Sortino, Calmar, etc.) and reports (tables, charts, CSV)
scripts/      — entry points: run a backtest, exploratory signal scanner
tests/        — unit tests for metrics and strategy logic (synthetic data, no network)

The separation is simple: `data/` knows nothing about the strategy, `strategies/` knows nothing about where the data comes from or how P&L is calculated, and `engine/` just runs the strategy day by day and passes the result to `analytics/`. Each file can be read and understood on its own, without holding the whole project in your head at once.

## Example strategy: Gap-Up Premarket Breakout

`strategies/gap_up_break.py` is a simple example with two functions: `find_entry_signal()` looks for the setup, `check_exit()` checks whether it's time to close the position.

1. Regular session opens above yesterday's postmarket high (gap)
2. Volume confirmation: 6th one-minute candle's volume must exceed the 5th candle's volume
3. Entry: close of the 6th one-minute candle, once it closes above the high of the 1st candle
4. Stop: low of the breakout candle (candle #1). Take-profit = `entry + R × 2`, where `R` is the risk per trade
5. Exit: take-profit, stop, or end of session

**This is not a trading recommendation.** Parameters have not been optimized on a broad sample of tickers and periods — see "Limitations" below.

## How to run

```bash
pip install -r requirements.txt
cp .env.example .env        # add your Polygon.io API key (free tier available)

python -m scripts.scan_signals    # exploratory: how often the gap pattern even occurs
python -m scripts.run_backtest    # full backtest: trades, metrics, equity curve
pytest tests/                     # tests on synthetic data, no API calls
```

## Metrics

All P&L is converted into R-units (risk per trade = 1R), which allows:
- comparing strategies with different account sizes,
- computing Sharpe/Sortino on daily returns **including days with no trades** — otherwise volatility is underestimated and the metrics look better than they actually are.

## Limitations (honestly)

This is an important part of the project — without it, a backtest reads like marketing rather than research:

- **Single ticker, short period.** The example in this README is tested on SPY over a few weeks — this is hypothesis exploration, not a statistically significant sample. Real conclusions would need months/years of data and several instruments.
- **No slippage model.** Commissions are accounted for, but real execution at the calculated price isn't guaranteed, especially on a breakout through volatile levels.
- **Simplified holiday calendar.** `prev_trading_day()` only accounts for weekends, not exchange holidays — dates around holidays may be slightly off.
- **One bar = one decision.** The strategy doesn't account for what might have happened *inside* a given bar (when stop and take-profit are both hit within the same bar, it's resolved conservatively — the stop is assumed to have triggered first).
- **Overfitting risk.** Parameters (TP_R_MULTIPLE, gap filter) were chosen intuitively during exploration, not through formal optimization/walk-forward testing — so there's a risk they simply fit this particular data period.

## Stack

Python, pandas, numpy, matplotlib, pytest. Data source: Polygon.io REST API.