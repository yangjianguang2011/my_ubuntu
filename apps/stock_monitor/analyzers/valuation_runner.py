# -*- coding: utf-8 -*-
"""
估值报告后台运行器 —— 单例，同一时刻只运行一个报告任务。

设计同 `analyzers/picker_runner`：
  1. 单例 ValuationRunner + 线程锁，避免并发拉取打爆 stockdb/akshare。
  2. 报告在后台 daemon 线程计算，结果缓存在进程内，供 Web 轮询：
       POST /api/valuation/report/run   启动计算（body: {code, start?, force?}）
       GET  /api/valuation/report/status  查询进度
       GET  /api/valuation/report/<code>/data  取报告 JSON
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from config import setup_logger
from ..core.runner_base import finish_task, start_task

logger = setup_logger(__name__)


@dataclass
class ValuationStatus:
    running: bool = False
    code: str = ""
    name: str = ""
    message: str = ""
    error: str = ""
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> Dict:
        return {
            "running": self.running,
            "code": self.code,
            "name": self.name,
            "message": self.message,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class ValuationRunner:
    """进程内单例估值报告调度器。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self.status = ValuationStatus()
        self._result: Optional[dict] = None
        self._result_code: str = ""

    # -- 对外接口 ---------------------------------------------------------- #
    def start(self, code: str, start: Optional[str] = None, force: bool = False) -> Dict:
        """启动后台报告计算；若已在跑则返回当前状态（不重启）。"""
        code = (code or "").strip()

        def _make_status():
            return ValuationStatus(
                running=True, code=code,
                started_at=datetime.now().isoformat(timespec="seconds"),
            )

        return start_task(
            self, _make_status, self._run, (code, start),
            name="valuation_report",
            can_reuse=lambda: (not force and self._result_code == code
                               and self._result is not None),
        )

    def status_dict(self) -> Dict:
        return self.status.to_dict()

    def get_result(self, code: str) -> Optional[dict]:
        code = (code or "").strip()
        return self._result if self._result_code == code else None

    # -- 内部 -------------------------------------------------------------- #
    def _run(self, code: str, start: Optional[str]):
        st = self.status
        try:
            st.message = "正在拉取日K数据…"
            from .valuation_engine import run_valuation

            result = run_valuation(code, start=start)
            self._result = result
            self._result_code = code
            st.name = result.get("meta", {}).get("name", "")
            rows = result.get("chart", {}).get("dates", [])
            st.message = f"完成：{st.name or code}（{len(rows)} 行时序）"
        except Exception as e:  # noqa: BLE001
            logger.error(f"估值报告({code}) 计算失败: {e}", exc_info=True)
            finish_task(st, e)
            return
        finish_task(st)


# 模块级单例（Web 共用同一任务状态）
runner = ValuationRunner()
