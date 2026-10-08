# -*- coding: utf-8 -*-
"""买点门控 · 消融实验（离线、只读；不改任何生产逻辑）。

目的
----
2026-10-02 给估值信号加了「主信号 + 门控」架构（`valuation_engine.BUY_GATES`）：
  主信号 = 读数 ≤ buy_threshold；门控是"必须通过"的与条件，只作用于买。
本脚本用**生产同一套**二态机 + 交易统计，横截面比较「开/关各门控」的效果，
避免"拍脑袋加因子"。与 `valuation_eval_power.py` 的分工：
  * `valuation_eval_power.py`  —— 因子层（IC / 分位超额）与事件层（单因子）
  * 本脚本                      —— **门控层**的消融对比

口径（务必连着读）
-----------------
* 目标 = 策略收益 vs 一直持有（超额），**不惩罚回撤** —— 对防守型门控不公平；
* 门控的**副作用是降低持仓占比**（买得更少），所以必须同时看「持仓占比」与「交易笔数」，
  否则"超额高"可能只是"买得少"；
* 单段行情会制造假象（2021-2026 价值风格占优），结论只对"这批股 / 这段行情 / 这个目标"成立；
* 缺数据 fail-open（与生产一致），故预热期不拦。

用法（需先启动 stockdb；B 轨首次会联网拉季报 ROE）
    python scripts/valuation_eval_gates.py                    # hs300 前 60 只
    python scripts/valuation_eval_gates.py --top 120 --pool zz500
    python scripts/valuation_eval_gates.py --gates roe_quality
"""
from __future__ import annotations

import argparse
import time
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from _bootstrap import ensure_project_root

ensure_project_root()

from stock_monitor.analyzers import valuation_engine as VE  # noqa: E402
from stock_monitor.analyzers.factors_registry import get_factor  # noqa: E402
from stock_monitor.data_fetchers.pool_data_fetcher import get_index_constituents  # noqa: E402
from stock_monitor.data_fetchers.stockdb_data_fetcher import get_daily  # noqa: E402

# 消融组合：每项 = (标签, 门控列表)
COMBOS = [
    ("无门控（对照）", []),
    ("仅盈利质量", ["roe_quality"]),
    ("仅价格位置", ["price_position"]),
    ("两者都开（当前默认）", ["roe_quality", "price_position"]),
]


def build_metrics(code: str) -> Optional[pd.DataFrame]:
    """单股因子管线（与 run_valuation 同源，但不出报告/图，也不需要营收）。"""
    df = get_daily(code, start=VE.DATA_START, fq=VE.FQ)
    if df is None or df.empty:
        return None
    roe_reports = None
    try:
        from stock_monitor.data_fetchers.fundamental_data_fetcher import get_report_roe
        roe_reports = get_report_roe(code)
    except Exception:  # noqa: BLE001
        pass
    base = get_factor("valuation")
    m = base.compute(df, roe_reports=roe_reports, revenue_reports=None,
                     market_level=None, payout_ratio=None)
    if m is None or len(m) < VE.DATA_START_VALID:
        return None
    # 并入价格周期（门控需要）
    pc = get_factor("price_cycle")
    if pc is not None:
        sub = pc.compute(df)
        if sub is not None and not sub.empty and "price_cycle" in sub.columns:
            m = m.merge(sub[["date", "price_cycle"]], on="date", how="left")
    return m


def evaluate_one(m: pd.DataFrame, code: str, gates: List[str]) -> Optional[Dict]:
    """用生产同一套二态机 + trade_stats 算一条样本。"""
    primary = "pb_adj_b" if "pb_adj_b" in m.columns else "pb_adj"
    col = f"{primary}_pct"
    if col not in m.columns:
        return None
    buy, sell = VE.thresholds_for(code)
    mask, _ = VE._gate_mask(m, gates) if gates else (None, {})
    stats_out: Dict = {}
    ev = VE._signal_events_hold(m, col=col, buy=buy, sell=sell,
                               gate_mask=mask, stats_out=stats_out)
    st = VE.trade_stats(m, ev)
    if not st:
        return None
    return {
        "code": code,
        "strat": st.get("strat_return", 0.0),
        "bh": st.get("bh_return", 0.0),
        "excess": st.get("strat_return", 0.0) - st.get("bh_return", 0.0),
        "strat_mdd": st.get("strat_mdd", 0.0),
        "bh_mdd": st.get("bh_mdd", 0.0),
        "pos_ratio": st.get("pos_ratio", 0.0),
        "trades": st.get("trades", 0),
        "blocked": stats_out.get("blocked_buys", 0),
    }


