# -*- coding: utf-8 -*-
"""
选股规则引擎 —— 「长周期均线趋势 + 回调买点」。

**纯计算，无 IO、无 Web 依赖**（数据获取在 `picker_runner.py`）。

结构：
  * 指标层 —— 已抽到共享模块 `analyzers/ma_indicators.py`（与「趋势分析」共用）
  * 规则层 —— `Params` 参数 + `evaluate_*` 纯函数，统一返回 `{passed, note, metrics}`；
    `evaluate_all` 串联必选规则得出最终结果

默认参数体现“趋势中回调买点”语义：A 多头结构 / B 金叉二次确认 / C 回调买点 为必选，
量能缩量为软条件（默认关）。
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Dict, List, Optional

import pandas as pd

from .ma_indicators import (
    add_ma,
    detect_ma_cross_up,
    dist_to_ma,
    records_to_frame,
    slope_pct,
)


# =========================================================================== #
# 规则层
# =========================================================================== #
@dataclass
class Params:
    """可参数化的策略参数（前端面板对应这些滑块/输入）。"""

    ma_fast: int = 20    # 快线 = 回调支撑
    ma_mid: int = 60     # 中线上穿慢线 = 二次确认
    ma_slow: int = 200   # 慢线 = 大趋势
    # 必选：多头结构（A）
    require_bull_structure: bool = True
    min_price_above_slow_ratio: float = 0.02   # 价格至少高于慢线 2%
    fast_slope_min_pct: float = 0.0            # 快线最近 window 斜率下限
    structure_slope_window: int = 10
    # 并入原「均线多头排列」：快线需高于慢线至少该百分比（0 = 不要求）
    min_fast_slow_gap_pct: float = 0.0
    # 必选：金叉二次确认（B）
    require_golden_cross: bool = True
    cross_lookback_bars: int = 120        # 在多少根K线内发生过 ma_mid 上穿 ma_slow
    cross_min_bars_since: int = 1         # 金叉最早至少距离 1 根（排除刚金叉即算）
    cross_max_bars_since: int = 120       # 金叉最晚允许距今的根数(与 lookback 一致即可)
    # 必选：回调买点（C）
    require_pullback: bool = True
    # —— C1 现价贴近快线(买点)：均为相对 ma_fast 的乖离率(%),供"今天收盘价"判断 ——
    pullback_min_dist_pct: float = -0.5   # 现价距快线的允许下穿下限(如 -0.5% => 收盘仅允许略破快线)
    pullback_max_dist_pct: float = 5.0    # 现价距快线(上方)的容忍上限：<=5% 皆视为仍贴近快线
    pullback_confirm_window: int = 10     # 回踩确认用的回顾窗口(近 N 根)
    # —— C2 回踩确认(历史上曾回踩过快线)：近窗口内存在某根K线的 low 进入快线附近带 ——
    pullback_low_touch_below_pct: float = 1.5  # low 允许下探到快线下方最多 1.5%
    pullback_low_touch_above_pct: float = 3.0  # low 允许回踩带上界：高于快线最多 3%(以免把单边冲高当回踩)
    allow_close_break_mid: bool = False   # 是否允许 close 跌破 ma_mid（默认不允许）
    mid_break_tolerance_pct: float = 1.0  # 允许 close 下穿 ma_mid 但不超过此比例
    # 软条件：成交量
    use_volume_shrink: bool = False       # 是否启用缩量软条件
    volume_shrink_lookback: int = 5
    volume_shrink_max_ratio: float = 0.8  # 近 N 日均量 / 放量参考 ≤ 此值视为缩量

    @classmethod
    def from_dict(cls, d: Optional[Dict]) -> "Params":
        """从请求参数构造，**只接受已知键**并做类型/范围校验（非法 → ValueError）。"""
        known = {f.name: f.type for f in fields(cls)}
        kwargs: Dict = {}
        for k, v in (d or {}).items():
            if k not in known:
                continue
            kwargs[k] = _coerce(k, known[k], v)

        p = cls(**kwargs)
        if p.cross_min_bars_since > p.cross_max_bars_since:
            raise ValueError("cross_min_bars_since 不能大于 cross_max_bars_since")
        if p.pullback_min_dist_pct > p.pullback_max_dist_pct:
            raise ValueError("pullback_min_dist_pct 不能大于 pullback_max_dist_pct")
        return p

    def to_dict(self) -> Dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


# 数值参数的允许区间（越界 → ValueError）
_RANGES = {
    "ma_fast": (2, 500),
    "ma_mid": (2, 500),
    "ma_slow": (2, 500),
    "min_price_above_slow_ratio": (-100.0, 100.0),
    "fast_slope_min_pct": (-100.0, 100.0),
    "structure_slope_window": (2, 250),
    "min_fast_slow_gap_pct": (0.0, 100.0),
    "cross_lookback_bars": (0, 1000),
    "cross_min_bars_since": (0, 1000),
    "cross_max_bars_since": (0, 1000),
    "pullback_min_dist_pct": (-100.0, 100.0),
    "pullback_max_dist_pct": (-100.0, 100.0),
    "pullback_confirm_window": (1, 250),
    "pullback_low_touch_below_pct": (0.0, 100.0),
    "pullback_low_touch_above_pct": (0.0, 100.0),
    "mid_break_tolerance_pct": (0.0, 100.0),
    "volume_shrink_lookback": (1, 250),
    "volume_shrink_max_ratio": (0.0, 10.0),
}


def _coerce(name: str, type_hint, value):
    """按 dataclass 字段类型把入参转成正确类型并校验范围。

    `from __future__ import annotations` 下 `type_hint` 是字符串（'int'/'float'/'bool'）。
    """
    kind = type_hint if isinstance(type_hint, str) else getattr(type_hint, "__name__", "")
    try:
        if kind == "bool":
            val = value if isinstance(value, bool) else str(value).strip().lower() in (
                "1", "true", "yes", "on")
        elif kind == "int":
            val = int(float(value))
        else:
            val = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"参数 {name} 取值非法: {value!r}") from None

    if kind in ("int", "float") and name in _RANGES:
        lo, hi = _RANGES[name]
        if not (lo <= val <= hi):
            raise ValueError(f"参数 {name}={val} 超出允许范围 [{lo}, {hi}]")
    return val


def evaluate_structure(df: pd.DataFrame, p: Params) -> dict:
    """A 多头结构：价格站上慢线、中/快线高于慢线、快线向上。"""
    if df.empty:
        return _not("数据为空")
    ma_f = f"ma{p.ma_fast}"
    ma_m = f"ma{p.ma_mid}"
    ma_s = f"ma{p.ma_slow}"
    if not all(c in df.columns for c in (ma_f, ma_m, ma_s)):
        return _not("行情不足以计算所需均线")
    row = df.iloc[-1]
    mf, mm, ms = row[ma_f], row[ma_m], row[ma_s]
    if any(_isna(v) for v in (mf, mm, ms)):
        return _not("均线数据含空缺(上市时间不足)")

    price = float(row["close"])
    metrics = {
        "price": round(price, 2),
        "ma_slow": round(float(ms), 2),
    }
    checks = [(price > float(ms) * (1 + p.min_price_above_slow_ratio / 100), "价格站上慢线")]
    if p.require_bull_structure:
        checks.append((float(mm) > float(ms), "中线高于慢线"))
        checks.append((float(mf) > float(mm), "快线高于中线"))

    slope = slope_pct(df, ma_f, p.structure_slope_window)
    metrics["fast_slope_pct"] = slope
    if slope is not None:
        checks.append((slope >= p.fast_slope_min_pct, "快线向上(斜率下限)"))

    return _and(checks, "structure", metrics)


def evaluate_golden_cross(df: pd.DataFrame, p: Params) -> dict:
    """B 金叉二次确认：lookback 内 ma_mid 上穿 ma_slow，且距今日根数落在 [min, max]。"""
    res = detect_ma_cross_up(df, f"ma{p.ma_mid}", f"ma{p.ma_slow}", p.cross_lookback_bars)
    if res is None:
        return _not(
            f"近{p.cross_lookback_bars}根未出现 ma{p.ma_mid}上穿ma{p.ma_slow} 的金叉"
        )
    bars = res["cross_bars_ago"]
    ok_window = p.cross_min_bars_since <= bars <= p.cross_max_bars_since
    note = f"金叉于 {res['cross_date']}(距今{bars}根)"
    metrics = {"cross_bars_ago": bars, "cross_date": res["cross_date"]}
    if not ok_window:
        return _not(note + f"，不在{bars}窗口内", metrics)
    return _ok(note, metrics)


def evaluate_pullback(df: pd.DataFrame, p: Params) -> dict:
    """C 回调买点，两处独立校验都在相对快线(ma_fast) 的百分比上进行：
        C1 现价(收盘)贴近快线：dist∈[pullback_min_dist, pullback_max_dist]，且不深破中线(ma_mid)。
        C2 回踩确认：近 N 根内存在某根 LOW 落在快线回踩带 touch_below~touch_above。
    """
    if df.empty:
        return _not("空数据")
    ma_f = f"ma{p.ma_fast}"
    ma_m = f"ma{p.ma_mid}"
    if ma_f not in df.columns or ma_m not in df.columns:
        return _not("均线缺失")

    dist = dist_to_ma(df, ma_f)  # close 相对 fast 乖离率（%）
    if dist is None:
        return _not("无法计算乖离")

    ok_dist = p.pullback_min_dist_pct <= dist <= p.pullback_max_dist_pct
    notes = []
    metrics = {"dist_to_ma_fast_pct": dist}
    # 中线不破检查
    last = df.iloc[-1]
    mid = last[ma_m]
    if _isna(mid):
        return _not("中线缺数据")
    mid = float(mid)
    metrics["ma_mid"] = round(mid, 2)
    below_mid_pct = round((float(last["close"]) - mid) / mid * 100, 2)
    metrics["dist_to_ma_mid_pct"] = below_mid_pct
    if below_mid_pct < 0 and not p.allow_close_break_mid:
        # 只允许最多略破(容差内)
        if abs(below_mid_pct) <= p.mid_break_tolerance_pct:
            notes.append(f"close 略破中线({below_mid_pct}%)，容差内")
        else:
            return _not(f"close 已深跌破中线({below_mid_pct}%)", metrics)
    else:
        notes.append(f"close 仍在中线之上({below_mid_pct}%)")

    ok_low = _low_confirmed_pushback(df, p)
    if ok_dist:
        notes.append(f"乖离 {dist}% 在回调带内")
    elif dist < p.pullback_min_dist_pct:
        notes.append(f"乖离 {dist}% 过深(跌破快线容差)")
    else:
        notes.append(f"乖离 {dist}% 过大(离快线太远，或为上涨途中)")

    if not ok_low:
        notes.append("近窗口 Low 未形成贴近快线的回踩确认")
    mid_break_ok = (below_mid_pct >= -p.mid_break_tolerance_pct) or p.allow_close_break_mid
    passed = ok_dist and ok_low and mid_break_ok
    return _result(passed, "; ".join(notes), metrics)


def _low_confirmed_pushback(df: pd.DataFrame, p: Params) -> bool:
    """近期(pullback_confirm_window 根)，是否存在某根K线 its LOW 已进入"快线回踩带"。

    回踩带上界 = ma_fast × (1 + pullback_low_touch_above_pct / 100)
    回踩带下界 = ma_fast × (1 − pullback_low_touch_below_pct / 100)
    只要 LOW 落在该带内 → 说明股价确实曾下探并"贴近/回踩"过快线，属于回踩确认证据。
    """
    seg = df.tail(p.pullback_confirm_window)
    ma_f = f"ma{p.ma_fast}"
    if len(seg) == 0:
        return False
    hi = 1 + p.pullback_low_touch_above_pct / 100.0
    lo = 1 - p.pullback_low_touch_below_pct / 100.0
    for _, r in seg.iterrows():
        fast = r[ma_f]
        if _isna(fast):
            continue
        low = r["low"]
        if float(fast * lo) <= float(low) <= float(fast * hi):
            return True
    return False


def evaluate_volume(df: pd.DataFrame, p: Params) -> dict:
    """软条件：回调期量能相对放量段收窄。无成交量数据时跳过视为通过（防止误杀）。"""
    if not p.use_volume_shrink:
        return _ok("未启用", {})
    if df.empty or "volume" not in df.columns:
        return _ok("无成交量数据，跳过", {})

    recent = float(pd.to_numeric(df["volume"].tail(p.volume_shrink_lookback),
                                 errors="coerce").mean())
    peak = float(pd.to_numeric(df["volume"], errors="coerce")
                 .tail(p.volume_shrink_lookback * 3).max())
    if not peak:
        return _ok("量能为0，跳过", {})
    ratio = round(recent / peak, 3)
    ok = ratio <= p.volume_shrink_max_ratio
    return _result(ok, f"量能比 {ratio}" + ("(缩量)" if ok else "(未缩量)"),
                   {"volume_ratio": ratio})


def evaluate_all(records: List[dict], p: Params) -> dict:
    """对单只股票的完整判定。records 为升序 K 线。返回:
        {passed, reasons:[{rule_id,passed,note,metrics}...]}  passed=所有(必选)规则 合取
    数据不足时该股直接 miss，不触发后续。
    """
    frame = records_to_frame(records)
    needs = max(p.ma_fast, p.ma_mid, p.ma_slow)
    if len(frame) < needs:
        return {
            "passed": False,
            "reasons": [
                {
                    "rule_id": "data",
                    "passed": False,
                    "note": f"交易日({len(frame)})不足计算 {needs} 日均线",
                    "metrics": {"bars": len(frame), "need": needs},
                }
            ],
        }
    frame = add_ma(frame, [p.ma_fast, p.ma_mid, p.ma_slow])
    evals = []
    if p.require_bull_structure:
        evals.append(("structure", evaluate_structure(frame, p)))
    if p.require_golden_cross:
        evals.append(("golden_cross", evaluate_golden_cross(frame, p)))
    if p.require_pullback:
        evals.append(("pullback", evaluate_pullback(frame, p)))
    if p.use_volume_shrink:
        evals.append(("volume", evaluate_volume(frame, p)))

    reasons = [
        {"rule_id": rid, "passed": r["passed"], "note": r["note"], "metrics": r.get("metrics", {})}
        for rid, r in evals
    ]
    passed = bool(evals) and all(rule_res["passed"] for _, rule_res in evals)
    return {"passed": passed, "reasons": reasons}


# =========================================================================== #
# helpers
# =========================================================================== #
def _not(note: str, metrics: dict = None) -> dict:
    return {"passed": False, "note": note, "metrics": metrics or {}}


def _ok(note: str, metrics: dict = None) -> dict:
    return {"passed": True, "note": note, "metrics": metrics or {}}


def _result(passed: bool, note: str, metrics: dict = None) -> dict:
    return {"passed": bool(passed), "note": note, "metrics": metrics or {}}


def _and(checks, rule_id: str, metrics: dict) -> dict:
    """把若干 (cond,label) 合成一个规则结果，供结构判定。任何时候 check False 即规则 miss。"""
    msgs = []
    ok = True
    for cond, label in checks:
        if cond:
            msgs.append(f"[通过] {label}")
        else:
            msgs.append(f"[未过] {label}")
            ok = False
    return _result(ok, "; ".join(msgs), metrics)


def _isna(v):
    """兼容 float nan / None / pandas / numpy NaN 的空值判断。"""
    try:
        return bool(pd.isna(v))
    except Exception:  # noqa: BLE001
        return False
