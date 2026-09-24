# -*- coding: utf-8 -*-
"""东方财富分析师页面 —— 配置常量（**以真实页面结构为准**）。

参考样本（同目录，由用户保存）：
  * `page_ele.txt` / `main_cont.txt` —— 列表页（`.../invest/invest/list.html`）
  * `cont_top.txt`                  —— 列表页顶部筛选区（期间按钮 + 行业按钮）
  * `run/analyst_data/processed_*/analyst_*.html` —— 详情页（脚本自己存的）

命令行参数一律用**英文 slug**（便于在 shell 里书写，避免中文），例如::

    python3 eastmoney_analyst.py -c electronics -p 2026_latest

中文显示名与 `data-value` 编码仅作为**兼容输入**，同时用于：
  * 输出文件名（`全部类别_3个月排行_20260903.xlsx`）
  * 日志与 `--list` 展示

页面关键结构
------------
期间按钮（列表页 `#chart_type > li`，带稳定属性）::

    <li class="linklab spe-padding at" year="2026" sort="YEAR_YIELD">2026 最新排行</li>
    <li class="linklab spe-padding"    year="1"    sort="INDEX_VALUE">最新总排行</li>

行业按钮（列表页 `.cateday ul.st_type > li`，带 data-value 编码）::

    <li class="at2" data="all" data-value="">全部</li>
    <li data="270000" data-value="270000">电子</li>

列表页数据表（表头带 `data-field`）::

    th[data-field] 顺序: _totalnumber / ANALYST_NAME / ORG_NAME / INDEX_VALUE /
                         detail / YEAR_YIELD / YIELD_3 / YIELD_6 / YIELD_12 /
                         SECURITY_COUNT / NEWEST_STOCK_RATING

详情页（两张表，带稳定 id）::

    <div class="content" id="news_table">    <table class="table-model">…</table></div>
    <div class="content" id="history_table"> <table class="table-model">…</table></div>
"""
from __future__ import annotations

from datetime import datetime

# 列表页 URL（详情页相对链接基于它解析：{fxs_id}.html → /invest/invest/{fxs_id}.html）
LIST_URL = "https://data.eastmoney.com/invest/invest/list.html"

# 「全部」的 slug；输出文件名里写作「全部类别」
ALL_CATEGORY = "all"
ALL_CATEGORY_LABEL = "全部类别"
ALL_CATEGORY_DISPLAY = "全部"

# 行业类别：slug -> (中文显示名, 页面 li 的 data-value 编码)
# 来源：cont_top.txt 的 <ul class="st_type st_type_3">，共 30 个
INDUSTRY_CATEGORIES = {
    "agriculture": ("农林牧渔", "110000"),
    "chemicals": ("基础化工", "220000"),
    "steel": ("钢铁", "230000"),
    "nonferrous_metals": ("有色金属", "240000"),
    "electronics": ("电子", "270000"),
    "automobile": ("汽车", "280000"),
    "home_appliances": ("家用电器", "330000"),
    "food_beverage": ("食品饮料", "340000"),
    "textiles_apparel": ("纺织服饰", "350000"),
    "light_manufacturing": ("轻工制造", "360000"),
    "pharma_biotech": ("医药生物", "370000"),
    "utilities": ("公用事业", "410000"),
    "transportation": ("交通运输", "420000"),
    "real_estate": ("房地产", "430000"),
    "retail": ("商贸零售", "450000"),
    "social_services": ("社会服务", "460000"),
    "banks": ("银行", "480000"),
    "nonbank_finance": ("非银金融", "490000"),
    "building_materials": ("建筑材料", "610000"),
    "construction_decoration": ("建筑装饰", "620000"),
    "power_equipment": ("电力设备", "630000"),
    "machinery": ("机械设备", "640000"),
    "defense": ("国防军工", "650000"),
    "computers": ("计算机", "710000"),
    "media": ("传媒", "720000"),
    "telecom": ("通信", "730000"),
    "coal": ("煤炭", "740000"),
    "oil_petrochemical": ("石油石化", "750000"),
    "environmental": ("环保", "760000"),
    "beauty_care": ("美容护理", "770000"),
}

