# Intraday Backtesting Pipeline

A backtesting pipeline built around one example strategy (premarket gap-up breakout). The strategy is simple on purpose — the interesting part is the architecture: clean separation between data, strategy, execution, and metrics, and a few places where the obvious way to compute something would have quietly given wrong numbers.

<img width="2100" height="1050" alt="equity_curve" src="https://github.com/user-attachments/assets/dce8e3d9-9030-4ef9-b206-4dd578432958" />

<img width="847" height="179" alt="Screenshot 2026-07-08 at 22 45 51" src="https://github.com/user-attachments/assets/75f1e5eb-f458-4a61-8e19-5ad89585382d" />


## Architecture

```
config/       — settings; secrets (API keys) read from .env, never from code
data/         — loads bars from Polygon.io, resamples timeframes
strategies/   — the trading hypothesis: signal detection and exit rules
engine/       — day-by-day backtest loop, position sizing, P&L
analytics/    — metrics (Sharpe, Sortino, Calmar…) and reporting (tables, charts, CSV)
scripts/      — entry points: run a backtest, scan for signal frequency
tests/        — unit tests on synthetic data, no network calls
```

Each layer only knows what it needs to know:

- `data/` has no idea a strategy exists.
- `strategies/` has no idea how P&L or position sizing works.
- `engine/` just runs the loop and hands results to `analytics/`.

That separation isn't decoration. It means you can read any single file in isolation, swap the strategy without touching the backtester, or swap the data source without touching anything downstream.

## Decisions worth explaining

A few places where the "obvious" approach would have quietly produced wrong or misleading numbers, and what I did instead:

**Sharpe/Sortino use every calendar day, not just trading days.** If you compute volatility only on days you traded, you understate it — the strategy looks smoother than it is. `_daily_returns()` builds a full daily series, filling non-trading days with zero, before computing either ratio.

**Stop wins if stop and take-profit are both hit in the same bar.** With 1-minute bars you don't know the true intra-bar path. Assuming take-profit hit first is optimistic and would inflate results. `check_exit()` always resolves the conflict in the stop's favor.

**P&L is expressed in R-units, not dollars.** Every trade's result is normalized against a fixed risk-per-trade before any statistic is computed. This makes win rate, profit factor, and the equity curve independent of account size — and makes it possible to compare strategies with completely different position-sizing rules.

**The equity curve and per-trade P&L are two separate panels, not one dual-axis chart.** Equity moves in single-digit percentages; individual trades move in fractions of a percent. Overlaying them on one axis made every individual trade invisible next to the equity line. Two panels, shared x-axis, was the simpler fix.

**Data loading is isolated to one file.** `loader.py` is the only place that knows Polygon's response format. Everything downstream just sees a plain DataFrame with `[open, high, low, close, volume]`. Changing data providers means touching one file, not the whole codebase.

## Example strategy: gap-up premarket breakout

`strategies/gap_up_break.py`, included as the worked example the pipeline runs on:

1. Regular session opens above yesterday's postmarket high (gap).
2. Volume of the 6th one-minute candle exceeds the 5th (confirmation).
3. Entry on the close of the 6th candle, once it closes above the high of the 1st.
4. Stop = low of the 1st candle. Take-profit = entry + 2R.
5. Exit on stop, take-profit, or end of session.

**This is not a trading recommendation** — see limitations below.

## How to run

```bash
pip install -r requirements.txt
cp .env.example .env        # add your Polygon.io API key (free tier available)

python -m scripts.scan_signals    # how often the pattern occurs, before committing to a full backtest
python -m scripts.run_backtest    # full backtest: trades, metrics, equity curve
pytest tests/                     # synthetic data, no API calls
```

## Limitations

- **No slippage model.** Commissions are accounted for; real fills at the calculated price are not guaranteed, especially on a breakout through a volatile level.
- **Simplified holiday calendar.** `prev_trading_day()` only skips weekends, not exchange holidays.
- **Single-threaded backtest loop.** Days are processed sequentially — fine for the data volumes here, but it's not built for parallel or distributed runs.

## Stack

Python, pandas, numpy, matplotlib, pytest. Data source: Polygon.io REST API.
