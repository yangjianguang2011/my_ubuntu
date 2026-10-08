# -*- coding: utf-8 -*-
"""
选股条件注册表 —— 「技术面 × 估值面」灵活融合的骨架。

目标：选股策略可**自由组合**条件；**加/改条件只需在本模块 register()**，
不动编排器（`picker_runner`）与前端（表单由 `params` 规格动态生成）。

与 `analyzers/factors_registry.py` 同构（dict + dataclass）。

数据需求 `needs`（决定编排的**分层**，性能关键）：
  * `"kline"`     —— 日K + 均线（**快**，批量一次；300 只约 20s）
  * `"valuation"` —— 估值读数（**慢**，单股约 0.1s；首次需财报）
  * `"ps"`        —— 估值中的市销率 PS（**最慢**，需拉营业收入财报，**按需才拉**）

参数分两层：
  * **全局参数** `GLOBAL_PARAMS`（均线体系 ma_fast/ma_mid/ma_slow，各条件共享）
  * **条件参数** `Condition.params`（该条件专属阈值）

`Condition.evaluate(ctx, prepared)` 约定：
  * `ctx`       —— `{"code","name","frame"(带MA的DataFrame|None),"readings"(dict|None)}`
  * `prepared`  —— 由 `Condition.prepare(global_p, cond_p)` 预生成（**每条件一次**，非每股）
  返回统一结构 `{"passed": bool, "note": str, "metrics": dict}`
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .picker_rules import (
    Params,
    evaluate_golden_cross,
    evaluate_pullback,
    evaluate_structure,
    evaluate_volume,
)

GROUP_TECH = "技术面"
GROUP_VAL = "估值面"
GROUP_STRATEGY = "策略信号"

# ---------------------------------------------------------------- 全局参数
GLOBAL_PARAMS: Dict[str, dict] = {
    "ma_fast": {"label": "快线 MA", "type": "int", "default": 20, "min": 2, "max": 500},
    "ma_mid": {"label": "中线 MA", "type": "int", "default": 60, "min": 2, "max": 500},
    "ma_slow": {"label": "慢线 MA", "type": "int", "default": 200, "min": 2, "max": 500},
}

# `picker_rules.Params` 的默认值（用于补齐未显式给出的字段，保证语义与原实现一致）
_PARAMS_DEFAULTS = Params().to_dict()


# ---------------------------------------------------------------- 规格/校验
def coerce_param(name: str, spec: dict, value):
    """按规格把入参转成正确类型并校验范围（非法 → ValueError）。"""
    kind = spec.get("type", "float")
    try:
        if kind == "bool":
            v = value if isinstance(value, bool) else str(value).strip().lower() in (
                "1", "true", "yes", "on")
        elif kind == "int":
            v = int(float(value))
        elif kind == "select":
            v = str(value)
            opts = spec.get("options") or []
            if opts and v not in opts:
                raise ValueError(f"取值必须是 {opts} 之一")
        else:
            v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"参数 {name} 取值非法: {value!r}") from None

    if kind in ("int", "float") and ("min" in spec or "max" in spec):
        lo, hi = spec.get("min"), spec.get("max")
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            raise ValueError(f"参数 {name}={v} 超出允许范围 [{lo}, {hi}]")
    return v


def normalize_params(spec: Dict[str, dict], given: Optional[dict]) -> dict:
    """按规格归一化一组参数：未给的用默认值，给了的做类型/范围校验。"""
    out = {}
    given = given or {}
    for name, s in (spec or {}).items():
        if name in given and given[name] is not None and given[name] != "":
            out[name] = coerce_param(name, s, given[name])
        else:
            out[name] = s.get("default")
    return out


# ---------------------------------------------------------------- 结果助手
def _miss(note: str, metrics: dict = None) -> dict:
    return {"passed": False, "note": note, "metrics": metrics or {}}


def _ok(note: str, metrics: dict = None) -> dict:
    return {"passed": True, "note": note, "metrics": metrics or {}}


def _res(passed: bool, note: str, metrics: dict = None) -> dict:
    return {"passed": bool(passed), "note": note, "metrics": metrics or {}}


# ---------------------------------------------------------------- Condition
@dataclass
class Condition:
    id: str
    label: str
    group: str
    evaluate: Callable
    params: Dict[str, dict] = field(default_factory=dict)   # 条件专属参数规格
    needs: Tuple[str, ...] = ("kline",)                     # 数据需求（决定分层）
    default_on: bool = False
    note: str = ""                                          # 说明（前端常显，支持 **加粗**）
    details: Tuple[str, ...] = ()                           # 展开后的明细（前端 <details> 折叠）
    prepare: Optional[Callable] = None                      # (global_p, cond_p) -> 预生成对象

    @property
    def slow(self) -> bool:
        return "valuation" in self.needs or "ps" in self.needs


_REGISTRY: Dict[str, Condition] = {}
_ORDER: List[str] = []


def register(c: Condition) -> Condition:
    """幂等注册（同 id 覆盖）。"""
    if c.id not in _REGISTRY:
        _ORDER.append(c.id)
    _REGISTRY[c.id] = c
    return c


def get_condition(cid: str) -> Optional[Condition]:
    return _REGISTRY.get(cid)


def all_conditions() -> List[Condition]:
    return [_REGISTRY[i] for i in _ORDER]


def conditions_by_group() -> Dict[str, List[Condition]]:
    out: Dict[str, List[Condition]] = {}
    for c in all_conditions():
        out.setdefault(c.group, []).append(c)
    return out


def condition_catalog() -> dict:
    """供前端动态生成表单：全局参数 + 条件清单（含参数规格）。"""
    return {
        "global_params": GLOBAL_PARAMS,
        "groups": [
            {
                "group": g,
                "conditions": [
                    {
                        "id": c.id, "label": c.label, "group": c.group,
                        "params": c.params, "needs": list(c.needs),
                        "default_on": c.default_on, "slow": c.slow, "note": c.note,
                        "details": list(c.details),
                    }
                    for c in lst
                ],
            }
            for g, lst in conditions_by_group().items()
        ],
    }


# ---------------------------------------------------------------- 技术面条件
def _prep_rules(global_p: dict, cond_p: dict) -> Params:
    """把「全局参数 + 该条件参数」合成为 `picker_rules.Params`（保留原语义）。"""
    d = dict(_PARAMS_DEFAULTS)
    d.update(global_p or {})
    d.update(cond_p or {})
    return Params.from_dict(d)


def _ev_structure(ctx, p: Params) -> dict:
    """A 多头结构：价格站上慢线、中/快线高于慢线、快线向上。

    已并入原「均线多头排列」：`min_fast_slow_gap_pct > 0` 时，额外要求
    **快线高于慢线至少该百分比**（用于过滤"三线刚缠绕在一起"的伪排列）。
    """
    frame = ctx.get("frame")
    if frame is None or frame.empty:
        return _miss("无行情数据")
    res = evaluate_structure(frame, p)

    gap = float(getattr(p, "min_fast_slow_gap_pct", 0) or 0)
    if gap <= 0:
        return res
    row = frame.iloc[-1]
    c_fast, c_slow = f"ma{p.ma_fast}", f"ma{p.ma_slow}"
    if c_fast not in frame.columns or c_slow not in frame.columns:
        return res
    mf, ms = row[c_fast], row[c_slow]
    if pd.isna(mf) or pd.isna(ms) or float(ms) == 0:
        return res
    actual = (float(mf) / float(ms) - 1) * 100
    ok = actual >= gap
    metrics = dict(res.get("metrics") or {})
    metrics["fast_slow_gap_pct"] = round(actual, 3)
    note = (res.get("note") or "") + "; " + (
        f"[{'通过' if ok else '未过'}] 快线高于慢线 {round(actual, 2)}%（要求 ≥{gap}%）")
    return _res(bool(res.get("passed")) and ok, note, metrics)


def _ev_golden_cross(ctx, p: Params) -> dict:
    frame = ctx.get("frame")
    if frame is None or frame.empty:
        return _miss("无行情数据")
    return evaluate_golden_cross(frame, p)


def _ev_pullback(ctx, p: Params) -> dict:
    frame = ctx.get("frame")
    if frame is None or frame.empty:
        return _miss("无行情数据")
    return evaluate_pullback(frame, p)


def _ev_volume(ctx, p: Params) -> dict:
    frame = ctx.get("frame")
    if frame is None or frame.empty:
        return _miss("无行情数据")
    return evaluate_volume(frame, p)


def _ev_ma_slope(ctx, p: dict) -> dict:
    """快线斜率下限（首尾变化率，%）。"""
    from .ma_indicators import slope_pct
    frame = ctx.get("frame")
    if frame is None or frame.empty:
        return _miss("无行情数据")
    s = slope_pct(frame, f"ma{p['ma_fast']}", p["window"])
    if s is None:
        return _miss("斜率无法计算")
    ok = s >= p["min_pct"]
    return _res(ok, f"快线 {p['window']} 根斜率 {s}% "
                    f"{'>=' if ok else '<'} {p['min_pct']}%", {"ma_slope_pct": s})


def _ev_bias_band(ctx, p: dict) -> dict:
    """现价相对某均线的乖离率落在带内。"""
    from .ma_indicators import dist_to_ma
    frame = ctx.get("frame")
    if frame is None or frame.empty:
        return _miss("无行情数据")
    ma = {"fast": f"ma{p['ma_fast']}", "mid": f"ma{p['ma_mid']}",
          "slow": f"ma{p['ma_slow']}"}.get(p["which"])
    d = dist_to_ma(frame, ma)
    if d is None:
        return _miss("乖离无法计算")
    ok = p["min_pct"] <= d <= p["max_pct"]
    return _res(ok, f"距{ma} 乖离 {d}%（要求 {p['min_pct']}% ~ {p['max_pct']}%）",
                {"dist_pct": d})


register(Condition(
    id="structure", label="多头结构", group=GROUP_TECH, evaluate=_ev_structure,
    prepare=_prep_rules, default_on=False,
    note="价格站上慢线、中/快线依次高于慢线、快线向上；"
         "「快慢线最小间距」>0 时额外要求快线高于慢线该幅度（原「均线多头排列」已并入）",
    params={
        "min_price_above_slow_ratio": {"label": "价格高于慢线%", "type": "float",
                                       "default": 0.02, "min": -100, "max": 100},
        "fast_slope_min_pct": {"label": "快线斜率下限%", "type": "float",
                               "default": 0.0, "min": -100, "max": 100},
        "structure_slope_window": {"label": "斜率窗口(根)", "type": "int",
                                   "default": 10, "min": 2, "max": 250},
        "min_fast_slow_gap_pct": {"label": "快慢线最小间距%", "type": "float",
                                  "default": 0.0, "min": 0, "max": 100},
    },
))
register(Condition(
    id="golden_cross", label="金叉确认", group=GROUP_TECH, evaluate=_ev_golden_cross,
    prepare=_prep_rules, default_on=False,
    note="近 N 根内中线（ma_mid）上穿慢线（ma_slow）",
    params={
        "cross_lookback_bars": {"label": "金叉回溯(根)", "type": "int",
                                "default": 120, "min": 1, "max": 1000},
        "cross_min_bars_since": {"label": "距今最少(根)", "type": "int",
                                 "default": 1, "min": 0, "max": 1000},
        "cross_max_bars_since": {"label": "距今最多(根)", "type": "int",
                                 "default": 120, "min": 0, "max": 1000},
    },
))
register(Condition(
    id="pullback", label="回踩买点", group=GROUP_TECH, evaluate=_ev_pullback,
    prepare=_prep_rules, default_on=False,
    note="现价贴近快线且不深破中线；近 N 根内 LOW 曾回踩快线带",
    params={
        "pullback_min_dist_pct": {"label": "距快线下限%", "type": "float",
                                  "default": -0.5, "min": -100, "max": 100},
        "pullback_max_dist_pct": {"label": "距快线上限%", "type": "float",
                                  "default": 5.0, "min": -100, "max": 100},
        "pullback_confirm_window": {"label": "回踩窗口(根)", "type": "int",
                                    "default": 10, "min": 1, "max": 250},
        "pullback_low_touch_below_pct": {"label": "回踩带下探%", "type": "float",
                                         "default": 1.5, "min": 0, "max": 100},
        "pullback_low_touch_above_pct": {"label": "回踩带上浮%", "type": "float",
                                         "default": 3.0, "min": 0, "max": 100},
        "mid_break_tolerance_pct": {"label": "破中线容差%", "type": "float",
                                    "default": 1.0, "min": 0, "max": 100},
        "allow_close_break_mid": {"label": "允许跌破中线", "type": "bool",
                                  "default": False},
    },
))
register(Condition(
    id="volume_shrink", label="缩量（软条件）", group=GROUP_TECH, evaluate=_ev_volume,
    prepare=_prep_rules, default_on=False,
    note="近 N 日均量 / 放量参考 ≤ 阈值",
    params={
        "volume_shrink_lookback": {"label": "均量窗口(根)", "type": "int",
                                   "default": 5, "min": 1, "max": 250},
        "volume_shrink_max_ratio": {"label": "量能比上限", "type": "float",
                                    "default": 0.8, "min": 0, "max": 10},
    },
))
register(Condition(
    id="ma_slope", label="快线斜率下限", group=GROUP_TECH,
    evaluate=_ev_ma_slope, default_on=False,
    note="快线近 N 根的首尾变化率 ≥ 阈值（正值=向上）",
    params={
        "window": {"label": "窗口(根)", "type": "int", "default": 10, "min": 2, "max": 250},
        "min_pct": {"label": "斜率下限%", "type": "float",
                    "default": 0.0, "min": -100, "max": 100},
    },
))
register(Condition(
    id="bias_band", label="乖离带", group=GROUP_TECH, evaluate=_ev_bias_band,
    default_on=False,
    note="现价相对指定均线的乖离率落在带内",
    params={
        "which": {"label": "参照均线", "type": "select", "default": "fast",
                  "options": ["fast", "mid", "slow"]},
        "min_pct": {"label": "下限%", "type": "float", "default": -0.5, "min": -100, "max": 100},
        "max_pct": {"label": "上限%", "type": "float", "default": 5.0, "min": -100, "max": 100},
    },
))


# ---------------------------------------------------------------- 估值面条件
def _read(ctx, field: str):
    """取读数 (label, value, pct)；缺失返回 (label, None, None)。"""
    r = (ctx.get("readings") or {}).get(field) or {}
    return (r.get("label") or field), r.get("value"), r.get("pct")


def _ev_val_max(ctx, p: dict) -> dict:
    """估值读数（绝对值或历史位置）≤ 阈值。"""
    if not ctx.get("readings"):
        return _miss("无估值读数")
    label, v, pct = _read(ctx, p["field"])
    use_pct = p["basis"] == "pct"
    x = pct if use_pct else v
    if x is None:
        return _miss(f"{label} 不可得")
    thr = p["threshold"]
    if use_pct:
        # 分位口径：读数是 0~1，阈值也按百分比展示（0.30 → 30%）
        disp, thr_disp = f"{x*100:.1f}%", f"{thr*100:.1f}%"
    else:
        disp, thr_disp = f"{x:.4f}", f"{thr:g}"
    ok = x <= thr
    return _res(ok, f"{label}{'历史位置' if use_pct else ''} {disp} "
                    f"{'<=' if ok else '>'} {thr_disp}",
                {f"{p['field']}_{p['basis']}": x})


_VAL_FIELD_OPTS = [
    ["pr", "市赚率 PR（日频隐含ROE）"],
    ["pr_adj", "修正市赚率 N×PR（分红质量修正）"],
    ["pb_adj_b", "盈利调节市净率（季报口径·主）"],
    ["pb_adj", "盈利调节市净率（v1 日频）"],
    ["pb", "市净率 PB"],
    ["pe_ttm", "市盈率 PE_TTM"],
    ["price_cycle", "价格周期位置"],
]

# 每个读数注册**一条独立条件**（而非一条带下拉）——这样可同时 AND 多个估值条件，
# 例如「盈利调节市净率(季报) 分位≤0.30」AND「市赚率PR < 0.8」。
# 默认口径用 **value（绝对值）**，需要分位时在卡片里切到 pct。
for _f, _lbl in _VAL_FIELD_OPTS:
    register(Condition(
        id=f"val_{_f}", label=f"{_lbl} ≤ 阈值", group=GROUP_VAL,
        evaluate=_ev_val_max, needs=("valuation",), default_on=False,
        note="口径可选「绝对值」或「历史位置(0~1)」；越低越便宜（价格周期位置亦然）",
        params={
            "field": {"label": "读数", "type": "select", "default": _f, "options": [_f]},
            "basis": {"label": "口径", "type": "select", "default": "value",
                      "options": ["value", "pct"]},
            "threshold": {"label": "阈值", "type": "float", "default": 0.10,
                          "min": -1000000, "max": 1000000},
        },
    ))


# ---------------------------------------------------------------- 策略信号条件
# 反转体系（月线反转 / 三线红）—— **横截面 RPS** 是全系统唯一的跨股票维度，
# 与「相对自身历史」的时序读数正交，故单独成组（见 `docs/…-安装与配置指南.md` §7）。
def _ev_monthly_reversal(ctx, p: dict) -> dict:
    """月线反转 6.5：近 N 个交易日内出现过信号（事件型，非当日态）。

    RPS 由编排器**一次性横截面预计算**后放进 `ctx["rps"]`（{code: DataFrame}），
    因此本条件**不需要** `needs=("valuation",)` —— 它只依赖日K + RPS。
    """
    from .strategy_tbs import compute_tbs

    frame = ctx.get("frame")
    if frame is None or frame.empty:
        return _miss("无行情数据")

    rps = (ctx.get("rps") or {}).get(ctx.get("code"))
    if rps is None:
        return _miss("RPS 不可得（上市不足一年 / 已被剔除 / RPS 未计算）")

    try:
        m = compute_tbs(frame, rps=rps)
    except Exception as e:  # noqa: BLE001
        return _miss(f"信号计算异常：{type(e).__name__}")

    if m.empty:
        return _miss("信号计算失败")

    win = int(p.get("lookback_days") or 15)
    sig = m["monthly_reversal"].fillna(False).astype(bool)
    recent = sig.tail(win)
    hit = bool(recent.any())
    days_ago = None
    if hit:
        days_ago = int(len(sig) - 1 - np.flatnonzero(sig.values)[-1])
    return _res(
        hit,
        (f"近 {win} 日内{'出现' if hit else '未出现'}月线反转信号"
         + (f"（{days_ago} 日前）" if hit else "")),
        {"monthly_reversal_days_ago": days_ago,
         "rps50": None if pd.isna(m["rps50"].iloc[-1]) else float(m["rps50"].iloc[-1]),
         "rps120": None if pd.isna(m["rps120"].iloc[-1]) else float(m["rps120"].iloc[-1]),
         "rps250": None if pd.isna(m["rps250"].iloc[-1]) else float(m["rps250"].iloc[-1])},
    )


def _ev_triple_red(ctx, p: dict) -> dict:
    """三线红：RPS50 / RPS120 / RPS250 **同时** ≥ 阈值（默认 90）。"""
    frame = ctx.get("frame")
    if frame is None or frame.empty:
        return _miss("无行情数据")
    m = (ctx.get("rps") or {}).get(ctx.get("code"))
    if m is None or m.empty:
        return _miss("RPS 不可得")

    thr = float(p.get("rps_min") or 0.90)
    last = m.iloc[-1]
    vals = [last.get(c) for c in ("rps50", "rps120", "rps250")]
    if any(v is None or pd.isna(v) for v in vals):
        return _miss("RPS 不完整（三线需 50/120/250 全部可得）")
    ok = all(float(v) >= thr for v in vals)
    return _res(ok, f"RPS50/120/250 = "
                    f"{', '.join(f'{float(v) * 100:.1f}' for v in vals)}"
                    f"（要求全部 ≥{thr * 100:.0f}）",
                {"rps50": float(vals[0]), "rps120": float(vals[1]),
                 "rps250": float(vals[2])})


register(Condition(
    id="monthly_reversal", label="月线反转 6.5", group=GROUP_STRATEGY,
    evaluate=_ev_monthly_reversal, default_on=False,
    note="「月线反转」：挑底部转强、涨得还不多的股票。7 组条件须同日全中才算一次信号。"
         "事件型：看「近 N 日内是否出现过」（不要求今天正好是信号日）。",
    details=(
        "FYX1 相对强度：RPS50 > 87 或 RPS120 > 90（池内排名 ×100）",
        "FYX2 结构紧凑：低点抬高 —— 50日低>200日低 / 30日低>120日低 / 20日低>50日低",
        "FYX3 创N日新高：10日内曾创80日新高；或 当天创50日新高且 RPS≥90",
        "FYX4 站上均线：收盘 > MA20 且 > MA200，且 MA120/MA200 > 0.9",
        "FYX5 站上天数：45日内站上MA200 2~44天；或曾跌破200/250线后重新站上",
        "FYX6 涨幅上限：30日最高/120日最低 < 1.50~1.65（涨太多就排除）",
        "FYX7 距高点：(5日最高/120日最高 > 0.85 或 >0.8) 且 收盘/10日最高 > 0.9",
    ),
    params={
        "lookback_days": {"label": "近 N 日内出现过", "type": "int",
                          "default": 15, "min": 1, "max": 250},
    },
))
register(Condition(
    id="triple_red", label="三线红", group=GROUP_STRATEGY,
    evaluate=_ev_triple_red, default_on=False,
    note="RPS50 / RPS120 / RPS250 同时翻红 —— 短中长期均处于市场强势前列。"
         "（与「月线反转」近似互斥：后者命中的股票当前 RPS 通常只有 80 上下，建议二选一）",
    params={
        "rps_min": {"label": "RPS 下限(0~1)", "type": "float",
                    "default": 0.90, "min": 0.0, "max": 1.0},
    },
))
