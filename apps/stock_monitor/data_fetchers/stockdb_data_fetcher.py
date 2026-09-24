"""
stockdb 本地引擎接入层 — SDK 加载/连接、日K读取。

说明：指数成分股**不在这里**（stockdb 的 `get_index_stocks` 是在线接口，
需服务端配置 `mapi_url`，当前不可用）。成分股统一走
`data_fetchers/pool_data_fetcher.get_index_constituents()`（akshare + cache.db）。
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional

import pandas as pd

from config import get_path, setup_logger

logger = setup_logger(__name__)

_PYBAO_DIR = get_path("stockdb", "pybao_dir", "/root/apps/stockdb/pybao")
_STOCKDB_HOST = get_path("stockdb", "host", "192.168.50.50")
_STOCKDB_PORT = int(get_path("stockdb", "port", "7899"))
_STOCKDB_DIR = get_path("stockdb", "dir", "/root/apps/stockdb")
# 在线接口（指数成分 / 全市场证券等）所需的 API 地址，形如 "host:port"。
# 留空 = 用服务端数据库里的 mapi_url 配置（服务端没配时会报"API IP地址未配置"）。
_STOCKDB_API_URL = get_path("stockdb", "api_url", "") or ""


_sdk = None
FETCH_TRIES = 3
FETCH_RETRY_SLEEP = 1

# 连接失败熔断：单次连接失败要等数秒超时，若每只股票/基金都重试，整个页面会被拖垮
# （实测 stockdb 不可达时取 67 只基金要 23s）。失败后在冷却期内直接复用上次错误。
FAIL_COOLDOWN = 60.0  # 秒
_last_fail_at = 0.0
_last_error = ""


def last_error() -> str:
    """最近一次 stockdb 失败原因（空串 = 正常）。供上层在响应里提示用户。"""
    return _last_error


def _record_failure(msg: str) -> None:
    """记录失败并开启熔断窗口。"""
    global _sdk, _last_fail_at, _last_error
    _last_fail_at = time.time()
    _last_error = msg
    _sdk = None  # 连接可能已失效，下次重新 init


def ensure_sdk():
    """加载并 init stockdb SDK（pybao），进程内缓存；失败后 60s 内熔断（不重复连接）。"""
    global _sdk, _last_error
    if _sdk is not None:
        return _sdk

    if _last_error and (time.time() - _last_fail_at) < FAIL_COOLDOWN:
        raise RuntimeError(_last_error)  # 熔断中：直接复用上次失败原因

    try:
        if not os.path.isdir(_PYBAO_DIR):
            raise RuntimeError(f"stockdb pybao 目录不存在: {_PYBAO_DIR}")
        if _PYBAO_DIR not in sys.path:
            sys.path.insert(0, _PYBAO_DIR)
        sys.modules.pop("stock_sdk", None)
        try:
            import stock_sdk as sdk
        except Exception as e:
            raise RuntimeError(f"导入 stock_sdk 失败（{_PYBAO_DIR}）: {e}")
        if not (hasattr(sdk, "rd") and hasattr(sdk.rd, "get_data")):
            raise RuntimeError(f"{_PYBAO_DIR} 的 stock_sdk 缺少 rd.get_data")
        try:
            sdk.init(_STOCKDB_HOST, _STOCKDB_PORT)
        except Exception as e:
            raise RuntimeError(
                f"连接 stockdb({_STOCKDB_HOST}:{_STOCKDB_PORT}) 失败: {e}"
                f"——请确认 stockdb 服务已启动且可访问（{_STOCKDB_DIR}）")
    except Exception as e:
        _record_failure(str(e))
        raise

    if _STOCKDB_API_URL:
        try:
            _set_init(sdk, False)
            logger.info(f"stockdb 在线 API 已配置: {_STOCKDB_API_URL}")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"stockdb 在线 API 配置失败（{_STOCKDB_API_URL}）: {e}")

    logger.info(f"stockdb SDK 就绪: {_STOCKDB_HOST}:{_STOCKDB_PORT}")
    _sdk = sdk
    _last_error = ""
    return _sdk


def get_raw(codes, start=None, end=None, fq="qfq", fields=None,
            tries=FETCH_TRIES) -> pd.DataFrame:
    """底层日K读取（带重试），返回原始 DataFrame。"""
    sdk = ensure_sdk()
    start, end = _resolve_range(start, end)
    code_list = [codes] if isinstance(codes, str) else list(codes)
    kw = {"fields": fields} if fields else {}
    last = None
    for i in range(max(1, tries)):
        try:
            raw = sdk.rd.get_data(code_list, start=start, end=end,
                                  frequency="1d", fq=fq, as_df=True, **kw)
        except Exception as e:
            # 查询异常：记录并熔断（下次 ensure_sdk 会重新 init）
            _record_failure(f"stockdb 查询失败（{_STOCKDB_HOST}:{_STOCKDB_PORT}）: {e}")
            raise
        last = raw
        if raw is not None and len(raw) > 0:
            return raw
        if i + 1 < tries:
            logger.warning(f"stockdb 返回空（{i+1}/{tries}），重试…")
            time.sleep(FETCH_RETRY_SLEEP)
    logger.warning(f"stockdb 连续 {tries} 次返回空：{code_list[:3]}")
    return last if last is not None else pd.DataFrame()


def _norm_df(df: pd.DataFrame) -> pd.DataFrame:
    """规整 stockdb 日K：date 统一为 %Y-%m-%d 升序、数值列转 float。"""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d", errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date")
        df = df.drop_duplicates(subset=["date", "code"], keep="last")
    for c in ("open", "high", "low", "close", "volume", "amount", "pb",
              "pe_ttm", "turnover", "total_mv", "float_mv", "pct_chg"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.reset_index(drop=True)


def get_daily(code: str, start=None, end=None, fq="qfq", fields=None) -> pd.DataFrame:
    """单只股票日K（date 为 datetime64，升序）。

    `fields` 透传给底层 `get_raw()`（如 "date,close,pct_chg" 可减少传输量）。
    """
    s, e = _resolve_range(start, end)
    raw = get_raw([code], start=s, end=e, fq=fq, fields=fields)
    df = _to_df(raw, code)
    if df.empty:
        logger.warning(f"get_daily 无数据: {code}")
        return pd.DataFrame()
    logger.info(f"get_daily({code}) -> {len(df)} 行")
    return _norm_df(df)




def _to_df(raw, code: Optional[str]) -> pd.DataFrame:
    """兼容 stockdb 返回 dict 或 DataFrame。"""
    if raw is None:
        return pd.DataFrame()
    if isinstance(raw, pd.DataFrame):
        df = raw
        if code is not None and "code" in df.columns:
            df = df[df["code"] == code]
        return df
    if isinstance(raw, dict):
        rows = raw.get(code, []) if code else [
            r for v in raw.values() for r in (v if isinstance(v, list) else [v])
        ]
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    return pd.DataFrame()


def _set_init(sdk, df: bool) -> None:
    """配置在线接口的返回模式（`df=True` → DataFrame）。

    若配置了 `[stockdb] api_url`，则一并指定在线 API 地址
    （等价于官方文档的 `set_init("host:port", df=True)`）。
    """
    if _STOCKDB_API_URL:
        sdk.set_init(_STOCKDB_API_URL, df=df)
    else:
        sdk.set_init(df=df)


def _fmt_date(d):
    if not d:
        return None
    return str(d).replace("-", "") if len(str(d)) <= 10 else str(d)


def _resolve_range(start, end):
    """stockdb 要求 start/end 成对；缺端补全。"""
    if not start and not end:
        return None, None
    if start and not end:
        return _fmt_date(start), pd.Timestamp.now().strftime("%Y%m%d")
    if end and not start:
        return "20000101", _fmt_date(end)
    return _fmt_date(start), _fmt_date(end)
