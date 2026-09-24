# -*- coding: utf-8 -*-
"""
估值报告引擎 —— 编排单只 A 股估值/价格周期计算，返回结构化 JSON（供前端渲染）。

口径：见 docs/SPEC.md §2.3（盈利调节）、§2.4（市场水位）、§2.5（价格周期）。

本模块仅负责编排：日K读取 → 因子计算（注册表驱动）→ 读数面板 → 买卖信号 →
报告 JSON（valuation_report）。不再写 HTML/PNG 文件。
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config import get_path, setup_logger
from ..core.utils import fmt_pct, safe_float

from ..data_fetchers.stockdb_data_fetcher import get_daily
from ..data_fetchers.fundamental_data_fetcher import get_payout_ratio, get_report_revenue, get_report_roe
from ..analyzers.market_temperature import get_market_level, latest_temperature_cached, MARKET_INDICES
from ..analyzers.valuation_report import build_report
from . import factor_valuation  # noqa: F401  触发 register()，估值为主面板，须先注册
from . import factor_price_cycle  # noqa: F401  触发 register()
from . import factor_fusion  # noqa: F401  触发 register()（融合层，依赖估值列）
from .factors_registry import all_factors, get_factor

logger = setup_logger(__name__)

# 常量（config.ini 驱动，env 可覆盖 STOCK_MONITOR_VALUATION_*）
# fetch_start: 日K 拉取起点（要早于窗口，保证滚动窗口有足够样本）；data_start 仅作百分位起算后备
DATA_START = get_path("valuation", "fetch_start",
                      get_path("valuation", "data_start", "20100101"))
FQ = get_path("valuation", "fq", "qfq")
DATA_START_VALID = 300
PCT_BUY = 0.10
PCT_SELL = 0.90
LOOKAHEAD = 60
# 信号规则（config.ini 驱动）：two_state=二态机（买入持有，连续同向归并成一笔）/ cross=旧口径
SIGNAL_MODE = get_path("valuation", "signal_mode", "two_state").lower()
BUY_THRESHOLD = float(get_path("valuation", "buy_threshold", "0.10"))
SELL_THRESHOLD = float(get_path("valuation", "sell_threshold", "0.90"))
# 个股阈值覆盖：{"000725": (0.05, 0.95), ...}
_DEFAULT_THRESHOLD = (BUY_THRESHOLD, SELL_THRESHOLD)


def _parse_overrides() -> Dict[str, tuple]:
    raw = get_path("valuation", "threshold_overrides", "") or ""
    out: Dict[str, tuple] = {}
    for item in str(raw).split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue
        code, _, thr = item.partition(":")
        parts = thr.split("/")
        try:
            out[code.strip().zfill(6)] = (float(parts[0]), float(parts[1]))
        except (ValueError, IndexError):
            continue
    return out


THRESHOLD_OVERRIDES = _parse_overrides()


def thresholds_for(code: str) -> tuple:
    """该股生效的 (buy, sell) 阈值：优先个股覆盖，否则全局默认。"""
    return THRESHOLD_OVERRIDES.get((code or "").strip().zfill(6), _DEFAULT_THRESHOLD)
# 多因子融合层开关（默认关；开启则第一层用 sync 融合读数打买卖点）
FUSION_ENABLED = get_path("valuation", "fusion_enabled", "false").lower() in ("1", "true", "yes")
MARKET_LEVEL_ENABLED = get_path("valuation", "market_level_enabled", "false").lower() in ("1", "true", "yes")
MARKET_POOL = get_path("valuation", "market_level_pool", "hs300")
# 温度门控参考指数（sh/sz/cyb → MARKET_INDICES）
TEMP_INDEX_KEY = get_path("valuation", "temp_index", "sh").lower()


def run_valuation(code: str, start: Optional[str] = None) -> dict:
    """生成单股估值报告 → 结构化 dict（前端渲染用）。"""
    start = start or DATA_START
    df = get_daily(code, start=start, fq=FQ)
    if df.empty:
        raise RuntimeError(f"无日K数据: {code}（起于 {start}）")

    # 季报 ROE（B 轨）；akshare 不可用/失败返回 None，自动退化为 A/v1 口径
    roe_reports = None
    try:
        roe_reports = get_report_roe(code)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"{code} 季报ROE 获取异常，B 轨缺席: {type(e).__name__}: {e}")

    # 分红支付率（修正市赚率的 N）；失败返回 None -> N=1.0
    payout = None
    try:
        payout = get_payout_ratio(code)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"{code} 分红率获取异常，N=1.0: {type(e).__name__}: {e}")

    # 营业收入（盈利调节市销率 PS 的分母）；失败返回 None -> PS 缺席
    revenue_reports = None
    try:
        revenue_reports = get_report_revenue(code)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"{code} 营业收入获取异常，PS 缺席: {type(e).__name__}: {e}")

    # 可选：残差内扣"市场估值中枢长期漂移"（默认关闭，实测更差）
    market_level, ml_note = None, "未启用"
    if MARKET_LEVEL_ENABLED:
        try:
            market_level = get_market_level(MARKET_POOL)
            ml_note = ("已扣减" if market_level is not None else "构造失败，未扣减")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{code} 市场水位漂移不可用: {type(e).__name__}: {e}")
            ml_note = f"不可用（{type(e).__name__}）"

    # ---- 因子计算（注册表驱动）----
    base = get_factor("valuation")
    metrics = base.compute(df, roe_reports=roe_reports, revenue_reports=revenue_reports,
                           market_level=market_level,
                           payout_ratio=(payout or {}).get("payout"))
    if len(metrics) < DATA_START_VALID:
        raise RuntimeError(f"{code} 数据不足（{len(metrics)} 行），无法计算估值因子")

    # 并入非基础因子列（如 price_cycle / fusion）
    # 注意：fusion 依赖估值因子产出的 *_pct 列，故传入 metrics 而非原始 df。
    price_cycle_val, price_cycle_detail = None, None
    for f in all_factors():
        if f.is_base or not f.merge_cols:
            continue
        try:
            sub = f.compute(metrics if f.name == "fusion" else df)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{code} {f.name} 计算失败: {type(e).__name__}: {e}")
            continue
        if sub is not None and not sub.empty and set(f.merge_cols) <= set(sub.columns):
            metrics = metrics.merge(sub[["date", *f.merge_cols]], on="date", how="left")
    if "price_cycle" in metrics.columns:
        price_cycle_val = safe_float(metrics["price_cycle"].iloc[-1])
        pc_factor = get_factor("price_cycle")
        if pc_factor and pc_factor.latest:
            price_cycle_detail = pc_factor.latest(metrics)

    readings = base.latest(metrics, payout=payout)
    # 并入非基础因子的读数（如 fusion），供面板/结论使用
    for f in all_factors():
        if f.is_base or not f.latest:
            continue
        try:
            extra_reads = f.latest(metrics) or {}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{code} {f.name}.latest 失败: {type(e).__name__}: {e}")
            continue
        for k, v in extra_reads.items():
            readings.setdefault(k, v)
    # 注入各口径的原始残差（单位 PB 倍），供面板并列展示
    for k in ("pb_adj_b", "pb_adj"):
        if readings.get(k) is not None and k in metrics.columns:
            res = metrics[k].iloc[-1]
            readings[k]["residual"] = (None if pd.isna(res) else float(res))

    primary = "pb_adj_b" if "pb_adj_b" in metrics.columns else "pb_adj"
    name = str(df["name"].iloc[-1]) if "name" in df.columns else ""
    as_of = readings.get("date", {}).get("value", metrics["date"].iloc[-1])

    logger.info(f"{code} {name} 报告计算：{len(metrics)} 行，截至 {as_of}，"
                f"季报ROE={len(roe_reports) if roe_reports else 0} 期，主口径={primary}，"
                f"价格周期={price_cycle_val if price_cycle_val is None else round(price_cycle_val, 3)}，"
                f"分红支付率={fmt_pct((payout or {}).get('payout'))}")

    # 买卖信号口径：默认主估值口径（单因子）；fusion_enabled 时用融合读数
    if FUSION_ENABLED and "fusion_pct" in metrics.columns \
            and metrics["fusion_pct"].notna().any():
        sig_col = "fusion_pct"
    else:
        sig_col = f"{primary}_pct"
    buy_thr, sell_thr = thresholds_for(code)
    if SIGNAL_MODE == "two_state":
        events = _signal_events_hold(metrics, col=sig_col, buy=buy_thr, sell=sell_thr)
    else:
        events = _signal_events(metrics, col=sig_col, buy=buy_thr, sell=sell_thr)
    # 多次触发标记（每次进入极端区都记；只用于第一层图上显示，不影响二态机）
    triggers = _signal_events(metrics, col=sig_col, buy=buy_thr, sell=sell_thr)
    stats = trade_stats(metrics, events)
    roe_warn = roe_regime_warning(metrics)
    logger.info(f"{code} {name} 信号口径: {sig_col} · 模式={SIGNAL_MODE} · 阈值 {buy_thr}/{sell_thr}"
                f"（{'个股覆盖' if (code.zfill(6) in THRESHOLD_OVERRIDES) else '全局默认'}），"
                f"交易 {len(events)} 笔，触发标记 {len(triggers)} 个"
                + (f"，持仓占比 {stats.get('pos_ratio', 0)*100:.0f}%，"
                   f"策略 {stats.get('strat_return', 0)*100:.0f}% vs 持有 {stats.get('bh_return', 0)*100:.0f}%"
                   if stats else "")
                + (f"；⚠ {roe_warn[:20]}…" if roe_warn else ""))

    # 市场温度门控参考（只读缓存；无缓存不现算）
    symbol, _label = MARKET_INDICES.get(TEMP_INDEX_KEY, ("000001.SH", "上证综指"))
    mkt = None
    try:
        mkt = latest_temperature_cached(symbol)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"{code} 温度门控读取失败: {e}")
    if mkt and mkt.get("temperature") is not None:
        mkt_note = (f"{symbol}·温度 {mkt['temperature']*100:.0f}℃（{mkt['state']}，截至 {mkt['date']}）"
                    "—— 市场温度仅作门控参考，未参与个股读数计算")
    else:
        mkt_note = "市场温度未缓存（先在'股票监控'页底部点击『刷新温度』后可用）"

    return build_report(code, name, as_of, readings, events, primary,
                        roe_src=(len(roe_reports) if roe_reports else 0),
                        ml_note=ml_note,
                        signal_col=sig_col,
                        stats=stats,
                        roe_warning=roe_warn,
                        mkt_note=mkt_note,
                        thresholds=(buy_thr, sell_thr),
                        triggers=triggers,
                        price_cycle=price_cycle_val, price_cycle_detail=price_cycle_detail,
                        metrics=metrics)


# ---------------------------------------------------------------- 信号
def _signal_events_hold(metrics: pd.DataFrame, col: str = "pb_adj_b_pct",
                        buy: float = 0.06, sell: float = 0.94,
                        lookahead: int = LOOKAHEAD) -> List[Dict]:
    """二态机（买入持有）—— 作者"4 笔交易"口径的信号实现。

    状态机：只有两个状态
        空仓：读数 < buy  → 开一笔买，进入持仓（此后读数再低不再触发，**直到**读数>sell）
        持仓：读数 > sell → 卖出，回到空仓（此后读数再高不再触发）
    与"每次进极端区都记一次"的 cross 口径（_signal_events，图上多次触发标记）的区别：
    两态机的买/卖事件**必然交替**，连续同向读数只记第一次进入 —— 这就是文章里
    "很多连续标记、归并成几次交易"的做法。事件数（=交易笔数）远少于标记数。

    buy/sell 阈值来自 `thresholds_for(code)`（个股覆盖优先于全局默认）。
    返回与 _signal_events 同构的事件列表（按时间升序）。
    """
    if metrics is None or metrics.empty or col not in metrics.columns:
        return []
    s = metrics[col].values
    close = metrics["close"].values
    dates = metrics["date"].values
    ev: List[Dict] = []
    holding = False
    for i, v in enumerate(s):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue  # 空读数不影响状态（如回归窗口未满、季报未生效）
        if not holding and v < buy:
            holding = True   # 空仓 → 买入
            ev.append(_mk_event(dates[i], "买", float(v), float(close[i]), close, i, lookahead))
        elif holding and v > sell:
            holding = False
            ev.append(_mk_event(dates[i], "卖", float(v), float(close[i]), close, i, lookahead))
    return ev


def _signal_events(metrics: pd.DataFrame, col: str = "pb_adj_b_pct",
                   buy: float = PCT_BUY, sell: float = PCT_SELL,
                   lookahead: int = LOOKAHEAD) -> List[Dict]:
    """cross 口径（多次触发标记）：每次"进入"极端区都记一次，供第一层图上全画。

    与二态机 `_signal_events_hold` 的区别：这里 state 在读数回到中间区时清零，
    因此同一轮行情里"围绕阈值反复穿越"会记成多个标记（京东方 54 个/兴业 22 个…）。
    **只用于展示**（`triggers`→图），不构成交易、不进统计；真正驱动交易表/统计的
    仍是二态机的 events。事件列表同构：[{date, kind, read, close, fwd60}]。
    """
    if metrics is None or metrics.empty or col not in metrics.columns:
        return []
    s = metrics[col]
    close = metrics["close"].values
    dates = metrics["date"].values
    ev: List[Dict] = []
    state: Optional[str] = None
    for i, v in enumerate(s.values):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        if v < buy:
            if state != "buy":
                ev.append(_mk_event(dates[i], "买", float(v), float(close[i]), close, i, lookahead))
                state = "buy"
        elif v > sell:
            if state != "sell":
                ev.append(_mk_event(dates[i], "卖", float(v), float(close[i]), close, i, lookahead))
                state = "sell"
        else:
            state = None
    return ev


def _mk_event(d, kind: str, read: float, close: float, closes, i: int, la: int) -> Dict:
    fwd = closes[i + la] / close - 1.0 if (i + la) < len(closes) else None
    return {"date": str(pd.Timestamp(d))[:10], "kind": kind, "read": read,
            "close": close, "fwd60": (None if fwd is None else round(float(fwd), 4))}


# ---------------------------------------------------------------- 交易统计
def trade_stats(metrics: pd.DataFrame, events: List[Dict]) -> Dict:
    """二态机策略统计：持仓占比、总收益、最大回撤，并与"一直持有"对比。

    规则：按事件序列在买点全仓、卖点空仓；日频结算，空仓期资金不动（收益 0）。
    """
    if metrics is None or metrics.empty:
        return {}
    close = metrics["close"].values.astype(float)
    dates = metrics["date"].values
    n = len(close)
    if n < 2:
        return {}

    # 事件日期 → 索引；用二态机推每日持仓状态
    ev_idx = {}
    for e in events:
        try:
            i = int((pd.to_datetime(metrics["date"]) == pd.Timestamp(e["date"])).idxmax())
            ev_idx[i] = e["kind"]
        except Exception:  # noqa: BLE001
            continue

    holding = False
    equity, bh = [1.0], [1.0]
    pos_days = 0
    for i in range(1, n):
        if i - 1 in ev_idx:
            holding = ev_idx[i - 1] == "买"
        # 当日收益：持仓则跟随涨幅，否则 0
        r = close[i] / close[i - 1] - 1.0 if holding else 0.0
        equity.append(equity[-1] * (1.0 + r))
        bh.append(bh[-1] * (close[i] / close[i - 1]))
        if holding:
            pos_days += 1

    def _mdd(curve):
        peak, mdd = curve[0], 0.0
        for v in curve:
            peak = max(peak, v)
            mdd = min(mdd, v / peak - 1.0)
        return mdd

    buys = sum(1 for e in events if e["kind"] == "买")
    sells = sum(1 for e in events if e["kind"] == "卖")
    last_kind = events[-1]["kind"] if events else None
    bt, st = thresholds_for(metrics["code"].iloc[-1] if "code" in metrics.columns else "")
    return {
        "total_days": n,
        "pos_days": pos_days,
        "pos_ratio": round(pos_days / (n - 1), 4) if n > 1 else 0.0,
        "trades": buys,
        "buys": buys, "sells": sells,
        "holding_now": last_kind == "买",
        "start": str(pd.Timestamp(dates[0]))[:10],
        "end": str(pd.Timestamp(dates[-1]))[:10],
        "strat_return": round(equity[-1] - 1.0, 4),
        "bh_return": round(bh[-1] - 1.0, 4),
        "strat_mdd": round(_mdd(equity), 4),
        "bh_mdd": round(_mdd(bh), 4),
        "buy_threshold": bt, "sell_threshold": st,
    }


def roe_regime_warning(metrics: pd.DataFrame, window: int = 1250,
                       drop: float = 0.35, pct_lo: float = 0.10) -> Optional[str]:
    """盈利中枢警示：**ROE 相对自身近期水平大幅下移**时提示读数可能失真。

    只做提示，不改动任何读数/信号。
    判据：最新 ROE 相对近 window 日中位数**下移 ≥ drop**，且落在历史低位(pct_lo 分位以下)
    —— 对应"盈利中枢换轨"（老凤祥 ROE 22%→10.6%），而非"长期低 ROE"（工行/兴业）。
    """
    if metrics is None or metrics.empty or "roe_step_b" not in metrics.columns:
        return None
    s = metrics["roe_step_b"].dropna()
    if len(s) < 250:
        return None
    cur = float(s.iloc[-1])
    hist = s.iloc[-window:]
    med = float(hist.median())
    pct = float((hist <= cur).mean())
    if med > 0 and cur < med * (1.0 - drop) and pct <= pct_lo:
        return (f"盈利中枢下移：最新季报 ROE {cur*100:.1f}%，较近 5 年中位数 {med*100:.1f}% "
                f"下移 {100*(1-cur/med):.0f}%（历史 {pct*100:.0f}% 分位）"
                f"——盈利调节读数可能失真（线性外推对盈利骤降处理不佳，参见老凤祥案例）")
    return None
