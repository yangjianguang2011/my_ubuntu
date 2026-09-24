"""
估值因子计算 — 市赚率/盈利调节市净率/盈利调节市销率（单股，日频）。

产出指标（metrics 序列）：
  pb/pe_ttm/turnover    本地估值字段
  roe_impl              隐含ROE = pb/pe_ttm
  pr/pr_b/pr_avg        市赚率 = PE(倍)/ROE(%) 三口径
  pr_adj                修正市赚率 = N×PR
  pb_adj/pb_adj_b       盈利调节残差（v1 日频 / B 季报 两口径）的 expanding 历史位置
  ps/ps_adj/ps_adj_pct  市销率 / 盈利调节市销率残差（ps ~ 隐含净利率）/ 历史位置
  market_drift          市场估值中枢长期漂移（可选扣减）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from ..core.utils import clean_value, fmt_num, fmt_pct
from config import get_path
from .factor_utils import expanding_pct, rolling_pct
from .factors_registry import Factor, register

MAP_WINDOW = 1500
PCT_MIN_PERIODS = 250
STEP_LAG_DAYS = 30
LEVEL_WINDOW = 750
ROE_AVG_YEARS = 5

# 历史位置（expanding_pct）的起算日：对齐文章口径（默认 2012-01-01，可 env/ini 覆盖）
PCT_START_DATE = get_path("valuation", "data_start", "20120101")
PCT_START_DATE = (f"{PCT_START_DATE[:4]}-{PCT_START_DATE[4:6]}-{PCT_START_DATE[6:8]}"
                  if PCT_START_DATE and len(PCT_START_DATE) >= 8 else None)
# 滚动窗口（交易日）：>0 时用滚动窗口历史位置（去固定起点前视）；0=用 expanding
PCT_WINDOW = int(get_path("valuation", "pct_window", "0") or "0")

PAYOUT_HI = 0.50
PAYOUT_LO = 0.25

LevelLike = Optional[Union[pd.Series, Dict]]


@dataclass
class ValuationParams:
    map_window: int = MAP_WINDOW
    pct_min_periods: int = PCT_MIN_PERIODS
    step_lag_days: int = STEP_LAG_DAYS
    market_level: LevelLike = None
    market_level_window: int = LEVEL_WINDOW
    use_market_level: bool = True
    # 历史位置（expanding_pct）的起算日：此日之前不计入历史分布（对齐文章口径，默认 2012）
    pct_start_date: Optional[str] = PCT_START_DATE
    # 滚动窗口（交易日）：>0 时用滚动窗口（去固定起点前视）；0=用 expanding
    pct_window: int = PCT_WINDOW


def payout_to_n(payout, hi=PAYOUT_HI, lo=PAYOUT_LO, n_hi=1.0, n_lo=2.0) -> float:
    """股利支付率 → 修正系数 N。≥hi→1.0；≤lo→2.0；中间线性。"""
    try:
        x = float(payout)
    except (TypeError, ValueError):
        return n_hi
    if x != x:
        return n_hi
    if x >= hi:
        return n_hi
    if x <= lo:
        return n_lo
    return n_hi + (n_lo - n_hi) * (hi - x) / (hi - lo)


def avg_roe_from_reports(reports, years=ROE_AVG_YEARS) -> Optional[float]:
    """多年平均 ROE（小数）：近 years 个年报报告期 ROE 均值。"""
    if not reports:
        return None
    reps = sorted([r for r in reports if r.get("report_date")],
                  key=lambda r: str(r["report_date"]))
    annual = [float(r["roe"]) for r in reps
              if str(r.get("report_date", ""))[5:7] == "12" and isinstance(r.get("roe"), (int, float))]
    if annual:
        picked = annual[-years:]
    else:
        picked = [float(r["roe_ann"]) for r in reps
                  if isinstance(r.get("roe_ann"), (int, float))][-2 * years:]
    return sum(picked) / len(picked) / 100.0 if picked else None


def step_roe_from_reports(dates, reports, lag_days=STEP_LAG_DAYS,
                          field="roe_ann") -> pd.Series:
    """B 轨（主口径）：报告期 ROE 摊成日频台阶，供 `pb_adj_b` 的回归输入。

    做法：每期"年化 ROE"从 报告期+lag_days(默认30) 开始生效，期内沿用上一期
    （step = 上一个包含当天 t 的生效起点）。
    为什么 +30 天：季报要到公告后才能用，报告期本身在财报里是"未来时间戳"，
    直接用报告期会产生未来函数/回测作弊；**+30 天是对"公告日"的粗略近似**
    ——真正做法应取 em 接口的 NOTICE_DATE（公告日），此为已记录的待办（docs 规格文档）。
    读法：index 对齐日频 date，缺 ROE 的早期为 NaN（回归窗口自然跳过）。
    """
    if not reports:
        return pd.Series(np.nan, index=dates.index)
    reps = sorted([r for r in reports if r.get("report_date")],
                  key=lambda r: str(r["report_date"]))
    if not reps:
        return pd.Series(np.nan, index=dates.index)
    # 生效日 = 报告日 + team lag_days（2740 示例：2012-03-31 报 → 2012-04-30 起用该季数据）
    starts = np.array([np.datetime64(pd.Timestamp(r["report_date"]) + pd.Timedelta(days=lag_days))
                       for r in reps])
    # 年化 ROE 换小数：年报×1 / Q3×4/3 / H1×2 / Q1×4（见 _ANN_FACTOR），÷100 转小数
    vals = np.array([float(r.get(field)) if r.get(field) is not None else np.nan
                     for r in reps], dtype=float) / 100.0
    # 每个日频日期往回找"最后一个已生效的报告期"
    pos = np.searchsorted(starts, pd.to_datetime(dates).values, side="right") - 1
    out = np.where(pos >= 0, vals[np.clip(pos, 0, len(vals) - 1)], np.nan)
    return pd.Series(out, index=dates.index)


def _ttm_revenue(reports) -> Dict[str, float]:
    """报告期累计营收 → 各报告期的 TTM 营收（dict: report_date -> ttm）。"""
    reps = sorted(reports, key=lambda r: str(r["report_date"]))
    by_date = {str(r["report_date"]): float(r["revenue"]) for r in reps}
    ttm: Dict[str, float] = {}
    for r in reps:
        d = str(r["report_date"])
        y, md = int(d[:4]), d[5:]  # md = "MM-DD"
        rev = float(r["revenue"])
        if md == "12-31":
            ttm[d] = rev  # 年报 = 全年
        else:
            prev_annual = by_date.get(f"{y - 1}-12-31")
            prev_same = by_date.get(f"{y - 1}-{md}")
            if prev_annual is not None and prev_same is not None:
                ttm[d] = rev + prev_annual - prev_same
            else:
                ttm[d] = rev  # 缺上年数据时退化为当年累计
    return ttm


def revenue_ttm_from_reports(dates, reports, lag_days=STEP_LAG_DAYS) -> pd.Series:
    """报告期累计营收 → TTM 营收，摊成日频台阶。"""
    if not reports:
        return pd.Series(np.nan, index=dates.index)
    ttm = _ttm_revenue(reports)
    reps = sorted([(str(r["report_date"]), ttm[str(r["report_date"])]) for r in reports],
                  key=lambda x: x[0])
    starts = np.array([np.datetime64(pd.Timestamp(d) + pd.Timedelta(days=lag_days))
                       for d, _ in reps])
    vals = np.array([v for _, v in reps], dtype=float)
    pos = np.searchsorted(starts, pd.to_datetime(dates).values, side="right") - 1
    out = np.where(pos >= 0, vals[np.clip(pos, 0, len(vals) - 1)], np.nan)
    return pd.Series(out, index=dates.index)


def map_residual(y, x, window, min_periods) -> pd.Series:
    """滚动 OLS 残差 —— 盈利调节的核心：`残差 = y − (a + b·x)`。

    本项目 y=PB（市净率），x=ROE（盈利能力）：
        pb_adj = PB − (a + b·ROE)
    直观含义：先用"过去的赚钱水平"解释"一般的市净率该给多少"，解释不掉的部分
    才是市场情绪额外给的多/砍的少 —— 残差 >0 市场给多（贵），<0 给少（便宜）。
    与"市赚率 PE/ROE"同源不同做法：PE = PB/ROE（恒等式），故 PR = PB/ROE²；
    我们读的是回归残差（0829 文称二者是"同一件事的两种做法"）。

    窗口 window=1500 交易日 ≈ 6 年，对应文章"用历年盈利能力解释估值"；min_periods
    =250 保证少样本期不外推。
    已知近似：ROE 生效日用"报告期+30 天"模拟公告日（NOTICE_DATE 待接入，见 docs 规格文档）。
    """
    # 以下三行即滚动一元线性回归的两个参数：b(斜率)、a(截距)；仅用到当期 t 及以前，
    # 无未来信息（rolling 向后看）。min_periods=250 为每个窗口最少样本数。
    mx = x.rolling(window, min_periods=min_periods).mean()
    my = y.rolling(window, min_periods=min_periods).mean()
    b = (y.rolling(window, min_periods=min_periods).cov(x)
         / x.rolling(window, min_periods=min_periods).var().replace(0, np.nan))
    # 线性预测 = 均值 + 斜率 × 距离，残差 = 实际值 − 预测值
    return y - (my + b * (x - mx))


def market_drift(level, dates, window=LEVEL_WINDOW) -> Optional[pd.Series]:
    """市场水位对齐日频，返回偏离长期趋势的量。"""
    if level is None:
        return None
    if isinstance(level, pd.Series):
        s = pd.Series(level.values, index=pd.to_datetime(level.index), dtype=float)
    elif isinstance(level, dict):
        s = pd.Series({pd.Timestamp(k): float(v) for k, v in level.items()})
    else:
        return None
    if s.empty:
        return None
    s = s.sort_index()
    d = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    daily = s.reindex(s.index.union(d)).ffill().reindex(d).reset_index(drop=True)
    trend = daily.rolling(window, min_periods=max(60, window // 3)).mean()
    return daily - trend


def compute_valuation_metrics(df, params=None, roe_reports=None,
                              revenue_reports=None,
                              market_level=None, payout_ratio=None) -> pd.DataFrame:
    """输入升序日K(至少 date/close/pb/pe_ttm)，输出带全部估值指标的 DataFrame。

    产出与读法（供理解，详见 docs/盈利调节市净率-口径对齐-规格.md）：
    - roe_impl   隐含ROE = PB/PE_TTM。恒等式：ROE = EPS/BV = (P/PE)/(P/PB) = PB/PE，
                 即 隐含ROE 等于"价格除以市盈率"，天然日频、盈利慢 → 与 PE 高度同源。
    - pr         市赚率 = PE/ROE(%)（文章口径 ROE 取百分数值），越低越划算，是"比值"因子。
    - pb_adj_b   **主因子**：PB 对 季报年化ROE 的滚动回归残差（窗口≈6年），
                 残差>0 市场给多（贵）、<0 给少（便宜）。
    - pb_adj_b_pct / pb_adj_pct / pr*_pct 等为各自序列的 expanding 历史位置(0~1)，
                 **越低越便宜**；起算日由 pct_start_date 控制（=文章口径 2012 起）。
    """
    p = params or ValuationParams()
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    for c in ("pb", "pe_ttm"):
        if c not in out.columns:
            raise ValueError(f"日K缺少字段 {c}")

    # 隐含ROE = PB/PE_TTM：等价于 EPS/BV（净资产收益率），全历史可得、零外网依赖
    out["roe_impl"] = (out["pb"] / out["pe_ttm"]).where((out["pb"] > 0) & (out["pe_ttm"] > 0))
    # 市赚率 PR = PE / ROE(%)（ROE 取百分数值时 PE/ROE 即 0830 文口径，如 PE20/ROE15%=1.33）
    out["pr"] = out["pe_ttm"] / (out["roe_impl"] * 100.0)

    # ---- 盈利调节——v1 日频口径（旧口径，保留对照）：PB 对 日频隐含ROE 的滚动回归残差
    out["pb_adj"] = map_residual(out["pb"], out["roe_impl"], p.map_window, p.pct_min_periods)

    # ---- 盈利调节主口径（B 轨/季报ROE 台阶）----
    roe_step_b = step_roe_from_reports(out["date"], roe_reports, p.step_lag_days)
    out["roe_step_b"] = roe_step_b
    # 无季报时 B 轨缺席，主读数自动退化为 pb_adj（v1）
    if roe_reports:
        out["pb_adj_b"] = map_residual(out["pb"], roe_step_b, p.map_window, p.pct_min_periods)

    # 盈利调节市销率：PS = 总市值 / TTM营业收入；对称于盈利调节市净率
    if "total_mv" in out.columns and revenue_reports:
        revenue_ttm = revenue_ttm_from_reports(out["date"], revenue_reports, p.step_lag_days)
        out["revenue_ttm"] = revenue_ttm
        out["ps"] = (out["total_mv"] / revenue_ttm).where(revenue_ttm > 0)
        out["net_margin_impl"] = (out["ps"] / out["pe_ttm"]).where(out["pe_ttm"] > 0)
        out["ps_adj"] = map_residual(out["ps"], out["net_margin_impl"],
                                     p.map_window, p.pct_min_periods)

    out["pr_b"] = out["pe_ttm"].where(out["pe_ttm"] > 0) / (roe_step_b.where(roe_step_b > 0) * 100.0)
    roe_avg = avg_roe_from_reports(roe_reports)
    if roe_avg is not None and roe_avg > 0:
        out["roe_avg"] = roe_avg
        out["pr_avg"] = out["pe_ttm"].where(out["pe_ttm"] > 0) / (roe_avg * 100.0)
    out["n"] = payout_to_n(payout_ratio)
    out["pr_adj"] = out["n"] * out["pr"]

    lvl = market_level if market_level is not None else p.market_level
    if lvl is not None and p.use_market_level:
        drift = market_drift(lvl, out["date"], p.market_level_window)
        if drift is not None and drift.notna().any():
            out["market_drift"] = drift.values
            for col in ("pb_adj", "pb_adj_b"):
                if col in out.columns:
                    out[col] = out[col] - drift.values

    # 历史位置起算日（对齐文章口径）：此日之前的样本不计入 expanding 历史分布
    sp = 0
    if p.pct_start_date and "date" in out.columns:
        sp = int((pd.to_datetime(out["date"]) < pd.Timestamp(p.pct_start_date)).sum())

    def _pct(src: pd.Series) -> pd.Series:
        if p.pct_window and p.pct_window > 0:
            return rolling_pct(src, p.pct_window, p.pct_min_periods)
        return expanding_pct(src, p.pct_min_periods, start_pos=sp)

    for col in ("pb", "pe_ttm", "pr", "pr_adj", "pr_b", "pb_adj"):
        src = out[col] if col != "pe_ttm" else out["pe_ttm"].where(out["pe_ttm"] > 0)
        out[f"{col}_pct"] = _pct(src)
    if "pr_avg" in out.columns:
        out["pr_avg_pct"] = _pct(out["pr_avg"])
    if "pb_adj_b" in out.columns:
        out["pb_adj_b_pct"] = _pct(out["pb_adj_b"])
    if "ps_adj" in out.columns:
        out["ps_adj_pct"] = _pct(out["ps_adj"])
    return out.reset_index(drop=True)


def latest_readings(metrics, payout=None) -> Dict:
    """最新读数面板。"""
    if metrics is None or metrics.empty:
        return {}
    last = metrics.iloc[-1]
    reads: Dict = {}

    def _put(key, label, pct_key=None):
        reads[key] = {"label": label, "value": clean_value(last.get(key)),
                      "pct": clean_value(last.get(pct_key)) if pct_key and pct_key in last.index else None}
        return reads[key]

    _put("date", "日期")
    _put("close", "收盘")
    _put("pb", "市净率PB", "pb_pct")
    _put("pe_ttm", "市盈率PE_TTM", "pe_ttm_pct")
    _put("roe_impl", "隐含ROE(pb/pe_ttm)")
    _put("pr", "市赚率PR", "pr_pct")
    reads["pr"]["n"] = clean_value(last.get("n"))
    for key, label in (("pr_b", "市赚率PR(季报ROE口径)"), ("pr_avg", "市赚率PR(多年平均ROE口径)")):
        if key in metrics.columns:
            _put(key, label, f"{key}_pct")
    _put("pr_adj", "修正市赚率(N×PR)", "pr_adj_pct")
    reads["pr_adj"]["payout"] = payout
    for key, label, roe_key in (("pb_adj_b", "盈利调节市净率(季报口径B)", "roe_step_b"),
                                ("pb_adj", "盈利调节市净率(v1 日频ROE)", None)):
        if key in metrics.columns:
            _put(key, label, f"{key}_pct")
            if roe_key:
                reads[key]["roe"] = clean_value(last.get(roe_key))
    if "market_drift" in metrics.columns:
        reads["market_drift"] = {"label": "市场水位漂移(已扣减)",
                                 "value": clean_value(last.get("market_drift")), "pct": None}
    if "turnover" in metrics.columns:
        _put("turnover", "换手率%")
    return reads


def panel_rows(ctx: dict) -> List[Tuple[str, str, str]]:
    """估值面板行：(项目, 读数, 附注/历史位置)。"""
    g = ctx.get("readings", {}).get
    rows = []
    rows.append(("收盘价 / 日期", fmt_num(g("close", {}).get("value")),
                 str(g("date", {}).get("value"))))
    pb = g("pb", {})
    rows.append(("市净率 PB", fmt_num(pb.get("value")),
                 f"历史位置 {fmt_pct(pb.get('pct'))}"))
    pe = g("pe_ttm", {})
    rows.append(("市盈率 PE_TTM", fmt_num(pe.get("value")),
                 f"历史位置 {fmt_pct(pe.get('pct'))}"))
    roe = g("roe_impl", {})
    rows.append(("隐含ROE = PB/PE_TTM", fmt_pct(roe.get("value")), "年化，日频推导"))
    pr = g("pr", {})
    rows.append(("市赚率 PR = PE/ROE(%)", fmt_num(pr.get("value")),
                 f"越低越划算 · 历史位置 {fmt_pct(pr.get('pct'))}"))
    for key, label in (("pr_b", "市赚率 PR · 季报ROE口径"),
                       ("pr_avg", "市赚率 PR · 多年平均ROE口径")):
        d = g(key)
        if not d:
            continue
        rows.append((label, fmt_num(d.get("value")),
                     f"越低越划算 · 历史位置 {fmt_pct(d.get('pct'))}"))
    adj = g("pr_adj", {})
    n = pr.get("n")
    pay = adj.get("payout") or {}
    if pay.get("payout") is not None:
        note_n = f"N={fmt_num(n)} · 支付率 {fmt_pct(pay.get('payout'))}（{pay.get('year')} 年报）"
    elif n is not None:
        note_n = f"N={fmt_num(n)} · 分红数据缺失"
    else:
        note_n = "分红数据缺失"
    rows.append(("修正市赚率 = N×PR", fmt_num(adj.get("value")),
                 f"{note_n} · 历史位置 {fmt_pct(adj.get('pct'))}"))
    for key, label in (("pb_adj_b", "盈利调节市净率读数 · B 季报ROE(主)"),
                       ("pb_adj", "盈利调节市净率读数 · v1 日频ROE")):
        d = g(key)
        if not d:
            continue
        pos, res = d.get("pct"), d.get("residual")
        roe_v = d.get("roe")
        note = f"{fmt_pct(pos)} 位置 · 残差 {fmt_num(res, 4)} PB"
        if roe_v is not None:
            note += f" · 盈利ROE {fmt_pct(roe_v)}"
        rows.append((label, fmt_num(pos), note))
    md = g("market_drift")
    if md:
        rows.append((md.get("label") or "市场水位漂移", fmt_num(md.get("value"), 4),
                     "已从各口径残差中扣减（可选开关，默认关闭）"))
    to = g("turnover", {})
    tv = to.get("value")
    rows.append(("换手率", fmt_num(tv) + "%" if isinstance(tv, (int, float)) else "-", "日换手"))
    return rows


register(Factor(
    name="valuation",
    title="估值（市赚率/盈利调节市净率）",
    compute=compute_valuation_metrics,
    latest=latest_readings,
    panel_rows=panel_rows,
    is_base=True,
))
