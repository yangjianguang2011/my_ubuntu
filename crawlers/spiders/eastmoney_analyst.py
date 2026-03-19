#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
东方财富分析师数据自动化采集整合脚本

功能概述:
=============
本脚本整合了数据采集和提取功能，一次性完成东方财富分析师数据的采集、处理和保存。
- 自动采集指定时间段的分析师数据
- 将中间文件整理到单独的文件夹
- 按指定格式生成最终Excel文件

主要功能:
1. 自动浏览器控制 - 使用Selenium Chrome WebDriver
2. 数据采集 - 采集分析师排名数据并保存为HTML
3. 数据提取 - 从HTML文件中提取股票信息并保存到Excel
4. 文件管理 - 将中间文件归类整理，最终文件按指定格式命名
5. 错误处理和重试机制 - 处理页面加载失败、元素点击失败等情况
6. 详细日志记录 - 记录整个采集过程的详细信息

输出文件结构:
=============
output/
├── processed_YYYYMMDD_HHMMSS/     # 中间文件夹
│   ├── analyst_{category}_{period}_{rank}_{name}.html
│   ├── {category}_{period}_分析师基本信息_YYYYMMDD_HHMMSS.csv
│   └── {category}_{period}_分析师处理状态_YYYYMMDD_HHMMSS.csv
└── {category}_{period}_Firecrawl跟踪成份股数据_YYYYMMDD_HHMMSS.xlsx    # 最终Excel文件

