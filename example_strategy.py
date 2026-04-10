from __future__ import annotations

from typing import Dict

import pandas as pd

from interfaces import AllocationDecision, BaseStrategy


class TopKMomentumStrategy(BaseStrategy):
    """
    Public demo strategy.
    Uses only past 20-trade-day returns on the decision date.
    """

    def __init__(self, top_k: int = 2):
        self.top_k = top_k

    def generate_decision(
        self,
        history_by_code: Dict[str, pd.DataFrame],
        decision_date: pd.Timestamp,
    ) -> AllocationDecision:
        scores = {}
        for code, history in history_by_code.items():
            if len(history) < 21:
                continue
            close = history["close"]
            score = float(close.iloc[-1] / close.iloc[-21] - 1.0)
            scores[code] = score

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: self.top_k]
        if not ranked:
            return AllocationDecision(decision_date=decision_date, target_weights={}, metadata={"reason": "no_signal"})

        weight = 1.0 / len(ranked)
        targets = {code: weight for code, _ in ranked}
        return AllocationDecision(decision_date=decision_date, target_weights=targets, metadata={"top_k": len(ranked)})
