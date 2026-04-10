from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import pandas as pd

from calendar_utils import shift_trade_date


@dataclass
class Lot:
    code: str
    shares: float
    entry_price: float
    buy_date: str
    confirm_date: str
    sellable_date: str


@dataclass
class PositionState:
    cash: float
    positions: Dict[str, List[Lot]] = field(default_factory=dict)

    def market_value(self, prices: Dict[str, float]) -> float:
        total = self.cash
        for code, lots in self.positions.items():
            px = float(prices.get(code, 0.0))
            total += sum(lot.shares for lot in lots) * px
        return total

    def holding_shares(self, code: str) -> float:
        return sum(lot.shares for lot in self.positions.get(code, []))

    def sellable_shares(self, code: str, current_date: str) -> float:
        current = pd.Timestamp(current_date).normalize()
        return sum(
            lot.shares
            for lot in self.positions.get(code, [])
            if pd.Timestamp(lot.sellable_date).normalize() <= current
        )

    def buy(
        self,
        code: str,
        amount: float,
        execution_price: float,
        trade_date: pd.Timestamp,
        trade_calendar: pd.DatetimeIndex,
        confirm_days: int,
        sellable_after_confirm_days: int,
        buy_fee: float,
    ) -> None:
        if amount <= 0 or execution_price <= 0:
            return
        gross = float(amount)
        fee = gross * float(buy_fee)
        net = gross - fee
        shares = net / execution_price
        if shares <= 0 or gross > self.cash:
            return

        confirm_date = shift_trade_date(trade_calendar, trade_date, confirm_days)
        sellable_date = shift_trade_date(trade_calendar, confirm_date, sellable_after_confirm_days)

        lot = Lot(
            code=code,
            shares=shares,
            entry_price=execution_price,
            buy_date=pd.Timestamp(trade_date).strftime("%Y-%m-%d"),
            confirm_date=pd.Timestamp(confirm_date).strftime("%Y-%m-%d"),
            sellable_date=pd.Timestamp(sellable_date).strftime("%Y-%m-%d"),
        )
        self.positions.setdefault(code, []).append(lot)
        self.cash -= gross

    def sell(
        self,
        code: str,
        target_shares: float,
        execution_price: float,
        current_date: pd.Timestamp,
        sell_fee: float,
    ) -> float:
        if target_shares <= 0 or execution_price <= 0 or code not in self.positions:
            return 0.0

        remaining = float(target_shares)
        kept_lots: List[Lot] = []
        sold_shares = 0.0
        current = pd.Timestamp(current_date).normalize()

        for lot in self.positions[code]:
            if pd.Timestamp(lot.sellable_date).normalize() > current or remaining <= 0:
                kept_lots.append(lot)
                continue

            sell_now = min(lot.shares, remaining)
            leftover = lot.shares - sell_now
            sold_shares += sell_now
            remaining -= sell_now

            if leftover > 0:
                kept_lot = Lot(
                    code=lot.code,
                    shares=leftover,
                    entry_price=lot.entry_price,
                    buy_date=lot.buy_date,
                    confirm_date=lot.confirm_date,
                    sellable_date=lot.sellable_date,
                )
                kept_lots.append(kept_lot)

        gross = sold_shares * execution_price
        fee = gross * float(sell_fee)
        self.cash += gross - fee

        if kept_lots:
            self.positions[code] = kept_lots
        else:
            self.positions.pop(code, None)
        return sold_shares
