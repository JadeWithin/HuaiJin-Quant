from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd

from calendar_utils import get_prev_trade_date, normalize_trade_calendar
from config_template import BacktestConfig
from interfaces import BaseStrategy
from ledger import PositionState


class StrictBacktester:
    """
    Public-safe backtester focused on execution discipline rather than alpha logic.

    Core rules:
    - decision uses T-1 data
    - execution happens on T
    - positions are tracked at lot level
    - T+1 settlement constraints are respected
    """

    def __init__(
        self,
        price_data: Dict[str, pd.DataFrame],
        strategy: BaseStrategy,
        config: BacktestConfig,
    ):
        self.price_data = {code: df.copy().sort_index() for code, df in price_data.items()}
        self.strategy = strategy
        self.config = config
        self.ledger = PositionState(cash=config.initial_capital)
        self.history: List[Dict] = []
        self.trade_log: List[Dict] = []
        any_series = next(iter(self.price_data.values()))
        self.trade_calendar = normalize_trade_calendar(any_series.index)

    def _history_slice(self, decision_date: pd.Timestamp) -> Dict[str, pd.DataFrame]:
        sliced = {}
        for code, df in self.price_data.items():
            sliced[code] = df.loc[df.index <= decision_date].copy()
        return sliced

    def _execution_prices(self, trade_date: pd.Timestamp) -> Dict[str, float]:
        prices = {}
        for code, df in self.price_data.items():
            row = df.loc[df.index == trade_date]
            if row.empty:
                continue
            close = float(row.iloc[-1]["close"])
            prices[code] = close * (1.0 + self.config.slippage_bp / 10000.0)
        return prices

    def _mark_prices(self, trade_date: pd.Timestamp) -> Dict[str, float]:
        prices = {}
        for code, df in self.price_data.items():
            row = df.loc[df.index == trade_date]
            if row.empty:
                continue
            prices[code] = float(row.iloc[-1]["close"])
        return prices

    def _rebalance(self, trade_date: pd.Timestamp, target_weights: Dict[str, float], prices: Dict[str, float]) -> None:
        portfolio_value = self.ledger.market_value(prices)
        current_date_str = trade_date.strftime("%Y-%m-%d")

        for code in list(self.ledger.positions.keys()):
            target_weight = float(target_weights.get(code, 0.0))
            target_value = portfolio_value * target_weight
            current_shares = self.ledger.holding_shares(code)
            current_value = current_shares * prices.get(code, 0.0)
            excess_value = max(0.0, current_value - target_value)
            shares_to_sell = excess_value / max(prices.get(code, 0.0), 1e-12)
            sold = self.ledger.sell(
                code=code,
                target_shares=shares_to_sell,
                execution_price=prices.get(code, 0.0),
                current_date=trade_date,
                sell_fee=self.config.sell_fee,
            )
            if sold > 0:
                self.trade_log.append({
                    "trade_date": current_date_str,
                    "side": "sell",
                    "code": code,
                    "shares": sold,
                    "price": prices.get(code, 0.0),
                })

        portfolio_value = self.ledger.market_value(prices)
        for code, target_weight in target_weights.items():
            if code not in prices:
                continue
            target_value = portfolio_value * float(target_weight)
            current_value = self.ledger.holding_shares(code) * prices[code]
            gap = max(0.0, target_value - current_value)
            if gap <= 0:
                continue
            self.ledger.buy(
                code=code,
                amount=min(gap, self.ledger.cash),
                execution_price=prices[code],
                trade_date=trade_date,
                trade_calendar=self.trade_calendar,
                confirm_days=self.config.confirm_trade_days,
                sellable_after_confirm_days=self.config.sellable_after_confirm_days,
                buy_fee=self.config.buy_fee,
            )
            self.trade_log.append({
                "trade_date": current_date_str,
                "side": "buy",
                "code": code,
                "target_weight": float(target_weight),
                "price": prices[code],
            })

    def run(self) -> pd.DataFrame:
        start = pd.Timestamp(self.config.start_date).normalize()
        end = pd.Timestamp(self.config.end_date).normalize()
        active_dates = [dt for dt in self.trade_calendar if start <= pd.Timestamp(dt) <= end]

        for idx, trade_date in enumerate(active_dates):
            trade_date = pd.Timestamp(trade_date).normalize()
            decision_date = get_prev_trade_date(self.trade_calendar, trade_date)
            if decision_date is None:
                continue

            should_rebalance = idx % int(self.config.rebalance_every_n_trade_days) == 0
            prices = self._execution_prices(trade_date)
            if should_rebalance and prices:
                decision = self.strategy.generate_decision(
                    history_by_code=self._history_slice(decision_date),
                    decision_date=decision_date,
                )
                self._rebalance(trade_date, decision.target_weights, prices)

            mark_prices = self._mark_prices(trade_date)
            nav = self.ledger.market_value(mark_prices)
            self.history.append({
                "trade_date": trade_date.strftime("%Y-%m-%d"),
                "nav": nav,
                "cash": self.ledger.cash,
                "positions": {
                    code: round(self.ledger.holding_shares(code), 6) for code in self.ledger.positions
                },
            })

        return pd.DataFrame(self.history)

    def export_artifacts(self, output_dir: str | Path) -> Path:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)

        history_df = pd.DataFrame(self.history)
        trades_df = pd.DataFrame(self.trade_log)
        history_df.to_csv(output / "equity_curve.csv", index=False, encoding="utf-8-sig")
        trades_df.to_csv(output / "trade_log.csv", index=False, encoding="utf-8-sig")

        with open(output / "manifest.json", "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "config": self.config.__dict__,
                    "history_rows": int(len(history_df)),
                    "trade_rows": int(len(trades_df)),
                    "discipline": {
                        "decision": "T-1",
                        "execution": "T",
                        "lot_level_bookkeeping": True,
                        "t_plus_one_confirmation": True,
                    },
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )

        return output
