# -*- coding: utf-8 -*-
"""
估值报告 JSON 构建器 —— 自 html_renderer.py 改造，输出结构化 JSON 供前端渲染。

不再生成 HTML 文件：结论文字 _conclusion 原样保留，面板行/图表时序/事件/市场背景
统一汇总为一个 dict，由前端 ECharts + 面板渲染。
"""
from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from ..core.utils import fmt_num, fmt_pct
from .factors_registry import all_factors


def _conclusion(readings: Dict, primary: str = "pb_adj_b",
                price_cycle: Optional[float] = None) -> tuple:
    """结论文字：(状态名, 状态色, 主要结论, 补充判断)。原样搬移自 engine._conclusion。"""
    pb_pct = (readings.get("pb", {}).get("pct") or 0)
    read = (readings.get(primary, {}).get("pct") or 0.5)
    pr_pct = (readings.get("pr", {}).get("pct") or 0.5)
    pname = {"pb_adj_b": "季报口径B", "pb_adj": "日频v1"}.get(primary, primary)

    if read <= 0.10:
        state, color, main = "低估机会区", "#1f7a33", \
            f"盈利调节市净率读数（{pname}）{read:.2f}，处于自身历史 {read*100:.0f}% 位置：市场给的价低于盈利成色，属'价格跌过头'一类。"
    elif read >= 0.90:
        state, color, main = "高估风险区", "#c0392b", \
            f"盈利调节市净率读数（{pname}）{read:.2f}，处于自身历史 {read*100:.0f}% 位置：价格里情绪成分大，需警惕。"
    else:
        state, color, main = "中性区", "#8a6d3b", \
            f"盈利调节市净率读数（{pname}）{read:.2f}（历史 {read*100:.0f}% 位置），落在 10%~90% 之间，估值不算极端。"

    extras = []
    if pb_pct <= 0.10 and read >= 0.60:
        extras.append("注意：PB 已处历史低分位，但盈利调节读数不低——低 PB 可能源于盈利中枢下移（0823 文'便宜有两种'），需区分'跌过头'与'东西变了'。")
    if pb_pct <= 0.10 and read <= 0.10:
        extras.append("PB 与盈利调节同处低位：价格相对当前盈利成色确被低估，属'错杀'型便宜。")
    if pr_pct >= 0.90:
        extras.append("市赚率位置偏高（历史 90% 以上）：PE/ROE 处于自身高位，单看破净会误判为便宜。")
    if pr_pct <= 0.10:
        extras.append("市赚率位置偏低（历史 10% 以下）：PE 相对 ROE 处于历史划算档。")
    if price_cycle is not None:
        if read <= 0.10 and price_cycle <= 0.30:
            extras.append(f"三维共振：盈利调节读数低位（{read:.2f}）且价格周期低位（{price_cycle:.2f}）——估值与价格同时处于历史低位区。")
        elif read >= 0.90 and price_cycle >= 0.70:
            extras.append(f"三维共振：盈利调节读数高位（{read:.2f}）且价格周期高位（{price_cycle:.2f}）——双双处于高位，风险集中。")
        elif read <= 0.20 and price_cycle >= 0.70:
            extras.append(f"背离：盈利调节读数偏低（{read:.2f}）但价格周期已高（{price_cycle:.2f}）——价格已涨过一段，估值尚未走贵。")
        elif read >= 0.60 and price_cycle <= 0.30:
            extras.append(f"背离：盈利调节读数偏高（{read:.2f}）而价格周期仍低（{price_cycle:.2f}）——价格尚未反映估值压力。")
    extra = " ".join(extras) if extras else "估值两个维度（市赚率 / 盈利调节）均未处于历史极端位置。"
    return state, color, main, extra


def _s2list(s) -> List:
    """pandas Series → JSON 安全列表（NaN→None）。"""
    if s is None:
        return []
    return [None if pd.isna(v) else round(float(v), 4) for v in s.values]


def _dates(metrics: pd.DataFrame) -> List[str]:
    """date 列 → 'YYYY-MM-DD' 字符串列表。"""
    return [str(pd.Timestamp(v))[:10] for v in metrics["date"].values]


