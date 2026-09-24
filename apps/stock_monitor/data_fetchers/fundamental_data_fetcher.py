"""
财务数据接入 — 季报 ROE / 分红送配 / 营业收入。

数据源 akshare（不可用时返回 None，调用方降级处理，不阻塞主流程）。
缓存写入 `cache.db` 的 `long_term_storage`（`module_type="fundamental"`，稳定 key → 原地覆盖），
新鲜期 30 天，TTL 由 `fetched_at` 判定。**不落任何磁盘文件**。
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from config import setup_logger
from ..core.utils import is_fresh_meta

from ..core.cache_with_database import retrieve_long_term_data, store_long_term_data

logger = setup_logger(__name__)

REPORT_ROE_TTL = 30 * 24 * 3600
DIV_TTL = 30 * 24 * 3600
REVENUE_TTL = 30 * 24 * 3600
REPORT_ROE_START_YEAR = "2005"
_ANN_FACTOR = {3: 4.0, 6: 2.0, 9: 4.0 / 3.0, 12: 1.0}

_FUND_MODULE = "fundamental"


def _key(code: str, prefix: str) -> str:
    """`long_term_storage` 的 key（稳定，原地覆盖）。"""
    return f"fundamental_{prefix}_{code}"


def _cached(key: str, ttl: int, field: str):
    """命中新鲜缓存 → 返回该字段；否则 None。"""
    rec = retrieve_long_term_data(key)
    if rec and rec.get(field) and is_fresh_meta(rec, ttl):
        return rec[field]
    return None


def _store(key: str, code: str, field: str, value) -> None:
    try:
        store_long_term_data(
            key,
            {"fetched_at": datetime.now().isoformat(timespec="seconds"),
             "code": code, "source": "akshare", field: value},
            _FUND_MODULE,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"财务缓存写入失败({key}): {e}")


def _exchange_prefix(code: str) -> str:
    """6 位代码 → 交易所前缀（东财 akshare 格式：SH/SZ/BJ）。"""
    if code.startswith("6"):
        return "SH" + code
    if code.startswith(("0", "3")):
        return "SZ" + code
    if code.startswith(("4", "8", "9")):
        return "BJ" + code
    return code


def get_report_roe(code: str, force: bool = False) -> Optional[List[Dict]]:
    """季报 ROE 序列（akshare），缓存 30 天。返回 [{report_date, roe, roe_ann}]。

    首选东财接口 `stock_financial_analysis_indicator_em`（字段 ROEJQ=加权净资产收益率，
    符号需 SH/SZ/BJ 前缀且带交易所后缀）；旧接口 `stock_financial_analysis_indicator`
    作为回退（2026-09 起东财改版，旧接口普遍返回 None）。
    """
    key = _key(code, "fin")
    if not force:
        cached = _cached(key, REPORT_ROE_TTL, "rows")
        if cached:
            return cached
    try:
        import akshare as ak
    except Exception:
        logger.warning(f"季报ROE({code}) 跳过：未安装 akshare")
        return None
    rows: List[Dict] = []
    try:
        logger.info(f"拉取季报ROE(em): {code}")
        df = ak.stock_financial_analysis_indicator_em(
            symbol=_em_symbol(code), indicator="按报告期")
        rows = _parse_roe_em(df)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"季报ROE({code}) em 接口失败: {type(e).__name__}: {e}")
    if not rows:
        try:
            logger.info(f"拉取季报ROE(旧接口回退): {code}")
            df = ak.stock_financial_analysis_indicator(symbol=code,
                                                       start_year=REPORT_ROE_START_YEAR)
            rows = _parse_roe_legacy(df)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"季报ROE({code}) 旧接口失败: {type(e).__name__}: {e}")
    rows.sort(key=lambda x: x["report_date"])
    if rows:
        _store(key, code, "rows", rows)
        logger.info(f"季报ROE已缓存: {code} {len(rows)} 期")
    return rows or None


def _em_symbol(code: str) -> str:
    """6 位代码 → 东财 em 接口符号（带交易所后缀，如 601166.SH）。"""
    if code.startswith("6"):
        return f"{code}.SH"
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8", "9")):
        return f"{code}.BJ"
    return code


def _parse_roe_em(df) -> List[Dict]:
    """解析 em 接口：ROEJQ=加权净资产收益率(%)，REPORT_DATE=报告期。"""
    if df is None or getattr(df, "empty", True):
        return []
    col = {str(c): c for c in df.columns}
    c_date, c_roe = col.get("REPORT_DATE"), col.get("ROEJQ")
    if not (c_date and c_roe):
        return []
    rows: List[Dict] = []
    for _, r in df.iterrows():
        try:
            d = str(r[c_date])[:10]
            m = int(d[5:7])
            roe = float(r[c_roe])
        except (ValueError, TypeError, KeyError):
            continue
        if roe != roe:
            continue
        rows.append({"report_date": d, "roe": round(roe, 4),
                     "roe_ann": round(roe * _ANN_FACTOR.get(m, 1.0), 4)})
    return rows


def _parse_roe_legacy(df) -> List[Dict]:
    """解析旧接口：净资产收益率(%) + 日期。"""
    if df is None or df.empty or "日期" not in df.columns \
            or "净资产收益率(%)" not in df.columns:
        return []
    rows: List[Dict] = []
    for _, r in df.iterrows():
        try:
            d = str(r["日期"])[:10]
            m = int(d[5:7])
            roe = float(r["净资产收益率(%)"])
        except (ValueError, TypeError, KeyError):
            continue
        if roe != roe:
            continue
        rows.append({"report_date": d, "roe": round(roe, 4),
                     "roe_ann": round(roe * _ANN_FACTOR.get(m, 1.0), 4)})
    return rows


def get_payout_ratio(code: str, force: bool = False) -> Optional[Dict]:
    """股利支付率（akshare 分红送配），缓存 30 天。
    返回 {'payout', 'year', 'dps', 'eps'}；不可用返回 None。"""
    key = _key(code, "div")
    if not force:
        cached = _cached(key, DIV_TTL, "data")
        if cached:
            return cached
    try:
        import akshare as ak
    except Exception:
        logger.warning(f"分红率({code}) 跳过：未安装 akshare")
        return None
    try:
        logger.info(f"拉取分红送配: {code}")
        df = ak.stock_fhps_detail_em(symbol=code)
    except Exception as e:
        logger.warning(f"分红率({code}) 拉取失败: {e}")
        return None
    row = _pick_annual_payout(df)
    if row is None:
        logger.warning(f"分红率({code}) 无可用年报分红行，N=1.0")
        return None
    _store(key, code, "data", row)
    logger.info(f"分红率已缓存: {code} {row['year']} 年支付率={row['payout']:.1%}")
    return row


def get_report_revenue(code: str, force: bool = False) -> Optional[List[Dict]]:
    """历史营业收入（akshare 利润表，报告期累计值），缓存 30 天。
    返回 [{report_date, revenue}]（按报告期升序）；不可用返回 None。"""
    key = _key(code, "rev")
    if not force:
        cached = _cached(key, REVENUE_TTL, "rows")
        if cached:
            return cached
    try:
        import akshare as ak
    except Exception:
        logger.warning(f"营业收入({code}) 跳过：未安装 akshare")
        return None
    try:
        logger.info(f"拉取营业收入: {code}")
        df = ak.stock_profit_sheet_by_report_em(symbol=_exchange_prefix(code))
    except Exception as e:
        logger.warning(f"营业收入({code}) 拉取失败: {e}")
        return None
    if df is None or df.empty or "REPORT_DATE" not in df.columns or "OPERATE_INCOME" not in df.columns:
        return None
    rows: List[Dict] = []
    for _, r in df.iterrows():
        try:
            d = str(r["REPORT_DATE"])[:10]
            rev = float(r["OPERATE_INCOME"])
        except (ValueError, TypeError, KeyError):
            continue
        if rev != rev or rev <= 0:
            continue
        rows.append({"report_date": d, "revenue": round(rev, 2)})
    rows.sort(key=lambda x: x["report_date"])
    if rows:
        _store(key, code, "rows", rows)
        logger.info(f"营业收入已缓存: {code} {len(rows)} 期")
    return rows


def _pick_annual_payout(df) -> Optional[Dict]:
    """从 stock_fhps_detail_em 取最近年报的股利支付率。"""
    if df is None or getattr(df, "empty", True):
        return None
    col = {str(c): c for c in df.columns}
    c_rp = col.get("报告期")
    c_eps = col.get("每股收益")
    c_dps = next((c for k, c in col.items()
                 if "现金分红" in k and "比例" in k and "描述" not in k), None)
    if not (c_rp and c_dps and c_eps):
        return None
    agg: Dict[int, Dict] = {}
    for _, r in df.iterrows():
        d = str(r.get(c_rp, ""))[:10]
        if len(d) < 7 or d[5:7] != "12":
            continue
        try:
            dps = float(r[c_dps]) / 10.0
            eps = float(r[c_eps])
            year = int(d[:4])
        except (TypeError, ValueError):
            continue
        if dps != dps or eps != eps or dps <= 0 or eps <= 0:
            continue
        a = agg.setdefault(year, {"dps": 0.0, "eps": eps})
        a["dps"] += dps
    if not agg:
        return None
    year = max(agg)
    a = agg[year]
    return {"payout": a["dps"] / a["eps"], "year": year,
            "dps": round(a["dps"], 4), "eps": round(a["eps"], 4)}
