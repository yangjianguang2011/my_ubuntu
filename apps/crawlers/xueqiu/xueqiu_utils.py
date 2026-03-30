"""
雪球爬虫工具类 - 提取通用工具方法
"""

import re
import time
import random
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from selenium.webdriver.common.by import By

def parse_relative_time(time_text: str) -> Optional[datetime]:
    """
    解析相对时间格式，如"2小时前"、"13分钟前"、"昨天"、"修改于昨天"等
    统一返回datetime对象或None
    """
    if not time_text:
        return None

    now = datetime.now()

    # 处理"修改于昨天"等格式
    modified_match = re.search(r'修改于(.+)', time_text)
    if modified_match:
        time_text = modified_match.group(1)

    # 优先匹配完整日期格式 "2025-12-21 09:53"
    full_date_match = re.search(r'(\d{4}-\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{2})', time_text)
    if full_date_match:
        date_str = full_date_match.group(1)
        time_str = full_date_match.group(2)
        try:
            parsed_datetime = datetime.strptime(date_str + " " + time_str, "%Y-%m-%d %H:%M")
            return parsed_datetime
        except ValueError:
            pass  # 如果解析失败，继续尝试其他格式

    # 匹配"昨天 HH:MM"格式
    yesterday_match = re.search(r'昨天\s+(\d{1,2}:\d{2})', time_text)
    if yesterday_match:
        time_str = yesterday_match.group(1)
        # 昨天的日期
        yesterday_date = now.date() - timedelta(days=1)
        # 组合成完整时间
        return datetime.combine(yesterday_date, datetime.strptime(time_str, "%H:%M").time())

    # 匹配"01-20 13:15"等格式
    date_time_match = re.search(r'(\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{2})', time_text)
    if date_time_match:
        date_str = date_time_match.group(1)
        time_str = date_time_match.group(2)
        # 补全年份
        full_date_str = f"{now.year}-{date_str}"
        try:
            parsed_datetime = datetime.strptime(full_date_str + " " + time_str, "%Y-%m-%d %H:%M")
            return parsed_datetime
        except ValueError:
            pass  # 如果解析失败，继续尝试其他格式

    # 匹配"2小时前"格式
    hour_match = re.search(r'(\d+)\s*小时前', time_text)
    if hour_match:
        hours_ago = int(hour_match.group(1))
        return now - timedelta(hours=hours_ago)

    # 匉配"13分钟前"格式
    minute_match = re.search(r'(\d+)\s*分钟前', time_text)
    if minute_match:
        minutes_ago = int(minute_match.group(1))
        return now - timedelta(minutes=minutes_ago)

    # 匹配"今天"、"刚刚"等格式
    if '今天' in time_text or '刚刚' in time_text:
        return now

    return None

def convert_to_absolute_time(time_text: str) -> str:
    """
    将相对时间转换为绝对时间字符串
    如："2小时前" -> "2024-01-15 10:30"
    """
    if not time_text:
        return time_text

    now = datetime.now()

    # 处理"修改于昨天"等格式
    modified_match = re.search(r'修改于(.+)', time_text)
    if modified_match:
        time_text = modified_match.group(1)

    # 优先匹配完整日期格式 "2025-12-21 09:53"
    full_date_match = re.search(r'(\d{4}-\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{2})', time_text)
    if full_date_match:
        date_str = full_date_match.group(1)
        time_str = full_date_match.group(2)
        try:
            parsed_datetime = datetime.strptime(date_str + " " + time_str, "%Y-%m-%d %H:%M")
            return parsed_datetime.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass  # 如果解析失败，继续尝试其他格式

    # 匹配"昨天 HH:MM"格式
    yesterday_match = re.search(r'昨天\s+(\d{1,2}:\d{2})', time_text)
    if yesterday_match:
        time_str = yesterday_match.group(1)
        # 昨天的日期
        yesterday_date = now.date() - timedelta(days=1)
        # 组合成完整时间
        parsed_datetime = datetime.combine(yesterday_date, datetime.strptime(time_str, "%H:%M").time())
        return parsed_datetime.strftime("%Y-%m-%d %H:%M")

    # 匹配"01-20 13:15"等格式
    date_time_match = re.search(r'(\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{2})', time_text)
    if date_time_match:
        date_str = date_time_match.group(1)
        time_str = date_time_match.group(2)
        # 补全年份
        full_date_str = f"{now.year}-{date_str}"
        try:
            parsed_datetime = datetime.strptime(full_date_str + " " + time_str, "%Y-%m-%d %H:%M")
            return parsed_datetime.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass  # 如果解析失败，继续尝试其他格式

    # 匹配"2小时前"格式
    hour_match = re.search(r'(\d+)\s*小时前', time_text)
    if hour_match:
        hours_ago = int(hour_match.group(1))
        parsed_datetime = now - timedelta(hours=hours_ago)
        return parsed_datetime.strftime("%Y-%m-%d %H:%M")

    # 匹配"13分钟前"格式
    minute_match = re.search(r'(\d+)\s*分钟前', time_text)
    if minute_match:
        minutes_ago = int(minute_match.group(1))
        parsed_datetime = now - timedelta(minutes=minutes_ago)
        return parsed_datetime.strftime("%Y-%m-%d %H:%M")

    # 匹配"今天"、"刚刚"等格式
    if '今天' in time_text or '刚刚' in time_text:
        return now.strftime("%Y-%m-%d %H:%M")

    # 如果已经是标准格式，直接返回
    return time_text

