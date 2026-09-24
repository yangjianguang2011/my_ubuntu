# -*- coding: utf-8 -*-
"""
市场温度后台运行器 —— 单例，计算三大指数（上证综指/深证成指/创业板指）温度。

设计同 valuation_runner：daemon 线程 + 轮询。上证综指全市场（2189 只）冷算约需
1~3 分钟，结果进程内缓存，避免重复计算。
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
class MarketStatus:
    running: bool = False
    message: str = ""
    error: str = ""
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> Dict:
        return {
            "running": self.running,
            "message": self.message,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class MarketRunner:
    """进程内单例市场温度调度器。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self.status = MarketStatus()
        self._result: Optional[dict] = None

    # -- 对外接口 ---------------------------------------------------------- #
    def start(self, force: bool = False) -> Dict:
        """启动后台计算；若已在跑或已有缓存则返回当前状态（不重启）。"""
        def _make_status():
            return MarketStatus(
                running=True,
                started_at=datetime.now().isoformat(timespec="seconds"),
            )

        return start_task(
            self, _make_status, self._run, (force,),
            name="market_temperature",
            can_reuse=lambda: (not force and self._result is not None),
        )

    def status_dict(self) -> Dict:
        return self.status.to_dict()

    def get_result(self) -> Optional[dict]:
        return self._result

    # -- 内部 -------------------------------------------------------------- #
    def _run(self, force: bool):
        st = self.status
        try:
            st.message = "正在计算三大指数温度…（首次约需 1~3 分钟）"
            from .market_temperature import get_market_temperature_all

            result = get_market_temperature_all(force=force)
            self._result = result
            indices = result.get("indices", [])
            ok = [x for x in indices if not x.get("error")]
            if indices and not ok:
                # 全部失败：把首个原因（如 stockdb 不可达）报出来，避免"完成 0 个"式的假成功
                finish_task(st, indices[0].get("error") or "全部指数计算失败")
                return
            st.message = f"完成：{len(ok)}/{len(indices)} 个指数温度"
            degraded = [x for x in ok if x.get("degraded")]
            if degraded:
                st.message += f"（{len(degraded)} 个使用缓存）"
        except Exception as e:  # noqa: BLE001
            logger.error(f"市场温度计算失败: {e}", exc_info=True)
            finish_task(st, e)
            return
        finish_task(st)


# 模块级单例（Web 共用同一任务状态）
runner = MarketRunner()
