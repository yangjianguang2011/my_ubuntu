# -*- coding: utf-8 -*-
"""估值因子"有效性"检验台（离线、只读；不改任何生产逻辑）。

为什么要有它
------------
2026-09-28 那次复盘发现：用"单股锚点"判断因子好坏会反复踩坑 ——
"卖点一向很准"只对京东方成立；"加二次项能修好高 ROE 漏卖"被证伪。
所以把检验做成可复现的**批量对照**，改任何逻辑之前先跑这里。

两套口径（都只看**时序**，因为本系统的信号是"相对自己历史"）
  1) 因子层：每股算 reading 与"未来 H 日收益"的 Spearman IC → 训练段 / 测试段
     的 IC、IC 的跨股 IR、以及"最便宜 10% 分位的未来收益 − 全体均值"（买点超额）、
     买点超额为正的股票占比（命中率）。
  2) 事件层：用**生产同一套**二态机 `_signal_events_hold` + `trade_stats`，
     报告 策略收益 / 一直持有 / 策略回撤 / 持有回撤 / 在场占比 / "策略>持有"占比。

怎么读
------
- IC > 0 表示"reading 越低（越便宜）→ 未来收益越高"，越大越好；
- **训练段与测试段都要看**：只有训练段好 = 过拟合；
- 买点超额 = 策略真正吃到的部分；校准/测试切分由 --train-end / --test-start 控制
  （两段之间留 1 个 horizon 的间隔，避免前瞻收益跨段污染）。

⚠ 结论边界（务必连这些一起读）
- 目标取"未来 H 日收益"，**不惩罚回撤** —— 对防守型读数（本因子强项）不公平；
- 单段行情会制造假象：2021-2026 价值风格占优，"低 PB 分位"类因子会虚高，
  那是**风格 beta** 不是因子质量；
- 结论只对"这批票 / 这段行情 / 这个目标"成立，不能当普适真理。

用法（需先启动 stockdb；B 轨首次会联网拉季报 ROE）
    python scripts/valuation_eval_power.py                    # hs300 前 60 只，双口径
    python scripts/valuation_eval_power.py --top 120 --horizon 120
    python scripts/valuation_eval_power.py --factors pb_pct,adjb --mode ic
    python scripts/valuation_eval_power.py --pool zz500 --no-adjb
"""
from __future__ import annotations

import argparse
import time
import traceback
from typing import Dict, List, Optional

from _bootstrap import ensure_project_root

ensure_project_root()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from stock_monitor.data_fetchers.pool_data_fetcher import pool_codes  # noqa: E402
from stock_monitor.data_fetchers.stockdb_data_fetcher import get_daily, get_raw  # noqa: E402
from stock_monitor.data_fetchers.fundamental_data_fetcher import get_report_roe  # noqa: E402
from stock_monitor.analyzers.factor_utils import expanding_pct  # noqa: E402
from stock_monitor.analyzers.factor_valuation import compute_valuation_metrics  # noqa: E402
from stock_monitor.analyzers.valuation_engine import trade_stats, _signal_events_hold  # noqa: E402

PCT_MIN_PERIODS = 250
PRICE_FACTORS = ("pb_pct", "pe_pct", "relpb_pct", "turnover_pct", "bias20_pct", "slope20_pct")
ALL_FACTORS = PRICE_FACTORS + ("adjb",)


# --------------------------------------------------------------------- 数据
def load_panels(codes: List[str], start: str) -> Dict[str, pd.DataFrame]:
    """一次批量取本地日线 → 宽表（index=date, columns=code）。"""
    raw = get_raw(list(codes), start=start, end=None, fq="qfq",
                  fields="date,code,close,pb,pe_ttm,turnover")
    if raw is None or len(raw) == 0:
        raise RuntimeError("stockdb 返回空 —— 请先启动 stockdb.exe")
    raw = raw.copy()
    raw["date"] = pd.to_datetime(raw["date"].astype("int64").astype(str), format="%Y%m%d")
    return {k: raw.pivot_table(index="date", columns="code", values=k).sort_index()
            for k in ("close", "pb", "pe_ttm", "turnover")}


