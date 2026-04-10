from dataclasses import dataclass


@dataclass
class BacktestConfig:
    start_date: str = "2024-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = 100000.0
    rebalance_every_n_trade_days: int = 5
    buy_fee: float = 0.0
    sell_fee: float = 0.001
    slippage_bp: float = 5.0
    confirm_trade_days: int = 1
    sellable_after_confirm_days: int = 1
    min_hold_trade_days: int = 1