作者: AI Assistant
创建时间: 2024
"""

import csv
import glob
import json
import logging
import os
import re
import sys
import time
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from config import get_path, setup_logger

# 为东方财富分析师脚本创建独立的日志记录器
logger = setup_logger("eastmoney_analyst")


def setup_driver():
    """设置Chrome浏览器驱动"""
    chrome_options = Options()
    # 启用无头模式，使程序可以在没有图形界面的环境中运行（如Docker容器）
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-images")
    chrome_options.add_argument("--disable-javascript")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    # chrome_options.add_argument('--user-data-dir=/tmp/chrome-user-data')
    chrome_options.add_argument("lang=zh-CN")

    # 设置用户代理，避免被识别为爬虫
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(10)  # 设置隐式等待
    return driver


def click_industry_category(driver, category_name):
    """点击行业类别按钮"""
    try:
        # 行业类别映射到页面实际的按钮文本
        category_mapping = {
            "农林牧渔": "农林牧渔",
            "基础化工": "基础化工",
            "钢铁": "钢铁",
            "有色金属": "有色金属",
            "电子": "电子",
            "汽车": "汽车",
            "家用电器": "家用电器",
            "食品饮料": "食品饮料",
            "纺织服饰": "纺织服饰",
            "轻工制造": "轻工制造",
            "医药生物": "医药生物",
            "公用事业": "公用事业",
            "交通运输": "交通运输",
            "房地产": "房地产",
            "商贸零售": "商贸零售",
            "社会服务": "社会服务",
            "银行": "银行",
            "非银金融": "非银金融",
            "建筑材料": "建筑材料",
            "建筑装饰": "建筑装饰",
            "电力设备": "电力设备",
            "机械设备": "机械设备",
            "国防军工": "国防军工",
            "计算机": "计算机",
            "传媒": "传媒",
            "通信": "通信",
            "煤炭": "煤炭",
            "石油石化": "石油石化",
            "环保": "环保",
            "美容护理": "美容护理",
        }

        if category_name not in category_mapping:
            logger.warning(f"未知的行业类别：{category_name}")
            return False

        actual_name = category_mapping[category_name]
        logger.info(f"查找行业类别按钮：{actual_name}")

        # 尝试多种选择器查找行业类别按钮
        selectors = [
            f"//li[normalize-space(text())='{actual_name}']",
            f"//a[normalize-space(text())='{actual_name}']",
            f"//span[normalize-space(text())='{actual_name}']",
            f"//td[normalize-space(text())='{actual_name}']",
            f"//div[normalize-space(text())='{actual_name}']",
            f"//a[contains(text(), '{actual_name}')]",
        ]

        for selector in selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                for elem in elements:
                    if elem.text.strip() == actual_name:
                        driver.execute_script("arguments[0].click();", elem)
                        time.sleep(2)  # 等待数据加载
                        logger.info(
                            f"使用选择器 '{selector}' 成功点击行业类别：{actual_name}"
                        )
                        return True
            except Exception as e:
                logger.debug(f"选择器 '{selector}' 失败：{str(e)}")
                continue

        # 如果精确匹配失败，尝试模糊匹配
        fuzzy_selectors = [
            f"//a[contains(text(), '{actual_name}')]",
            f"//span[contains(text(), '{actual_name}')]",
            f"//td[contains(text(), '{actual_name}')]",
        ]

        for selector in fuzzy_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                for elem in elements:
                    text = elem.text.strip()
                    if text == actual_name or actual_name in text:
                        driver.execute_script("arguments[0].click();", elem)
                        time.sleep(2)
                        logger.info(
                            f"使用模糊选择器 '{selector}' 成功点击行业类别：{actual_name}"
                        )
                        return True
            except Exception as e:
                logger.debug(f"模糊选择器 '{selector}' 失败：{str(e)}")
                continue

        logger.warning(f"未找到行业类别按钮：{actual_name}")
        return False

    except Exception as e:
        logger.error(f"点击行业类别失败：{str(e)}")
        return False


def navigate_and_click_rank_period(driver, period="2025 年度排行", category="全部"):
    """导航到目标页面并点击指定时间段排行和行业类别"""
    try:
        logger.info("正在打开目标页面...")
        driver.get("https://data.eastmoney.com/invest/invest/list.html")
        time.sleep(5)  # 等待页面加载

        # 尝试多种选择器点击指定时间段排行
        logger.info(f"正在点击{period}...")

        # 使用normalize-space()函数处理文本匹配，这对处理HTML中分散的文本更有效
        period_selectors = []

        # 定义时间段与属性的映射
        period_mapping = {
            "2025 年度排行": {"year": "2025", "sort": "YEAR_YIELD"},
            "2024 年度排行": {"year": "2024", "sort": "YEAR_YIELD"},
            "2023 年度排行": {"year": "2023", "sort": "YEAR_YIELD"},
            "最新总排行": {"year": "1", "sort": "INDEX_VALUE"},
            "3个月排行": {"year": "3", "sort": "YIELD_3"},
            "6个月排行": {"year": "6", "sort": "YIELD_6"},
            "12个月排行": {"year": "12", "sort": "YIELD_12"},
        }

        # 如果当前时间段在映射中，优先使用属性匹配
        if period in period_mapping:
            attrs = period_mapping[period]
            period_selectors.extend(
                [
                    f"//li[@year='{attrs['year']}' and @sort='{attrs['sort']}']",  # 精确匹配属性
                    f"//li[contains(@class, 'linklab') and contains(@class, 'spe-padding') and @year='{attrs['year']}' and @sort='{attrs['sort']}']",
                    f"//li[contains(@class, 'spe-padding') and @year='{attrs['year']}' and @sort='{attrs['sort']}']",
                    f"//li[@year='{attrs['year']}' and contains(@class, 'at')]",  # 包含'at'类，表示当前选中状态
                ]
            )

            # 使用normalize-space()处理文本分散的问题
            if "年度排行" in period:
                year = attrs["year"]
                period_selectors.extend(
                    [
                        f"//li[normalize-space(text())='{year}年度排行']",
                        f"//li[contains(normalize-space(text()), '{year}') and contains(normalize-space(text()), '年度') and contains(normalize-space(text()), '排行')]",
                        f"//li[contains(@year, '{year}') and contains(@sort, 'YEAR')]",
                    ]
                )
            else:
                # 对于非年度排行，使用normalize-space处理
                period_selectors.append(f"//li[normalize-space(text())='{period}']")
                period_selectors.append(
                    f"//li[contains(normalize-space(text()), '{period.split()[0]}') and contains(normalize-space(text()), '排行')]"
                )
        else:
            # 如果不在映射中，使用通用选择器
            period_selectors = [
                f"//span[normalize-space(text())='{period}']",
                f"//a[normalize-space(text())='{period}']",
                f"//div[normalize-space(text())='{period}']",
                f"//li[normalize-space(text())='{period}']",
                f"//button[normalize-space(text())='{period}']",
                f"//li[contains(@year, '{period.split()[0]}') and @sort]",  # 处理年度排行的通用情况
            ]

        # 添加通用的linklab类选择器，这些通常是排行按钮的通用样式
        period_selectors.extend(
            [
                f"//li[contains(@class, 'linklab') and contains(normalize-space(text()), '{period.split()[0] if len(period.split()) > 0 else period}')]",
                f"//li[contains(@class, 'spe-padding') and contains(normalize-space(text()), '{period.split()[0] if len(period.split()) > 0 else period}')]",
            ]
        )

        clicked = False
        for selector in period_selectors:
            try:
                period_element = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                # 使用JavaScript执行点击操作，避免元素被遮挡的问题
                driver.execute_script("arguments[0].click();", period_element)
                time.sleep(3)  # 等待数据加载
                logger.info(f"使用选择器 '{selector}' 成功点击{period}")
                clicked = True
                break
            except Exception as e:
                logger.debug(f"选择器 '{selector}' 失败: {str(e)}")
                continue

        if not clicked:
            logger.warning(f"无法找到{period}按钮，继续处理当前页面数据")
            # 检查当前页面是否已经是所需页面（例如，如果所需排行已经被选中）
            try:
                # 检查是否有对应时间段相关数据的元素
                if "2025" in period:
                    current_year_elements = driver.find_elements(
                        By.XPATH,
                        "//span[contains(text(), '2025') or contains(@class, 'year_txt') or @data-field='YEAR_YIELD']",
                    )
                    if current_year_elements:
                        logger.info(f"页面上已存在{period}相关数据，继续处理")
                        return True
                elif "3个月" in period:
                    current_elements = driver.find_elements(
                        By.XPATH,
                        "//span[contains(text(), '3个月') or @data-field='YIELD_3']",
                    )
                    if current_elements:
                        logger.info(f"页面上已存在{period}相关数据，继续处理")
                        return True
                elif "6个月" in period:
                    current_elements = driver.find_elements(
                        By.XPATH,
                        "//span[contains(text(), '6个月') or @data-field='YIELD_6']",
                    )
                    if current_elements:
                        logger.info(f"页面上已存在{period}相关数据，继续处理")
                        return True
                elif "12个月" in period:
                    current_elements = driver.find_elements(
                        By.XPATH,
                        "//span[contains(text(), '12个月') or @data-field='YIELD_12']",
                    )
                    if current_elements:
                        logger.info(f"页面上已存在{period}相关数据，继续处理")
                        return True
            except:
                pass
            return False

        # 点击行业类别
        if category != "全部":
            logger.info(f"正在点击行业类别：{category}...")
            category_clicked = click_industry_category(driver, category)
            if category_clicked:
                logger.info(f"成功点击行业类别：{category}")
            else:
                logger.warning(f"未能点击行业类别：{category}，将使用默认'全部'类别")
            time.sleep(2)
        else:
            logger.info("行业类别为'全部'，不需要点击")

        logger.info("页面加载完成")
        return True
    except Exception as e:
        logger.error(f"导航到目标页面失败: {str(e)}")
        return False


def get_analyst_links_from_page(driver):
    """从页面获取分析师链接"""
    try:
        logger.info("正在获取分析师链接...")

        # 尝试多种选择器获取分析师链接
        analyst_link_selectors = [
            "//a[contains(@href, '/invest/analyst/')]",
            "//a[contains(@href, 'analyst')]",
            "//tr//a[contains(@href, 'invest')]",
            "//table//a[contains(@href, 'eastmoney')]",
        ]

        analysts = []
        for selector in analyst_link_selectors:
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )

                analyst_links = driver.find_elements(By.XPATH, selector)
                logger.info(
                    f"使用选择器 '{selector}' 找到 {len(analyst_links)} 个分析师链接"
                )

                for i, link in enumerate(
                    analyst_links[:10], 1
                ):  # 只取前10个避免过多请求
                    try:
                        analyst_name = link.text.strip()
                        analyst_url = link.get_attribute("href")

                        if analyst_name and analyst_url and "analyst" in analyst_url:
                            # 检查是否已存在相同分析师
                            existing_analyst = next(
                                (a for a in analysts if a["name"] == analyst_name), None
                            )
                            if not existing_analyst:
                                analyst_info = {
                                    "rank": len(analysts) + 1,
                                    "name": analyst_name,
                                    "url": analyst_url,
                                }
                                analysts.append(analyst_info)
                                logger.info(f"已获取分析师: {analyst_name}")

                    except Exception as e:
                        logger.error(f"获取第{i}个分析师链接时出错: {str(e)}")
                        continue

                if analysts:
                    break

            except Exception:
                continue

        if not analysts:
            logger.warning("尝试从表格中直接提取分析师数据...")
            # 如果找不到链接，尝试从表格中直接提取数据
            analysts = extract_analysts_from_table(driver)

        logger.info(f"总共获取到 {len(analysts)} 个分析师")
        return analysts
    except Exception as e:
        logger.error(f"获取分析师链接失败: {str(e)}")
        return []


def extract_analysts_from_table(driver):
    """从表格中直接提取分析师数据"""
    try:
        logger.info("正在从表格中提取分析师数据...")

        # 尝试多种表格选择器
        table_selectors = [
            "//div[@class='dataview-body']//table",
            "//table[@data-type='month']",
            "//table[contains(@class, 'dataview-body')]//table",
            "//table//tbody//tr",
        ]

        analysts = []
        for selector in table_selectors:
            try:
                if "tr" in selector:
                    # 直接查找表格行
                    rows = WebDriverWait(driver, 5).until(
                        EC.presence_of_all_elements_located((By.XPATH, selector))
                    )
                    logger.info(f"使用选择器 '{selector}' 找到 {len(rows)} 行数据")
                else:
                    # 查找表格
                    table = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    logger.info(f"使用选择器 '{selector}' 找到 {len(rows)} 行数据")

                for i, row in enumerate(rows[1:], 1):  # 跳过表头
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 10:  # 确保有足够的列
                            # 获取分析师名称和链接
                            name_cell = cells[1]
                            name_link = name_cell.find_element(By.TAG_NAME, "a")
                            analyst_name = name_link.text.strip()
                            analyst_url = name_link.get_attribute("href")

                            # 获取机构名称
                            institution = cells[2].text.strip()

                            # 获取其他数据
                            latest_index = cells[3].text.strip()
                            three_month_return = cells[5].text.strip()
                            six_month_return = cells[6].text.strip()
                            twelve_month_return = cells[7].text.strip()
                            stock_count = cells[8].text.strip()
                            latest_rating = cells[9].text.strip()

                            if analyst_name and analyst_url:
                                analyst_info = {
                                    "rank": i,
                                    "name": analyst_name,
                                    "institution": institution,
                                    "url": analyst_url,
                                    "latest_index": latest_index,
                                    "three_month_return": three_month_return,
                                    "six_month_return": six_month_return,
                                    "twelve_month_return": twelve_month_return,
                                    "stock_count": stock_count,
                                    "latest_rating": latest_rating,
                                }
                                analysts.append(analyst_info)
                                logger.info(
                                    f"从表格中提取分析师: {analyst_name} - {institution}"
                                )

                    except Exception as e:
                        logger.error(f"处理第{i}行数据时出错: {str(e)}")
                        continue

                if analysts:
                    break

            except Exception as e:
                logger.warning(f"使用选择器 '{selector}' 失败: {str(e)}")
                continue

        logger.info(f"成功从表格中提取 {len(analysts)} 个分析师数据")
        return analysts
    except Exception as e:
        logger.error(f"从表格中提取分析师数据失败: {str(e)}")
        return []


def save_page_html(driver, filename):
    """保存页面HTML内容"""
    try:
        html_content = driver.page_source
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"页面已保存到: {filename}")
        return True
    except Exception as e:
        logger.error(f"保存页面失败: {str(e)}")
        return False


def save_data_to_csv(data, filename_prefix, output_dir):
    """保存数据到CSV文件"""
    try:
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"{filename_prefix}_{timestamp}.csv")

        if not data:
            logger.warning("没有数据可保存")
            return None

        # 获取所有可能的列名
        fieldnames = set()
        for item in data:
            fieldnames.update(item.keys())
        fieldnames = sorted(fieldnames)

        # 写入CSV文件
        with open(output_file, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for item in data:
                writer.writerow(item)

        logger.info(f"数据已成功保存到: {output_file}")
        logger.info(f"总共保存了 {len(data)} 条数据")
        return output_file
    except Exception as e:
        logger.error(f"保存数据时出错: {str(e)}")
        return None


def scrape_analysts_for_category(driver, category_name, period, output_dir):
    """
    刮取指定类别下的分析师数据并保存到指定目录
    """
    try:
        logger.info(
            f"===== 东方财富分析师数据收集开始 - 类别: {category_name}, 期间: {period} ====="
        )

        # 保存主页面HTML用于分析
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(
            output_dir, f"{category_name}_{period}_{timestamp}.html"
        )
        save_page_html(driver, output_file)

        # 获取分析师链接
        # analysts = get_analyst_links_from_page(driver)
        analysts = extract_analysts_from_table(driver)
        if not analysts:
            logger.error(f"无法获取 {category_name} 类别的分析师链接，跳过此类别")
            return None

        # 保存分析师基本信息
        analyst_file = save_data_to_csv(
            analysts, f"{category_name}_{period}_分析师基本信息", output_dir
        )
        logger.info(f"{category_name} 类别分析师基本信息已保存到: {analyst_file}")

        # 收集每个分析师的跟踪成份股数据
        all_stock_data = []
        for i, analyst in enumerate(analysts, 1):
            logger.info(
                f"\n正在处理第 {i}/{len(analysts)} 个分析师: {analyst['name']} (类别: {category_name}, 期间: {period})"
            )

            try:
                # 访问分析师详情页
                driver.get(analyst["url"])
                time.sleep(3)

                # 保存分析师详情页HTML
                output_file = os.path.join(
                    output_dir,
                    f"analyst_{category_name}_{period}_{i}_{analyst['name']}.html",
                )
                save_page_html(driver, output_file)

                stock_info = {
                    "分析师名称": analyst["name"],
                    "分析师排名": analyst["rank"],
                    "分析师链接": analyst["url"],
                    "处理状态": "页面已保存，待使用Firecrawl提取",
                    "类别": category_name,
                    "期间": period,
                }
                all_stock_data.append(stock_info)

                if i < len(analysts):
                    time.sleep(2)

            except Exception as e:
                logger.error(
                    f"处理分析师 {analyst['name']} (类别: {category_name}, 期间: {period}) 时出错: {str(e)}"
                )
                continue

        # 保存处理状态
        if all_stock_data:
            status_file = save_data_to_csv(
                all_stock_data, f"{category_name}_{period}_分析师处理状态", output_dir
            )
            logger.info(f"\n{category_name} 类别处理状态已保存到: {status_file}")
        else:
            logger.warning(f"{category_name} 类别未能处理任何分析师数据")

        logger.info(
            f"\n{category_name} 类别所有页面HTML已保存，可以使用Firecrawl进行后续结构化提取"
        )
        return all_stock_data

    except Exception as e:
        logger.error(f"刮取 {category_name} 类别数据时出错: {str(e)}")
        return None
    finally:
        logger.info(
            f"===== 东方财富分析师数据收集结束 - 类别: {category_name}, 期间: {period} ====="
        )


def extract_analyst_tracking_stocks(analyst_url, analyst_name, html_file_path=None):
    """
    从分析师HTML文件中提取跟踪成份股数据

    Args:
        analyst_url: 分析师页面URL
        analyst_name: 分析师名称
        html_file_path: 本地HTML文件路径（可选）

    Returns:
        list: 跟踪成份股数据列表
    """
    try:
        logger.info(f"正在提取分析师 {analyst_name} 的跟踪成份股数据...")

        # 读取HTML内容
        if html_file_path and os.path.exists(html_file_path):
            with open(html_file_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            logger.info(f"从本地文件读取HTML内容: {html_file_path}")
        else:
            logger.warning(f"本地HTML文件不存在，将使用URL直接访问: {html_file_path}")
            # 如果没有本地文件，尝试直接访问URL
            response = requests.get(
                analyst_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                },
            )
            html_content = response.text

        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(html_content, "html.parser")

        tracking_data = []

        # 查找所有内容框div
        content_boxes = soup.find_all("div", class_="contentBox")
        logger.info(f"找到 {len(content_boxes)} 个内容框")

        for box in content_boxes:
            # 从标题判断表格类型
            titbar = box.find("div", class_="titbar")
            if titbar:
                tit = titbar.find("div", class_="tit")
                if tit:
                    title_text = tit.get_text().strip()
                    if "历史跟踪成分股" in title_text:
                        table_type = "历史跟踪"
                    elif "最新跟踪成分股" in title_text:
                        table_type = "最新跟踪"
                    else:
                        continue  # 跳过不匹配的框
                else:
                    continue
            else:
                continue

            # 查找表格
            table = box.find("table", class_="table-model")
            if not table:
                continue

            # 解析表格
            rows = table.find_all("tr")
            if not rows:
                continue

            # 获取表头
            header_row = rows[0]
            headers = [
                cell.get_text().strip() for cell in header_row.find_all(["th", "td"])
            ]
            logger.info(f"表头 ({table_type}): {headers}")

            # 处理数据行
            data_rows = rows[1:]
            for row in data_rows:
                cells = row.find_all(["td", "th"])
                if len(cells) != len(headers):
                    continue

                stock_info = {"分析师名称": analyst_name, "股票类型": table_type}

                for i, cell in enumerate(cells):
                    header = headers[i] if i < len(headers) else f"列{i+1}"
                    text = cell.get_text().strip()

                    # 根据具体表头映射字段
                    if header == "序号":
                        pass  # 序号不需要保存
                    elif header == "股票代码":
                        stock_info["股票代码"] = text
                        # 提取股票代码对应的链接
                        link_tag = cell.find("a")
                        if link_tag and link_tag.get("href"):
                            stock_url = link_tag.get("href")
                            if not stock_url.startswith("http"):
                                if stock_url.startswith("//"):
                                    stock_url = "https:" + stock_url
                                elif stock_url.startswith("/"):
                                    stock_url = "https://data.eastmoney.com" + stock_url
                            stock_info["股票链接"] = stock_url
                    elif header == "股票名称":
                        stock_info["股票名称"] = text
                        # 如果股票代码列没有提取到链接，尝试从股票名称列提取
                        if "股票链接" not in stock_info:
                            link_tag = cell.find("a")
                            if link_tag and link_tag.get("href"):
                                stock_url = link_tag.get("href")
                                if not stock_url.startswith("http"):
                                    if stock_url.startswith("//"):
                                        stock_url = "https:" + stock_url
                                    elif stock_url.startswith("/"):
                                        stock_url = (
                                            "https://data.eastmoney.com" + stock_url
                                        )
                                stock_info["股票链接"] = stock_url
                    elif header == "相关链接":
                        pass  # 相关链接是股吧、资金流等，不是股票行情链接
                    elif header == "调入日期":
                        stock_info["调入日期"] = text
                    elif header == "调出日期":
                        stock_info["调出日期"] = text
                    elif header == "调入时评级名称":
                        stock_info["调入时评级名称"] = text
                    elif header == "调出原因":
                        stock_info["调出原因"] = text
                    elif header == "累计涨跌幅":
                        stock_info["累计涨跌幅"] = text
                    elif header == "最新评级日期":
                        stock_info["最新评级日期"] = text
                    elif header == "当前评级名称":
                        stock_info["当前评级名称"] = text
                    elif header == "成交价格(前复权)":
                        stock_info["成交价格(前复权)"] = text
                    elif header == "最新价格":
                        stock_info["最新价格"] = text
                    elif header == "阶段涨跌幅":
                        stock_info["阶段涨跌幅"] = text
                    else:
                        # 保留其他字段
                        stock_info[header] = text

                # 检查是否为有效的股票数据记录
                # 有效记录应该有股票代码或股票名称
                has_stock_code = bool(stock_info.get("股票代码"))
                has_stock_name = bool(stock_info.get("股票名称"))

                if has_stock_code or has_stock_name:
                    tracking_data.append(stock_info)

        logger.info(
            f"成功提取分析师 {analyst_name} 的 {len(tracking_data)} 条跟踪成份股数据"
        )
        return tracking_data

    except Exception as e:
        logger.error(f"提取分析师 {analyst_name} 的跟踪成份股数据时出错: {str(e)}")
        return []


def save_data_to_html(data, filename_prefix, output_dir):
    """保存数据到HTML文件，包含最新跟踪和历史跟踪两个表格，以及分析师重点关注股票"""
    try:
        # 确保输出目录存在
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        if not data:
            logger.warning("没有数据可保存")
            return None

        # 根据股票类型分组数据，并移除不需要的列
        current_tracking_data = []
        history_tracking_data = []
        for item in data:
            # 创建新字典，排除不需要的列
            filtered_item = {
                k: v
                for k, v in item.items()
                if k not in ["股票类型", "类别", "期间", "分析师链接", "数据来源文件"]
            }
            if item.get("股票类型") == "最新跟踪":
                current_tracking_data.append(filtered_item)
            elif item.get("股票类型") == "历史跟踪":
                history_tracking_data.append(filtered_item)

        # 统计最新跟踪成份股，按股票代码分组
        stock_stats = {}
        for item in current_tracking_data:
            stock_code = item.get("股票代码", "")
            if stock_code:
                if stock_code not in stock_stats:
                    stock_stats[stock_code] = {
                        "analyst_count": 0,
                        "stock_name": item.get("股票名称", ""),
                        "stock_url": item.get("股票链接", ""),
                        "trade_prices": [],
                        "latest_price": "",  # 只取第一个最新价格
                        "analysts": [],
                    }

                # 更新分析师数量和列表
                analyst_name = item.get("分析师名称", "")
                if analyst_name not in stock_stats[stock_code]["analysts"]:
                    stock_stats[stock_code]["analysts"].append(analyst_name)
                    stock_stats[stock_code]["analyst_count"] += 1

                # 收集成交价格
                trade_price_str = item.get("成交价格(前复权)", "")
                if (
                    trade_price_str
                    and trade_price_str != ""
                    and trade_price_str != "--"
                ):
                    try:
                        trade_price = float(trade_price_str)
                        stock_stats[stock_code]["trade_prices"].append(trade_price)
                    except ValueError:
                        pass  # 如果无法转换为数字则跳过

                # 只取第一个最新价格，如果还没有设置的话
                latest_price_str = item.get("最新价格", "")
                if (
                    latest_price_str
                    and latest_price_str != ""
                    and latest_price_str != "--"
                    and not stock_stats[stock_code]["latest_price"]
                ):
                    stock_stats[stock_code]["latest_price"] = latest_price_str

        # 计算统计信息并按分析师数量排序
        stock_stats_list = []
        for stock_code, stats in stock_stats.items():
            if stats["trade_prices"]:
                avg_trade_price = sum(stats["trade_prices"]) / len(
                    stats["trade_prices"]
                )
                max_trade_price = max(stats["trade_prices"])
                min_trade_price = min(stats["trade_prices"])
            else:
                avg_trade_price = 0
                max_trade_price = 0
                min_trade_price = 0

            # 使用第一个最新价格
            latest_price = stats["latest_price"] if stats["latest_price"] else ""

            stock_info = {
                "分析师个数": stats["analyst_count"],
                "股票代码": stock_code,
                "股票名称": stats["stock_name"],
                "股票链接": stats["stock_url"],
                "平均成交价格": (
                    round(avg_trade_price, 2) if avg_trade_price != 0 else 0
                ),
                "最高成交价格": max_trade_price,
                "最低成交价格": min_trade_price,
                "最新价格": latest_price,
            }
            stock_stats_list.append(stock_info)

        # 按分析师个数从大到小排序，取前20名
        stock_stats_list.sort(key=lambda x: x["分析师个数"], reverse=True)
        top_20_stocks = stock_stats_list[:20]

        # 生成时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_file = os.path.join(output_dir, f"{filename_prefix}_{timestamp}.html")

        # 生成HTML内容
        html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #3;
            text-align: center;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #5;
            margin-top: 30px;
            border-left: 4px solid #2196F3;
            padding-left: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 14px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
            word-wrap: break-word;
        }}
        th {{
            background-color: #f2f2f2;
            font-weight: bold;
            position: sticky;
            top: 0;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        tr:hover {{
            background-color: #f5f5;
        }}
        .stock-link {{
            color: #1976D2;
            text-decoration: none;
        }}
        .stock-link:hover {{
            text-decoration: underline;
        }}
        .no-data {{
            text-align: center;
            padding: 20px;
            color: #66;
            font-style: italic;
        }}
        .summary {{
            background-color: #e8f5e8;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .summary h3 {{
            margin-top: 0;
            color: #2e7d32;
        }}
        .summary p {{
            margin: 5px 0;
        }}
        .data-link {{
            text-align: center;
            margin-bottom: 20px;
        }}
        .data-link a {{
            color: #1976D2;
            text-decoration: none;
            font-size: 16px;
            font-weight: bold;
        }}
        .data-link a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>

        <div class="data-source-link" style="text-align: center; margin-bottom: 20px;">
            <a href="https://data.eastmoney.com/invest/invest/list.html" target="_blank" style="color: #1976D2; text-decoration: none; font-size: 16px; font-weight: bold;">东方财富分析师数据源</a>
        </div>

        <div class="summary">
            <h3>数据摘要</h3>
            <p>总记录数: {total_count}</p>
            <p>最新跟踪: {current_count} 条</p>
            <p>历史跟踪: {history_count} 条</p>
            <p>分析师数量: {analyst_count} 个</p>
        </div>

        <h2>分析师重点关注股票（按分析师持有数量排序，前20名）</h2>
        <table>
            <thead>
                <tr>
                    <th>分析师个数</th>
                    <th>股票代码</th>
                    <th>股票名称</th>
                    <th>股票链接</th>
                    <th>平均成交价格</th>
                    <th>最高成交价格</th>
                    <th>最低成交价格</th>
                    <th>最新价格</th>
                </tr>
            </thead>
            <tbody>
""".format(
            title=f"{filename_prefix} - 分析师跟踪成份股数据",
            total_count=len(data),
            current_count=len(current_tracking_data),
            history_count=len(history_tracking_data),
            analyst_count=len(set([item["分析师名称"] for item in data])),
        )

        # 添加分析师重点关注股票表格数据
        for stock in top_20_stocks:
            html_content += f"""                <tr>
                    <td>{stock['分析师个数']}</td>
                    <td>{stock['股票代码']}</td>
                    <td>{stock['股票名称']}</td>
                    <td><a href="{stock['股票链接']}" target="_blank" class="stock-link">{stock['股票链接']}</a></td>
                    <td>{stock['平均成交价格']}</td>
                    <td>{stock['最高成交价格']}</td>
                    <td>{stock['最低成交价格']}</td>
                    <td>{stock['最新价格']}</td>
                </tr>
"""

        html_content += """            </tbody>
        </table>
"""

        # 添加最新跟踪数据表格
        if current_tracking_data:
            html_content += """
        <h2>最新跟踪成份股</h2>
        <table>
            <thead>
                <tr>
"""
            # 获取列名并生成表头
            if current_tracking_data:
                fieldnames = sorted(
                    set().union(*(d.keys() for d in current_tracking_data))
                )
                for field in fieldnames:
                    html_content += f"                    <th>{field}</th>\n"

            html_content += """                </tr>
            </thead>
            <tbody>
"""
            # 添加数据行
            for item in current_tracking_data:
                html_content += "                <tr>\n"
                for field in fieldnames:
                    value = item.get(field, "")
                    if field == "股票链接" and value:
                        html_content += f'                    <td><a href="{value}" target="_blank" class="stock-link">{value}</a></td>\n'
                    elif field == "数据来源文件" and value:
                        html_content += f'                    <td><a href="{value}" target="_blank" class="stock-link">{os.path.basename(value)}</a></td>\n'
                    else:
                        html_content += f"                    <td>{value}</td>\n"
                html_content += "                </tr>\n"

            html_content += """            </tbody>
        </table>
"""
        else:
            html_content += """
        <h2>最新跟踪成份股</h2>
        <div class="no-data">暂无最新跟踪成份股数据</div>
"""

        # 添加历史跟踪数据表格
        if history_tracking_data:
            html_content += """
        <h2>历史跟踪成份股</h2>
        <table>
            <thead>
                <tr>
"""
            # 获取列名并生成表头
            if history_tracking_data:
                fieldnames = sorted(
                    set().union(*(d.keys() for d in history_tracking_data))
                )
                for field in fieldnames:
                    html_content += f"                    <th>{field}</th>\n"

            html_content += """                </tr>
            </thead>
            <tbody>
"""
            # 添加数据行
            for item in history_tracking_data:
                html_content += "                <tr>\n"
                for field in fieldnames:
                    value = item.get(field, "")
                    if field == "股票链接" and value:
                        html_content += f'                    <td><a href="{value}" target="_blank" class="stock-link">{value}</a></td>\n'
                    elif field == "数据来源文件" and value:
                        html_content += f'                    <td><a href="{value}" target="_blank" class="stock-link">{os.path.basename(value)}</a></td>\n'
                    else:
                        html_content += f"                    <td>{value}</td>\n"
                html_content += "                </tr>\n"

            html_content += """            </tbody>
        </table>
"""
        else:
            html_content += """
        <h2>历史跟踪成份股</h2>
        <div class="no-data">暂无历史跟踪成份股数据</div>
"""

        html_content += """
    </div>
</body>
</html>
"""

        # 写入HTML文件
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"HTML文件已成功保存到: {html_file}")
        return html_file

    except Exception as e:
        logger.error(f"保存HTML数据时出错: {str(e)}")
        return None