def summarize(rows: List[Dict], label: str) -> Dict:
    if not rows:
        return {}
    ex = np.array([r["excess"] for r in rows], dtype=float)
    return {
        "label": label,
        "n": len(rows),
        "strat": float(np.mean([r["strat"] for r in rows])),
        "bh": float(np.mean([r["bh"] for r in rows])),
        "excess": float(np.mean(ex)),
        "excess_med": float(np.median(ex)),
        "win": float((ex > 0).mean()),
        # 回撤（门控的"防守价值"主要看这里）：平均策略回撤 / 平均持有回撤
        "strat_mdd": float(np.mean([r["strat_mdd"] for r in rows])),
        "bh_mdd": float(np.mean([r["bh_mdd"] for r in rows])),
        # 策略跑赢"一直持有"的股票占比（比超额均值更抗离群值）
        "beat": float(np.mean([r["strat"] > r["bh"] for r in rows])),
        "pos_ratio": float(np.mean([r["pos_ratio"] for r in rows])),
        "trades": float(np.mean([r["trades"] for r in rows])),
        "blocked": float(np.mean([r["blocked"] for r in rows])),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="买点门控消融实验")
    ap.add_argument("--pool", default="hs300")
    ap.add_argument("--top", type=int, default=60, help="取池内前 N 只")
    ap.add_argument("--gates", default="", help="只测指定门控（逗号分隔）；默认测全部组合")
    ap.add_argument("--codes", default="", help="直接指定代码（逗号分隔），跳过指数成分拉取")
    ap.add_argument("--codes-file", default="", help="从文件读代码（每行一个）")
    args = ap.parse_args(argv)

    if args.codes or args.codes_file:
        if args.codes_file:
            codes = [ln.strip() for ln in open(args.codes_file, encoding="utf-8")
                     if ln.strip() and not ln.startswith("#")]
        else:
            codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        print(f"直接指定 {len(codes)} 只（跳过指数成分拉取）")
    else:
        cons = get_index_constituents(args.pool) or []
        codes = [c["code"] if isinstance(c, dict) else str(c) for c in cons][:args.top]
        print(f"池={args.pool}  取 {len(codes)} 只")
    codes = codes[:args.top]
    print(f"门控阈值 roe_quality≥{VE.GATE_ROE_QUALITY_MIN} / price_position≤{VE.GATE_PRICE_POSITION_MAX}")

    combos = COMBOS
    if args.gates:
        want = [g.strip() for g in args.gates.split(",") if g.strip()]
        combos = [("指定：" + "+".join(want), want)]

    # 一次取数，多组合复用
    cache: Dict[str, pd.DataFrame] = {}
    t0 = time.time()
    for i, code in enumerate(codes, 1):
        try:
            m = build_metrics(code)
        except Exception as e:  # noqa: BLE001
            print(f"  [{i}/{len(codes)}] {code} 失败: {type(e).__name__}: {str(e)[:60]}")
            continue
        if m is not None:
            cache[code] = m
        if i % 20 == 0:
            print(f"  …已算 {i}/{len(codes)}（{time.time()-t0:.0f}s，成功 {len(cache)}）")
    print(f"取数完成：{len(cache)} 只有效，耗时 {time.time()-t0:.0f}s\n")

    results = {}
    for label, gates in combos:
        rows = []
        for code, m in cache.items():
            r = evaluate_one(m, code, gates)
            if r:
                rows.append(r)
        results[label] = (summarize(rows, label), rows)

    base = results[combos[0][0]][0]
    print("=" * 132)
    print(f"{'组合':<22}{'样本':>5}{'平均策略':>10}{'平均持有':>10}{'平均超额':>10}"
          f"{'超额中位':>10}{'跑赢率':>8}{'策略回撤':>10}{'持有回撤':>10}"
          f"{'持仓占比':>10}{'交易笔数':>9}{'挡下':>7}")
    print("-" * 132)
    for label, (s, _) in results.items():
        if not s:
            print(f"{label:<22} (无样本)")
            continue
        print(f"{label:<22}{s['n']:>5}{s['strat']*100:>9.1f}%{s['bh']*100:>9.1f}%"
              f"{s['excess']*100:>9.1f}%{s['excess_med']*100:>9.1f}%{s['beat']*100:>7.0f}%"
              f"{s['strat_mdd']*100:>9.1f}%{s['bh_mdd']*100:>9.1f}%"
              f"{s['pos_ratio']*100:>9.0f}%{s['trades']:>9.1f}{s['blocked']:>7.1f}")
    print("=" * 132)

    if len(results) > 1 and base:
        print("\n相对「无门控」的增量（正 = 门控有帮助）：")
        for label, (s, _) in list(results.items())[1:]:
            if not s:
                continue
            print(f"  {label:<22} 超额 {100*(s['excess']-base['excess']):+6.2f}pp"
                  f" · 跑赢率 {100*(s['beat']-base['beat']):+5.1f}pp"
                  f" · 回撤改善 {100*(s['strat_mdd']-base['strat_mdd']):+6.2f}pp"
                  f" · 持仓 {100*(s['pos_ratio']-base['pos_ratio']):+5.1f}pp"
                  f" · 交易 {s['trades']-base['trades']:+.1f} 笔")

    print("\n读法提醒：")
    print("  * 门控的**主要价值在回撤**（'别接飞刀'），所以先看『回撤改善』再看『超额』；")
    print("  * 超额为正 ≠ 门控好 —— 还要看持仓占比是否被压太低、交易笔数是否骤减；")
    print("  * 目标未惩罚回撤的『超额』对防守型门控天生不公平，单段行情也会制造假象。")


if __name__ == "__main__":
    main()