# 时间段排行：slug -> (中文显示名, year, sort)
# 中文显示名与页面按钮文本完全一致（含空格差异）
PERIODS = {
    "2026_latest": ("2026 最新排行", "2026", "YEAR_YIELD"),
    "latest_total": ("最新总排行", "1", "INDEX_VALUE"),
    "3m": ("3个月排行", "3", "YIELD_3"),
    "6m": ("6个月排行", "6", "YIELD_6"),
    "12m": ("12个月排行", "12", "YIELD_12"),
    "2025_yearly": ("2025年度排行", "2025", "YEAR_YIELD"),
}

# 菜单顺序（`--list` 与交互菜单按此展示）
CATEGORY_ORDER = [ALL_CATEGORY, *INDUSTRY_CATEGORIES]
PERIOD_ORDER = list(PERIODS)

# 列表页表头 th[data-field] -> 内部字段名
LIST_FIELDS = {
    "_totalnumber": "rank",
    "ANALYST_NAME": "name",
    "ORG_NAME": "institution",
    "INDEX_VALUE": "latest_index",
    "YEAR_YIELD": "year_return",
    "YIELD_3": "three_month_return",
    "YIELD_6": "six_month_return",
    "YIELD_12": "twelve_month_return",
    "SECURITY_COUNT": "stock_count",
    "NEWEST_STOCK_RATING": "latest_rating",
}

# 详情页两张表的 id（比按标题文本匹配可靠）
DETAIL_TABLES = (("news_table", "最新跟踪"), ("history_table", "历史跟踪"))

# 采集阶段写在处理目录里的清单文件名（后处理阶段据此关联，不再解析 HTML 文件名）
MANIFEST_NAME = "manifest.json"


# ---------------------------------------------------------------- 取值/规范化


def category_display(slug: str) -> str:
    """slug -> 中文显示名。"""
    if slug == ALL_CATEGORY:
        return ALL_CATEGORY_DISPLAY
    return INDUSTRY_CATEGORIES[slug][0]


def period_display(slug: str) -> str:
    """slug -> 中文显示名。"""
    return PERIODS[slug][0]


def period_attrs(slug: str) -> tuple:
    """slug -> (year, sort)，用于页面按钮定位。"""
    return PERIODS[slug][1], PERIODS[slug][2]


def industry_code(slug: str) -> str:
    """slug -> 页面 li 的 data-value 编码（「全部」为空串）。"""
    return "" if slug == ALL_CATEGORY else INDUSTRY_CATEGORIES[slug][1]


def resolve_category(value) -> str:
    """把用户输入规范成行业 slug：接受 slug / 中文名 / data-value 编码。"""
    v = str(value or "").strip()
    if not v or v == ALL_CATEGORY:
        return ALL_CATEGORY
    if v in INDUSTRY_CATEGORIES:
        return v
    for slug, (name, code) in INDUSTRY_CATEGORIES.items():
        if v == name or v == code:
            return slug
    raise ValueError(
        f"未知行业：{v}（用 --list 查看可选 slug，共 {len(INDUSTRY_CATEGORIES)} 个行业 + {ALL_CATEGORY}）"
    )


def resolve_period(value) -> str:
    """把用户输入规范成期间 slug：接受 slug / 中文名 / 菜单序号（兼容旧写法）。"""
    v = str(value or "").strip()
    if v in PERIODS:
        return v
    for slug, (name, _year, _sort) in PERIODS.items():
        if v == name:
            return slug
    if v.isdigit():
        idx = int(v)
        if 0 <= idx < len(PERIOD_ORDER):
            return PERIOD_ORDER[idx]
    raise ValueError(f"未知期间：{v}（用 --list 查看可选 slug）")


def report_stem(category: str, period: str) -> str:
    """最终产物文件名主干：`{类别}_{期间}_{YYYYMMDD}`（「全部」→「全部类别」）。

    文件名用**中文显示名**（便于阅读），参数用英文 slug。
    """
    label = ALL_CATEGORY_LABEL if category == ALL_CATEGORY else INDUSTRY_CATEGORIES[category][0]
    return f"{label}_{period_display(period)}_{datetime.now().strftime('%Y%m%d')}"
