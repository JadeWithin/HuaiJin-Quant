from pathlib import Path

import numpy as np
import pandas as pd

from config_template import BacktestConfig
from example_strategy import TopKMomentumStrategy
from strict_backtester import StrictBacktester


def build_demo_prices() -> dict[str, pd.DataFrame]:
    trade_dates = pd.bdate_range("2024-01-01", "2024-06-30")
    rng = np.random.default_rng(42)
    price_data = {}

    for idx, code in enumerate(["FUND_A", "FUND_B", "FUND_C", "FUND_D"], start=1):
        drift = 0.0005 * idx
        noise = rng.normal(loc=drift, scale=0.01, size=len(trade_dates))
        close = 100 * np.cumprod(1 + noise)
        price_data[code] = pd.DataFrame({"close": close}, index=trade_dates)
    return price_data


def main() -> None:
    config = BacktestConfig(
        start_date="2024-01-15",
        end_date="2024-06-30",
        initial_capital=100000.0,
        rebalance_every_n_trade_days=5,
    )
    strategy = TopKMomentumStrategy(top_k=2)
    backtester = StrictBacktester(build_demo_prices(), strategy, config)
    history = backtester.run()
    output_dir = backtester.export_artifacts(Path("demo_output"))
    print(history.tail())
    print(f"Artifacts exported to: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