def save_data_to_excel(data, filename_prefix, output_dir):
    """保存数据到Excel文件，包含最新跟踪和历史跟踪两个工作表"""
    try:
        # 确保输出目录存在
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        if not data:
            logger.warning("没有数据可保存")
            return None

        # 根据股票类型分组数据，但不包含股票类型列
        current_tracking_data = []
        history_tracking_data = []
        for item in data:
            # 创建新字典，排除股票类型列
            filtered_item = {k: v for k, v in item.items() if k != "股票类型"}
            if item.get("股票类型") == "最新跟踪":
                current_tracking_data.append(filtered_item)
            elif item.get("股票类型") == "历史跟踪":
                history_tracking_data.append(filtered_item)

        # 定义固定的列名顺序
        fieldnames = [
            "分析师名称",
            "分析师排名",
            "股票代码",
            "股票名称",
            "股票链接",
            "当前价格",
            "成交价格(前复权)",
            "最新价格",
            "涨跌幅",
            "阶段涨跌幅",
            "累计涨跌幅",
            "调入日期",
            "调出日期",
            "最新评级日期",
            "调入时评级名称",
            "当前评级名称",
            "调出原因",
            "目标价",
            "评级",
            "数据来源",
        ]

        # 生成时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_file = os.path.join(output_dir, f"{filename_prefix}_{timestamp}.xlsx")

        # 创建Excel写入器
        with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:

            # 保存最新跟踪数据到工作表
            if current_tracking_data:
                current_df = create_dataframe(current_tracking_data, fieldnames)
                current_df.to_excel(writer, sheet_name="最新跟踪", index=False)
                logger.info(
                    f"最新跟踪数据已保存到工作表: 共 {len(current_tracking_data)} 条"
                )

            # 保存历史跟踪数据到工作表
            if history_tracking_data:
                history_df = create_dataframe(history_tracking_data, fieldnames)
                history_df.to_excel(writer, sheet_name="历史跟踪", index=False)
                logger.info(
                    f"历史跟踪数据已保存到工作表: 共 {len(history_tracking_data)} 条"
                )

        logger.info(f"Excel文件已成功保存到: {excel_file}")
        return excel_file

    except Exception as e:
        logger.error(f"保存Excel数据时出错: {str(e)}")
        return None


