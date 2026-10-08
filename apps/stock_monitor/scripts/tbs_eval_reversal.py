# -*- coding: utf-8 -*-
"""
「月线反转 6.5」+ 三线红 **离线验证跑**（步骤 2）。

目的：在动任何界面之前，先回答一个问题 ——
      **这套信号在全 A 上到底出多少、质量如何、适用什么时期？**

复用现有 `valuation_eval_*` 的评测套路（前视收益、超额、胜率、回撤）。

用法（需先启动 stockdb）：
    python -m stock_monitor.scripts.tbs_eval_reversal                    # 全市场，2012 起
    python -m stock_monitor.scripts.tbs_eval_reversal --start 20150101
    python -m stock_monitor.scripts.tbs_eval_reversal --quick            # 只跑 800 只（快）

输出：
    * 信号数量 / 年（按月线反转、三线红分别统计）
    * 信号后 3/6/12 个月 的 绝对收益 / 超额（vs 全市场等权）/ 胜率
    * **分段**（熊末牛初 vs 牛市后期）对照 —— 该体系限定了适用时期
    * 条件组命中分布（FYX 卡在哪一条最多）
    * 卖点（有效跌破 20 日线）触发统计
"""
from __future__ import annotations

import argparse
import time
from typing import Dict, Optional

from _bootstrap import ensure_project_root

ensure_project_root()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from stock_monitor.analyzers import strategy_tbs as ST  # noqa: E402
from stock_monitor.analyzers.factor_rps import (  # noqa: E402
    RpsParams, all_market_codes, compute_rps, load_panel,
)

# 分段：月线反转「主要适用于熊市中后期和牛市初期」
REGIMES = {
    "熊末牛初(2013-2014)": ("2013-01-01", "2015-06-30"),
    "牛市后期(2015H1)":    ("2015-01-01", "2015-06-30"),
    "熊市(2018)":          ("2018-01-01", "2019-03-31"),
    "熊末牛初(2019)":      ("2018-10-01", "2019-12-31"),
    "疫情后牛初(2020H2)":  ("2020-07-01", "2021-06-30"),
    "熊末牛初(2022Q4)":    ("2022-09-01", "2023-06-30"),
    "熊末牛初(2024Q4-)":   ("2024-09-01", "2026-09-30"),
}
HORIZONS = (60, 120, 250)      # ≈ 3 / 6 / 12 个月（交易日）


# --------------------------------------------------------------------- 评测
def forward_return(close: pd.DataFrame, h: int) -> pd.DataFrame:
    """逐只按自己的交易日算未来 h 日收益（避免面板空洞错位）。"""
    out = {}
    for c in close.columns:
        s = close[c].dropna()
        out[c] = s.shift(-h) / s - 1.0
    return pd.DataFrame(out).reindex(close.index)


def _event_rows(close: pd.DataFrame, sig: pd.DataFrame, h: int):
    """按**事件日**取样本：只保留信号日当天的 (收益, 超额)，不做窗口内重复计数。

    返回 (ret: Series, exc: Series, n_events: int)。全部为 NaN 的丢弃。
    """
    fr = forward_return(close, h)
    bench = fr.mean(axis=1)                      # 全市场等权基准（逐日）
    mask = sig.fillna(False).astype(bool) & fr.notna()
    vals = fr.where(mask)
    exc = vals.sub(bench, axis=0)

    # 只取信号日为 True 的格子（stack 前先与 mask 对齐，避免把窗口内其它日算进来）
    v = vals.where(mask).stack()
    e = exc.where(mask).stack()
    ok = v.notna()
    return v[ok], e[ok], int(ok.sum())


def signal_report(close: pd.DataFrame, sig: pd.DataFrame, name: str,
                  horizons=HORIZONS) -> Dict:
    """给定布尔宽表，统计信号数/年 + 事件日前视收益/超额/胜率。"""
    years = close.index.year
    rows = []
    for h in horizons:
        v, e, n = _event_rows(close, sig, h)
        rows.append({
            "horizon": h,
            "n": n,
            "ret_mean": float(v.mean()) if n else np.nan,
            "ret_med": float(v.median()) if n else np.nan,
            "excess_mean": float(e.mean()) if n else np.nan,
            "win_rate": float((v > 0).mean()) if n else np.nan,
            "beat_rate": float((e > 0).mean()) if n else np.nan,
        })

    cnt = sig.fillna(False).astype(bool).sum(axis=1)
    per_year = cnt.groupby(years).sum()
    return {"name": name, "total": int(sig.fillna(False).values.sum()),
            "per_year": per_year, "returns": rows,
            "daily_mean": float(cnt[cnt > 0].mean()) if (cnt > 0).any() else 0.0,
            "days_with_signal": int((cnt > 0).sum())}


