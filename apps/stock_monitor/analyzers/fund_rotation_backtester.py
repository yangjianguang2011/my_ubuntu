"""
Fund rotation backtester.

This module is intentionally standalone: it reuses fund_data_fetcher for fund
NAV history, then performs monthly ETF/fund rotation backtests locally. It does
not depend on the web app.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    from config import setup_logger
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from config import setup_logger

logger = setup_logger(__name__)

try:
    from ..data_fetchers.fund_data_fetcher import (
        SELECTED_FUND_LIST,
        get_fund_daily_data,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from stock_monitor.data_fetchers.fund_data_fetcher import (
        SELECTED_FUND_LIST,
        get_fund_daily_data,
    )


DEFAULT_BENCHMARKS = ["510310"]

THEME_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("semiconductor", ("半导体", "芯片", "集成电路", "科创芯片", "科创半导体")),
    ("ai_software", ("人工智能", "AI", "软件", "云计算", "信创", "信息技术", "计算机")),
    ("robotics", ("机器人", "智能制造", "工业软件")),
    ("defense", ("军工", "国防", "航天", "航空")),
    ("energy", ("煤炭", "石油", "能源", "新能源", "光伏", "储能", "电池", "锂电")),
    ("materials", ("有色", "钢铁", "稀土", "矿业", "建材", "材料", "资源", "化工")),
    ("finance", ("证券", "券商", "银行", "金融", "保险", "地产", "房地产")),
    ("consumer", ("消费", "食品", "酒", "家电", "旅游", "影视", "传媒")),
    ("healthcare", ("医疗", "医药", "创新药", "生物", "疫苗", "中药")),
    ("communication", ("通信", "5G", "电信", "物联网")),
    ("agriculture", ("农业", "农牧", "养殖", "粮食", "畜牧")),
    ("transport", ("交通", "物流", "交运")),
    ("broad_index", ("沪深300", "中证500", "A50", "MSCI", "红利", "价值", "央企")),
]


@dataclass(frozen=True)
class RotationConfig:
    name: str = "multi_momentum"
    lookback_weights: Tuple[Tuple[int, float], ...] = ((63, 0.5), (126, 0.3), (252, 0.2))
    top_n: int = 5
    buffer_rank: int = 10
    max_per_theme: int = 2
    absolute_momentum_window: int = 63
    absolute_momentum_threshold: float = 0.0
    use_absolute_momentum: bool = True
    volatility_window: int = 63
    volatility_penalty: float = 0.0
    transaction_fee: float = 0.001
    slippage: float = 0.0005
    initial_capital: float = 100000.0
    benchmark_symbols: Tuple[str, ...] = tuple(DEFAULT_BENCHMARKS)


@dataclass
class BacktestResult:
    config: Dict
    summary: Dict
    benchmark_summary: Dict[str, Dict]
    equity_curve: List[Dict]
    rebalances: List[Dict]


class FundRotationBacktester:
    def __init__(
        self,
        funds: Optional[Sequence[Dict]] = None,
        benchmarks: Optional[Sequence[str]] = None,
    ):
        self.funds = list(funds or SELECTED_FUND_LIST)
        self.benchmarks = tuple(benchmarks or DEFAULT_BENCHMARKS)

    def run_backtest(
        self,
        config: RotationConfig,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit_funds: Optional[int] = None,
    ) -> BacktestResult:
        fund_meta = self._build_fund_meta(limit_funds=limit_funds)
        symbols = list(fund_meta.keys())
        all_symbols = sorted(set(symbols).union(config.benchmark_symbols))

        price_matrix = self._load_price_matrix(all_symbols)
        if price_matrix.empty:
            raise ValueError("No fund price history is available.")

        price_matrix = self._filter_date_range(price_matrix, start_date, end_date)
        price_matrix = price_matrix.dropna(axis=1, how="all").ffill()
        symbols = [symbol for symbol in symbols if symbol in price_matrix.columns]
        if not symbols:
            raise ValueError("No candidate fund has usable price history.")

        max_lookback = max(
            [days for days, _ in config.lookback_weights]
            + [config.absolute_momentum_window, config.volatility_window]
        )
        signal_to_execution = self._monthly_signal_execution_dates(price_matrix.index)
        signal_to_execution = {
            signal: execution
            for signal, execution in signal_to_execution.items()
            if price_matrix.index.get_loc(signal) >= max_lookback
        }
        if not signal_to_execution:
            raise ValueError("Not enough history to create any rebalance date.")

        target_by_execution: Dict[pd.Timestamp, List[str]] = {}
        rank_by_signal: Dict[pd.Timestamp, List[Dict]] = {}
        current_holdings: List[str] = []

        for signal_date, execution_date in signal_to_execution.items():
            ranks = self._rank_funds(price_matrix, symbols, fund_meta, signal_date, config)
            selected = self._select_with_buffer_and_theme_limit(
                ranks, current_holdings, config
            )
            target_by_execution[execution_date] = selected
            rank_by_signal[signal_date] = ranks
            current_holdings = selected

        equity_curve, rebalances = self._simulate_portfolio(
            price_matrix=price_matrix,
            target_by_execution=target_by_execution,
            execution_to_signal={execution: signal for signal, execution in signal_to_execution.items()},
            config=config,
            fund_meta=fund_meta,
        )
        summary = self._calculate_metrics(equity_curve, rebalances, config.initial_capital)
        benchmark_summary = self._benchmark_summaries(
            price_matrix, config.benchmark_symbols, config.initial_capital
        )

        return BacktestResult(
            config=self._config_to_dict(config),
            summary=summary,
            benchmark_summary=benchmark_summary,
            equity_curve=equity_curve,
            rebalances=rebalances,
        )

    def run_grid_search(
        self,
        base_config: Optional[RotationConfig] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit_funds: Optional[int] = None,
        param_grid: Optional[Dict[str, Sequence]] = None,
    ) -> List[BacktestResult]:
        base = base_config or RotationConfig()
        grid = param_grid or default_param_grid()

        results = []
        keys = list(grid.keys())
        for values in itertools.product(*(grid[key] for key in keys)):
            params = dict(zip(keys, values))
            config = replace(base, **params)
            config = replace(config, name=self._grid_name(config))
            try:
                result = self.run_backtest(config, start_date, end_date, limit_funds)
                results.append(result)
                logger.info(
                    "Grid result %s: annual=%.2f%%, max_dd=%.2f%%, sharpe=%.2f",
                    config.name,
                    result.summary["annual_return_pct"],
                    result.summary["max_drawdown_pct"],
                    result.summary["sharpe_ratio"],
                )
            except Exception as e:
                logger.warning("Grid combination failed %s: %s", params, e)

        results.sort(
            key=lambda item: (
                item.summary.get("annual_return_pct", -math.inf),
                -item.summary.get("max_drawdown_pct", math.inf),
            ),
            reverse=True,
        )
        return results

    def _build_fund_meta(self, limit_funds: Optional[int] = None) -> Dict[str, Dict]:
        funds = self.funds[:limit_funds] if limit_funds else self.funds
        meta = {}
        for fund in funds:
            symbol = normalize_symbol(fund.get("基金代码"))
            if not symbol:
                continue
            name = str(fund.get("基金简称", symbol))
            meta[symbol] = {
                "symbol": symbol,
                "name": name,
                "theme": classify_fund_theme(name),
            }
        return meta

    def _load_price_matrix(self, symbols: Sequence[str]) -> pd.DataFrame:
        series_map = {}
        for symbol in symbols:
            history = get_fund_daily_data(symbol, apply_delay=False)
            series = self._history_to_series(history)
            if series.empty:
                logger.warning("No history for fund %s", symbol)
                continue
            series_map[symbol] = series

        if not series_map:
            return pd.DataFrame()

        prices = pd.DataFrame(series_map).sort_index()
        return prices

    def _history_to_series(self, history: pd.DataFrame) -> pd.Series:
        """兼容两种 schema：旧（净值日期/单位净值…）与新（日期/收盘价，stockdb）。"""
        if history is None or history.empty:
            return pd.Series(dtype=float)
        date_col = "净值日期" if "净值日期" in history.columns else "日期"
        if date_col not in history.columns:
            return pd.Series(dtype=float)

        value_col = None
        for candidate in ("单位净值", "累计净值", "累计收益率", "收盘价"):
            if candidate in history.columns:
                value_col = candidate
                break
        if value_col is None:
            return pd.Series(dtype=float)

        df = history[[date_col, value_col]].copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
        df = df.dropna().sort_values(date_col)
        if df.empty:
            return pd.Series(dtype=float)
        return df.drop_duplicates(date_col).set_index(date_col)[value_col]

    def _filter_date_range(
        self, prices: pd.DataFrame, start_date: Optional[str], end_date: Optional[str]
    ) -> pd.DataFrame:
        result = prices
        if start_date:
            result = result[result.index >= pd.to_datetime(start_date)]
        if end_date:
            result = result[result.index <= pd.to_datetime(end_date)]
        return result

    def _monthly_signal_execution_dates(
        self, dates: pd.DatetimeIndex
    ) -> Dict[pd.Timestamp, pd.Timestamp]:
        month_ends = pd.Series(dates, index=dates).groupby(dates.to_period("M")).last()
        mapping = {}
        for signal_date in month_ends:
            position = dates.get_loc(signal_date)
            if position + 1 < len(dates):
                mapping[pd.Timestamp(signal_date)] = pd.Timestamp(dates[position + 1])
        return mapping

    def _rank_funds(
        self,
        prices: pd.DataFrame,
        symbols: Sequence[str],
        fund_meta: Dict[str, Dict],
        signal_date: pd.Timestamp,
        config: RotationConfig,
    ) -> List[Dict]:
        row = prices.index.get_loc(signal_date)
        ranks = []
        for symbol in symbols:
            current_price = prices.iloc[row][symbol]
            if pd.isna(current_price) or current_price <= 0:
                continue

            weighted_return = 0.0
            has_all_lookbacks = True
            lookback_returns = {}
            for days, weight in config.lookback_weights:
                if row - days < 0:
                    has_all_lookbacks = False
                    break
                past_price = prices.iloc[row - days][symbol]
                if pd.isna(past_price) or past_price <= 0:
                    has_all_lookbacks = False
                    break
                period_return = current_price / past_price - 1
                lookback_returns[str(days)] = period_return
                weighted_return += weight * period_return

            if not has_all_lookbacks:
                continue

            absolute_return = None
            if config.use_absolute_momentum:
                window = config.absolute_momentum_window
                if row - window < 0:
                    continue
                absolute_base = prices.iloc[row - window][symbol]
                if pd.isna(absolute_base) or absolute_base <= 0:
                    continue
                absolute_return = current_price / absolute_base - 1
                if absolute_return <= config.absolute_momentum_threshold:
                    continue

            volatility = self._annualized_volatility(prices[symbol].iloc[: row + 1], config)
            score = weighted_return - config.volatility_penalty * volatility
            ranks.append(
                {
                    "symbol": symbol,
                    "name": fund_meta[symbol]["name"],
                    "theme": fund_meta[symbol]["theme"],
                    "score": score,
                    "weighted_return": weighted_return,
                    "absolute_return": absolute_return,
                    "volatility": volatility,
                    "lookback_returns": lookback_returns,
                }
            )

        ranks.sort(key=lambda item: item["score"], reverse=True)
        for idx, item in enumerate(ranks, start=1):
            item["rank"] = idx
        return ranks

    def _annualized_volatility(self, series: pd.Series, config: RotationConfig) -> float:
        window = config.volatility_window
        recent = series.dropna().tail(window + 1)
        if len(recent) < 2:
            return 0.0
        returns = recent.pct_change().dropna()
        if returns.empty:
            return 0.0
        return float(returns.std() * math.sqrt(252))

    def _select_with_buffer_and_theme_limit(
        self,
        ranks: List[Dict],
        current_holdings: Sequence[str],
        config: RotationConfig,
    ) -> List[str]:
        rank_map = {item["symbol"]: item for item in ranks}
        selected: List[str] = []
        theme_counts: Dict[str, int] = {}

        for symbol in current_holdings:
            item = rank_map.get(symbol)
            if not item or item["rank"] > config.buffer_rank:
                continue
            if self._theme_available(item["theme"], theme_counts, config.max_per_theme):
                selected.append(symbol)
                theme_counts[item["theme"]] = theme_counts.get(item["theme"], 0) + 1
            if len(selected) >= config.top_n:
                return selected

        for item in ranks:
            symbol = item["symbol"]
            if symbol in selected:
                continue
            if not self._theme_available(item["theme"], theme_counts, config.max_per_theme):
                continue
            selected.append(symbol)
            theme_counts[item["theme"]] = theme_counts.get(item["theme"], 0) + 1
            if len(selected) >= config.top_n:
                break

        return selected

    def _theme_available(
        self, theme: str, theme_counts: Dict[str, int], max_per_theme: int
    ) -> bool:
        if max_per_theme <= 0:
            return True
        return theme_counts.get(theme, 0) < max_per_theme

    def _simulate_portfolio(
        self,
        price_matrix: pd.DataFrame,
        target_by_execution: Dict[pd.Timestamp, List[str]],
        execution_to_signal: Dict[pd.Timestamp, pd.Timestamp],
        config: RotationConfig,
        fund_meta: Dict[str, Dict],
    ) -> Tuple[List[Dict], List[Dict]]:
        start_date = min(target_by_execution)
        dates = price_matrix.index[price_matrix.index >= start_date]
        cash = config.initial_capital
        shares: Dict[str, float] = {}
        equity_curve: List[Dict] = []
        rebalances: List[Dict] = []
        total_cost_rate = config.transaction_fee + config.slippage

        for date in dates:
            portfolio_value = cash + sum(
                qty * price_matrix.at[date, symbol]
                for symbol, qty in shares.items()
                if symbol in price_matrix.columns and not pd.isna(price_matrix.at[date, symbol])
            )

            if date in target_by_execution:
                target_symbols = target_by_execution[date]
                before_values = {
                    symbol: qty * price_matrix.at[date, symbol]
                    for symbol, qty in shares.items()
                    if symbol in price_matrix.columns and not pd.isna(price_matrix.at[date, symbol])
                }
                target_weight = 1 / len(target_symbols) if target_symbols else 0
                target_values = {
                    symbol: portfolio_value * target_weight for symbol in target_symbols
                }
                all_symbols = set(before_values).union(target_values)
                turnover_value = sum(
                    abs(target_values.get(symbol, 0.0) - before_values.get(symbol, 0.0))
                    for symbol in all_symbols
                )
                cost = turnover_value * total_cost_rate
                portfolio_value_after_cost = portfolio_value - cost
                shares = {}
                cash = portfolio_value_after_cost
                if target_symbols:
                    per_symbol_value = portfolio_value_after_cost / len(target_symbols)
                    for symbol in target_symbols:
                        price = price_matrix.at[date, symbol]
                        if pd.isna(price) or price <= 0:
                            continue
                        shares[symbol] = per_symbol_value / price
                    cash = 0.0

                portfolio_value = cash + sum(
                    qty * price_matrix.at[date, symbol] for symbol, qty in shares.items()
                )
                signal_date = execution_to_signal.get(date)
                rebalances.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "signal_date": signal_date.strftime("%Y-%m-%d") if signal_date else None,
                        "holdings": [
                            {
                                "symbol": symbol,
                                "name": fund_meta.get(symbol, {}).get("name", symbol),
                                "theme": fund_meta.get(symbol, {}).get("theme", "other"),
                                "weight": round(1 / len(target_symbols), 4)
                                if target_symbols
                                else 0,
                            }
                            for symbol in target_symbols
                        ],
                        "turnover_pct": turnover_value / portfolio_value if portfolio_value else 0,
                        "cost": cost,
                    }
                )

            holdings_value = {
                symbol: qty * price_matrix.at[date, symbol] for symbol, qty in shares.items()
            }
            portfolio_value = cash + sum(holdings_value.values())
            equity_curve.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "portfolio_value": portfolio_value,
                    "cash": cash,
                    "holdings": sorted(shares.keys()),
                    "total_return_pct": (portfolio_value / config.initial_capital - 1) * 100,
                }
            )

        return equity_curve, rebalances

    def _calculate_metrics(
        self, equity_curve: List[Dict], rebalances: List[Dict], initial_capital: float
    ) -> Dict:
        if not equity_curve:
            return {}

        df = pd.DataFrame(equity_curve)
        df["date"] = pd.to_datetime(df["date"])
        values = df["portfolio_value"].astype(float)
        total_return = values.iloc[-1] / initial_capital - 1
        days = max((df["date"].iloc[-1] - df["date"].iloc[0]).days, 1)
        annual_return = (values.iloc[-1] / initial_capital) ** (365 / days) - 1
        daily_returns = values.pct_change().dropna()
        volatility = float(daily_returns.std() * math.sqrt(252)) if len(daily_returns) > 1 else 0
        sharpe = (
            float(daily_returns.mean() / daily_returns.std() * math.sqrt(252))
            if len(daily_returns) > 1 and daily_returns.std() > 1e-12
            else 0.0
        )
        max_drawdown = calculate_max_drawdown(values)
        turnover_values = [item["turnover_pct"] for item in rebalances]
        avg_holdings = float(np.mean([len(item["holdings"]) for item in rebalances])) if rebalances else 0

        return {
            "start_date": df["date"].iloc[0].strftime("%Y-%m-%d"),
            "end_date": df["date"].iloc[-1].strftime("%Y-%m-%d"),
            "initial_capital": initial_capital,
            "final_capital": float(values.iloc[-1]),
            "total_return_pct": float(round(total_return * 100, 2)),
            "annual_return_pct": float(round(annual_return * 100, 2)),
            "max_drawdown_pct": float(round(max_drawdown * 100, 2)),
            "sharpe_ratio": float(round(sharpe, 3)),
            "annual_volatility_pct": float(round(volatility * 100, 2)),
            "rebalance_count": len(rebalances),
            "avg_turnover_pct": round(float(np.mean(turnover_values)) * 100, 2)
            if turnover_values
            else 0,
            "avg_holdings": round(avg_holdings, 2),
        }

    def _benchmark_summaries(
        self,
        prices: pd.DataFrame,
        benchmark_symbols: Sequence[str],
        initial_capital: float,
    ) -> Dict[str, Dict]:
        summaries = {}
        for symbol in benchmark_symbols:
            if symbol not in prices.columns:
                continue
            series = prices[symbol].dropna()
            if len(series) < 2:
                continue
            series = series[series.index >= prices.index.min()]
            values = initial_capital * series / series.iloc[0]
            equity_curve = [
                {"date": idx.strftime("%Y-%m-%d"), "portfolio_value": float(value)}
                for idx, value in values.items()
            ]
            summaries[symbol] = self._calculate_metrics(equity_curve, [], initial_capital)
        return summaries

    def _config_to_dict(self, config: RotationConfig) -> Dict:
        result = asdict(config)
        result["lookback_weights"] = list(config.lookback_weights)
        result["benchmark_symbols"] = list(config.benchmark_symbols)
        return result

    def _grid_name(self, config: RotationConfig) -> str:
        weights = "-".join(f"{days}d{weight:g}" for days, weight in config.lookback_weights)
        return (
            f"top{config.top_n}_buf{config.buffer_rank}_theme{config.max_per_theme}_"
            f"abs{config.absolute_momentum_window}_{weights}"
        )


def normalize_symbol(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip().zfill(6)


def classify_fund_theme(name: str) -> str:
    for theme, keywords in THEME_RULES:
        if any(keyword in name for keyword in keywords):
            return theme
    return "other"


def calculate_max_drawdown(values: pd.Series) -> float:
    running_max = values.cummax()
    drawdowns = values / running_max - 1
    return abs(float(drawdowns.min())) if not drawdowns.empty else 0.0


def parse_weights(text: str) -> Tuple[Tuple[int, float], ...]:
    parts = []
    for item in text.split(","):
        days_text, weight_text = item.split(":")
        parts.append((int(days_text), float(weight_text)))
    total_weight = sum(weight for _, weight in parts)
    if total_weight <= 0:
        raise ValueError("lookback weights must sum to a positive value")
    return tuple((days, weight / total_weight) for days, weight in parts)


def default_param_grid() -> Dict[str, Sequence]:
    return {
        "lookback_weights": [
            ((21, 1.0),),
            ((63, 1.0),),
            ((63, 0.5), (126, 0.3), (252, 0.2)),
        ],
        "top_n": [3, 5],
        "buffer_rank": [5, 10],
        "max_per_theme": [1, 2],
        "absolute_momentum_window": [63, 126],
    }


def save_result(result: BacktestResult, output_dir: Path, prefix: str = "fund_rotation") -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / f"{prefix}_result.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "config": result.config,
                "summary": result.summary,
                "benchmark_summary": result.benchmark_summary,
                "rebalances": result.rebalances,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    pd.DataFrame(result.equity_curve).to_csv(
        output_dir / f"{prefix}_equity_curve.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(result.rebalances).to_csv(
        output_dir / f"{prefix}_rebalances.csv", index=False, encoding="utf-8-sig"
    )


def save_grid_results(results: List[BacktestResult], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in results:
        rows.append(
            {
                "name": item.config["name"],
                **item.summary,
                "config": json.dumps(item.config, ensure_ascii=False),
            }
        )
    pd.DataFrame(rows).to_csv(
        output_dir / "fund_rotation_grid_results.csv", index=False, encoding="utf-8-sig"
    )
    if results:
        save_result(results[0], output_dir, prefix="fund_rotation_best")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fund rotation backtester")
    parser.add_argument("--start", help="Backtest start date, e.g. 2021-01-01")
    parser.add_argument("--end", help="Backtest end date, e.g. 2026-06-10")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--buffer-rank", type=int, default=10)
    parser.add_argument("--max-per-theme", type=int, default=2)
    parser.add_argument("--weights", default="63:0.5,126:0.3,252:0.2")
    parser.add_argument("--abs-window", type=int, default=63)
    parser.add_argument("--abs-threshold", type=float, default=0.0)
    parser.add_argument("--no-absolute-momentum", action="store_true")
    parser.add_argument("--volatility-penalty", type=float, default=0.0)
    parser.add_argument("--fee", type=float, default=0.001)
    parser.add_argument("--slippage", type=float, default=0.0005)
    parser.add_argument("--initial-capital", type=float, default=100000.0)
    parser.add_argument("--benchmark", action="append", default=[])
    parser.add_argument("--grid", action="store_true", help="Run default parameter grid")
    parser.add_argument("--limit-funds", type=int, help="Limit candidate funds for quick tests")
    parser.add_argument(
        "--output-dir",
        default="apps/stock_monitor/reports/fund_rotation",
        help="Directory for JSON/CSV output",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    benchmarks = tuple(args.benchmark) if args.benchmark else tuple(DEFAULT_BENCHMARKS)
    base_config = RotationConfig(
        lookback_weights=parse_weights(args.weights),
        top_n=args.top_n,
        buffer_rank=args.buffer_rank,
        max_per_theme=args.max_per_theme,
        absolute_momentum_window=args.abs_window,
        absolute_momentum_threshold=args.abs_threshold,
        use_absolute_momentum=not args.no_absolute_momentum,
        volatility_penalty=args.volatility_penalty,
        transaction_fee=args.fee,
        slippage=args.slippage,
        initial_capital=args.initial_capital,
        benchmark_symbols=benchmarks,
    )
    backtester = FundRotationBacktester(benchmarks=benchmarks)
    output_dir = Path(args.output_dir)

    if args.grid:
        results = backtester.run_grid_search(
            base_config=base_config,
            start_date=args.start,
            end_date=args.end,
            limit_funds=args.limit_funds,
        )
        save_grid_results(results, output_dir)
        if not results:
            print("No successful grid result.")
            return
        best = results[0]
        print_summary(best, title="Best grid result")
    else:
        result = backtester.run_backtest(
            base_config,
            start_date=args.start,
            end_date=args.end,
            limit_funds=args.limit_funds,
        )
        save_result(result, output_dir)
        print_summary(result)


def print_summary(result: BacktestResult, title: str = "Fund rotation result") -> None:
    print(f"\n{title}")
    print(json.dumps(result.summary, ensure_ascii=False, indent=2))
    if result.benchmark_summary:
        print("\nBenchmarks")
        print(json.dumps(result.benchmark_summary, ensure_ascii=False, indent=2))
    print("\nConfig")
    print(json.dumps(result.config, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
