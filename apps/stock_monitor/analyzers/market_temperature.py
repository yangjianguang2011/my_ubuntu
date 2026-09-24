"""
市场温度 / 水位 — 合并自 market_signal + market_level + market_report。

温度 = 50%×PE位 + 50%×PB位（市值加权整体法，近10年分位）。
市场水位 = 月频成分中位 PB（可选扣减残差中的长期漂移）。

缓存：温度/水位序列都是**计算产物**（冷算 1~3 分钟），存入 `cache.db` 的
`long_term_storage`（`module_type="market_temp"`/`"market_level"`，稳定 key → 原地覆盖），
新鲜期分别 `MARKET_TTL`/`LEVEL_TTL`；重建失败时回退旧记录并标注降级。
**不落任何磁盘文件。**
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from config import setup_logger
from ..core.utils import is_fresh_meta

from ..core.cache_with_database import retrieve_long_term_data, store_long_term_data

logger = setup_logger(__name__)

MARKET_TTL = 24 * 3600
LEVEL_TTL = 7 * 24 * 3600
PCT_YEARS = 10
PCT_STEP = 21
PCT_MIN_PERIODS = 300
MA_WINDOW = 250
_FIELDS = "date,code,pb,pe_ttm,total_mv,turnover,close"

_MAIN_ITEMS = [("w_pe", "指数PE(整体法/市值加权)", +1),
               ("w_pb", "指数PB(市值加权)", +1)]
_AUX_ITEMS = [("bk_rate", "破净率", -1),
              ("med_turnover", "中位换手率", +1),
              ("above_ma250", "站上MA250占比", +1),
              ("new_high", "250日新高占比", +1)]

# 市场温度展示的三大指数（现显示在「股票监控」页底部）：key -> (stockdb 指数符号, 显示名)
MARKET_INDICES = {
    "sh": ("000001.SH", "上证综指"),
    "sz": ("399001.SZ", "深证成指"),
    "cyb": ("399006.SZ", "创业板指"),
}


_MKT_MODULE = "market_temp"
_LVL_MODULE = "market_level"


def _mkt_key(symbol: str) -> str:
    """温度序列在 `long_term_storage` 的 key。"""
    return f"market_temp_{symbol.replace('.', '_')}"


def _lvl_key(pool: str) -> str:
    return f"market_level_{pool}"


def _ctx_to_records(df: pd.DataFrame) -> list:
    """DataFrame -> JSON 友好 records（date 转 'YYYY-MM-DD'，NaN -> null）。"""
    out = df.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return json.loads(out.to_json(orient="records"))


def _records_to_ctx(rows) -> Optional[pd.DataFrame]:
    """records -> 按 date 升序的 DataFrame；空/坏 -> None。"""
    if not rows:
        return None
    try:
        df = pd.DataFrame(rows)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
        return df.reset_index(drop=True) if len(df) else None
    except Exception as e:  # noqa: BLE001
        logger.warning(f"温度缓存解析失败: {e}")
        return None


def _rolling_pct_stepped(s: pd.Series, years=PCT_YEARS, step=PCT_STEP,
                min_periods=PCT_MIN_PERIODS) -> pd.Series:
    """近 years 年滚动分位（0~1）——**按 step 天步进计算**以提速（与 factor_utils.rolling_pct 的定长窗口实现不同，故不重名）。"""
    n = len(s)
    win = int(252 * years)
    vals = s.values.astype(float)
    out = np.full(n, np.nan)
    for i in range(0, n, step):
        seg = vals[max(0, i - win + 1):i + 1]
        seg = seg[~np.isnan(seg)]
        if len(seg) < min_periods:
            continue
        order = np.sort(seg)
        for j in range(i, min(i + step, n)):
            v = vals[j]
            if v == v:
                out[j] = np.searchsorted(order, v, side="right") / len(order)
    return pd.Series(out, index=s.index)


def build_market_context(symbol="000300.SH", start="20100101", end=None) -> pd.DataFrame:
    """构造指数温度/市场水位的日频序列。symbol 为 stockdb 指数符号。"""
    from ..data_fetchers.pool_data_fetcher import get_index_constituents
    from ..data_fetchers.stockdb_data_fetcher import get_raw

    rows = get_index_constituents(symbol)
    codes = [r["code"] for r in rows]
    if not codes:
        raise RuntimeError(f"市场温度({symbol})：成分拉取为空")
    raw = get_raw(list(codes), start=start, end=end, fq="qfq", fields=_FIELDS)
    if raw is None or len(raw) == 0:
        raise RuntimeError(f"市场温度({symbol})：成分日K返回空")
    df = raw.dropna(subset=["total_mv"]).copy()
    df["dt"] = pd.to_datetime(df["date"].astype("int64").astype(str), format="%Y%m%d")
    df = df.sort_values(["code", "dt"])
    g = df.groupby("dt")

    out = pd.DataFrame(index=g.size().index)
    out["n"] = g.size()
    d_pe = df[df["pe_ttm"] != 0]
    out["w_pe"] = (d_pe.groupby("dt")["total_mv"].sum()
                   / d_pe.assign(_e=d_pe["total_mv"] / d_pe["pe_ttm"]).groupby("dt")["_e"].sum())
    d_pb = df[df["pb"] > 0]
    out["w_pb"] = (d_pb.groupby("dt")["total_mv"].sum()
                   / d_pb.assign(_b=d_pb["total_mv"] / d_pb["pb"]).groupby("dt")["_b"].sum())

    out["med_pb"] = g["pb"].median()
    out["med_pe"] = df[df["pe_ttm"] > 0].groupby("dt")["pe_ttm"].median()
    out["bk_rate"] = df.assign(_bk=(df["pb"] < 1).astype(float)).groupby("dt")["_bk"].mean()
    out["med_turnover"] = g["turnover"].median()
    df["ma"] = df.groupby("code")["close"].transform(
        lambda x: x.rolling(MA_WINDOW, min_periods=int(MA_WINDOW * 0.8)).mean())
    df["hi"] = df.groupby("code")["close"].transform(
        lambda x: x.rolling(MA_WINDOW, min_periods=int(MA_WINDOW * 0.8)).max())
    agg = (df.assign(_above=(df["close"] > df["ma"]).astype(float),
                     _newhigh=(df["close"] >= df["hi"] * 0.999).astype(float))
           .groupby("dt")[["_above", "_newhigh"]].mean())
    out["above_ma250"] = agg["_above"]
    out["new_high"] = agg["_newhigh"]

    pos_cols = []
    for col, _label, direction in _MAIN_ITEMS + _AUX_ITEMS:
        p = _rolling_pct_stepped(out[col])
        if direction < 0:
            p = 1.0 - p
        out[f"pos_{col}"] = p
        pos_cols.append(f"pos_{col}")

    out["temperature"] = out[["pos_w_pe", "pos_w_pb"]].mean(axis=1, skipna=True)
    out["market_position"] = out[pos_cols].mean(axis=1, skipna=True)
    return out.reset_index().rename(columns={"dt": "date"})


# 指数温度降级原因（symbol_key -> 说明），供上层在结果里标注
_ctx_degraded: dict = {}


def get_market_context(symbol="000300.SH", force=False) -> Optional[pd.DataFrame]:
    """指数温度序列（带 1 天缓存；**重建失败时回退到过期记录**）。

    symbol 为指数符号（如 `000001.SH`）。成份股是低频数据，缓存几天不影响判断，
    故在线接口不可用时用旧记录继续算，而不是整块报错。
    """
    key = _mkt_key(symbol)
    _ctx_degraded.pop(key, None)

    if not force:
        rec = retrieve_long_term_data(key)
        if rec and is_fresh_meta(rec, MARKET_TTL):
            df = _records_to_ctx(rec.get("rows"))
            if df is not None:
                return df

    try:
        df = build_market_context(symbol)
    except Exception as e:  # noqa: BLE001
        # 重建失败 → 回退到过期记录（低频数据，几天内不影响判断）
        stale = retrieve_long_term_data(key)
        stale_df = _records_to_ctx(stale.get("rows")) if stale else None
        if stale_df is not None:
            logger.warning(f"指数温度重建失败({symbol})，回退过期缓存：{e}")
            _ctx_degraded[key] = f"温度序列用缓存（{stale.get('fetched_at')}）"
            return stale_df
        logger.warning(f"指数温度构造失败({symbol}) 且无可用缓存：{e}")
        raise

    try:
        store_long_term_data(
            key,
            {"fetched_at": datetime.now().isoformat(timespec="seconds"),
             "symbol": symbol, "rows": _ctx_to_records(df)},
            _MKT_MODULE,
        )
        logger.info(f"指数温度已存入 cache.db: {symbol} {len(df)} 行")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"指数温度缓存写入失败: {e}")
    return df




def _state(pos) -> tuple:
    """(状态名, 颜色) — 位置越高越贵/热。"""
    if pos is None or pos != pos:
        return "数据不足", "#8a6d3b"
    if pos >= 0.90:
        return "高估/风险区", "#c0392b"
    if pos <= 0.10:
        return "低估/机会区", "#1f7a33"
    if pos >= 0.70:
        return "偏贵/偏热", "#b9770e"
    if pos <= 0.30:
        return "偏便宜/偏冷", "#2874a6"
    return "中性", "#8a6d3b"


def build_market_cards(ctx: pd.DataFrame, pair: str = "hs300") -> dict:
    """市场背景数据（替代原 market_cards_html）。"""
    if ctx is None or ctx.empty:
        return {}
    last = ctx.iloc[-1]
    temp = float(last.get("temperature", float("nan")))
    broad = float(last.get("market_position", float("nan")))
    state, color = _state(temp)
    d = str(pd.Timestamp(last["date"]))[:10]
    cards = []
    for col, label, _d in _MAIN_ITEMS + _AUX_ITEMS:
        v = float(last.get(col, float("nan")))
        p = float(last.get(f"pos_{col}", float("nan")))
        group = "main" if (col, label, _d) in _MAIN_ITEMS else "aux"
        cards.append({"item": label, "value": v, "pos": p, "group": group})
    return {"cards": cards, "state": state, "color": color, "date": d,
            "temperature": temp, "broad": broad}


def get_market_temperature_all(force: bool = False) -> dict:
    """三大指数（上证综指/深证成指/创业板指）市场温度卡片。

    在线成分/温度接口不可靠，故每个指数会标注 `degraded`/`degraded_reason`
    （成分或温度序列使用了缓存），前端据此提示数据截至时间。
    """
    from ..data_fetchers.pool_data_fetcher import index_cons_meta

    out = []
    for key, (symbol, label) in MARKET_INDICES.items():
        item = {"key": key, "label": label, "symbol": symbol}
        try:
            ctx = get_market_context(symbol, force=force)
            if ctx is not None and not ctx.empty:
                item.update(build_market_cards(ctx, pair=label))

                reasons = []
                cons = index_cons_meta(symbol)
                if str(cons.get("source", "")).startswith("cache"):
                    reasons.append(f"成分股用 {cons.get('fetched_at')} 的缓存")
                ctx_reason = _ctx_degraded.get(_mkt_key(symbol))
                if ctx_reason:
                    reasons.append(ctx_reason)
                if reasons:
                    item["degraded"] = True
                    item["degraded_reason"] = "；".join(reasons)
            else:
                item["error"] = "数据不足"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"市场温度({label}) 计算失败: {e}")
            item["error"] = str(e)
        out.append(item)
    return {"indices": out}


def latest_temperature_cached(symbol: str = "000001.SH") -> Optional[dict]:
    """只读已缓存的指数温度（不触发任何计算）。

    供个股报告做"温度门控"参考：命中缓存返回
    {symbol, temperature, state, date}；无缓存返回 None —— **绝不在此处现算**，
    避免报告接口被 ~1 分钟的成分拉取拖住。
    """
    rec = retrieve_long_term_data(_mkt_key(symbol))
    df = _records_to_ctx(rec.get("rows")) if rec else None
    if df is None or df.empty:
        return None
    last = df.iloc[-1]
    try:
        temp = float(last.get("temperature", float("nan")))
    except (TypeError, ValueError):
        temp = float("nan")
    state, _color = _state(temp)
    return {"symbol": symbol, "temperature": (None if temp != temp else round(temp, 4)),
            "state": state, "date": str(pd.Timestamp(last["date"]))[:10]}


def build_market_level(pool="hs300", start="20100101", end=None) -> pd.Series:
    """月频中位 PB 序列（index=月首 Timestamp）。"""
    from ..data_fetchers.pool_data_fetcher import pool_codes
    from ..data_fetchers.stockdb_data_fetcher import get_raw

    codes = pool_codes(pool)
    if not codes:
        raise RuntimeError(f"市场水位({pool})：股票池为空")
    end = end or pd.Timestamp.now().strftime("%Y%m%d")
    raw = get_raw(list(codes), start=start, end=end, fq=None, fields="date,code,pb")
    if raw is None or len(raw) == 0:
        raise RuntimeError(f"市场水位({pool})：成分日K返回空")
    df = raw.dropna(subset=["pb"]).copy()
    if df.empty:
        raise RuntimeError(f"市场水位({pool})：pb 字段全为空")
    df["dt"] = pd.to_datetime(df["date"].astype("int64").astype(str), format="%Y%m%d")
    s = df.groupby(df["dt"].dt.to_period("M"))["pb"].median()
    s.index = s.index.to_timestamp()
    return s.sort_index()


def get_market_level(pool="hs300", force=False) -> Optional[pd.Series]:
    """月频中位 PB 序列（带 7 天缓存，存 `cache.db`）。"""
    key = _lvl_key(pool)
    if not force:
        rec = retrieve_long_term_data(key)
        if rec and rec.get("points") and is_fresh_meta(rec, LEVEL_TTL):
            try:
                s = pd.Series({pd.Timestamp(p["date"]): float(p["pb_median"])
                               for p in rec["points"]})
                if len(s):
                    return s.sort_index()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"市场水位缓存解析失败({pool}): {e}")
    try:
        s = build_market_level(pool)
    except Exception as e:
        logger.warning(f"市场水位构造失败({pool}): {e}")
        return None
    try:
        store_long_term_data(
            key,
            {"fetched_at": datetime.now().isoformat(timespec="seconds"), "pool": pool,
             "n": int(len(s)),
             "points": [{"date": str(d.date()), "pb_median": round(float(v), 4)}
                        for d, v in s.items()]},
            _LVL_MODULE,
        )
        logger.info(f"市场水位已存入 cache.db: {pool} {len(s)} 个点")
    except Exception as e:
        logger.warning(f"市场水位缓存写入失败: {e}")
    return s