def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符"""
    illegal_chars = r'[<>:"/\\|?*]'
    cleaned = re.sub(illegal_chars, '', filename)
    cleaned = cleaned.strip()
    if len(cleaned) > 100:
        cleaned = cleaned[:100]
    return cleaned or "untitled"

def human_like_delay(min_sec: float = 0.5, max_sec: float = 1.5) -> None:
    """随机延迟模拟人类操作"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(int(delay * 10) / 10)  # 转换为浮点数但保留一位小数

def get_month_from_time(time_text: str) -> str:
    """从时间文本中提取年月信息"""
    now = datetime.now()
    year_month = now.strftime("%Y-%m")

    if time_text:
        try:
            # 首先处理"修改于"前缀
            time_text_clean = time_text
            if '修改于' in time_text:
                time_text_clean = time_text.replace('修改于', '').strip()

            # 优先匹配 2025-12-21 完整日期格式
            match = re.search(r'(\d{4})-(\d{1,2})-\d{1,2}', time_text_clean)
            if match:
                year = match.group(1)
                month = match.group(2).zfill(2)
                year_month = f"{year}-{month}"
            # 匹配 2025-01 格式
            elif re.search(r'(\d{4})[-/年](\d{1,2})', time_text_clean):
                match = re.search(r'(\d{4})[-/年](\d{1,2})', time_text_clean)
                if match:
                    year = match.group(1)
                    month = match.group(2).zfill(2)
                    year_month = f"{year}-{month}"
            # 匹配 01-18 格式（假设是当年）
            elif re.search(r'(\d{1,2})-(\d{1,2})', time_text_clean):
                match = re.search(r'(\d{1,2})-(\d{1,2})', time_text_clean)
                if match:
                    month = match.group(1).zfill(2)
                    year_month = f"{now.year}-{month}"

        except Exception as e:
            pass  # 解析失败时使用当前月份

    return year_month

def is_content_truncated(content: str) -> bool:
    """检查内容是否被截断"""
    return content.endswith('...') or '...' in content.split()[-1]

def find_expand_button(element: Any) -> Optional[Any]:
    """查找展开按钮"""
    expand_selectors = [
        '.timeline__expand__control',
        '.timeline__unfold__control',
        'a:has-text("展开")',
        'button:has-text("展开")',
        'span:has-text("展开")',
        'div:has-text("展开")',
        'a[href="javascript:;"][class*="expand"]',
        'a[class*="unfold"]',
        'div[class*="expand"]',
        'div[class*="unfold"]',
        # XPath选择器作为备选
        '//a[contains(text(), "展开")]',
        '//button[contains(text(), "展开")]',
        '//span[contains(text(), "展开")]/parent::a',
        '//div[contains(text(), "展开")]/parent::a',
    ]

    for selector in expand_selectors:
        try:
            btn = element.find_element(By.CSS_SELECTOR, selector)
            if btn.is_displayed() and ('展开' in btn.text or '全文' in btn.text or '阅读全文' in btn.text):
                return btn
        except:
            try:
                # 尝试XPath选择器
                if selector.startswith('//'):
                    btn = element.find_element(By.XPATH, selector)
                    if btn.is_displayed() and ('展开' in btn.text or '全文' in btn.text):
                        return btn
            except:
                continue
    return None
