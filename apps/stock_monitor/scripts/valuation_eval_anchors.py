# -*- coding: utf-8 -*-
"""锚点验收：把"盈利调节市净率"三口径读数与 docs/ref_docs 文章给出的读数对照。

另打印**市赚率 PR 三口径**（隐含ROE / 季报ROE / 多年平均ROE）与 N、修正PR 的最新值
（文章口径见 0830 文与 ericwarn"巴菲特与市赚率"系列）。

用法（需先启动 stockdb.exe；B 轨首次运行会联网拉季报 ROE）：
  python scripts/valuation_eval_anchors.py            # 打印读数对照表
  python scripts/valuation_eval_anchors.py 002001     # 只看某只

两口径：B=季报 ROE（akshare，年化）／v1=日频隐含ROE(pb/pe_ttm)。
读数一律为"截至当期历史位置(0~1)"。是否扣"市场水位"由 config.ini [valuation] market_level_enabled 控制（默认关闭）。
"""
from __future__ import annotations

import sys

from _bootstrap import ensure_project_root

ensure_project_root()

from config import get_path  # noqa: E402
from stock_monitor.core.utils import safe_float  # noqa: E402
from stock_monitor.data_fetchers.stockdb_data_fetcher import get_daily  # noqa: E402
from stock_monitor.data_fetchers.fundamental_data_fetcher import get_report_roe  # noqa: E402
from stock_monitor.analyzers.factor_valuation import compute_valuation_metrics  # noqa: E402
from stock_monitor.analyzers.market_temperature import get_market_level  # noqa: E402

MARKET_LEVEL_ENABLED = get_path("valuation", "market_level_enabled", "false").lower() in ("1", "true", "yes")
MARKET_LEVEL_POOL = get_path("valuation", "market_level_pool", "hs300")

# (code, name, [(文章日期, 文章读数, 备注)])
ANCHORS = [
    ("002001", "新和成", [("2023-07-07", 0.060, "见底"),
                          ("2026-03-12", 0.847, "阶段顶"),
                          ("2026-04-07", 0.890, "上穿卖线")]),
    ("600612", "老凤祥", [("2026-08-28", 0.210, "长期低位")]),
    ("600660", "福耀玻璃", [("2026-08-28", 0.130, "低位")]),
    ("601398", "工商银行", [("2026-08-28", 0.960, "高位")]),
    ("600618", "氯碱化工", [("2026-09-05", 0.730, "偏贵")]),
    ("601166", "兴业银行", []),
]


def build(code: str, use_level: bool):
    df = get_daily(code, start="20100101")
    if df is None or df.empty:
        return None
    reps = get_report_roe(code)
    ml = get_market_level(MARKET_LEVEL_POOL) if use_level else None
    return compute_valuation_metrics(df, roe_reports=reps, market_level=ml)


def _pct(r, prefix):
    v = safe_float(r.get(f"{prefix}_pct"))
    return f"{v:.3f}" if v is not None else "  -  "


def _val(r, col):
    v = safe_float(r.get(col))
    return f"{v:.2f}" if v is not None else "  -  "


def main(codes=None):
    print(f"市场水位扣减: {'启用' if MARKET_LEVEL_ENABLED else '关闭'}（config.ini [valuation] market_level_enabled）\n")
    header = f"{'标的':<16}{'日期':<12}{'v1日频':>8}{'B季报':>9}{'文章':>8}"
    print(header)
    print("-" * len(header))

    latest = []
    for code, name, pts in ANCHORS:
        if codes and code not in codes:
            continue
        m = build(code, MARKET_LEVEL_ENABLED)
        if m is None:
            print(f"{name}({code}) 无日K，跳过")
            continue
        latest.append((code, name, m.iloc[-1]))
        for date_str, doc, _note in pts:
            sub = m[m["date"] <= date_str]
            if sub.empty:
                continue
            r = sub.iloc[-1]
            roe_b = r.get("roe_step_b")
            roe_txt = f"{float(roe_b)*100:.1f}%" if roe_b is not None and roe_b == roe_b else "-"
            print(f"{name + '(' + code + ')':<16}{str(r['date'])[:10]:<12}"
                  f"{_pct(r, 'pb_adj'):>8}{_pct(r, 'pb_adj_b'):>9}"
                  f"{doc:>8.3f}   B轨ROE={roe_txt}")

    if latest:
        print("\n--- 市赚率 PR（最新，三口径；文章：PR = PE/ROE，越低越划算）---")
        hdr = f"{'标的':<16}{'隐含ROE':>9}{'季报ROE':>9}{'多年均ROE':>10}{'N':>7}{'修正PR':>9}"
        print(hdr)
        print("-" * len(hdr))
        for code, name, r in latest:
            print(f"{name + '(' + code + ')':<16}{_val(r, 'pr'):>9}{_val(r, 'pr_b'):>9}"
                  f"{_val(r, 'pr_avg'):>10}{_val(r, 'n'):>7}{_val(r, 'pr_adj'):>9}")
    print("文章锚点：0830 文（新和成/老凤祥/福耀/工行，读数截至 2026-08-28）、0905 文（新和成日期）、0906 文（氯碱）。")


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