def create_dataframe(data, fieldnames):
    """从数据列表创建DataFrame"""
    rows = []
    for item in data:
        row_data = create_csv_row(item, fieldnames)
        rows.append(row_data)

    return pd.DataFrame(rows, columns=fieldnames)


def create_csv_row(item, fieldnames):
    """创建CSV行数据，处理特殊字段格式"""
    row_data = {}
    for field in fieldnames:
        if field in item:
            # 处理股票代码，确保保留前导零
            if field == "股票代码" and item[field]:
                stock_code = str(item[field])
                # 确保股票代码是6位数字，不足6位在前面补零
                if len(stock_code) < 6:
                    stock_code = stock_code.zfill(6)
                row_data[field] = stock_code
            # 处理数据来源URL格式
            elif field == "数据来源" and item[field]:
                url = item[field]
                # 修正URL格式
                if "data.eastmoney.com" in url:
                    # 提取data.eastmoney.com及之后的部分
                    match = re.search(r"(data\.eastmoney\.com.*)", url)
                    if match:
                        row_data[field] = "https://" + match.group(1)
                    else:
                        row_data[field] = url
                else:
                    row_data[field] = url
            else:
                row_data[field] = item[field]
        else:
            row_data[field] = ""
    return row_data


def detect_analyst_html_files(category_name, period, processed_dir):
    """检测指定目录下的分析师HTML文件，按类别和期间过滤"""
    try:
        logger.info(
            f"正在检测分析师HTML文件 (类别: {category_name}, 期间: {period})..."
        )

        # 查找所有analyst开头的HTML文件，匹配指定类别和期间
        all_analyst_files = glob.glob(
            os.path.join(processed_dir, f"analyst_{category_name}_{period}_*.html")
        )
        logger.info(
            f"找到 {len(all_analyst_files)} 个分析师HTML文件 (类别: {category_name}, 期间: {period})"
        )

        analysts = []
        for file_path in all_analyst_files:
            try:
                # 从文件名中提取分析师信息
                # 文件名格式: analyst_{category}_{period}_{rank}_{name}.html
                filename = os.path.basename(file_path)
                # 移除 .html 扩展名
                name_part = filename[:-5]  # 移除 .html

                # 分割文件名部分
                parts = name_part.split("_")
                if len(parts) >= 5:  # 至少有 analyst, category, period, rank, name
                    try:
                        # 从后部分提取排名和姓名
                        rank_str = parts[-2]  # 倒数第二个是排名
                        name = "_".join(parts[4:])  # 中间的部分是姓名（可能包含下划线）

                        # 验证排名是否为数字
                        rank = int(rank_str)

                        analyst_info = {
                            "name": name,
                            "url": f"https://data.eastmoney.com/invest/analyst/{rank}.html",
                            "rank": rank,
                            "html_file": file_path,
                            "category": category_name,
                            "period": period,
                        }
                        analysts.append(analyst_info)
                        logger.info(
                            f"检测到分析师: {name} (排名: {rank}, 文件: {file_path}, 类别: {category_name}, 期间: {period})"
                        )
                    except ValueError:
                        # 如果排名不是数字，跳过这个文件
                        logger.warning(f"文件名格式不正确，无法提取排名: {filename}")
                        continue
                else:
                    logger.warning(f"文件名格式不正确: {filename}")
                    continue

            except Exception as e:
                logger.error(f"解析文件 {file_path} 时出错: {str(e)}")
                continue

        # 按排名排序
        analysts.sort(key=lambda x: x["rank"])
        logger.info(
            f"成功检测到 {len(analysts)} 个分析师 (类别: {category_name}, 期间: {period})"
        )
        return analysts

    except Exception as e:
        logger.error(f"检测分析师HTML文件时出错: {str(e)}")
        return []