def regime_report(close, sig, horizons=(250,)) -> pd.DataFrame:
    """分段统计（按事件日）。"""
    h = horizons[0]
    rows = []
    for label, (a, b) in REGIMES.items():
        idx = close.index[(close.index >= a) & (close.index <= b)]
        if len(idx) == 0:
            continue
        sub = sig.reindex(index=idx).fillna(False)
        # forward_return 需要完整面板（未来 h 日可能跨出窗口），故用完整 close 算完再裁
        fr_full = forward_return(close, h)
        fr = fr_full.reindex(index=idx)
        bench = fr_full.mean(axis=1).reindex(index=idx)
        vals = fr.where(sub)
        exc = vals.sub(bench, axis=0)
        vv = vals.where(sub).stack()
        ee = exc.where(sub).stack()
        ok = vv.notna()
        vv, ee = vv[ok], ee[ok]
        n = int(ok.sum())
        rows.append({
            "period": label,
            "days": len(idx),
            "events": n,
            "per_100d": round(n / max(len(idx), 1) * 100, 1),
            "ret_12m": None if not n else round(float(vv.mean()) * 100, 1),
            "excess_12m": None if not n else round(float(ee.mean()) * 100, 1),
            "win": None if not n else round(float((vv > 0).mean()) * 100, 0),
            "beat": None if not n else round(float((ee > 0).mean()) * 100, 0),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------- 主流程
def run(start: str, quick: int = 0, top_n: int = 40, out_csv: Optional[str] = None):
    t0 = time.time()
    codes = all_market_codes()
    if quick:
        codes = codes[:quick]
    print(f"全市场代码 {len(codes)} 只")

    panel = load_panel(codes, start=start)
    close = panel.get("close")
    high = panel.get("high", close)
    low = panel.get("low", close)
    if close is None or close.empty:
        raise SystemExit("stockdb 无数据")
    print(f"面板 {close.shape[0]} 交易日 × {close.shape[1]} 只，取数 {time.time() - t0:.0f}s")

    t1 = time.time()
    rps = compute_rps(close, RpsParams(),
                      name_by_code=panel.get("name_by_code"),
                      volume=panel.get("volume"))
    print(f"RPS 完成（{time.time() - t1:.0f}s）")

    t1 = time.time()
    sig = ST.scan_panel(close, high, low, rps)
    print(f"策略扫描完成（{time.time() - t1:.0f}s）")

    print()
    print("=" * 72)
    for key, label in (("monthly_reversal", "月线反转 6.5"),
                       ("monthly_reversal_first", "月线反转（去重后首日）"),
                       ("triple_red", "三线红")):
        rep = signal_report(close, sig[key].fillna(False), label)
        print(f"\n【{label}】累计 {rep['total']} 个信号日，"
              f"有信号的交易日 {rep['days_with_signal']} 天")
        py = rep["per_year"]
        print("  每年信号数：", "  ".join(f"{y}:{int(v)}" for y, v in py.items() if v > 0))
        for r in rep["returns"]:
            print(f"  未来 {r['horizon']:>3} 日： 事件数={r['n']:>6}  "
                  f"绝对均值 {r['ret_mean'] * 100:>6.1f}%  中位 {r['ret_med'] * 100:>6.1f}%  "
                  f"超额 {r['excess_mean'] * 100:>6.1f}%  "
                  f"胜率 {r['win_rate'] * 100:>4.0f}%  跑赢 {r['beat_rate'] * 100:>4.0f}%")

    print()
    print("=" * 72)
    print("\n【分段对照】月线反转（12 个月，按事件日）")
    rg = regime_report(close, sig["monthly_reversal"].fillna(False))
    print(rg.to_string(index=False))
    print("\n【分段对照】三线红（12 个月，按事件日）")
    rg2 = regime_report(close, sig["triple_red"].fillna(False))
    print(rg2.to_string(index=False))

    print()
    print("【卖点】有效跌破 20 日线 触发统计")
    ex = sig["break_ma20_exit"].fillna(False)
    print(f"  累计触发 {int(ex.values.sum())} 次，"
          f"平均每只 {float(ex.sum(axis=1).mean()):.1f} 次/日")

    print()
    print("【条件组命中分布】每只股票单日的 FYX 命中组数（诊断卡点）")
    hit = sig["fyx_hit"].loc[sig["fyx_hit"].index >= "2013-01-01"]
    dist = hit.stack().value_counts().sort_index()
    tot = int(dist.sum())
    for k, v in dist.items():
        print(f"  命中 {int(k)}/7 组：{int(v):>9}  ({v / tot * 100:5.2f}%)")

    print()
    last_date = close.index[-1]
    now = sig["monthly_reversal"].fillna(False).loc[last_date]
    hit_codes = [c for c in now[now].index]
    print(f"【最新一日 {last_date.date()}】月线反转 {len(hit_codes)} 只")
    nm = panel.get("name_by_code") or {}
    r50, r120, r250 = (rps["rps50"].loc[last_date], rps["rps120"].loc[last_date],
                       rps["rps250"].loc[last_date])
    for c in hit_codes[:top_n]:
        print(f"    {c} {nm.get(c, ''):10s} "
              f"RPS50={r50.get(c, float('nan')) * 100:5.1f}  "
              f"RPS120={r120.get(c, float('nan')) * 100:5.1f}  "
              f"RPS250={r250.get(c, float('nan')) * 100:5.1f}")

    if out_csv:
        sig["monthly_reversal"].fillna(False).to_csv(out_csv, encoding="utf-8-sig")
        print(f"\n信号宽表已写出：{out_csv}")
    print(f"\n总耗时 {time.time() - t0:.0f}s")


def main():
    ap = argparse.ArgumentParser(description="月线反转 6.5 验证跑")
    ap.add_argument("--start", default="20120101", help="数据起点（默认 20120101）")
    ap.add_argument("--quick", type=int, default=0, help="只跑前 N 只（0=全市场）")
    ap.add_argument("--top", type=int, default=40, help="最新一日清单打印条数")
    ap.add_argument("--out", default=None, help="把月线反转信号宽表写到该 csv")
    args = ap.parse_args()
    run(args.start, quick=args.quick, top_n=args.top, out_csv=args.out)


if __name__ == "__main__":
    main()
