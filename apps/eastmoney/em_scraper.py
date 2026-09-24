# -*- coding: utf-8 -*-
"""东方财富分析师 —— 采集层（Selenium）。

职责：打开列表页 → 选期间 → 选行业 → 抓表格 → 逐个存详情页 HTML/CSV → 写 manifest.json。

选择器一律基于**真实页面结构**（见 `em_config` docstring 的样本），不做"逐个选择器猜测重试"：

* 期间按钮：`li[year][sort]`（页面 `#chart_type` 内的 li 带这两个属性）
* 行业按钮：`li[data-value]`（页面 `.cateday ul.st_type` 内的 li 带编码）
* 数据表格：`div.dataview-body > table`
  （`#year_table` / `#month_table` 在 HTML 里是**被注释掉的模板占位**，不是真实元素；
    `div.dataview-floatheader` 里那份 table 是隐藏的浮动表头，不能用）
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urljoin

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from config import setup_logger  # noqa: E402
from selenium import webdriver  # noqa: E402
from selenium.webdriver.chrome.options import Options  # noqa: E402
from selenium.webdriver.common.by import By  # noqa: E402
from selenium.webdriver.support import expected_conditions as EC  # noqa: E402
from selenium.webdriver.support.ui import WebDriverWait  # noqa: E402

from em_config import (  # noqa: E402
    ALL_CATEGORY,
    INDUSTRY_CATEGORIES,
    LIST_FIELDS,
    LIST_URL,
    MANIFEST_NAME,
    PERIOD_ORDER,
    category_display,
    industry_code,
    period_attrs,
    period_display,
)

logger = setup_logger("eastmoney_analyst")

# 列表页数据表（真实表格在 dataview-body 内）
TABLE_SELECTOR = "div.dataview-body > table"
ROW_SELECTOR = "tbody tr"
# 详情页的跟踪成份股表格
DETAIL_TABLE_SELECTOR = "table.table-model"

PAGE_WAIT = 20  # 页面元素等待上限（秒）


def _safe_name(name: str) -> str:
    """把分析师姓名清理成可做文件名的形式。"""
    cleaned = re.sub(r'[<>:"/\\|?*\s]+', "_", str(name)).strip("_")
    return (cleaned or "unknown")[:60]


def setup_driver():
    """创建 Chrome 无头驱动。

    注：原配置里有 `--disable-javascript`，但本流程**依赖 JS**（点击期间/行业按钮、
    `emdataview.js` 渲染表格），故移除——它只会让流程不可靠。
    """
    opts = Options()
    for arg in (
        "--headless",
        "--start-maximized",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--disable-extensions",
        "--disable-plugins",
        "--disable-images",
        "--remote-debugging-port=9222",
        "--disable-logging",
        "--no-first-run",
        "--no-default-browser-check",
        "lang=zh-CN",
    ):
        opts.add_argument(arg)
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    driver = webdriver.Chrome(options=opts)
    driver.implicitly_wait(10)
    return driver


def _wait_table(driver):
    """等列表页数据表就绪。"""
    WebDriverWait(driver, PAGE_WAIT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, TABLE_SELECTOR))
    )


def click_rank_period(driver, period: str):
    """点击时间段排行按钮（页面 li 带稳定的 year/sort 属性）。`period` 为期间 slug。"""
    if period not in PERIOD_ORDER:
        raise ValueError(f"未知期间 slug：{period}（可用：{'、'.join(PERIOD_ORDER)}）")
    year, sort = period_attrs(period)
    selector = f"//li[@year='{year}' and @sort='{sort}']"
    logger.info(f"点击期间：{period_display(period)}（{selector}）")
    el = WebDriverWait(driver, PAGE_WAIT).until(
        EC.element_to_be_clickable((By.XPATH, selector))
    )
    driver.execute_script("arguments[0].click();", el)
    _wait_table(driver)
    time.sleep(2)  # 等表格重绘完成


def click_industry_category(driver, category: str):
    """点击行业类别（页面 li 带 data-value 编码；「全部」的 data-value 为空串）。

    `category` 为行业 slug。
    """
    if category != ALL_CATEGORY and category not in INDUSTRY_CATEGORIES:
        raise ValueError(f"未知行业 slug：{category}")
    code = industry_code(category)
    selector = f"//div[contains(@class,'cateday')]//li[@data-value='{code}']"
    logger.info(f"点击行业：{category_display(category)}（data-value={code}）")
    el = WebDriverWait(driver, PAGE_WAIT).until(
        EC.element_to_be_clickable((By.XPATH, selector))
    )
    driver.execute_script("arguments[0].click();", el)
    _wait_table(driver)
    time.sleep(2)


def navigate_and_click_rank_period(driver, period: str, category: str = ALL_CATEGORY):
    """打开列表页 → 选期间 → （可选）选行业。"""
    logger.info(f"打开列表页：{LIST_URL}")
    driver.get(LIST_URL)
    _wait_table(driver)
    time.sleep(3)

    click_rank_period(driver, period)
    if category and category != ALL_CATEGORY:
        click_industry_category(driver, category)
    return True


def extract_analysts_from_table(driver):
    """从列表页数据表提取分析师（**按表头 th[data-field] 定位，不依赖列下标**）。

    真实列序（11 列）::

        _totalnumber / ANALYST_NAME / ORG_NAME / INDEX_VALUE / detail /
        YEAR_YIELD / YIELD_3 / YIELD_6 / YIELD_12 / SECURITY_COUNT / NEWEST_STOCK_RATING

    旧实现按 `cells[8]`、`cells[9]` 等硬编码下标取值，比真实列序**错位一位**
    （把 YIELD_12 当成 stock_count、SECURITY_COUNT 当成 latest_rating），故改为按字段名取。
    """
    table = driver.find_element(By.CSS_SELECTOR, TABLE_SELECTOR)

    fields = {}
    for i, th in enumerate(table.find_elements(By.CSS_SELECTOR, "thead th")):
        key = LIST_FIELDS.get(th.get_attribute("data-field") or "")
        if key:
            fields[i] = key
    if not fields:
        raise RuntimeError("列表页表头缺少 data-field，页面结构可能已变化")

    name_idx = next((i for i, k in fields.items() if k == "name"), None)
    if name_idx is None:
        raise RuntimeError("列表页表头未找到 ANALYST_NAME 列")

    analysts = []
    for row in table.find_elements(By.CSS_SELECTOR, ROW_SELECTOR):
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) <= name_idx:
            continue

        info = {k: cells[i].text.strip() for i, k in fields.items() if i < len(cells)}
        name = info.get("name", "")
        if not name:
            continue

        # 详情页链接：列表页里是相对路径（如 11000300437.html），
        # 解析后为 https://data.eastmoney.com/invest/invest/11000300437.html
        href = ""
        links = cells[name_idx].find_elements(By.TAG_NAME, "a")
        if links:
            href = links[0].get_attribute("href") or ""
        info["url"] = urljoin(LIST_URL, href) if href else ""

        rank = str(info.get("rank", ""))
        info["rank"] = int(rank) if rank.isdigit() else len(analysts) + 1
        analysts.append(info)

    logger.info(f"从列表页提取到 {len(analysts)} 位分析师")
    return analysts


def save_page_html(driver, filename):
    """保存当前页面 HTML。"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info(f"页面已保存：{filename}")
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"保存页面失败：{e}")
        return False


