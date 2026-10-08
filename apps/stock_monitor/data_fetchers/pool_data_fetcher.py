"""
股票池 / 指数成分股 — hs300 / zz500 等。

来源：akshare 两个**互补**接口
  * 中证/上证系（`000xxx` / `930xxx`）→ `index_stock_cons_csindex`（中证官网，权威，含名称+日期）
  * 深交所系（`399xxx`）              → `index_stock_cons_sina`（新浪，含名称）

  ⚠️ 不要用 `index_stock_cons`（新浪的另一个接口）：它含**完全重复**的行，
     去重后成员缺失（实测沪深300 缺 12、中证500 缺 71）。

缓存：成分股是低频数据（几天不更新不影响判断），写入 `cache.db` 的 `long_term_storage`
（`module_type="index_cons"`，稳定 key → 原地覆盖），新鲜期 `CONS_TTL`=3 天；
在线失败时回退旧记录并标注降级。**不再产生任何磁盘文件**。
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from config import setup_logger
from ..core.utils import is_fresh_meta

from ..core.cache_with_database import retrieve_long_term_data, store_long_term_data

logger = setup_logger(__name__)

# 池定义：key -> 纯指数代码（akshare 的这两个接口都收纯代码，不带 .SH/.SZ）
POOL_INDEX_SYMBOL = {
    "hs300": "000300",
    "zz500": "000905",
    "zz1000": "000852",
    "zz2000": "932000",
}
# 「优选池」= 多个指数成分的**并集**（沪深300 + 中证500 + 中证1000 + 中证2000）
POOL_UNION = {"union": ("000300", "000905", "000852", "932000")}
POOL_UNION_NAME = {"union": "优选池"}
# 下拉顺序：优选池置顶（默认）
POOL_NAME = {
    "union": "优选池（沪深300+中证500+中证1000+中证2000）",
    "hs300": "沪深300",
    "zz500": "中证500",
    "zz1000": "中证1000",
    "zz2000": "中证2000",
    "all": "全市场",
}
DEFAULT_POOL = "union"

# 全市场池的进程内缓存（低频数据；代码+名称）
_ALL_MARKET_CACHE: Dict[str, list] = {}
# 优选池（并集）的进程内缓存
_UNION_CACHE: Dict[str, list] = {}

CONS_TTL = 3 * 24 * 3600   # 成分股缓存新鲜期：3 天
MIN_POOL_ROWS = 100        # 完整性校验：有效成分少于该数视为源异常
_CONS_MODULE = "index_cons"

# index_code -> {"source": "online"/"cache"/"cache_stale", "fetched_at": ..., "error": ...}
_cons_source: Dict[str, dict] = {}


def _norm_code(c) -> str:
    """只保留数字并补足 6 位。"""
    return "".join(ch for ch in str(c) if ch.isdigit()).zfill(6)


def _valid_code(code: str) -> bool:
    return len(code) == 6 and code.isdigit() and code != "000000"


def _cons_key(index_code: str) -> str:
    """缓存 key —— 用**纯代码**归一，避免 `000300` 与 `000300.SH` 存两份。"""
    return f"index_cons_{_bare_code(index_code)}"


def index_cons_meta(index_code: str) -> dict:
    """最近一次 `get_index_constituents(index_code)` 的来源信息（供上层标注降级）。"""
    return dict(_cons_source.get(index_code) or {})


def _bare_code(index_code: str) -> str:
    """`000001.SH` / `399001.SZ` → 纯代码 `000001`。

    ⚠️ akshare 的 `index_stock_cons_csindex` / `index_stock_cons_sina`
    **只接受纯代码**；带 `.SH` 后缀会让 csindex 报
    "Excel file format cannot be determined"。
    """
    return str(index_code).split(".")[0].strip().zfill(6)


def _fetch_constituents_remote(index_code: str) -> List[Dict]:
    """用 akshare 拉指数成分（中证系走中证官网；深交所系走新浪）。返回 `[{code,name}]`。"""
    import akshare as ak

    bare = _bare_code(index_code)
    if bare.startswith("399"):
        df = ak.index_stock_cons_sina(symbol=bare)
        code_col, name_col = "code", "name"
    else:
        df = ak.index_stock_cons_csindex(symbol=bare)
        code_col, name_col = "成分券代码", "成分券名称"

    if df is None or df.empty:
        return []
    if code_col not in df.columns:
        raise RuntimeError(f"成分接口返回异常列：{list(df.columns)[:8]}")

    rows: List[Dict] = []
    seen = set()
    for _, r in df.iterrows():
        code = _norm_code(r.get(code_col))
        if not _valid_code(code) or code in seen:
            continue
        seen.add(code)
        rows.append({"code": code, "name": str(r.get(name_col) or "").strip()})
    return rows


def get_index_constituents(index_code: str, force: bool = False) -> List[Dict]:
    """指数成分股 `[{code, name}]`（带 `cache.db` 缓存 3 天；在线失败回退旧缓存）。"""
    key = _cons_key(index_code)

    if not force:
        rec = retrieve_long_term_data(key)
        if rec and rec.get("rows") and is_fresh_meta(rec, CONS_TTL):
            _cons_source[index_code] = {
                "source": "cache", "fetched_at": rec.get("fetched_at")}
            return rec["rows"]

    rows: List[Dict] = []
    err = None
    try:
        rows = _fetch_constituents_remote(index_code)
    except Exception as e:  # noqa: BLE001
        err = e

    if rows:
        at = datetime.now().isoformat(timespec="seconds")
        store_long_term_data(
            key,
            {"fetched_at": at, "index_code": index_code, "rows": rows},
            _CONS_MODULE,
        )
        _cons_source[index_code] = {"source": "online", "fetched_at": at}
        logger.info(f"指数成分({index_code}) -> {len(rows)} 只（在线）")
        return rows

    # 在线失败/为空 → 回退旧缓存（成分股是低频数据，过期几天不影响判断）
    stale = retrieve_long_term_data(key)
    if stale and stale.get("rows"):
        logger.warning(f"指数成分({index_code}) 在线获取失败，回退缓存：{err}")
        _cons_source[index_code] = {
            "source": "cache_stale",
            "fetched_at": stale.get("fetched_at"),
            "error": str(err) if err is not None else "返回为空",
        }
        return stale["rows"]

    if err is not None:
        raise RuntimeError(f"指数成分({index_code}) 获取失败且无缓存：{err}") from err
    raise RuntimeError(f"指数成分({index_code}) 返回为空且无缓存")


def load_pool(pool: str = DEFAULT_POOL, force: bool = False) -> List[Dict]:
    """返回池成分行 `[{code, name}]`。

    `pool="all"`   —— **全市场**（stockdb 全 A 代码 + 名称），不走指数成分接口。
    `pool="union"` —— **优选池**：多个指数成分的并集（300+500+1000 ≈ 1800 只）。
    """
    if pool == "all":
        return _load_all_market()

    if pool in POOL_UNION:
        return _load_union(pool, force=force)

    if pool not in POOL_INDEX_SYMBOL:
        raise ValueError(
            f"未知股票池 {pool}，可选: {list(POOL_INDEX_SYMBOL)} + {list(POOL_UNION)} + ['all']")

    rows = get_index_constituents(POOL_INDEX_SYMBOL[pool], force=force)
    if len(rows) < MIN_POOL_ROWS:
        raise RuntimeError(
            f"{pool} 成分不可用：有效 {len(rows)} 只（<{MIN_POOL_ROWS}），"
            f"请检查 akshare 成分接口是否正常")
    return rows


def _load_union(pool: str, force: bool = False) -> List[Dict]:
    """多个指数成分的**并集**（去重，保序：先出现的指数优先）。"""
    cache_key = f"union::{pool}"
    if not force and _UNION_CACHE.get(cache_key):
        return _UNION_CACHE[cache_key]

    seen: Dict[str, Dict] = {}
    for idx in POOL_UNION[pool]:
        for r in get_index_constituents(idx, force=force):
            seen.setdefault(r["code"], r)
    rows = list(seen.values())
    if len(rows) < MIN_POOL_ROWS:
        raise RuntimeError(f"{pool} 并集成分不足：{len(rows)} 只（<{MIN_POOL_ROWS}）")
    _UNION_CACHE[cache_key] = rows
    logger.info(f"优选池({pool}) -> {len(rows)} 只（{'+'.join(POOL_UNION[pool])}）")
    return rows


def _load_all_market() -> List[Dict]:
    """全市场 A 股 `[{code, name}]`（stockdb 代码 + 名称）。

    名称从日K 的 `name` 字段取（**分块请求**：一次几千只会把 stockdb 请求挂住）。
    股票池是**低频**数据，结果做进程内缓存，避免每次选股都打一遍 stockdb。
    """
    cached = _ALL_MARKET_CACHE.get("rows")
    if cached:
        return cached

    from ..analyzers.factor_rps import all_market_codes
    from .stockdb_data_fetcher import get_raw

    codes = all_market_codes()
    if not codes:
        raise RuntimeError("全市场代码为空 —— 请确认 stockdb 服务已启动")

    # 只取最近一小段（够拿 name 即可）+ **分块**，避免大请求挂死
    names: Dict[str, str] = {}
    chunk = 800
    for i in range(0, len(codes), chunk):
        part = codes[i:i + chunk]
        try:
            raw = get_raw(part, start=None, end=None, fq="qfq",
                          fields="code,name")
            if raw is not None and len(raw):
                df = raw.copy()
                df["code"] = df["code"].astype(str).str.zfill(6)
                names.update(df.dropna(subset=["name"]).groupby("code")["name"]
                             .last().astype(str).to_dict())
        except Exception as e:  # noqa: BLE001
            logger.warning(f"全市场名称分块 {i} 失败（继续）：{type(e).__name__}: {e}")

    rows = [{"code": c, "name": names.get(c, "")} for c in codes]
    _ALL_MARKET_CACHE["rows"] = rows
    logger.info(f"全市场池：{len(rows)} 只（有名称 {len(names)}）")
    return rows


def pool_codes(pool: str = DEFAULT_POOL, force: bool = False) -> List[str]:
    return [r["code"] for r in load_pool(pool, force=force)]
