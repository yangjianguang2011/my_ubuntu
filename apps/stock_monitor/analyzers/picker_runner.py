# -*- coding: utf-8 -*-
"""
选股批量编排 —— 股票池 → 一次批量取日线 → 逐只判定 → 结果快照。

设计：
  1. 单例 `ScreenRunner`：同一时刻只允许一个扫描任务（`_lock`），避免多线程打爆外部行情源。
  2. 扫描在后台 daemon 线程执行，进度/中间结果通过 job 对象共享，供 Web 轮询：
       GET /api/picker/status  →  {running, pool, done, total, matched, partial, progress_pct}
  3. 数据来源（原实现在 `stock_picker/`，已废弃）：
       * 成分股 → `data_fetchers.pool_data_fetcher.load_pool`（akshare + cache.db）
       * 日线   → `data_fetchers.stockdb_data_fetcher.get_raw`（stockdb **本地库**，
                  500 只**一次批量**，替代原「akshare 逐只拉 300~500 次 + 自建 sqlite 缓存」）
  4. 每次跑完追加一份结果快照到 `cache.db` 的 `long_term_storage`
     （`module_type="picker_run"`，key = `picker_run_<时间戳>`），供"我的选股历史"回看；
     只保留最近 `SNAPSHOT_KEEP` 份。**不落任何磁盘文件。**
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from config import setup_logger

from ..core.cache_with_database import (
    delete_long_term_data,
    get_module_long_term_data,
    retrieve_long_term_data,
    store_long_term_data,
)
from ..core.runner_base import finish_task, start_task
from ..data_fetchers.pool_data_fetcher import POOL_NAME, load_pool
from ..data_fetchers.stockdb_data_fetcher import get_raw
from .picker_rules import Params, evaluate_all

logger = setup_logger(__name__)

SNAPSHOT_KEEP = 50                      # 历史快照最多保留份数
_RUN_MODULE = "picker_run"
# 批量取日线所需字段（够算 MA/量能即可）
_KLINE_FIELDS = "date,code,open,high,low,close,volume"


@dataclass
class ScreenStatus:
    running: bool = False
    pool: Optional[str] = None
    pool_label: str = ""
    total: int = 0
    done: int = 0
    matched: List[dict] = field(default_factory=list)  # 完整命中：含 reasons
    partial: List[dict] = field(default_factory=list)  # 分规则命中(观察)
    failed: int = 0
    message: str = ""
    error: str = ""
    run_id: Optional[str] = None
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> Dict:
        return {
            "running": self.running,
            "pool": self.pool,
            "pool_label": self.pool_label,
            "total": self.total,
            "done": self.done,
            "progress_pct": round(self.done / self.total * 100, 1) if self.total else 0,
            "matched": self.matched,
            "partial": self.partial,
            "failed": self.failed,
            "message": self.message,
            "error": self.error,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class ScreenRunner:
    """进程内单例扫描任务调度器。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.status = ScreenStatus()

    # -- 对外接口 ---------------------------------------------------------- #
    def start(self, params_dict: Optional[dict] = None, pool: str = "hs300",
              force_refresh: bool = False):
        """立即跑一次后台扫描；若已在跑则返回当前状态(不重启)。

        `pool` / `params` 非法会**同步抛 `ValueError`**（供 Web 层返回 400）。
        """
        params = Params.from_dict(params_dict or {})
        if pool not in POOL_NAME:
            raise ValueError(f"未知的股票池: {pool}，可选: {list(POOL_NAME)}")

        def _make_status():
            st = ScreenStatus(running=True, pool=pool,
                              pool_label=POOL_NAME.get(pool, pool))
            st.started_at = datetime.now().isoformat(timespec="seconds")
            return st

        return start_task(
            self, _make_status, self._run_sync, (params, pool, force_refresh),
            name="picker_scan",
        )

    def stop(self):
        self._stop.set()

    def status_dict(self) -> Dict:
        return self.status.to_dict()

    # -- 内部 -------------------------------------------------------------- #
    def _run_sync(self, params: Params, pool_key: str, force_refresh: bool):
        self._stop.clear()
        st = self.status
        try:
            constituents = load_pool(pool_key, force=force_refresh)
            st.total = len(constituents)
            if not constituents:
                finish_task(st, RuntimeError("获取成分股为空，扫描未开始"))
                return

            names = {r["code"]: r.get("name", "") for r in constituents}
            codes = list(names)
            st.message = f"批量拉取 {len(codes)} 只日线…"

            df = self._fetch_kline(codes, self._wanted(params))
            if df is None or df.empty:
                finish_task(st, RuntimeError("批量日线为空，扫描未开始"))
                return

            groups = {c: g for c, g in df.groupby("code")}
            st.matched, st.partial = [], []
            for i, code in enumerate(codes):
                if self._stop.is_set():
                    st.message = "已手动停止"
                    break
                st.done = i + 1
                g = groups.get(code)
                if g is None or g.empty:
                    st.failed += 1
                    continue
                try:
                    result = evaluate_all(g.to_dict("records"), params)
                except Exception as e:  # noqa: BLE001
                    logger.error(f"判定失败 {names.get(code, '')}({code}): {e}")
                    st.failed += 1
                    continue

                summary = {"code": code, "name": names.get(code, ""),
                           **compact_latest(g)}
                if result["passed"]:
                    summary["reasons"] = result["reasons"]
                    st.matched.append(summary)
                else:
                    # partial：有一项命中(任意 reason passed) 供观察
                    on = [r for r in result["reasons"] if r["passed"]]
                    if on:
                        summary["hit_rules"] = [r["rule_id"] for r in on]
                        st.partial.append(summary)
                if i % 20 == 0:
                    st.message = f"扫描 {st.done}/{st.total}…命中 {len(st.matched)}"

            st.run_id = self._persist_snapshot(
                pool_key, params, st.matched, st.total, st.failed)
            st.message = f"完成：命中 {len(st.matched)} / 扫描 {st.done}"
            finish_task(st)
        except Exception as e:  # noqa: BLE001
            logger.error(f"扫描异常: {e}", exc_info=True)
            finish_task(st, e)

    @staticmethod
    def _wanted(params: Params) -> int:
        """需要的交易日根数：ma_slow 有足够非空连续 + 余量。"""
        return params.ma_slow + 70

    @staticmethod
    def _fetch_kline(codes: List[str], wanted: int) -> Optional[pd.DataFrame]:
        """一次批量取日线（stockdb 本地库），返回按 (code, date) 升序的 DataFrame。"""
        natural = int(wanted * 7 / 5) + 60      # 交易日 -> 自然日，再留停牌/节假日余量
        start = (pd.Timestamp.now() - pd.Timedelta(days=natural)).strftime("%Y%m%d")
        raw = get_raw(codes, start=start, end=None, fq="qfq", fields=_KLINE_FIELDS)
        if raw is None or len(raw) == 0:
            return None
        df = raw.copy()
        # stockdb 的 date 是 int(YYYYMMDD) -> datetime；数值列转 float
        df["date"] = pd.to_datetime(df["date"].astype("int64").astype(str), format="%Y%m%d")
        for c in ("open", "high", "low", "close", "volume"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.sort_values(["code", "date"]).reset_index(drop=True)

    def _persist_snapshot(self, pool_key, params, matched, scanned, failed) -> Optional[str]:
        """把本次结果写入 `long_term_storage`；返回快照 key。"""
        try:
            created_at = datetime.now().isoformat(timespec="seconds")
            key = f"{_RUN_MODULE}_{created_at.replace(':', '').replace('-', '')}"
            store_long_term_data(
                key,
                {
                    "pool": pool_key,
                    "pool_label": POOL_NAME.get(pool_key, pool_key),
                    "params": params.to_dict(),
                    "matched": matched,
                    "scanned": scanned,
                    "failed": failed,
                    "matched_count": len(matched),
                    "created_at": created_at,
                },
                _RUN_MODULE,
            )
            self._trim_snapshots()
            return key
        except Exception as e:  # noqa: BLE001
            logger.error(f"快照保存失败: {e}")
            return None

    @staticmethod
    def _trim_snapshots(keep: int = SNAPSHOT_KEEP) -> None:
        """只保留最近 keep 份快照。"""
        try:
            rows = get_module_long_term_data(_RUN_MODULE)
            for r in rows[keep:]:
                delete_long_term_data(r["key"])
        except Exception as e:  # noqa: BLE001
            logger.warning(f"快照清理失败: {e}")


# 模块级单例（Web/脚本共用同一任务状态）
runner = ScreenRunner()


def compact_latest(g: pd.DataFrame) -> Dict:
    """从日线里凝练 '现价/最近日期/涨跌' 便于列表展示（不额外调行情接口）。"""
    if g is None or len(g) == 0:
        return {}
    last = g.iloc[-1]
    out: Dict = {"as_of": str(pd.Timestamp(last["date"]))[:10]}
    close = last.get("close")
    if close is not None and close == close:
        out["price"] = round(float(close), 2)
    vol = last.get("volume")
    if vol is not None and vol == vol:
        out["volume"] = float(vol)
    # 向前一根收盘估算当日涨跌幅
    if close is not None and close == close and len(g) >= 2:
        prev = g.iloc[-2].get("close")
        if prev is not None and prev == prev and float(prev):
            out["change_pct"] = round((float(close) - float(prev)) / float(prev) * 100, 2)
    return out


def list_snapshots(limit: int = 20) -> List[dict]:
    """查询历史扫描快照（供"我的观察历史"）。"""
    rows = get_module_long_term_data(_RUN_MODULE, limit=limit)
    out = []
    for r in rows:
        d = r.get("data") or {}
        out.append({
            "run_id": r["key"],
            "pool": d.get("pool"),
            "pool_label": d.get("pool_label"),
            "scanned": d.get("scanned"),
            "matched_count": d.get("matched_count"),
            "failed": d.get("failed"),
            "created_at": d.get("created_at") or r.get("updated_at"),
            "params": d.get("params") or {},
        })
    return out


def get_snapshot(run_id: str) -> Optional[dict]:
    d = retrieve_long_term_data(run_id)
    if not d:
        return None
    return {"run_id": run_id, **d}
