from __future__ import annotations

import pandas as pd


def normalize_trade_calendar(index_like) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(list(index_like))).normalize().sort_values().unique()


def get_prev_trade_date(trade_calendar: pd.DatetimeIndex, current_date: pd.Timestamp):
    current = pd.Timestamp(current_date).normalize()
    idx = trade_calendar.searchsorted(current)
    if idx >= len(trade_calendar) or trade_calendar[idx] != current:
        idx -= 1
    if idx <= 0:
        return None
    return pd.Timestamp(trade_calendar[idx - 1]).normalize()


def shift_trade_date(trade_calendar: pd.DatetimeIndex, base_date: pd.Timestamp, offset: int) -> pd.Timestamp:
    current = pd.Timestamp(base_date).normalize()
    idx = trade_calendar.searchsorted(current)
    if idx >= len(trade_calendar):
        idx = len(trade_calendar) - 1
    if trade_calendar[idx] != current:
        idx = max(0, idx - 1)
    target_idx = min(max(idx + int(offset), 0), len(trade_calendar) - 1)
    return pd.Timestamp(trade_calendar[target_idx]).normalize()
