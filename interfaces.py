from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict

import pandas as pd


@dataclass
class AllocationDecision:
    decision_date: pd.Timestamp
    target_weights: Dict[str, float]
    metadata: Dict[str, float | str] | None = None


class BaseStrategy(ABC):
    @abstractmethod
    def generate_decision(
        self,
        history_by_code: Dict[str, pd.DataFrame],
        decision_date: pd.Timestamp,
    ) -> AllocationDecision:
        """
        Return target portfolio weights using only data up to decision_date.
        """

