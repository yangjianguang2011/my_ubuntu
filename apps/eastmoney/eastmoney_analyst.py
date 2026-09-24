#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""东方财富分析师数据采集 —— 入口。

用法::

    python3 eastmoney_analyst.py -c electronics -p 2026_latest
    python3 eastmoney_analyst.py -c all -p 12m
    python3 eastmoney_analyst.py --list          # 列出可选的行业与期间（slug + 中文）
    python3 eastmoney_analyst.py                 # 不带参数 → 交互式菜单
    python3 eastmoney_analyst.py 0 0             # 兼容旧写法：<行业序号> <期间序号>

参数一律用**英文 slug**（便于在 shell 里书写）：`-c electronics`、`-p 2026_latest`。
也兼容中文名（`-c 电子`）与页面编码（`-c 270000`），但推荐用 slug。

产出（写入 `[eastmoney] data_dir`，容器内为 `/data/analyst_data`）::

    processed_YYYYMMDD_HHMMSS/          # 中间文件（列表页/详情页 HTML、CSV、manifest.json）
    {类别}_{期间}_{YYYYMMDD}.xlsx       # 最终 Excel（最新跟踪 / 历史跟踪 两个工作表）
    {类别}_{期间}_{YYYYMMDD}.html       # 最终 HTML 报告（文件名用中文，便于阅读）

模块划分::

    em_config.py   常量（期间/行业/表头字段，以真实页面结构为准）
    em_scraper.py  采集层（Selenium：列表页 → 选期间/行业 → 存详情页）
    em_report.py   后处理层（读 manifest → 解析详情页 → 生成报告）

页面结构参考样本见 `em_config` 的 docstring。
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

# 允许直接运行本脚本（python apps/eastmoney/eastmoney_analyst.py）：
# 把 apps/ 加入 sys.path，才能 import config
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from config import get_path, setup_logger  # noqa: E402

from em_config import (  # noqa: E402
    ALL_CATEGORY,
    CATEGORY_ORDER,
    PERIOD_ORDER,
    category_display,
    industry_code,
    period_attrs,
    period_display,
    resolve_category,
    resolve_period,
)
from em_report import extract_and_save_analyst_data  # noqa: E402
from em_scraper import (  # noqa: E402
    navigate_and_click_rank_period,
    scrape_analysts_for_category,
    setup_driver,
)

logger = setup_logger("eastmoney_analyst")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="eastmoney_analyst.py",
        description="东方财富分析师数据采集（列表页 → 详情页 → HTML/Excel 报告）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  %(prog)s -c electronics -p 12m\n"
            "  %(prog)s -c all -p 2026_latest\n"
            "  %(prog)s --list\n"
        ),
    )
    p.add_argument("-c", "--category", metavar="行业",
                   help="行业类别（中文名或 data-value 编码；默认「全部」）")
    p.add_argument("-p", "--period", metavar="期间",
                   help="时间段排行（如 '2026 最新排行' / '12个月排行'）")
    p.add_argument("-l", "--list", action="store_true", dest="list_choices",
                   help="列出可选的行业与期间后退出")
    p.add_argument("legacy", nargs="*",
                   help="兼容旧写法：<行业序号> <期间序号>（如 0 0）")
    return p


def print_choices() -> None:
    print("行业类别（-c/--category，用英文 slug）：")
    for i, slug in enumerate(CATEGORY_ORDER):
        print(f"  {i:2d}. {slug:<24} {category_display(slug):<10} {industry_code(slug) or '-'}")
    print("\n时间段排行（-p/--period，用英文 slug）：")
    for i, slug in enumerate(PERIOD_ORDER):
        year, sort = period_attrs(slug)
        print(f"  {i:2d}. {slug:<14} {period_display(slug):<14} year={year} sort={sort}")
    print("\n示例：python3 eastmoney_analyst.py -c electronics -p 2026_latest")


def _resolve_legacy_category(value: str) -> str:
    """旧写法传的是菜单序号；也接受 slug / 中文名 / 编码。"""
    if str(value).isdigit():
        idx = int(value)
        if 0 <= idx < len(CATEGORY_ORDER):
            return CATEGORY_ORDER[idx]
    return resolve_category(value)


def _ask_choice(title: str, slugs: list, label) -> str:
    """交互式选择（输入序号，返回 slug）。"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)
    for i, slug in enumerate(slugs):
        print(f"  {i:2d}. {slug:<24} {label(slug)}")
    print("=" * 60)
    while True:
        raw = input(f"请输入序号 (0-{len(slugs) - 1}): ").strip()
        if raw.isdigit() and 0 <= int(raw) < len(slugs):
            return slugs[int(raw)]
        print(f"输入无效，请输入 0-{len(slugs) - 1} 之间的数字")


def parse_args(argv):
    """解析命令行，返回 (category, period)；`--list` 时返回 (None, None)。"""
    args = build_parser().parse_args(argv)

    if args.list_choices:
        print_choices()
        return None, None

    if args.category or args.period:
        category = resolve_category(args.category) if args.category else ALL_CATEGORY
        if not args.period:
            raise SystemExit("缺少 --period（可用 --list 查看可选值）")
        return category, resolve_period(args.period)

    # 兼容旧写法：两个位置参数（行业序号、期间序号）
    if len(args.legacy) >= 2:
        return _resolve_legacy_category(args.legacy[0]), resolve_period(args.legacy[1])
    if args.legacy:
        raise SystemExit("旧写法需要两个参数：<行业序号> <期间序号>（如 0 0）")

    # 无参数 → 交互式菜单
    category = _ask_choice("行业类别选择", CATEGORY_ORDER, category_display)
    period = _ask_choice("时间段选择", PERIOD_ORDER, period_display)
    return category, period


def main():
    category, period = parse_args(sys.argv[1:])
    if category is None:  # --list
        return

    logger.info(f"===== 东方财富分析师采集开始 - 类别: {category}, 期间: {period} =====")
    driver = None
    try:
        main_output_dir = get_path("eastmoney", "data_dir", "/data/analyst_data")
        processed_dir = os.path.join(
            main_output_dir, f"processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        os.makedirs(processed_dir, exist_ok=True)
        logger.info(f"中间文件目录：{processed_dir}")

        driver = setup_driver()
        navigate_and_click_rank_period(driver, period, category)
        scrape_analysts_for_category(driver, category, period, processed_dir)
        extract_and_save_analyst_data(processed_dir, main_output_dir)
        logger.info("===== 采集与报告生成完成 =====")
    except Exception as e:  # noqa: BLE001
        logger.error(f"执行失败：{e}", exc_info=True)
        raise
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("浏览器已关闭")
            except Exception as e:  # noqa: BLE001
                logger.debug(f"关闭浏览器时出错：{e}")


if __name__ == "__main__":
    main()
