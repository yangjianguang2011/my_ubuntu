# -*- coding: utf-8 -*-
"""单任务后台运行器的公共骨架。

系统中三个后台运行器（`analyzers/valuation_runner`、`analyzers/market_runner`、
`analyzers/picker_runner`）原先各自重复实现同一套模式：

    加锁 → 若已有任务在跑则直接返回当前状态 → 否则新建 daemon 线程 →
    try/except 记录错误 → finally 置 running=False 并写 finished_at

这里抽出两个小助手，保留各运行器自己的状态数据结构与业务语义：

  * `start_task(owner, make_status, target, args, name, can_reuse)`：
    统一「防重入 + 可选缓存复用 + 启动线程」。
  * `finish_task(status, error)`：统一收尾（错误记录 + running/finished_at）。
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable, Dict, Optional, Sequence


def start_task(owner, make_status: Callable[[], object], target: Callable,
               args: Sequence = (), name: str = "task",
               can_reuse: Optional[Callable[[], bool]] = None) -> Dict:
    """在 `owner._lock` 内启动后台任务。

    :param owner:      持有 `_lock` / `_thread` / `status` 的运行器实例
    :param make_status: 返回「初始状态对象」的无参函数（由调用方构造，字段各自定义）
    :param target:     线程目标函数
    :param args:       target 的位置参数
    :param name:       线程名（便于排查）
    :param can_reuse:  返回 True 表示可复用已有结果、不重启（如命中缓存）
    :return:           当前状态字典（`status.to_dict()`）
    """
    with owner._lock:
        if owner._thread and owner._thread.is_alive():
            return owner.status.to_dict()          # 已在跑 → 不重启
        if can_reuse is not None and can_reuse():
            return owner.status.to_dict()          # 命中缓存 → 直接返回
        owner.status = make_status()
        owner._thread = threading.Thread(
            target=target, args=tuple(args), daemon=True, name=name)
        owner._thread.start()
    return owner.status.to_dict()


def finish_task(status, error: Optional[BaseException] = None) -> None:
    """统一收尾：错误写入 status.error/message，置 running=False 并记 finished_at。"""
    if error is not None:
        status.error = str(error)
        status.message = f"失败: {error}"
    status.running = False
    status.finished_at = datetime.now().isoformat(timespec="seconds")