def extract_and_save_analyst_data(category_name, period, processed_dir, output_dir):
    """
    提取分析师跟踪成份股数据并保存到Excel文件。
    从指定的processed_dir读取HTML文件，将最终结果保存到output_dir
    """
    try:
        logger.info(
            f"===== Firecrawl分析师跟踪成份股数据提取开始 - 类别: {category_name}, 期间: {period} ====="
        )

        # 检测processed_dir目录下的分析师HTML文件
        analysts = detect_analyst_html_files(category_name, period, processed_dir)

        if not analysts:
            logger.warning(
                f"未找到任何分析师HTML文件 (类别: {category_name}, 期间: {period})，请确保已运行爬虫部分"
            )
            return None

        all_tracking_data = []

        # 提取每个分析师的跟踪成份股数据
        for analyst in analysts:
            logger.info(
                f"\n正在处理分析师: {analyst['name']} (排名: {analyst['rank']}, 类别: {analyst['category']}, 期间: {analyst['period']})"
            )

            tracking_data = extract_analyst_tracking_stocks(
                analyst["url"], analyst["name"], analyst.get("html_file")
            )

            # 添加分析师排名和类别信息
            for stock in tracking_data:
                stock["分析师名称"] = analyst["name"]  # 确保分析师名称被正确设置
                stock["分析师排名"] = analyst["rank"]
                stock["分析师链接"] = analyst["url"]
                stock["类别"] = analyst.get("category", "无")
                stock["期间"] = analyst.get("period", "无")
                if analyst.get("html_file"):
                    stock["数据来源文件"] = analyst["html_file"]

            all_tracking_data.extend(tracking_data)

            # 避免请求过于频繁
            time.sleep(1)

        # 保存跟踪成份股数据
        if all_tracking_data:
            filename_prefix = f"{category_name}_{period}_东方财富分析师跟踪成份股"
            excel_file = save_data_to_excel(
                all_tracking_data, filename_prefix, output_dir
            )
            html_file = save_data_to_html(
                all_tracking_data, filename_prefix, output_dir
            )
            if excel_file:
                logger.info(f"\n数据提取完成！结果已保存到Excel文件: {excel_file}")
                logger.info("Excel文件包含两个工作表:")
                logger.info(" - '最新跟踪': 包含当前正在跟踪的股票数据")
                logger.info("  - '历史跟踪': 包含历史跟踪过的股票数据")
            if html_file:
                logger.info(f"数据提取完成！结果已保存到HTML文件: {html_file}")
                logger.info("HTML文件包含两个表格:")
                logger.info(" - '最新跟踪': 包含当前正在跟踪的股票数据")
                logger.info(" - '历史跟踪': 包含历史跟踪过的股票数据")

            # 显示数据统计
            analyst_count = len(set([item["分析师名称"] for item in all_tracking_data]))
            stock_count = len(all_tracking_data)

            # 按股票类型统计
            current_count = len(
                [
                    item
                    for item in all_tracking_data
                    if item.get("股票类型") == "最新跟踪"
                ]
            )
            history_count = len(
                [
                    item
                    for item in all_tracking_data
                    if item.get("股票类型") == "历史跟踪"
                ]
            )

            logger.info(
                f"共处理了 {analyst_count} 个分析师的 {stock_count} 条跟踪成份股数据 (类别: {category_name}, 期间: {period})"
            )
            logger.info(
                f"其中: 最新跟踪 {current_count} 条, 历史跟踪 {history_count} 条"
            )

            # 显示处理的分析师列表
            analyst_names = sorted(
                set([item["分析师名称"] for item in all_tracking_data])
            )
            logger.info(f"处理的分析师: {', '.join(analyst_names)}")
        else:
            logger.warning(
                f"未能提取到任何跟踪成份股数据 (类别: {category_name}, 期间: {period})"
            )

        return all_tracking_data

    except Exception as e:
        logger.error(f"程序执行出错 (类别: {category_name}, 期间: {period}): {str(e)}")
        return None
    finally:
        logger.info(
            f"===== Firecrawl分析师跟踪成份股数据提取结束 - 类别: {category_name}, 期间: {period} ====="
        )


