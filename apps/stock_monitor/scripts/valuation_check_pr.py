# -*- coding: utf-8 -*-
"""市赚率口径自检（离线，不依赖 stockdb / 网络）。

覆盖：
  1) payout_to_n：分红率 → 修正系数 N 的分段与线性插值（0830 文口径）；
  2) avg_roe_from_reports：多年平均 ROE（近 N 个年报均值 / 退化路径）；
  3) 市赚率合成算例：PE 20 / ROE 15% → 1.33（0830 文数字）；
  4) N 生效：修正市赚率 = N × PR；多口径列存在性。

用法：python scripts/valuation_check_pr.py     退出码 0=全通过，1=有失败项。
"""
from __future__ import annotations

from _bootstrap import ensure_project_root

ensure_project_root()

import pandas as pd  # noqa: E402

from stock_monitor.analyzers.factor_valuation import (  # noqa: E402
    avg_roe_from_reports,
    compute_valuation_metrics,
    payout_to_n,
)

_failed: list = []


def check(name: str, got, want: float, tol: float = 1e-6) -> None:
    ok = got is not None and abs(float(got) - float(want)) <= tol
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got={got} want={want}")
    if not ok:
        _failed.append(name)


def check_true(name: str, cond: bool) -> None:
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        _failed.append(name)


def _mk_df(pb: float, pe: float, n: int = 10) -> pd.DataFrame:
    """合成日K：pb/pe_ttm 恒定，隐含ROE = pb/pe 恒定。"""
    return pd.DataFrame({
        "date": pd.bdate_range("2024-01-01", periods=n),
        "close": [pb * 10.0] * n,
        "pb": [pb] * n,
        "pe_ttm": [pe] * n,
    })


def main() -> int:
    print("== payout_to_n（分红率 → N，0830 文：≥50%→1.0 / ≤25%→2.0 / 中间线性）==")
    check("分红率 50% -> N", payout_to_n(0.50), 1.0)
    check("分红率 25% -> N", payout_to_n(0.25), 2.0)
    check("分红率 37.5% -> N", payout_to_n(0.375), 1.5)
    check("分红率 60% -> N（上限截断）", payout_to_n(0.60), 1.0)
    check("分红率 10% -> N（下限截断）", payout_to_n(0.10), 2.0)
    check("分红率 None -> N=1.0", payout_to_n(None), 1.0)
    check("分红率 NaN -> N=1.0", payout_to_n(float("nan")), 1.0)

    print("\n== avg_roe_from_reports（多年平均 ROE，小数）==")
    reps = [{"report_date": f"{2020 + i}-12-31", "roe": 10.0 + 10 * i, "roe_ann": 10.0 + 10 * i}
            for i in range(6)]
    check("近 5 年年报均值（取最近 5 期）", avg_roe_from_reports(reps),
          (20 + 30 + 40 + 50 + 60) / 5 / 100.0)
    check("无年报时退化为年化 ROE 均值",
          avg_roe_from_reports([{"report_date": "2026-06-30", "roe": 8.0, "roe_ann": 16.0}]), 0.16)
    check_true("空列表 -> None", avg_roe_from_reports([]) is None)
    check_true("None -> None", avg_roe_from_reports(None) is None)

    print("\n== 市赚率合成算例（0830 文：PE 20 倍 / ROE 15% -> 1.33）==")
    m = compute_valuation_metrics(_mk_df(pb=3.0, pe=20.0))
    check("PR = PE / ROE(%)", float(m["pr"].iloc[-1]), 20.0 / 15.0)
    check("PR = 1.0（PE 15 / ROE 15%）",
          float(compute_valuation_metrics(_mk_df(pb=2.25, pe=15.0))["pr"].iloc[-1]), 1.0)
    check_true("亏损（PE<0）-> PR 缺席",
               bool(compute_valuation_metrics(_mk_df(pb=1.0, pe=-10.0))["pr"].isna().all()))

    print("\n== N 生效：修正市赚率 = N × PR ==")
    m3 = compute_valuation_metrics(_mk_df(pb=3.0, pe=20.0), payout_ratio=0.43)
    n = float(m3["n"].iloc[-1])
    check("支付率 43% -> N", n, 1.0 + (0.5 - 0.43) / 0.25)
    check("pr_adj = N × pr", float(m3["pr_adj"].iloc[-1]), n * float(m3["pr"].iloc[-1]))
    check("缺分红数据 -> N=1.0", float(compute_valuation_metrics(
        _mk_df(pb=3.0, pe=20.0))["n"].iloc[-1]), 1.0)

    print("\n== 多口径列存在性 ==")
    check_true("pr_b 列始终存在", "pr_b" in m.columns)
    check_true("无季报 -> pr_avg 列缺席", "pr_avg" not in m.columns)
    check_true("有季报 -> pr_avg 列存在",
               "pr_avg" in compute_valuation_metrics(_mk_df(pb=3.0, pe=20.0),
                                                     roe_reports=reps).columns)

    print()
    if _failed:
        print(f"FAILED {len(_failed)}: {_failed}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