def _extract_chart(metrics: pd.DataFrame, events: List[Dict], primary: str) -> dict:
    """ECharts 四层时序所需数据。"""
    chart = {"dates": _dates(metrics)}

    # 第1层：收盘价
    if "close" in metrics.columns:
        chart["close"] = _s2list(metrics["close"])

    # 各层曲线：融合读数 + 盈利调节读数 + PB/PE（pct）
    for col in ("fusion_pct", "pb_adj_b_pct", "pb_adj_pct", "ps_adj_pct",
                "pb_pct", "pe_ttm_pct"):
        if col in metrics.columns:
            chart[col] = _s2list(metrics[col])

    # 第3层：市赚率位置（两口径 pct）
    for col in ("pr_pct", "pr_avg_pct"):
        if col in metrics.columns:
            chart[col] = _s2list(metrics[col])

    # 第4层：价格周期位置
    if "price_cycle" in metrics.columns:
        chart["price_cycle"] = _s2list(metrics["price_cycle"])

    # 买卖标记（按主口径）
    chart["buy_markers"] = [{"date": e["date"], "value": round(e["read"], 4),
                             "close": round(e["close"], 2)}
                            for e in events if e["kind"] == "买"]
    chart["sell_markers"] = [{"date": e["date"], "value": round(e["read"], 4),
                              "close": round(e["close"], 2)}
                             for e in events if e["kind"] == "卖"]
    return chart


def build_report(code: str, name: str, as_of, readings: Dict, events: List[Dict],
                 primary: str, roe_src: int = 0, ml_note: str = "未启用",
                 signal_col: Optional[str] = None,
                 stats: Optional[dict] = None,
                 roe_warning: Optional[str] = None,
                 mkt_note: Optional[str] = None,
                 thresholds: Optional[tuple] = None,
                 triggers: Optional[List[Dict]] = None,
                 price_cycle: Optional[float] = None,
                 price_cycle_detail: Optional[dict] = None,
                 metrics: Optional[pd.DataFrame] = None) -> dict:
    """汇总估值报告为结构化 JSON。"""
    state, color, main, extra = _conclusion(readings, primary, price_cycle)

    # 面板行：遍历注册因子收集（原 _read_rows 逻辑）
    panel_ctx = {"readings": readings, "price_cycle": price_cycle}
    panel_rows: List[dict] = []
    for f in all_factors():
        if f.panel and f.panel_rows:
            for k, v, note in (f.panel_rows(panel_ctx) or []):
                panel_rows.append({"label": k, "value": v, "note": note})

    chart = _extract_chart(metrics, triggers if triggers is not None else events, primary) \
        if metrics is not None else {}

    # 口径说明
    pname = {"pb_adj_b": "B 季报ROE（主）", "pb_adj": "v1 日频ROE"}.get(primary, primary)
    roe_note = (f"季报 ROE 已载入 {roe_src} 期（akshare，报告期后 30 天生效）"
                if roe_src else "季报 ROE 不可用（akshare 未装/拉取失败），B 轨缺席，主口径退化为 v1 日频ROE")
    pc_note = ("价格周期位置 " + fmt_num(price_cycle)) if price_cycle is not None else "价格周期不可用"
    pay = (readings.get("pr_adj") or {}).get("payout") or {}
    payout_note = (f"{pay.get('year')} 年报支付率 {fmt_pct(pay.get('payout'))}"
                   if pay.get("payout") is not None else "本地不可得，N=1.0 未做质量修正")
    sig_name = {"fusion_pct": "多因子融合读数", "pb_adj_b_pct": "盈利调节市净率(B)",
                "pb_adj_pct": "盈利调节市净率(v1)"}.get(signal_col or "", signal_col or primary)

    return {
        "meta": {
            "code": code,
            "name": name,
            "as_of": str(pd.Timestamp(as_of))[:10],
            "primary": primary,
            "primary_name": pname,
            "roe_src": roe_src,
            "roe_note": roe_note,
            "ml_note": ml_note,
            "pc_note": pc_note,
            "payout_note": payout_note,
            "signal_col": signal_col,
            "signal_name": sig_name,
            "mkt_note": mkt_note,
            "buy_threshold": (thresholds[0] if thresholds else None),
            "sell_threshold": (thresholds[1] if thresholds else None),
            "triggers": triggers or [],
            "rows_count": len(metrics) if metrics is not None else 0,
        },
        "conclusion": {"state": state, "color": color, "main": main, "extra": extra,
                       "warning": roe_warning},
        "panel_rows": panel_rows,
        "events": events,
        "stats": stats or {},
        "price_cycle_detail": price_cycle_detail,
        "chart": chart,
    }