def price_readings(panel: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """只用价格/估值字段就能算的读数（低 = 便宜/超卖）。"""
    close, pb, pe, to = panel["close"], panel["pb"], panel["pe_ttm"], panel["turnover"]
    ma20 = close.rolling(20, min_periods=20).mean()
    raw_f = {
        "pb_pct": pb,
        "pe_pct": pe,
        "relpb_pct": pb.div(pb.median(axis=1), axis=0),   # 相对市场的 PB（风格中性雏形）
        "turnover_pct": to,
        "bias20_pct": close / ma20 - 1.0,
        "slope20_pct": ma20 / ma20.shift(20) - 1.0,
    }
    return {k: v.apply(lambda s: expanding_pct(s, PCT_MIN_PERIODS)) for k, v in raw_f.items()}


def adjb_reading(codes: List[str], start: str, close: pd.DataFrame) -> Optional[pd.DataFrame]:
    """B 轨主读数 pb_adj_b_pct（需季报 ROE，逐只走 akshare + compute_valuation_metrics）。"""
    got: Dict[str, pd.Series] = {}
    t0, miss = time.time(), 0
    for i, c in enumerate(codes, 1):
        try:
            df = get_daily(c, start=start)
            reps = get_report_roe(c)
            if df is None or df.empty or not reps:
                miss += 1
                continue
            m = compute_valuation_metrics(df, roe_reports=reps)
            got[c] = pd.Series(m["pb_adj_b_pct"].values, index=pd.to_datetime(m["date"]))
        except Exception as e:  # noqa: BLE001
            miss += 1
            print(f"    [warn] {c} 跳过：{type(e).__name__}: {e}")
        if i % 20 == 0:
            print(f"    ... {i}/{len(codes)} 已算 {len(got)}，{time.time() - t0:.0f}s")
    if not got:
        return None
    return pd.DataFrame(got).sort_index().reindex(close.index)


# --------------------------------------------------------------------- 口径
def forward_returns(close: pd.DataFrame, h: int) -> pd.DataFrame:
    """**逐只按自己的交易日**算未来 H 日收益（避免面板空洞把 shift 错位/污染成 NaN）。"""
    out = {}
    for c in close.columns:
        s = close[c].dropna()
        out[c] = s.shift(-h) / s - 1.0
    return pd.DataFrame(out).reindex(close.index)


def ic_table(readings: Dict[str, pd.DataFrame], fwd: pd.DataFrame,
             train: pd.Series, test: pd.Series, min_obs: int) -> None:
    hdr = (f"{'factor':<14}{'IC_train':>10}{'IR_train':>10}{'n_tr':>6}"
           f"{'IC_test':>10}{'IR_test':>10}{'n_te':>6}{'edge_test':>11}{'edge>0':>8}")
    print(hdr)
    print("-" * len(hdr))
    for name, r in readings.items():
        ics_tr, ics_te, edges = [], [], []
        for c in r.columns:
            if c not in fwd.columns:
                continue
            x, y = -r[c], fwd[c]                      # 取负 → IC>0 表示"读数低=好"
            m1 = train & x.notna() & y.notna()
            m2 = test & x.notna() & y.notna()
            if int(m1.sum()) >= min_obs:
                ics_tr.append(x[m1].corr(y[m1], method="spearman"))
            if int(m2.sum()) >= min_obs:
                ics_te.append(x[m2].corr(y[m2], method="spearman"))
                thr = x[m2].quantile(0.90)            # 最便宜 10%（= 取负后最高 10%）
                edges.append(y[m2 & (x >= thr)].mean() - y[m2].mean())
        ic_tr, ic_te = np.nanmean(ics_tr), np.nanmean(ics_te)
        print(f"{name:<14}{ic_tr:>10.3f}{np.nanmean(ics_tr) / np.nanstd(ics_tr):>10.2f}{len(ics_tr):>6}"
              f"{ic_te:>10.3f}{np.nanmean(ics_te) / np.nanstd(ics_te):>10.2f}{len(ics_te):>6}"
              f"{np.nanmean(edges):>11.2%}{np.mean([e > 0 for e in edges]):>8.0%}")


def event_table(readings: Dict[str, pd.DataFrame], close: pd.DataFrame,
                buy: float, sell: float, min_days: int) -> None:
    hdr = (f"{'factor':<14}{'strat_ret_med':>15}{'bh_ret_med':>12}{'strat_MDD':>11}"
           f"{'bh_MDD':>9}{'in_mkt':>8}{'strat>bh':>10}{'mdd>-60pct':>12}{'n':>5}")
    print(hdr)
    print("-" * len(hdr))
    for name, r in readings.items():
        per = []
        for c in r.columns:
            if c not in close.columns:
                continue
            # 只取该股**自己的交易日**（面板对齐会带停牌空洞 → trade_stats 的 bh 会变 NaN）
            s = close[c].dropna()
            if len(s) < min_days:
                continue
            sr = r[c].reindex(s.index)
            m = pd.DataFrame({"date": s.index, "close": s.values, name: sr.values})
            ev = _signal_events_hold(m, col=name, buy=buy, sell=sell)
            st = trade_stats(m, ev)
            if st and st.get("total_days", 0) >= min_days:
                per.append(st)
        if not per:
            print(f"{name:<14}{'(no data)':>15}")
            continue
        d = pd.DataFrame(per)
        print(f"{name:<14}{d.strat_return.median():>15.1%}{d.bh_return.median():>12.1%}"
              f"{d.strat_mdd.median():>11.1%}{d.bh_mdd.median():>9.1%}"
              f"{d.pos_ratio.mean():>8.0%}{(d.strat_return > d.bh_return).mean():>10.0%}"
              f"{(d.strat_mdd > -0.60).mean():>12.0%}{len(d):>5}")


# --------------------------------------------------------------------- main
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="估值因子有效性检验台（只读）")
    ap.add_argument("--pool", default="hs300", help="股票池（hs300/zz500）")
    ap.add_argument("--top", type=int, default=60, help="取池中前 N 只（0=全部）")
    ap.add_argument("--start", default="20120101", help="日线起点（=分位起算）")
    ap.add_argument("--train-end", default="2020-12-31", help="训练段结束日")
    ap.add_argument("--test-start", default="2021-01-01", help="测试段开始日")
    ap.add_argument("--horizon", type=int, default=250, help="目标=未来 H 日收益")
    ap.add_argument("--factors", default="", help=f"逗号分隔，默认全部：{','.join(ALL_FACTORS)}")
    ap.add_argument("--buy", type=float, default=0.10, help="事件层买入阈值")
    ap.add_argument("--sell", type=float, default=0.90, help="事件层卖出阈值")
    ap.add_argument("--min-obs", type=int, default=500, help="单股 IC 的最少观测数")
    ap.add_argument("--min-days", type=int, default=1000, help="事件层纳入统计的最少天数")
    ap.add_argument("--no-adjb", action="store_true", help="跳过 B 轨（免联网拉季报 ROE）")
    ap.add_argument("--mode", default="both", choices=("ic", "events", "both"))
    args = ap.parse_args(argv)

    codes = pool_codes(args.pool)
    if args.top and args.top > 0:
        codes = codes[: args.top]
    want = [f.strip() for f in args.factors.split(",") if f.strip()] or list(ALL_FACTORS)

    print(f"[eval] pool={args.pool} n={len(codes)} start={args.start} "
          f"horizon={args.horizon} train<={args.train_end} test>={args.test_start} "
          f"thr={args.buy}/{args.sell}")
    t0 = time.time()
    panel = load_panels(codes, args.start)
    close = panel["close"]
    print(f"[eval] 面板 {close.shape[0]} 日 × {close.shape[1]} 只，{time.time() - t0:.0f}s")

    readings = {k: v for k, v in price_readings(panel).items() if k in want}
    if "adjb" in want and not args.no_adjb:
        print("[eval] 计算 B 轨 pb_adj_b_pct（逐只季报 ROE）…")
        a = adjb_reading(codes, args.start, close)
        if a is not None:
            readings["adjb"] = a
    if not readings:
        print("[eval] 没有可算的因子")
        return 1

    fwd = forward_returns(close, args.horizon)
    train = pd.Series((close.index >= "2013-01-01") & (close.index <= args.train_end), index=close.index)
    test = pd.Series(close.index >= args.test_start, index=close.index)

    if args.mode in ("ic", "both"):
        base = fwd[test].stack().mean()
        print(f"\n== 因子层（目标=未来 {args.horizon} 日收益；测试段基准均值 {base:.2%}）==")
        ic_table(readings, fwd, train, test, args.min_obs)

    if args.mode in ("events", "both"):
        print(f"\n== 事件层（生产同款二态机 {args.buy}/{args.sell}，全期）==")
        event_table(readings, close, args.buy, args.sell, args.min_days)

    print(f"\n[eval] 完成，{time.time() - t0:.0f}s。⚠ 记牢：目标不惩罚回撤；单段行情有风格 beta；"
          f"训练/测试都要看。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(1)
