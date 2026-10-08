"""
RPS 底座 —— 横截面相对强度（欧奈尔 RPS / 反转体系的核心）。

与系统内其它因子的**根本区别**：其它因子都是「相对自身历史」的**时序**读数
（见 `factor_fusion.py` 的说明："信号在时序不在横截面"），
而 RPS 是「相对**其他股票**」的**横截面**读数 —— 这是一个正交的新维度。

口径（对齐欧奈尔 RPS 曲线的编制方法）：
  1. 每只股票算 EXTRS = close[t] / close[t-N] - 1      （N = 50 / 120 / 250）
  2. **同一交易日横截面**上，把 EXTRS 转成百分位排名（0~1，越接近 1 越强）
  3. 通达信里是 RPS = 百分位 × 100（0~1000 归一化 ÷ 10）

本模块内部统一存 **0~1**（与 `factor_utils` 的 `*_pct` 体系一致，可直接当门控/条件用），
展示时乘 100（见 `fmt_rps`）。

样本池（对齐「上市一年以上」自建板块，见 `_eligible_mask`）：
  * 上市满 `min_listed_bars` 个交易日（剔新股 —— 新股一字板会霸榜污染排名）
  * 非 ST（名称含 ST / *ST / 退）
  * 非长期停牌（近 `max_stale_bars` 根内有过成交）

数据源：stockdb 日K（**qfq 前复权**，与估值/基金/市场温度同一口径）。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from config import setup_logger

logger = setup_logger(__name__)

# ---------------------------------------------------------------- 常量
RPS_WINDOWS = (50, 120, 250)
RPS_COLS = tuple(f"rps{w}" for w in RPS_WINDOWS)

# 「上市一年以上」：约 250 个交易日
MIN_LISTED_BARS = 250
# 长期停牌：近 60 个交易日内无成交 → 视为不可交易
MAX_STALE_BARS = 60

# ST / 退市 识别（stockdb 的 name 字段；取不到 name 时该判据自动跳过）
_ST_PAT = re.compile(r"(^\*?ST|退$|退市)")

MERGED_COLS = RPS_COLS + ("rps_eligible",)


@dataclass
class RpsParams:
    """RPS 参数。

    `windows`        —— 相对强度窗口（交易日），默认 50/120/250
    `min_listed_bars`—— 上市最少交易日（剔新股）
    `max_stale_bars` —— 近多少根内有过成交才视为在交易
    `exclude_st`     —— 是否剔除 ST
    """

    windows: Sequence[int] = RPS_WINDOWS
    min_listed_bars: int = MIN_LISTED_BARS
    max_stale_bars: int = MAX_STALE_BARS
    exclude_st: bool = True

    def cols(self) -> tuple:
        return tuple(f"rps{w}" for w in self.windows)


# ---------------------------------------------------------------- 纯计算
def rps_columns(extrs: pd.DataFrame) -> pd.DataFrame:
    """横截面百分位：index=date、columns=code 的「涨幅」宽表 → 0~1 分位宽表。

    用 `rank(pct=True)`（对 NaN 自动跳过，不参与排名），
    等价于"该股当日涨幅在全市场中的位置"。
    """
    return extrs.rank(axis=1, pct=True, na_option="keep")


def compute_rps(close: pd.DataFrame,
                params: Optional[RpsParams] = None,
                name_by_code: Optional[Dict[str, str]] = None,
                volume: Optional[pd.DataFrame] = None) -> Dict[str, pd.DataFrame]:
    """由收盘价宽表算 RPS 宽表。

    参数：
      `close`          —— index=date（升序）、columns=code 的收盘价宽表（**qfq**）
      `name_by_code`   —— {code: 股票名称}，用于剔除 ST（缺省则不剔）
      `volume`         —— 同形状成交量宽表，用于识别长期停牌（缺省则不剔）

    返回：{ "rps50": DataFrame, "rps120": ..., "rps250": ..., "rps_eligible": bool 宽表 }
    """
    p = params or RpsParams()
    if close is None or close.empty:
        return {}

    out: Dict[str, pd.DataFrame] = {}
    for w in p.windows:
        # EXTRS = close[t] / close[t-w] - 1（不足 w 根 → NaN，即"上市不满一年"）
        extrs = close / close.shift(w) - 1.0
        out[f"rps{w}"] = rps_columns(extrs)

    # 合格样本掩码（**必须**与排名同时点，避免用未来信息）
    out["rps_eligible"] = _eligible_mask(close, p, name_by_code, volume)

    # 不合格样本的 RPS 置空（不参与选股，但仍保留在宽表里便于排查）
    elig = out["rps_eligible"]
    for w in p.windows:
        out[f"rps{w}"] = out[f"rps{w}"].where(elig)

    logger.info(f"RPS 计算完成：{close.shape[1]} 只 × {close.shape[0]} 交易日，"
                f"窗口 {list(p.windows)}，合格样本均值 "
                f"{float(elig.mean().mean()):.1%}")
    return out


def _eligible_mask(close: pd.DataFrame, p: RpsParams,
                   name_by_code: Optional[Dict[str, str]],
                   volume: Optional[pd.DataFrame]) -> pd.DataFrame:
    """合格样本掩码（逐日）：上市够久 + 非 ST + 非长期停牌。"""
    n = close.notna().cumsum()                 # 累计有效交易日 = 已上市天数
    mask = n >= p.min_listed_bars

    if volume is not None and not volume.empty:
        # 近 max_stale_bars 根内有过成交量 → 在交易
        traded = (volume.fillna(0) > 0).rolling(
            p.max_stale_bars, min_periods=1).max().astype(bool)
        mask &= traded.reindex_like(mask).fillna(False)

    if p.exclude_st and name_by_code:
        st_codes = [c for c, nm in name_by_code.items()
                    if nm and _ST_PAT.search(str(nm).strip())]
        if st_codes:
            mask.loc[:, [c for c in st_codes if c in mask.columns]] = False
            logger.info(f"RPS 剔除 ST/退市 {len(st_codes)} 只")

    return mask.fillna(False).astype(bool)


# ---------------------------------------------------------------- 取数
OHLCV_FIELDS = "date,code,open,high,low,close,volume,name"


def load_panel(codes: Sequence[str], start: str,
               fields: str = OHLCV_FIELDS,
               chunk: int = 1200,
               progress: bool = True) -> Dict[str, pd.DataFrame]:
    """批量取 stockdb 日K → 宽表。

    返回 `{"close","open","high","low","volume"}`（DataFrame 宽表）
    与 `"name_by_code"`（dict）。

    ⚠️ 必须**分块**请求：stockdb 一次吃几千只代码会超时/爆内存
    （实测 7563 只分 7 块约 264s）。
    """
    from ..data_fetchers.stockdb_data_fetcher import get_raw

    codes = [str(c).zfill(6) for c in codes]
    frames: List[pd.DataFrame] = []
    for i in range(0, len(codes), chunk):
        part = codes[i:i + chunk]
        raw = get_raw(part, start=start, end=None, fq="qfq", fields=fields)
        if raw is None or len(raw) == 0:
            logger.warning(f"stockdb 空返回：第 {i}~{i + len(part)} 只")
            continue
        frames.append(raw)
        if progress:
            logger.info(f"已取 {min(i + chunk, len(codes))}/{len(codes)} 只日K")

    if not frames:
        return {}

    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"].astype("int64").astype(str),
                                format="%Y%m%d")
    df["code"] = df["code"].astype(str).str.zfill(6)
    num_cols = ("open", "high", "low", "close", "volume", "amount")
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    out: Dict[str, pd.DataFrame] = {}
    for c in num_cols:
        if c in df.columns:
            out[c] = df.pivot_table(index="date", columns="code",
                                    values=c).sort_index()
    if "name" in df.columns:
        names = (df.dropna(subset=["name"])
                   .groupby("code")["name"].last().astype(str).to_dict())
        out["name_by_code"] = names
    logger.info(f"面板就绪：{len(out.get('close', pd.DataFrame()).columns)} 只 × "
                f"{len(out.get('close', pd.DataFrame()))} 交易日")
    return out


# 向后兼容旧名
load_close_panel = load_panel


# ---------------------------------------------------------------- 磁盘缓存
# RPS 必须全市场横截面计算（首次 ~280s 取数），故落 `cache.db` 长期存储：
#   key = "rps_panel_{start}" → {rps50/rps120/rps250 的分位矩阵 + 日期索引 + 股票代码}
# TTL 由 RPS_CACHE_TTL_HOURS 控制（默认 24h，"加长缓存时间"由用户调）。
RPS_CACHE_MODULE = "rps_panel"
RPS_CACHE_TTL_HOURS = float(os.environ.get("RPS_CACHE_TTL_HOURS", "24"))


def _panel_cache_key(start: str) -> str:
    return f"rps_panel_{start}"


def load_rps_cached(start: str, codes: Optional[Sequence[str]] = None,
                    force: bool = False) -> Optional[Dict[str, pd.DataFrame]]:
    """带 `cache.db` 长期缓存的 RPS 计算（**全市场横截面**）。

    返回 `{rps50, rps120, rps250, rps_eligible}` 宽表（index=date、columns=code）。
    命中缓存直接返回（秒级）；未命中才全市场重算并写缓存。
    """
    from ..core.cache_with_database import (retrieve_long_term_data,
                                            store_long_term_data)

    key = _panel_cache_key(start)
    if not force:
        rec = retrieve_long_term_data(key)
        if rec and rec.get("blocks"):
            frames = _read_rps_cache(rec)
            if frames is not None:
                logger.info(f"RPS 命中缓存（{rec.get('fetched_at', '?')}）："
                            f"{len(frames['rps50'].columns)} 只 × "
                            f"{len(frames['rps50'])} 交易日")
                return frames

    market = list(codes) if codes else all_market_codes()
    if not market:
        return None
    panel = load_panel(market, start=start, progress=False)
    close = panel.get("close")
    if close is None or close.empty:
        return None
    res = compute_rps(close, RpsParams(),
                      name_by_code=panel.get("name_by_code"),
                      volume=panel.get("volume"))

    # 只缓存 `rps50/120/250`（bool 列与 panel 都不必存）；
    # 用**紧凑 JSON**（日期字符串 + 每列 hex 化的 float32）——直接 json.dumps
    # 1100 万个格子会又慢又大（实测写不进去），故走 base64。
    _write_rps_cache(key, start, res)
    return res


def _write_rps_cache(key: str, start: str, res: Dict[str, pd.DataFrame]) -> None:
    """把 RPS 宽表写成紧凑 JSON 存 `cache.db`。

    格式：`{dates: ["YYYY-MM-DD", ...], cols: {code: [...]}, data: {rps50: <b64 float32>}}`
    —— 逐列打包，避免 1100 万个 `{"日期": 值}` 字典（体积/耗时都不可接受）。
    """
    import base64

    from ..core.cache_with_database import store_long_term_data

    try:
        any_df = res["rps50"]
        codes = [str(c) for c in any_df.columns]
        dates = [str(pd.Timestamp(d))[:10] for d in any_df.index]
        blocks = {}
        for win in ("rps50", "rps120", "rps250"):
            arr = np.nan_to_num(
                res[win].to_numpy(dtype="float32"), nan=-1.0)
            blocks[win] = {"b64": base64.b64encode(arr.tobytes()).decode("ascii"),
                           "shape": list(arr.shape)}
        payload = {
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "start": start, "dates": dates, "codes": codes, "blocks": blocks,
        }
        ok = store_long_term_data(key, payload, RPS_CACHE_MODULE,
                                  expires_in_seconds=int(RPS_CACHE_TTL_HOURS * 3600))
        logger.info(f"RPS 写入缓存{'成功' if ok else '失败'}（TTL "
                    f"{RPS_CACHE_TTL_HOURS:.0f}h）：{key}，{len(codes)} 只")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"RPS 写缓存失败（不影响本次结果）：{type(e).__name__}: {e}")


def _read_rps_cache(rec: dict) -> Optional[Dict[str, pd.DataFrame]]:
    """解析紧凑 JSON → RPS 宽表（NaN 用 -1 哨兵编码）。"""
    import base64

    from ..core.cache_with_database import retrieve_long_term_data  # noqa: F401

    try:
        dates = pd.to_datetime(rec["dates"])
        codes = [str(c) for c in rec["codes"]]
        out = {}
        for win in ("rps50", "rps120", "rps250"):
            blk = rec["blocks"][win]
            arr = np.frombuffer(base64.b64decode(blk["b64"]),
                                dtype="float32").reshape(blk["shape"])
            arr = np.where(arr < 0, np.nan, arr).astype("float32")
            out[win] = pd.DataFrame(arr, index=dates, columns=codes)
        return out
    except Exception as e:  # noqa: BLE001
        logger.warning(f"RPS 缓存解析失败：{type(e).__name__}: {e}")
        return None


# ---------------------------------------------------------------- 选股池 RPS 缓存
PICKER_RPS_MODULE = "picker_rps"


def _picker_rps_key(codes: Sequence[str], start: str) -> str:
    """池指纹（代码排序 + 数量哈希）→ 不同池各自一份缓存。"""
    import hashlib

    joined = ",".join(sorted(str(c).zfill(6) for c in codes))
    digest = hashlib.md5(joined.encode()).hexdigest()[:12]
    return f"picker_rps_{start}_{len(codes)}_{digest}"


def load_picker_rps_cached(codes: Sequence[str],
                           start: str) -> Optional[Dict[str, pd.DataFrame]]:
    """读选股池 RPS 磁盘缓存 → `{code: DataFrame(rps50,rps120,rps250,date)}`。"""
    from ..core.cache_with_database import retrieve_long_term_data

    rec = retrieve_long_term_data(_picker_rps_key(codes, start))
    if not rec or not rec.get("blocks"):
        return None
    # 防御：日期全为 1970（历史 bug 写入的坏缓存）→ 视为未命中
    ds = rec.get("dates") or []
    if ds and all(str(d).startswith("1970-") for d in ds[:5]):
        logger.warning("选股池 RPS 缓存日期异常（全 1970），忽略并按未命中处理")
        return None
    wide = _read_rps_cache(rec)
    if wide is None:
        return None
    out: Dict[str, pd.DataFrame] = {}
    idx = wide["rps50"].index
    for code in wide["rps50"].columns:
        df = pd.DataFrame({w: wide[w][code].values
                           for w in ("rps50", "rps120", "rps250")})
        df["date"] = idx
        out[str(code)] = df.reset_index(drop=True)
    return out


def store_picker_rps_cached(codes: Sequence[str], start: str,
                            per_code: Dict[str, pd.DataFrame]) -> None:
    """写选股池 RPS 磁盘缓存（紧凑列式，TTL 同 `RPS_CACHE_TTL_HOURS`）。

    ⚠️ 不能用 `{日期: 值}` 字典（11M 格子既慢又大）；用列式 b64 float32。
    """
    import base64

    from ..core.cache_with_database import store_long_term_data

    try:
        any_df = next(iter(per_code.values()))
        order = list(per_code.keys())
        # ⚠️ `_build_rps` 产出的 DataFrame 已 reset_index，日期在 `date` **列**里，
        #    不在 index 上 —— 曾因取 index 导致所有日期写成 1970-01-01。
        if "date" in any_df.columns:
            dates = [str(pd.Timestamp(d))[:10] for d in any_df["date"]]
        else:
            dates = [str(pd.Timestamp(d))[:10] for d in any_df.index]
        blocks = {}
        for win in ("rps50", "rps120", "rps250"):
            arr = np.full((len(dates), len(order)), -1.0, dtype="float32")
            for j, c in enumerate(order):
                if win in per_code[c].columns:
                    arr[:, j] = np.nan_to_num(
                        per_code[c][win].to_numpy(dtype="float32"), nan=-1.0)
            blocks[win] = {"b64": base64.b64encode(arr.tobytes()).decode("ascii"),
                           "shape": list(arr.shape)}
        payload = {
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "start": start, "dates": dates, "codes": order, "blocks": blocks,
        }
        store_long_term_data(_picker_rps_key(codes, start), payload,
                             PICKER_RPS_MODULE,
                             expires_in_seconds=int(RPS_CACHE_TTL_HOURS * 3600))
        logger.info(f"选股池 RPS 已缓存：{len(order)} 只，TTL {RPS_CACHE_TTL_HOURS:.0f}h")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"选股池 RPS 写缓存失败（不影响本次）：{type(e).__name__}: {e}")


# ---------------------------------------------------------------- 单股场景
_RPS_CACHE: Dict[str, object] = {}


def rps_for_code(code: str, start: str, refresh: bool = False) -> Optional[pd.DataFrame]:
    """单只股票的 RPS 时序（**必须全市场横截面**算，故内部取全市场收盘价）。

    估值报告是逐股请求 —— 走 `load_rps_cached` 的**磁盘缓存**（TTL 默认 24h），
    进程内再加一层内存缓存。
    """
    code = str(code).zfill(6)

    rkey = f"rps::{start}"
    rps_map = _RPS_CACHE.get(rkey)
    if rps_map is None or refresh:
        rps_map = load_rps_cached(start, force=refresh)
        if rps_map is None:
            return None
        _RPS_CACHE[rkey] = rps_map

    cols = [c for c in ("rps50", "rps120", "rps250") if c in rps_map]
    if not cols or code not in rps_map[cols[0]].columns:
        return None
    out = pd.DataFrame({c: rps_map[c][code] for c in cols})
    out["date"] = rps_map[cols[0]].index
    return out.reset_index(drop=True)


def all_market_codes() -> List[str]:
    """stockdb 全市场证券代码（6 位数字），去重升序。

    ⚠️ `sdk.rd.get("股票代码")` 返回的 `QueryResult` **不是** dict（`.get` 是内置方法，
    会报 "Missing required parameters"），但 `repr()` 是标准 dict 字面量，
    且结果为**多个分片 key**（'0'/'1'/'3'/'5'/'6'…），必须合并全部 key。
    """
    import ast

    from ..data_fetchers.stockdb_data_fetcher import ensure_sdk

    sdk = ensure_sdk()
    q = sdk.rd.get("股票代码")

    data = None
    try:
        data = ast.literal_eval(repr(q))
    except (ValueError, SyntaxError):
        data = None
    if not isinstance(data, dict):
        logger.warning("stockdb 全市场代码解析失败（QueryResult 结构异常）")
        return []

    codes, seen = [], set()
    for part in data.values():
        if not isinstance(part, (list, tuple)):
            continue
        for c in part:
            s = str(c).strip()
            if len(s) == 6 and s.isdigit() and s not in seen:
                seen.add(s)
                codes.append(s)
    codes.sort()
    logger.info(f"stockdb 全市场代码：{len(codes)} 只")
    return codes


# ---------------------------------------------------------------- 展示助手
def fmt_rps(v: Optional[float]) -> str:
    """0~1 分位 → 通行的 0~100 显示（便于和通达信口径对照）。"""
    if v is None:
        return "-"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "-"
    if np.isnan(f):
        return "-"
    return f"{f * 100:.1f}"


def latest_rps(df: pd.DataFrame) -> Optional[Dict]:
    """单只股票最新一日的 RPS 读数（0~1）。"""
    if df is None or df.empty:
        return None
    last = df.iloc[-1]
    out = {c: (None if pd.isna(last.get(c)) else float(last.get(c)))
           for c in RPS_COLS}
    out["date"] = str(pd.Timestamp(last["date"]))[:10] if "date" in df.columns else ""
    out["eligible"] = bool(last.get("rps_eligible", False))
    return out
