"""
test_metrics.py — verifies the calculation of metrics using simple test cases that are easy
to check manually (we do not rely solely on the fact that they ‘look OK’).
"""

from engine.portfolio import TradeResult
from analytics.metrics import calculate_stats


def _make_trade(date: str, net_pnl: float, entry_time="09:35", exit_time="09:40") -> TradeResult:
    """Helper - creates a TradeResult with the minimum number of fields required to calculate metrics."""
    return TradeResult(
        date=date,
        entry_price=100.0,
        entry_time=entry_time,
        stop_price=99.0,
        take_profit=101.7,
        shares=10,
        exit_price=100.0 + net_pnl / 10,
        exit_time=exit_time,
        exit_reason="take_profit" if net_pnl > 0 else "stop",
        gross_pnl=net_pnl,
        commission=0.0,
        net_pnl=net_pnl,
        net_pnl_pct=net_pnl / 100,
    )


def test_no_trades_returns_none():
    assert calculate_stats([]) is None


def test_win_rate_counts_wins_and_losses_correctly():
    trades = [
        _make_trade("2026-01-05", net_pnl=50.0),
        _make_trade("2026-01-06", net_pnl=-25.0),
        _make_trade("2026-01-07", net_pnl=50.0),
        _make_trade("2026-01-08", net_pnl=-25.0),
    ]
    stats = calculate_stats(trades)

    assert stats.n_trades == 4
    assert stats.n_wins == 2
    assert stats.n_losses == 2
    assert stats.win_rate_pct == 50.0


def test_all_wins_gives_positive_total_return():
    trades = [_make_trade(f"2026-01-{5 + i:02d}", net_pnl=50.0) for i in range(5)]
    stats = calculate_stats(trades)

    assert stats.total_return_pct > 0
    assert stats.max_drawdown_pct == 0.0  


def test_profit_factor_matches_manual_calculation():
    trades = [
        _make_trade("2026-01-05", net_pnl=50.0),
        _make_trade("2026-01-06", net_pnl=50.0),
        _make_trade("2026-01-07", net_pnl=-25.0),
    ]
    stats = calculate_stats(trades)

    assert stats.profit_factor == 4.0


def test_max_drawdown_is_negative_or_zero():
    trades = [
        _make_trade("2026-01-05", net_pnl=50.0),
        _make_trade("2026-01-06", net_pnl=-100.0),  # просадка после роста
        _make_trade("2026-01-07", net_pnl=20.0),
    ]
    stats = calculate_stats(trades)

    assert stats.max_drawdown_pct <= 0