def save_data_to_csv(data, filename_prefix, output_dir):
    """把记录列表写成 CSV（列名取所有出现过的键）。"""
    if not data:
        logger.warning("没有数据可保存")
        return None
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(
        output_dir, f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    fieldnames = sorted({k for item in data for k in item})
    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    logger.info(f"数据已保存到：{output_file}（{len(data)} 条）")
    return output_file


def write_manifest(output_dir, category, period, analysts):
    """写 manifest.json：记录本次采集的类别/期间与分析师清单（含详情页文件路径）。

    后处理阶段直接读它，**不再靠解析 HTML 文件名**（旧实现用 `split('_')` 反解 rank/name，
    一旦命名规则或姓名含下划线就会静默错位）。
    """
    payload = {
        "category": category,
        "period": period,
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "analysts": analysts,
    }
    path = os.path.join(output_dir, MANIFEST_NAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"manifest 已写入：{path}（{len(analysts)} 位分析师）")
    return path


def scrape_analysts_for_category(driver, category, period, output_dir):
    """采集：列表页表格 → 逐个分析师的详情页 HTML → manifest。`category`/`period` 均为 slug。"""
    cat_label, per_label = category_display(category), period_display(period)
    logger.info(f"===== 采集开始 - 类别: {cat_label}, 期间: {per_label} =====")
    os.makedirs(output_dir, exist_ok=True)

    analysts = extract_analysts_from_table(driver)
    if not analysts:
        raise RuntimeError(f"未从列表页提取到分析师（类别 {cat_label} / 期间 {per_label}）")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_page_html(driver, os.path.join(output_dir, f"list_{stamp}.html"))
    save_data_to_csv(analysts, "分析师基本信息", output_dir)

    day = datetime.now().strftime("%Y%m%d")
    for i, a in enumerate(analysts, 1):
        a["html_file"] = ""
        if not a.get("url"):
            logger.warning(f"[{i}/{len(analysts)}] {a['name']}：无详情页链接，跳过")
            continue
        fname = f"analyst_{a['rank']:02d}_{_safe_name(a['name'])}_{day}.html"
        path = os.path.join(output_dir, fname)
        try:
            driver.get(a["url"])
            WebDriverWait(driver, PAGE_WAIT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, DETAIL_TABLE_SELECTOR))
            )
            save_page_html(driver, path)
            a["html_file"] = path
            logger.info(f"[{i}/{len(analysts)}] {a['name']} → {fname}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"[{i}/{len(analysts)}] {a['name']} 详情页失败：{e}")
        time.sleep(1)

    write_manifest(output_dir, category, period, analysts)
    logger.info(f"===== 采集结束 - 类别: {cat_label}, 期间: {per_label} =====")
    return analysts
