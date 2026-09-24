"""
轻量因子注册表 — dict + dataclass。
因子模块底部显式 register(Factor(...))，engine 通过 all_factors() 遍历。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

PanelRowsFn = Optional[Callable[[dict], List[Tuple[str, str, str]]]]


@dataclass
class Factor:
    name: str
    title: str
    compute: Optional[Callable] = None
    latest: Optional[Callable] = None
    panel_rows: PanelRowsFn = None
    merge_cols: Tuple[str, ...] = ()
    is_base: bool = False
    panel: bool = True
    chart: bool = True


_REGISTRY: Dict[str, Factor] = {}
_ORDER: List[str] = []


def register(f: Factor) -> Factor:
    """幂等写入注册表（同 name 覆盖）。"""
    if f.name not in _REGISTRY:
        _ORDER.append(f.name)
    _REGISTRY[f.name] = f
    return f


def get_factor(name: str) -> Optional[Factor]:
    return _REGISTRY.get(name)


def all_factors() -> List[Factor]:
    """按注册顺序返回所有因子。"""
    return [_REGISTRY[n] for n in _ORDER]


def clear() -> None:
    _REGISTRY.clear()
    _ORDER.clear()