def main():
    driver = None
    try:
        logger.info("===== 东方财富分析师数据采集整合脚本开始执行 =====")

        # 获取命令行参数
        # 定义行业类别选项（共 31 个）
        categors = [
            "全部",
            "农林牧渔",
            "基础化工",
            "钢铁",
            "有色金属",
            "电子",
            "汽车",
            "家用电器",
            "食品饮料",
            "纺织服饰",
            "轻工制造",
            "医药生物",
            "公用事业",
            "交通运输",
            "房地产",
            "商贸零售",
            "社会服务",
            "银行",
            "非银金融",
            "建筑材料",
            "建筑装饰",
            "电力设备",
            "机械设备",
            "国防军工",
            "计算机",
            "传媒",
            "通信",
            "煤炭",
            "石油石化",
            "环保",
            "美容护理",
        ]

        # 定义时间段选项
        periods = [
            "2025 年度排行",
            "最新总排行",
            "3 个月排行",
            "6 个月排行",
            "12 个月排行",
        ]

        # 获取命令行参数，若未提供则交互式提示用户
        if len(sys.argv) < 3:
            # 交互式选择
            print("\n" + "=" * 60)
            print("东方财富分析师数据自动化采集 - 行业类别选择")
            print("=" * 60)
            for i, cat in enumerate(categors):
                print(f"  {i:2d}. {cat}")
            print("=" * 60)

            while True:
                try:
                    category_input = input(
                        f"请选择行业类别 (输入数字 0-{len(categors)-1}): "
                    ).strip()
                    category_index = int(category_input)
                    if 0 <= category_index < len(categors):
                        break
                    else:
                        print(f"输入无效，请输入 0-{len(categors)-1} 之间的数字")
                except ValueError:
                    print("输入无效，请输入数字")

            print("\n" + "=" * 60)
            print("时间段选择")
            print("=" * 60)
            for i, period in enumerate(periods):
                print(f"  {i}. {period}")
            print("=" * 60)

            while True:
                try:
                    period_input = input(
                        f"请选择时间段 (输入数字 0-{len(periods)-1}): "
                    ).strip()
                    period_index = int(period_input)
                    if 0 <= period_index < len(periods):
                        break
                    else:
                        print(f"输入无效，请输入 0-{len(periods)-1} 之间的数字")
                except ValueError:
                    print("输入无效，请输入数字")
        else:
            category_index = int(sys.argv[1])
            period_index = int(sys.argv[2])

            # 验证参数范围
            if category_index < 0 or category_index >= len(categors):
                logger.error(f"类别索引超出范围。有效范围：0-{len(categors)-1}")
                return
            if period_index < 0 or period_index >= len(periods):
                logger.error(f"期间索引超出范围。有效范围：0-{len(periods)-1}")
                return

        category = categors[category_index]
        period = periods[period_index]

        logger.info(f"开始处理类别: {category}, 期间: {period}")

        # 创建主输出目录
        main_output_dir = get_path("crawlers", "analyst_data_dir")
        # 创建本次运行的处理目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        processed_dir = os.path.join(main_output_dir, f"processed_{timestamp}")
        if not os.path.exists(processed_dir):
            os.makedirs(processed_dir)

        # 启动浏览器
        driver = setup_driver()

        # 导航到目标页面并点击指定时间段
        if not navigate_and_click_rank_period(driver, period, category):
            logger.error("无法打开目标页面，程序终止")
            return

        # 采集数据
        scrape_result = scrape_analysts_for_category(
            driver, category, period, processed_dir
        )
        if not scrape_result:
            logger.warning(f"未能采集到 {category} 类别的数据")
            return

        logger.info(f"数据采集完成，中间文件已保存到: {processed_dir}")

        # 提取数据并生成Excel
        extract_result = extract_and_save_analyst_data(
            category, period, processed_dir, main_output_dir
        )
        if not extract_result:
            logger.warning(f"未能提取 {category} 类别的数据")
            return

        logger.info(f"数据处理完成，最终Excel文件已保存到: {main_output_dir}")

    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}")
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("浏览器已关闭")
            except:
                pass
        logger.info("===== 东方财富分析师数据采集整合脚本执行结束 =====")


if __name__ == "__main__":
    main()
