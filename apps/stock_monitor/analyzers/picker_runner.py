# -*- coding: utf-8 -*-
"""
选股批量编排 —— 股票池 → **技术面粗筛 → 估值面精筛** → 结果快照。

设计（「灵活融合」的编排侧）：
  1. **条件清单驱动**：启用的条件来自 `analyzers/conditions.py` 的注册表，
     本模块**不写死任何条件**；加条件只需注册。
  2. **分层（性能关键）**：
       ① 池 → 批量取日K（1 次）→ 算均线 → 评估**技术面**条件
       ② 只对通过 ① 的（预计 300 → 30~80 只）→ 取估值读数 → 评估**估值面**条件
     估值读数走 `valuation_engine.compute_readings`（轻量、按天缓存）；
     `need_ps=False` 时**不拉营业收入**，全池约 31s（hs300 实测）。
  3. 单例 `ScreenRunner`：同一时刻只允许一个扫描任务。
  4. 每次跑完把「条件清单 + 参数 + 结果」存 `cache.db` 的 `long_term_storage`
     （`module_type="picker_run"`），只保留最近 `SNAPSHOT_KEEP` 份。
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

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
from .conditions import (
    GROUP_STRATEGY,
    GROUP_TECH,
    GLOBAL_PARAMS,
    all_conditions,
    get_condition,
    normalize_params,
)
from .ma_indicators import add_ma

logger = setup_logger(__name__)

SNAPSHOT_KEEP = 50                      # 历史快照最多保留份数
_RUN_MODULE = "picker_run"
_KLINE_FIELDS = "date,code,open,high,low,close,volume"
# 技术面尾部窗口的固定余量（斜率/乖离/回踩/量能等窗口都很小，70 足够）
_TAIL_BUFFER = 70


@dataclass
class ScreenStatus:
    running: bool = False
    pool: Optional[str] = None
    pool_label: str = ""
    total: int = 0
    done: int = 0
    matched: List[dict] = field(default_factory=list)
    partial: List[dict] = field(default_factory=list)
    failed: int = 0
    message: str = ""
    error: str = ""
    run_id: Optional[str] = None
    started_at: str = ""
    finished_at: str = ""
    # —— 融合相关 ——
    stage: str = ""                       # 当前阶段（技术面粗筛 / 估值面精筛 / 完成）
    conditions: List[str] = field(default_factory=list)   # 本次启用的条件 id
    tech_passed: int = 0                  # 通过技术面的只数（= 估值精筛的输入）
    val_scanned: int = 0                  # 实际算了估值的只数
    # —— 阶段进度：`done`/`stage_total` 描述**当前阶段**，与池大小 `total` 分离，
    #    避免「估值精筛 27 只却按 300 算百分比」导致进度条倒退。
    stage_total: int = 0

    def to_dict(self) -> Dict:
        return {
            "running": self.running, "pool": self.pool, "pool_label": self.pool_label,
            "total": self.total,                     # 池大小
            "done": self.done,                       # 当前阶段已完成
            "stage_total": self.stage_total or self.total,
            "progress_pct": (round(self.done / (self.stage_total or self.total) * 100, 1)
                             if (self.stage_total or self.total) else 0),
            "matched": self.matched, "partial": self.partial, "failed": self.failed,
            "message": self.message, "error": self.error, "run_id": self.run_id,
            "started_at": self.started_at, "finished_at": self.finished_at,
            "stage": self.stage, "conditions": self.conditions,
            "tech_passed": self.tech_passed, "val_scanned": self.val_scanned,
        }


class ScreenRunner:
    """进程内单例扫描任务调度器。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.status = ScreenStatus()

    # -- 对外接口 ---------------------------------------------------------- #
    def start(self, conditions: Optional[dict] = None,
              global_params: Optional[dict] = None,
              legacy_params: Optional[dict] = None,
              pool: str = "union", force_refresh: bool = False):
        """启动扫描。`pool`/参数非法会**同步抛 ValueError**（供 Web 层返回 400）。

        `conditions`：`{cid: {"enabled": bool, "params": {...}}}`；
        未给 `conditions` 而给了 `legacy_params`（旧格式）时，映射为原有 4 条件。
        """
        if pool not in POOL_NAME:
            raise ValueError(f"未知的股票池: {pool}，可选: {list(POOL_NAME)}")

        plan = build_plan(conditions, global_params, legacy_params)
        if not plan["enabled"]:
            raise ValueError("至少需要启用一个条件")

        def _make_status():
            st = ScreenStatus(running=True, pool=pool, pool_label=POOL_NAME.get(pool, pool))
            st.started_at = datetime.now().isoformat(timespec="seconds")
            st.conditions = [c.id for c, _ in plan["enabled"]]
            st.stage = "准备中"
            return st

        return start_task(
            self, _make_status, self._run_sync, (plan, pool, force_refresh),
            name="picker_scan",
        )

    def stop(self):
        self._stop.set()

    def status_dict(self) -> Dict:
        return self.status.to_dict()

    # -- 内部 -------------------------------------------------------------- #
    def _run_sync(self, plan: dict, pool_key: str, force_refresh: bool):
        self._stop.clear()
        st = self.status
        try:
            constituents = load_pool(pool_key, force=force_refresh)
            st.total = len(constituents)
            if not constituents:
                finish_task(st, RuntimeError("获取成分股为空，扫描未开始"))
                return
            if len(constituents) > 3000:
                st.message = (f"注意：全市场池 {len(constituents)} 只，"
                              "逐股扫描会比较久（技术面约几分钟）")

            names = {r["code"]: r.get("name", "") for r in constituents}
            codes = list(names)
            tech_conds = [(c, p) for c, p in plan["enabled"] if c.group == GROUP_TECH]
            strat_conds = [(c, p) for c, p in plan["enabled"]
                           if c.group == GROUP_STRATEGY]
            val_conds = [(c, p) for c, p in plan["enabled"]
                         if c.group not in (GROUP_TECH, GROUP_STRATEGY)]

            # ---------- ⓪ RPS 底座（仅当勾了「策略信号」条件才算）----------
            rps_map: Dict[str, pd.DataFrame] = {}
            if strat_conds:
                rps_map = self._build_rps(codes, plan["wanted"], st)
                if not rps_map:
                    st.message = "RPS 计算失败，策略信号条件无法评估"

            # ---------- ① 技术面粗筛 ----------
            st.stage = f"技术面粗筛（{len(codes)} 只）"
            st.stage_total = len(codes)
            st.message = f"批量拉取 {len(codes)} 只日线…"
            df = self._fetch_kline(codes, plan["wanted"])
            if df is None or df.empty:
                finish_task(st, RuntimeError("批量日线为空，扫描未开始"))
                return

            groups = {c: g for c, g in df.groupby("code")}
            ma_windows = sorted({plan["global"]["ma_fast"], plan["global"]["ma_mid"],
                                 plan["global"]["ma_slow"]})
            ma_needs = max(ma_windows)
            # 策略信号（月线反转）需要 ≥250 根才能算 MA200/250，故抬高最低根数要求
            if strat_conds:
                ma_needs = max(ma_needs, 251)

            tech_ok: List[Tuple[str, dict, List[dict]]] = []   # (code, frame, reasons)
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
                    frame = add_ma(g, ma_windows)
                except Exception as e:  # noqa: BLE001
                    logger.error(f"均线计算失败 {names.get(code, '')}({code}): {e}")
                    st.failed += 1
                    continue

                ctx_extra = {"code": code, "rps": rps_map}
                reasons, passed = self._eval(frame, tech_conds, ma_needs, {},
                                             extra=ctx_extra)
                if passed:
                    tech_ok.append((code, frame, reasons))
                else:
                    summary = {"code": code, "name": names.get(code, ""),
                               **compact_latest(frame)}
                    on = [r["rule_id"] for r in reasons if r["passed"]]
                    if on:
                        summary["hit_rules"] = on
                        summary["reasons"] = reasons
                        st.partial.append(summary)
                if i % 20 == 0:
                    st.message = f"技术面粗筛 {st.done}/{st.stage_total}…通过 {len(tech_ok)}"

            st.tech_passed = len(tech_ok)
            st.message = f"技术面通过 {len(tech_ok)} 只"
            logger.info(f"技术面粗筛完成：{st.total} → {len(tech_ok)} 只")

            # ---------- ② 策略信号（在通过技术面的样本上；不需要估值数据）----------
            # 说明：策略信号 + 估值面是**同一套筛选链**，都只对"上一阶段幸存者"评估
            #       （旧实现把两者并列且各自 append，导致重复计数 + "只勾策略"时全过）
            survivors: List[Tuple[str, dict, List[dict]]] = tech_ok
            if strat_conds:
                st.stage = f"策略信号（{len(survivors)} 只）"
                st.stage_total = len(survivors)
                passed_list: List[Tuple[str, dict, List[dict]]] = []
                for j, (code, frame, reasons) in enumerate(survivors):
                    if self._stop.is_set():
                        st.message = "已手动停止"
                        break
                    st.done = j + 1
                    r2, ok = self._eval(frame, strat_conds, ma_needs, {},
                                        extra={"code": code, "rps": rps_map})
                    reasons = reasons + r2
                    summary = {"code": code, "name": names.get(code, ""),
                               **compact_latest(frame)}
                    if ok:
                        passed_list.append((code, frame, reasons))
                    else:
                        on = [r["rule_id"] for r in reasons if r["passed"]]
                        if on:
                            summary["hit_rules"] = on
                            summary["reasons"] = reasons
                            st.partial.append(summary)
                    if j % 5 == 0:
                        st.message = (f"策略信号 {st.done}/{st.stage_total}"
                                      f"…通过 {len(passed_list)}")
                survivors = passed_list
                st.message = f"策略信号通过 {len(survivors)} 只"
                logger.info(f"策略信号筛选完成：{len(tech_ok)} → {len(survivors)} 只")

            # ---------- ③ 估值面精筛（按需，只对上一阶段幸存者）----------
            if val_conds and survivors:
                from .valuation_engine import compute_readings

                need_ps = any("ps" in c.needs for c, _ in val_conds)
                st.stage = f"估值面精筛（{len(survivors)} 只{'，含营收' if need_ps else ''}）"
                st.stage_total = len(survivors)
                for j, (code, frame, reasons) in enumerate(survivors):
                    if self._stop.is_set():
                        st.message = "已手动停止"
                        break
                    st.done = j + 1
                    st.val_scanned += 1
                    try:
                        readings = compute_readings(code, need_ps=need_ps)
                    except Exception as e:  # noqa: BLE001
                        logger.warning(f"估值读数失败 {code}: {type(e).__name__}: {e}")
                        readings = None
                    r2, passed = self._eval(frame, val_conds, ma_needs, readings or {},
                                            extra={"code": code, "rps": rps_map})
                    reasons = reasons + r2
                    summary = {"code": code, "name": names.get(code, ""),
                               **compact_latest(frame)}
                    if passed:
                        summary["reasons"] = reasons
                        st.matched.append(summary)
                    else:
                        on = [r["rule_id"] for r in reasons if r["passed"]]
                        if on:
                            summary["hit_rules"] = on
                            summary["reasons"] = reasons
                            st.partial.append(summary)
                    if j % 5 == 0:
                        st.message = f"估值精筛 {st.done}/{st.stage_total}…命中 {len(st.matched)}"
            elif val_conds:
                # 勾了估值条件但上一阶段已无幸存者 → 没有粗筛依据时走全池精算
                from .valuation_engine import compute_readings

                need_ps = any("ps" in c.needs for c, _ in val_conds)
                st.stage = f"估值精筛·全池（{len(codes)} 只{'，含营收' if need_ps else ''}）"
                st.stage_total = len(codes)
                for j, code in enumerate(codes):
                    if self._stop.is_set():
                        break
                    st.done = j + 1
                    st.val_scanned += 1
                    g = groups.get(code)
                    if g is None or g.empty:
                        st.failed += 1
                        continue
                    frame = add_ma(g, ma_windows)
                    try:
                        readings = compute_readings(code, need_ps=need_ps)
                    except Exception as e:  # noqa: BLE001
                        logger.warning(f"估值读数失败 {code}: {type(e).__name__}: {e}")
                        readings = None
                    reasons, passed = self._eval(frame, val_conds, ma_needs,
                                                 readings or {},
                                                 extra={"code": code, "rps": rps_map})
                    summary = {"code": code, "name": names.get(code, ""),
                               **compact_latest(frame)}
                    if passed:
                        summary["reasons"] = reasons
                        st.matched.append(summary)
                    else:
                        on = [r["rule_id"] for r in reasons if r["passed"]]
                        if on:
                            summary["hit_rules"] = on
                            summary["reasons"] = reasons
                            st.partial.append(summary)
                    if j % 5 == 0:
                        st.message = f"估值精筛 {st.done}/{st.stage_total}…命中 {len(st.matched)}"
            elif survivors:
                # 只勾技术面 / 策略信号：幸存者即命中
                for code, frame, reasons in survivors:
                    summary = {"code": code, "name": names.get(code, ""),
                               **compact_latest(frame), "reasons": reasons}
                    st.matched.append(summary)

            st.stage = "完成"
            # 结果按**股票代码升序**排列（便于对照观察；实时与历史快照都生效）
            _by_code = lambda m: str(m.get("code") or "")
            st.matched.sort(key=_by_code)
            st.partial.sort(key=_by_code)

            st.run_id = self._persist_snapshot(plan, pool_key, st.matched, st.total, st.failed)
            st.message = (
                f"完成：命中 {len(st.matched)}"
                + (f"（技术面通过 {st.tech_passed} / 池 {st.total}）" if st.tech_passed
                   else f"（池 {st.total}）")
            )
            finish_task(st)
        except Exception as e:  # noqa: BLE001
            logger.error(f"扫描异常: {e}", exc_info=True)
            finish_task(st, e)

    @staticmethod
    def _eval(frame, conds, ma_needs: int, readings: dict, extra: dict = None):
        """评估一组条件（纯函数）。返回 (reasons, 全部通过)。"""
        if not conds:
            return [], True
        if frame is None or len(frame) < ma_needs:
            return [{"rule_id": "data", "passed": False,
                     "note": f"交易日({0 if frame is None else len(frame)})不足计算 {ma_needs} 日均线",
                     "metrics": {"bars": 0 if frame is None else len(frame), "need": ma_needs}}], False
        ctx = {"frame": frame, "readings": readings}
        if extra:
            ctx.update(extra)
        reasons, passed = [], True
        for c, prepared in conds:
            try:
                r = c.evaluate(ctx, prepared)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"条件 {c.id} 评估异常: {type(e).__name__}: {e}")
                r = {"passed": False, "note": f"评估异常：{type(e).__name__}", "metrics": {}}
            reasons.append({"rule_id": c.id, "passed": bool(r.get("passed")),
                            "note": r.get("note", ""), "metrics": r.get("metrics", {})})
            passed = passed and bool(r.get("passed"))
        return reasons, passed

    @staticmethod
    def _build_rps(codes: List[str], wanted: int, st) -> Dict[str, pd.DataFrame]:
        """横截面 RPS 预计算：{code: 单只 RPS DataFrame}。

        RPS 必须**全市场**算（否则排名失真），故这里按池代码**批量取数后再横截面排名**；
        为控制耗时，窗口只取策略信号需要的 50/120/250，起点按 `wanted` 反推。
        结果写 `cache.db`（TTL 见 `factor_rps.RPS_CACHE_TTL_HOURS`），下次命中即秒回。
        """
        from .factor_rps import (RpsParams, compute_rps,
                                 load_picker_rps_cached, store_picker_rps_cached)

        try:
            st.message = f"计算 RPS 相对强度（{len(codes)} 只，横截面）…"
            natural = int(max(wanted, 300) * 7 / 5) + 120
            start = (pd.Timestamp.now() - pd.Timedelta(days=natural)).strftime("%Y%m%d")

            # ① 先查磁盘缓存（按"池指纹 + 起点"为 key）
            hit = load_picker_rps_cached(codes, start)
            if hit:
                st.message = "RPS 命中缓存"
                logger.info(f"RPS 命中磁盘缓存：{len(hit)} 只")
                return hit

            # ② 未命中 → 池内批量取数 + 横截面排名
            raw = get_raw(codes, start=start, end=None, fq="qfq",
                          fields="date,code,close,volume")
            if raw is None or len(raw) == 0:
                return {}
            raw = raw.copy()
            raw["date"] = pd.to_datetime(raw["date"].astype("int64").astype(str),
                                         format="%Y%m%d")
            raw["code"] = raw["code"].astype(str).str.zfill(6)
            close = raw.pivot_table(index="date", columns="code",
                                    values="close").sort_index()
            vol = raw.pivot_table(index="date", columns="code",
                                  values="volume").sort_index()
            res = compute_rps(close, RpsParams(), volume=vol)
            cols = ("rps50", "rps120", "rps250")
            out: Dict[str, pd.DataFrame] = {}
            for code in close.columns:
                part = pd.DataFrame({c: res[c][code] for c in cols})
                part["date"] = close.index
                out[code] = part.reset_index(drop=True)
            store_picker_rps_cached(codes, start, out)
            logger.info(f"RPS 预计算完成：{len(out)} 只")
            return out
        except Exception as e:  # noqa: BLE001
            logger.warning(f"RPS 预计算失败：{type(e).__name__}: {e}")
            return {}

    @staticmethod
    def _fetch_kline(codes: List[str], wanted: int) -> Optional[pd.DataFrame]:
        """一次批量取日线（stockdb 本地库），返回按 (code, date) 升序的 DataFrame。"""
        natural = int(wanted * 7 / 5) + 60
        start = (pd.Timestamp.now() - pd.Timedelta(days=natural)).strftime("%Y%m%d")
        raw = get_raw(codes, start=start, end=None, fq="qfq", fields=_KLINE_FIELDS)
        if raw is None or len(raw) == 0:
            return None
        df = raw.copy()
        df["date"] = pd.to_datetime(df["date"].astype("int64").astype(str), format="%Y%m%d")
        for c in ("open", "high", "low", "close", "volume"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.sort_values(["code", "date"]).reset_index(drop=True)

    def _persist_snapshot(self, plan, pool_key, matched, scanned, failed) -> Optional[str]:
        """把本次「条件清单 + 参数 + 结果」写入 `long_term_storage`；返回快照 key。"""
        try:
            created_at = datetime.now().isoformat(timespec="seconds")
            key = f"{_RUN_MODULE}_{created_at.replace(':', '').replace('-', '')}"
            store_long_term_data(
                key,
                {
                    "pool": pool_key,
                    "pool_label": POOL_NAME.get(pool_key, pool_key),
                    "global_params": plan["global"],
                    "conditions": {c.id: {"params": _dump_params(c, p)}
                                   for c, p in plan["enabled"]},
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
        try:
            rows = get_module_long_term_data(_RUN_MODULE)
            for r in rows[keep:]:
                delete_long_term_data(r["key"])
        except Exception as e:  # noqa: BLE001
            logger.warning(f"快照清理失败: {e}")


# 模块级单例（Web/脚本共用同一任务状态）
runner = ScreenRunner()


# ---------------------------------------------------------------- 编排计划
def _dump_params(c, prepared) -> dict:
    """把条件的预生成对象还原成可 JSON 存的参数 dict。"""
    if isinstance(prepared, dict):
        return {k: v for k, v in prepared.items()}
    # picker_rules.Params：只存该条件自己声明的字段
    return {k: getattr(prepared, k, None) for k in (c.params or {})}


def _wanted(plan: dict) -> int:
    """本次需要的交易日根数 = 最大均线 + 余量。

    关键：**金叉条件声明的回溯窗口必须真的可观测** —— ma_slow 预热会吃掉
    `ma_slow-1` 根，故需 `ma_slow + cross_lookback_bars` 才有足够"有效行"。
    （原实现固定 `ma_slow + 70`，导致 120 根的回溯实际只能看到约 70 根。）
    """
    ma_max = max(plan["global"]["ma_fast"], plan["global"]["ma_mid"], plan["global"]["ma_slow"])
    extra = _TAIL_BUFFER
    for c, prepared in plan["enabled"]:
        if c.id == "golden_cross":
            lb = getattr(prepared, "cross_lookback_bars", 0) or 0
            extra = max(extra, int(lb) + 10)
    return ma_max + extra


def build_plan(conditions: Optional[dict], global_params: Optional[dict],
               legacy_params: Optional[dict] = None) -> dict:
    """把前端下发的「条件清单 + 全局参数」校验并预生成成执行计划。

    * `conditions` 缺省而 `legacy_params` 存在 → 映射为原有 4 条件（向后兼容）
    * 旧格式的 `legacy_params` 里**也含全局均线参数**（ma_fast/ma_mid/ma_slow），
      需一并路由到全局参数，否则会被静默忽略（且失去范围校验）。
    """
    merged_global = dict(global_params or {})
    if legacy_params:
        for k in GLOBAL_PARAMS:
            if k in legacy_params and k not in merged_global:
                merged_global[k] = legacy_params[k]
    gp = normalize_params(GLOBAL_PARAMS, merged_global)

    if not conditions and legacy_params is not None:
        # 旧格式：{ma_fast, ..., use_volume_shrink} → 原 4 条件
        # 注：`legacy_params` 可能是**空 dict**（旧前端默认全用默认值），也要走这条映射，
        #     故用 `is not None` 而非真值判断。
        conditions = {
            "structure": {"enabled": True, "params": {
                k: legacy_params[k] for k in
                ("min_price_above_slow_ratio", "fast_slope_min_pct", "structure_slope_window")
                if k in legacy_params}},
            "golden_cross": {"enabled": True, "params": {
                k: legacy_params[k] for k in
                ("cross_lookback_bars", "cross_min_bars_since", "cross_max_bars_since")
                if k in legacy_params}},
            "pullback": {"enabled": True, "params": {
                k: legacy_params[k] for k in
                ("pullback_min_dist_pct", "pullback_max_dist_pct", "pullback_confirm_window",
                 "pullback_low_touch_below_pct", "pullback_low_touch_above_pct",
                 "mid_break_tolerance_pct", "allow_close_break_mid")
                if k in legacy_params}},
            "volume_shrink": {"enabled": bool(legacy_params.get("use_volume_shrink")),
                              "params": {k: legacy_params[k] for k in
                                         ("volume_shrink_lookback", "volume_shrink_max_ratio")
                                         if k in legacy_params}},
        }

    enabled: List[Tuple] = []
    for c in all_conditions():
        spec = (conditions or {}).get(c.id) or {}
        if not spec.get("enabled"):
            continue
        cp = normalize_params(c.params, spec.get("params"))
        if c.id == "volume_shrink":
            # 软条件：沿用原语义，`use_volume_shrink` 由"是否启用"决定
            cp = dict(cp, use_volume_shrink=True)
        # ⚠️ 没有 `prepare` 钩子的条件（ma_slope / bias_band / 估值类 / 策略信号）
        #    也要拿到**全局参数**（ma_fast/ma_mid/ma_slow），否则读 p['ma_fast'] 会 KeyError。
        #    带 `prepare` 的条件由 `_prep_rules(gp, cp)` 内部完成同样的合并。
        #    策略信号**不依赖**全局均线参数（月线反转用固定 20/120/200/250），故只给自身参数。
        if c.group == GROUP_STRATEGY:
            prepared = dict(cp)
        else:
            prepared = c.prepare(gp, cp) if c.prepare else {**gp, **cp}
        enabled.append((c, prepared))

    plan = {"global": gp, "enabled": enabled,
            "need_val": any(c.group not in (GROUP_TECH, GROUP_STRATEGY)
                            for c, _ in enabled)}
    plan["wanted"] = _wanted(plan)      # 需要的交易日根数（含金叉回溯的窗口修正）
    return plan


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
    if close is not None and close == close and len(g) >= 2:
        prev = g.iloc[-2].get("close")
        if prev is not None and prev == prev and float(prev):
            out["change_pct"] = round((float(close) - float(prev)) / float(prev) * 100, 2)
    return out


def list_snapshots(limit: int = 20) -> List[dict]:
    """查询历史扫描快照（供“我的观察历史”）。"""
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
            "global_params": d.get("global_params") or {},
            "conditions": d.get("conditions") or {},
            "params": d.get("params") or {},          # 旧快照兼容
        })
    return out


def get_snapshot(run_id: str) -> Optional[dict]:
    d = retrieve_long_term_data(run_id)
    if not d:
        return None
    return {"run_id": run_id, **d}
