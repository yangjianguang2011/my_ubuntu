# -*- coding: utf-8 -*-
"""公共工具集（供 stock_monitor 内部各子包共用）。

分两部分：

1. **通用工具**：纯 stdlib（数值安全 / 格式化 / 缓存新鲜度），供 data_fetchers、analyzers 使用。
2. **REST 助手**：参数校验 / 统一响应 / 异常包装，供各 Blueprint 共用。

（原 `apps/utils.py` 与 `core/api_utils.py` 已合并至此；对外统一 `stock_monitor.core.utils`。）
"""
from __future__ import annotations

import functools
from datetime import datetime
from numbers import Integral, Real
from typing import Any, Dict, Optional

from flask import jsonify, request

from config import setup_logger

logger = setup_logger(__name__)


# ================================================================ 通用工具
# ---------------------------------------------------------------- 缓存新鲜度

def is_fresh_meta(rec: Optional[Dict], ttl_seconds: int) -> bool:
    """判断带 `fetched_at` 的缓存记录是否在 TTL 内。

    记录来自 `cache.db` 的 `long_term_storage`（见 `core/cache_with_database.py`），
    结构形如 `{"fetched_at": "2026-09-24T10:00:00", ...}`。
    """
    if not rec or not rec.get("fetched_at"):
        return False
    try:
        t = datetime.fromisoformat(rec["fetched_at"])
    except (ValueError, TypeError):
        return False
    return (datetime.now() - t).total_seconds() < ttl_seconds


# ---------------------------------------------------------------- 数值安全

def safe_float(v: Any) -> Optional[float]:
    """None/NaN/不可转 -> None；否则 float。"""
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if x != x else x


# ---------------------------------------------------------------- 数值格式化

def clean_value(v: Any, nd_small: int = 4, nd_large: int = 2,
                threshold: float = 100.0) -> Any:
    """JSON 友好规整：None/NaN -> None；数字 -> 按量级 round；其它 -> str[:10]。"""
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    if isinstance(v, (Integral, Real)):
        x = float(v)
        return round(x, nd_small) if abs(x) < threshold else round(x, nd_large)
    s = str(v)
    return s[:10] if len(s) >= 10 else s


def fmt_num(v: Any, nd: int = 2, na: str = "-") -> str:
    """数值保留 nd 位；None/NaN/非数 -> na。"""
    if isinstance(v, (int, float)) and v == v:
        return f"{v:.{nd}f}"
    return na


def fmt_pct(v: Any, nd: int = 1, na: str = "-") -> str:
    """小数 -> '12.3%'；缺失 -> na。"""
    if isinstance(v, (int, float)) and v == v:
        return f"{v * 100:.{nd}f}%"
    return na


# ================================================================ REST API 助手
# 参数校验 / 统一响应 / 异常包装（供各 Blueprint 共用）。

class BadParam(ValueError):
    """请求参数非法（对应 HTTP 400）。"""


def int_arg(name: str, default=None, min_v: int = None, max_v: int = None) -> int:
    """读取并校验整数查询参数；缺失/非法/越界抛 `BadParam`。"""
    raw = request.args.get(name, default)
    if raw is None:
        raise BadParam(f"缺少参数 {name}")
    try:
        v = int(raw)
    except (TypeError, ValueError):
        raise BadParam(f"{name} 参数非法: {raw!r}") from None
    if min_v is not None and v < min_v:
        raise BadParam(f"{name} 过小（应 ≥{min_v}）: {v}")
    if max_v is not None and v > max_v:
        raise BadParam(f"{name} 过大（应 ≤{max_v}）: {v}")
    return v


def top_arg(name: str, default: int, all_value: int = 9999) -> int:
    """`top_*` 参数：'all' → all_value，否则整数校验。"""
    raw = request.args.get(name, str(default))
    if str(raw).lower() == "all":
        return all_value
    return int_arg(name, default, min_v=1, max_v=all_value)


def json_body() -> dict:
    """安全读取 JSON body（空/非 JSON → 空 dict，避免 500）。"""
    return request.get_json(silent=True) or {}


def ok(data=None, **extra):
    """成功响应：{success: true, data, **extra}。"""
    payload = {"success": True, "data": data}
    payload.update(extra)
    return jsonify(payload)


def err(msg: str, code: int = 500):
    """失败响应：({success: false, message}, code)。"""
    return jsonify({"success": False, "message": msg}), code


def api_guard(label: str):
    """统一异常处理：`BadParam` → 400，其余 → 500（并记日志）。"""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except BadParam as e:
                logger.warning(f"{label} 参数错误: {e}")
                return err(str(e), 400)
            except Exception as e:  # noqa: BLE001
                logger.error(f"{label}失败: {e}", exc_info=True)
                return err(f"{label}失败: {e}", 500)
        return wrapper
    return deco
