"""
雪球大V文章抓取工具 - Selenium 版本
功能：
1. 自动登录雪球（保存 Cookies）
2. 获取所有关注的人（处理分页）
3. 遍历每个关注的人，获取所有原发文章
4. 按作者分目录保存为 Markdown 文件
5. 基于文件存在判断去重
"""

import argparse
import json
import re
import time
import random
from pathlib import Path
from datetime import datetime, date, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from logger_config import setup_logger, gconfig

logger = setup_logger('xueqiu_selenium_scraper')


class XueqiuSeleniumScraper:
    def __init__(self, headless=False):
        self.cookies_file = "xueqiu_cookies.json"
        self.output_dir = gconfig.get('xueqiu_data_dir', '/data/stock_monitor/xueqiu_data')
        self.base_dir = Path(self.output_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.update_today = True  # 默认启用只更新当天模式
        
        self.scraped_authors_file = self.base_dir / "scraped_authors.json"
        self.scraped_authors = self._load_scraped_authors()
        
        self.driver = self._init_driver(headless)
        self.wait = WebDriverWait(self.driver, 10)
    
    def _init_driver(self, headless):
        """初始化 Chrome 驱动"""
        options = Options()
        
        # 无头模式配置
        if headless:
            options.add_argument('--headless=new')
        
        # 基础配置
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # 无头模式专用配置
        if headless:
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-images')
            options.add_argument('--disable-javascript')
            options.add_argument('--disable-logging')
            options.add_argument('--no-first-run')
            options.add_argument('--no-default-browser-check')
            options.add_argument('--lang=zh-CN')
            options.add_argument('--window-size=1920,1080')
        else:
            # 有头模式配置
            options.add_argument('--start-maximized')
        
        # User-Agent
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            driver = webdriver.Chrome(options=options)
            # 修改 navigator.webdriver 属性
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("浏览器初始化成功")
            return driver
        except Exception as e:
            logger.error(f"浏览器初始化失败: {e}")
            logger.error("请确保已安装Chrome浏览器和对应的ChromeDriver")
            logger.error("在无头模式下运行时，需要确保环境满足以下要求:")
            logger.error("1. 已安装Chrome浏览器")
            logger.error("2. 已安装对应版本的ChromeDriver")
            logger.error("3. 系统有足够权限运行Chrome")
            raise

    def _load_scraped_authors(self):
        """加载已抓取的作者列表"""
        if self.scraped_authors_file.exists():
            try:
                with open(self.scraped_authors_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载已抓取作者列表失败: {e}")
        return {}

    def _save_scraped_authors(self):
        """保存已抓取的作者列表"""
        try:
            with open(self.scraped_authors_file, 'w', encoding='utf-8') as f:
                json.dump(self.scraped_authors, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存已抓取作者列表失败: {e}")

    def _load_cookies(self):
        """加载已保存的cookies"""
        if Path(self.cookies_file).exists():
            try:
                # 先访问域名，否则会报域名不匹配错误
                self.driver.get('https://xueqiu.com')
                
                with open(self.cookies_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                    for cookie in cookies:
                        try:
                            # 只添加 xueqiu.com 域名的 cookies
                            if 'domain' in cookie and 'xueqiu' in cookie['domain']:
                                self.driver.add_cookie(cookie)
                        except Exception as e:
                            logger.debug(f"添加 cookie 失败: {e}")
                    return True
            except Exception as e:
                logger.warning(f"加载 cookies 失败: {e}")
        return False

    def _parse_relative_time(self, time_text):
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

        # 匹配"13分钟前"格式
        minute_match = re.search(r'(\d+)\s*分钟前', time_text)
        if minute_match:
            minutes_ago = int(minute_match.group(1))
            return now - timedelta(minutes=minutes_ago)

        # 匹配"今天"、"刚刚"等格式
        if '今天' in time_text or '刚刚' in time_text:
            return now

        return None

    def _save_cookies(self):
        """保存cookies"""
        try:
            cookies = self.driver.get_cookies()
            with open(self.cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            logger.info(f"Cookies 已保存到 {self.cookies_file}")
        except Exception as e:
            logger.warning(f"保存 cookies 失败: {e}")

    def _human_like_delay(self, min_sec=0.5, max_sec=1.5):
        """随机延迟模拟人类操作"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(int(delay * 10) / 10)  # 转换为浮点数但保留一位小数

    def sanitize_filename(self, filename):
        """清理文件名，移除非法字符"""
        illegal_chars = r'[<>:"/\\|?*]'
        cleaned = re.sub(illegal_chars, '', filename)
        cleaned = cleaned.strip()
        if len(cleaned) > 100:
            cleaned = cleaned[:100]
        return cleaned or "untitled"

    def get_following_authors(self):
        """获取所有关注的人（处理分页）"""
        logger.info("开始获取关注列表...")
        
        self.driver.get('https://xueqiu.com/center/#/friends')
        self._human_like_delay(3, 5)

        authors = []
        page_num = 1
        max_pages = 10
        
        while page_num <= max_pages:
            logger.info(f"正在获取第 {page_num} 页关注列表...")
            
            self._human_like_delay(1, 2)
            
            try:
                # 等待用户卡片加载
                author_cards = self.wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.profiles__user__card'))
                )
                
                logger.info(f"找到 {len(author_cards)} 个用户卡片")
                
                new_authors_this_page = 0
                for card in author_cards:
                    try:
                        # 提取作者名称和链接
                        name_elem = card.find_element(By.CSS_SELECTOR, '.user-name')
                        name = name_elem.text.strip()
                        
                        # 获取链接
                        link_elem = card.find_element(By.CSS_SELECTOR, 'a.user-name')
                        link = link_elem.get_attribute('href')
                        
                        if link and not link.startswith('http'):
                            link = 'https://xueqiu.com' + link
                        
                        if link and name:
                            author_id = link.split('/u/')[-1].split('?')[0] if '/u/' in link else link.split('/')[-1]
                            
                            if author_id not in [a['id'] for a in authors]:
                                authors.append({
                                    'id': author_id,
                                    'name': name,
                                    'link': link
                                })
                                new_authors_this_page += 1
                                logger.info(f"  找到作者: {name} (ID: {author_id})")
                    
                    except Exception as e:
                        logger.debug(f"  解析作者信息失败: {e}")
                        continue
                
                logger.info(f"第 {page_num} 页获取到 {new_authors_this_page} 个新作者，当前总计 {len(authors)} 个")
                
                if new_authors_this_page == 0:
                    logger.info("本页没有新作者，可能已到最后一页")
                    break
                
                page_num += 1
                
                self._human_like_delay(1, 2)
                
                # 查找下一页按钮
                try:
                    next_btns = self.driver.find_elements(By.XPATH, '//a[contains(text(), "下一页")]')
                    
                    if next_btns:
                        next_btn = next_btns[0]
                        class_attr = next_btn.get_attribute('class') or ''
                        if 'disabled' not in class_attr:
                            self.driver.execute_script("arguments[0].click();", next_btn)
                            self._human_like_delay(1, 2)
                        else:
                            logger.info("下一页按钮不可用，已到达最后一页")
                            break
                    else:
                        logger.info("没有找到下一页按钮，可能已到最后一页")
                        break
                
                except Exception as e:
                    logger.warning(f"点击下一页失败: {e}，可能已到最后一页")
                    break
                    
            except Exception as e:
                logger.error(f"获取第 {page_num} 页时出错: {e}")
                break
        
        logger.info(f"关注列表获取完成，共 {len(authors)} 个作者")
        return authors

    def click_original_tab(self):
        """点击'原发'标签"""
        try:
            self._human_like_delay(1, 2)
            
            # 查找原发标签
            tab_selectors = [
                (By.CSS_SELECTOR, 'a:has-text("原发")'),
                (By.XPATH, '//a[contains(text(), "原发")]'),
                (By.CSS_SELECTOR, '.tab-item:has-text("原发")'),
                (By.XPATH, '//a[contains(text(), "原发布")]'),
            ]
            
            for selector_type, selector_value in tab_selectors:
                try:
                    tab = self.driver.find_element(selector_type, selector_value)
                    if tab.is_displayed() and tab.is_enabled():
                        self.driver.execute_script("arguments[0].click();", tab)
                        logger.info(f"已点击'原发'标签")
                        self._human_like_delay(2, 3)
                        return True
                except:
                    continue
            
            logger.warning("未找到'原发'标签，可能默认显示原发内容")
            return True
        
        except Exception as e:
            logger.warning(f"点击'原发'标签失败: {e}")
            return True

    def get_author_articles(self, author, max_pages=50):
        """获取作者的所有原发文章（处理分页）"""
        logger.info(f"开始获取作者 {author['name']} 的文章...")
        
        author_id = author['id']
        author_name = author['name']
        
        author_dir = self.base_dir / f"{author_id}_{self.sanitize_filename(author_name)}"
        author_dir.mkdir(exist_ok=True)
        
        self.driver.get(author['link'])
        self._human_like_delay(3, 5)
        
        self.click_original_tab()
        
        articles = []
        page_num = 1
        
        # 用于汇总文件的列表
        update_entries = []
        
        while page_num <= max_pages:
            logger.info(f"  正在获取第 {page_num} 页文章...")
            
            # 减少等待时间
            self._human_like_delay(0.5, 1.0)
            
            try:
                # 等待文章内容加载
                # 使用 JavaScript 动态查找文章元素
                article_selectors = [
                    'article.timeline__item',
                    '.timeline__item',
                    'article.list-item',
                    '.list-item',
                ]
                
                article_elements = []
                for selector in article_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            logger.info(f"  使用选择器 '{selector}' 找到 {len(elements)} 个文章项")
                            article_elements = elements
                            break
                    except:
                        continue
                
                if not article_elements:
                    logger.info(f"  第 {page_num} 页没有找到文章，可能已到最后一页")
                    break
                
                new_articles_this_page = 0
                for element in article_elements:
                    try:
                        # 先滚动到元素位置
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                        # 减少等待时间
                        time.sleep(0.5)

                        # 点击"展开"按钮获取完整内容
                        expand_selectors = [
                            '.expand-btn',
                            '[class*="expand"]',
                            'button[class*="expand"]',
                            '.icon-arrow-down',
                            '.iconfont:contains("展开")',
                        ]

                        for selector in expand_selectors:
                            try:
                                expand_btn = element.find_element(By.CSS_SELECTOR, selector)
                                if expand_btn and expand_btn.is_displayed():
                                    self.driver.execute_script("arguments[0].click();", expand_btn)
                                    # 减少等待时间
                                    time.sleep(0.5)
                                    logger.debug("    已点击展开按钮")
                                    break
                            except:
                                continue

                        # 提取文章信息
                        title = ""
                        content = ""
                        time_text = ""

                        # 提取内容
                        try:
                            content_selectors = [
                                '.timeline__item__content .content',
                                '.content--description',
                                '.content',
                            ]

                            for selector in content_selectors:
                                try:
                                    content_elem = element.find_element(By.CSS_SELECTOR, selector)
                                    content = content_elem.text.strip()
                                    if content:
                                        break
                                except:
                                    continue

                            if content:
                                title = content[:30].strip()
                                if len(content) > 30:
                                    title += "..."
                            else:
                                title = "无标题"

                        except:
                            title = "无标题"
                            content = ""

                        # 提取时间
                        try:
                            time_selectors = [
                                '.date-and-source',
                                '.timestamp',
                                '.time',
                            ]

                            for selector in time_selectors:
                                try:
                                    time_elem = element.find_element(By.CSS_SELECTOR, selector)
                                    time_text = time_elem.text.strip()
                                    if time_text:
                                        break
                                except:
                                    continue
                        except:
                            time_text = ""

                        # 确保内容不为空
                        if content:
                            # 初始化display_time为time_text
                            display_time = time_text

                            # 如果启用了只更新当天模式，则检查文章时间
                            if self.update_today:
                                # 检查文章时间是否为今天
                                try:
                                    today = datetime.now().date()

                                    # 首先尝试标准日期解析
                                    date_match = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', time_text)
                                    if date_match:
                                        year = int(date_match.group(1))
                                        month = int(date_match.group(2))
                                        day = int(date_match.group(3))
                                        article_date = date(year, month, day)
                                    else:
                                        # 尝试解析相对时间
                                        parsed_time = self._parse_relative_time(time_text)
                                        if parsed_time:
                                            # 现在解析函数统一返回datetime对象
                                            article_date = parsed_time.date()
                                        else:
                                            # 如果无法解析时间，跳过这篇文章
                                            logger.info(f"    无法解析文章时间 {time_text}，跳过")
                                            continue
                                    #logger.info(f"    解析文章时间: {time_text} -> {article_date}")                   
                                    # 比较日期
                                    if article_date != today:
                                        logger.debug(f"    文章日期 {article_date} 不是今天 {today}，跳过")
                                        continue
                                except Exception as e:
                                    logger.info(f"    检查文章时间时出错: {e}，跳过")
                                    continue

                            article_data = {
                                'title': title if title else "无标题",
                                'content': content,
                                'time': display_time,  # 使用处理后的显示时间
                            }
                            
                            filepath = self._get_month_file_path(article_data, author_id, author_name)
                            
                            self._append_article_to_file(filepath, article_data, author)
                            articles.append(article_data)
                            new_articles_this_page += 1

                            # 添加到汇总列表
                            update_entries.append({
                                'author': author_name,
                                'title': title,
                                'time': time_text,
                                'content': content,  # 添加实际内容
                                'link': f"https://xueqiu.com/{author_id}"
                            })

                            logger.info(f"    追加文章到文件: {filepath.name}")
                        else:
                            logger.debug("    文章内容为空，跳过")

                    except Exception as e:
                        logger.warning(f"    解析文章失败: {e}")
                        continue

                logger.info(f"  第 {page_num} 页保存了 {new_articles_this_page} 篇新文章")
                
                # 如果文章日期晚于今天，停止处理该作者的后续文章
                if new_articles_this_page == 0:
                    logger.info("  本页没有新文章，可能已到最后一页")
                    break
                
                page_num += 1
                
                self._human_like_delay(1, 2)
                
                # 查找下一页按钮
                try:
                    next_selectors = [
                        '.pagination__next:not(.disabled)',
                        'a:has-text("下一页"):not(.disabled)',
                        '.pagination__next',
                    ]
                    
                    next_btn = None
                    for selector in next_selectors:
                        try:
                            btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if btns and btns[0].is_displayed() and btns[0].is_enabled():
                                next_btn = btns[0]
                                break
                        except:
                            continue
                    
                    if next_btn:
                        logger.info("  找到下一页按钮，准备点击")
                        self.driver.execute_script("arguments[0].scrollIntoView();", next_btn)
                        self._human_like_delay(1, 2)
                        self.driver.execute_script("arguments[0].click();", next_btn)
                        self._human_like_delay(1, 2)
                    else:
                        logger.info("  没有找到下一页按钮，可能已到最后一页")
                        break
                
                except Exception as e:
                    logger.warning(f"  点击下一页失败: {e}，可能已到最后一页")
                    break
            
            except Exception as e:
                logger.error(f"  获取第 {page_num} 页时出错: {e}")
                break
        
        logger.info(f"作者 {author_name} 的文章获取完成，共保存 {len(articles)} 篇")
        
        if articles:
            self.scraped_authors[author_id] = {
                'name': author_name,
                'link': author['link'],
                'article_count': len(articles),
                'last_scraped': datetime.now().isoformat()
            }
            self._save_scraped_authors()
        
        # 写入汇总文件
        if self.update_today and update_entries:
            self._write_update_summary(update_entries)
        
        return articles

    def _get_month_file_path(self, article_data, author_id, author_name):
        """获取月份文件路径：作者ID_年月.html"""
        time_text = article_data['time']

        author_dir = self.base_dir / f"{author_id}_{self.sanitize_filename(author_name)}"
        author_dir.mkdir(exist_ok=True)

        year_month = datetime.now().strftime("%Y-%m")

        if time_text:
            try:
                # 尝试从时间文本中提取年月信息
                # 支持格式：2025-01-18, 01-18, 今天, 01-18 14:30 等

                # 匹配 2025-01-18 格式
                match = re.search(r'(\d{4})[-/年](\d{1,2})', time_text)
                if match:
                    year = match.group(1)
                    month = match.group(2).zfill(2)
                    year_month = f"{year}-{month}"
                # 匹配 01-18 格式（假设是当年）
                elif re.search(r'(\d{1,2})[-/月](\d{1,2})', time_text):
                    match = re.search(r'(\d{1,2})[-/月](\d{1,2})', time_text)
                    if match:
                        month = match.group(1).zfill(2)
                        year_month = f"{datetime.now().year}-{month}"

            except Exception as e:
                logger.debug(f"解析时间失败，使用当前月份: {e}")

        # 文件名格式：作者ID_年月.html
        filename = f"{author_id}_{year_month}.html"
        filepath = author_dir / filename
        return filepath

    def _append_article_to_file(self, filepath, article_data, author):
        """追加文章到月份文件（txt格式） - 插入到文件开头"""
        try:
            # 生成HTML内容
            html_content = f"<div class='article'>\n"
            html_content += f"  <div class='header'>\n"
            html_content += f"    <div class='meta-info'>\n"
            html_content += f"      <span class='author'>作者: {author['name']}</span><br>\n"
            html_content += f"      <span class='author-link'>链接: <a href='{author['link']}' target='_blank'>{author['link']}</a></span><br>\n"
            html_content += f"      <span class='publish-time'>发布时间: {article_data['time']}</span>\n"
            html_content += f"    </div>\n"
            html_content += f"  </div>\n"
            html_content += f"  <div class='content'>\n"
            html_content += f"    {article_data['content'].replace('<', '&lt;').replace('>', '&gt;').replace('\\n', '<br>')}\n"
            html_content += f"  </div>\n"
            html_content += f"  <hr class='divider'>\n"
            html_content += f"</div>\n\n"

            # 将文件路径改为HTML格式
            html_filepath = filepath.with_suffix('.html')

            # 读取现有内容
            existing_content = ""
            if html_filepath.exists():
                with open(html_filepath, 'r', encoding='utf-8') as f:
                    existing_content = f.read()

            # 如果是新文件，添加HTML头部
            if not html_filepath.exists():
                html_header = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{author['name']} - 雪球文章</title>
    <style>
        body {{
            font-family: 'Microsoft YaHei', 'SimHei', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.8;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            color: #2c3e50;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1200px;
            margin: 20px auto;
            background-color: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
            position: relative;
            overflow: hidden;
        }}

        .container::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 5px;
            background: linear-gradient(90deg, #3498db, #2ecc71, #e74c3c, #9b59b6);
        }}

        h1 {{
            text-align: center;
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
            margin-top: 0;
            font-size: 2.5em;
            position: relative;
        }}

        h1::after {{
            content: '';
            position: absolute;
            bottom: -3px;
            left: 25%;
            width: 50%;
            height: 3px;
            background: linear-gradient(90deg, #3498db, #2ecc71);
        }}

        .article {{
            margin-bottom: 35px;
            padding: 25px;
            border-left: 5px solid #3498db;
            background: linear-gradient(to right, #f8f9fa, #ffffff);
            border-radius: 0 10px 10px 0;
            box-shadow: 0 4px 8px rgba(0,0,0,0.05);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}

        .article:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 16px rgba(0,0,0,0.1);
        }}

        .header {{
            margin-bottom: 15px;
        }}

        .meta-info {{
            color: #7f8c8d;
            font-size: 0.9em;
            margin-top: 10px;
        }}

        .publish-time {{
            color: #e74c3c;
            font-weight: bold;
        }}

        .content {{
            margin-top: 15px;
            font-size: 1.1em;
            line-height: 1.8;
        }}

        .content p {{
            margin: 15px 0;
            text-indent: 2em;
            line-height: 1.8;
        }}

        .divider {{
            border: 0;
            height: 1px;
            background: #ddd;
            margin: 30px 0;
        }}

        a {{
            color: #3498db;
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}

            .container {{
                padding: 20px;
                margin: 10px auto;
            }}

            h1 {{
                font-size: 2em;
            }}

            .article {{
                padding: 20px;
            }}

            .content p {{
                font-size: 1em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{author['name']} - 雪球文章</h1>
"""
                html_footer = """
    </div>
</body>
</html>
"""
                existing_content = html_header + existing_content + html_footer

            # 将新内容插入到HTML结束标签之前
            insert_pos = existing_content.rfind("</div>")  # 在容器结束前插入
            combined_content = existing_content[:insert_pos] + html_content + existing_content[insert_pos:]

            # 写入HTML文件
            logger.debug(f"正在向文件 {html_filepath.name} 写入文章内容（插入到开头）...")
            with open(html_filepath, 'w', encoding='utf-8') as f:
                f.write(combined_content)
            logger.debug(f"成功向文件 {html_filepath.name} 写入文章内容")
        except Exception as e:
            logger.error(f"写入文章到HTML文件失败 {filepath}: {e}")

    def _save_article_to_file(self, filepath, article_data, author):
        """保存文章为 Markdown 文件"""
        try:
            content = f"# {article_data['title']}\n\n"
            content += f"**作者**: {author['name']}\n\n"
            content += f"**发布时间**: {article_data['time']}\n\n"
            content += f"**作者链接**: {author['link']}\n\n"
            content += "---\n\n"
            content += article_data['content']
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            logger.error(f"保存文件失败 {filepath}: {e}")

    def _write_update_summary(self, update_entries):
        """写入更新汇总文件，包含所有文章内容（HTML格式）"""
        try:
            # 构建汇总文件路径
            summary_file = self.base_dir / "update_latest.html"

            # 准备HTML汇总内容
            html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>雪球大V文章更新汇总</title>
    <style>
        body {{
            font-family: 'Microsoft YaHei', 'SimHei', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.8;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            color: #2c3e50;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1200px;
            margin: 20px auto;
            background-color: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
            position: relative;
            overflow: hidden;
        }}

        .container::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 5px;
            background: linear-gradient(90deg, #3498db, #2ecc71, #e74c3c, #9b59b6);
        }}

        h1 {{
            text-align: center;
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
            margin-top: 0;
            font-size: 2.5em;
            position: relative;
        }}

        h1::after {{
            content: '';
            position: absolute;
            bottom: -3px;
            left: 25%;
            width: 50%;
            height: 3px;
            background: linear-gradient(90deg, #3498db, #2ecc71);
        }}

        .summary-date {{
            text-align: center;
            color: #7f8c8d;
            font-size: 1.2em;
            margin-bottom: 30px;
        }}

        .author-section {{
            margin-bottom: 40px;
            padding: 20px;
            border-left: 4px solid #9b59b6;
            background: linear-gradient(to right, #f8f9fa, #ffffff);
            border-radius: 0 10px 10px 0;
        }}

        .author-title {{
            color: #9b59b6;
            border-bottom: 2px solid #9b59b6;
            padding-bottom: 10px;
            margin-top: 0;
        }}

        .article {{
            margin-bottom: 30px;
            padding: 20px;
            border-left: 3px solid #3498db;
            background-color: #f8f9fa;
            border-radius: 0 5px 5px 0;
        }}

        .article-header {{
            margin-bottom: 15px;
        }}

        .article-title {{
            margin: 0 0 10px 0;
            color: #2c3e50;
        }}

        .meta-info {{
            color: #7f8c8d;
            font-size: 0.9em;
        }}

        .publish-time {{
            color: #e74c3c;
            font-weight: bold;
        }}

        .content {{
            margin-top: 15px;
            font-size: 1.1em;
            line-height: 1.8;
        }}

        .content p {{
            margin: 15px 0;
            text-indent: 2em;
            line-height: 1.8;
        }}

        a {{
            color: #3498db;
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}

            .container {{
                padding: 20px;
                margin: 10px auto;
            }}

            h1 {{
                font-size: 2em;
            }}

            .author-section {{
                padding: 15px;
            }}

            .content p {{
                font-size: 1em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>雪球大V文章更新汇总</h1>
        <div class="summary-date">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
"""

            # 按作者分组
            authors_dict = {}
            for entry in update_entries:
                author = entry['author']
                if author not in authors_dict:
                    authors_dict[author] = []
                authors_dict[author].append(entry)

            # 写入每个作者的信息，包含完整内容
            for author, entries in authors_dict.items():
                html_content += f"        <div class=\"author-section\">\n"
                html_content += f"            <h2 class=\"author-title\">作者: {author}</h2>\n"

                for entry in entries:
                    html_content += f"            <div class=\"article\">\n"
                    html_content += f"                <div class=\"article-header\">\n"
                    html_content += f"                    <h3 class=\"article-title\">{entry['title']}</h3>\n"
                    html_content += f"                    <div class=\"meta-info\">\n"
                    html_content += f"                        <span class=\"publish-time\">发布时间: {entry['time']}</span><br>\n"
                    html_content += f"                        <span class=\"article-link\">链接: <a href=\"{entry['link']}\" target=\"_blank\">{entry['link']}</a></span>\n"
                    html_content += f"                    </div>\n"
                    html_content += f"                </div>\n"
                    html_content += f"                <div class=\"content\">\n"
                    html_content += f"                    {entry['content'].replace('<', '&lt;').replace('>', '&gt;').replace('\\n', '<br>')}\n"
                    html_content += f"                </div>\n"
                    html_content += f"            </div>\n"

                html_content += f"        </div>\n"

            html_content += """    </div>
</body>
</html>"""

            # 写入HTML文件（覆盖模式）
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logger.info(f"更新汇总已写入文件: {summary_file}")

        except Exception as e:
            logger.error(f"写入更新汇总文件失败: {e}")

    def run(self, max_authors=None, test_mode=False, skip_login=False):
        """运行抓取流程"""
        try:
            logger.info("开始初始化抓取流程...")
            # 尝试加载 cookies
            cookies_loaded = self._load_cookies()
            
            if not cookies_loaded and not skip_login:
                logger.info("首次运行，请手动登录雪球")
                logger.info("="*60)
                
                self.driver.get('https://xueqiu.com')
                input("\n登录完成后，请按回车键继续...")
                self._save_cookies()
                logger.info("已保存 cookies")
            else:
                logger.info("使用已保存的 cookies")
                self.driver.get('https://xueqiu.com')
                self._human_like_delay(2, 3)

            logger.info("开始执行抓取流程...")
            logger.info(f"目标模式: {'测试模式' if test_mode else '完整模式' if max_authors is None else f'限制模式({max_authors}个作者)'}")

            authors = self.get_following_authors()

            if not authors:
                logger.error("未获取到任何关注作者")
                return

            # 检查是否已有处理记录，如果有则跳过已处理的作者
            # 但如果是 --update-today 模式，则不跳过已处理的作者
            processed_authors = set(self.scraped_authors.keys())
            
            
            # 优雅的处理逻辑：在 update-today 模式下，不跳过已处理的作者
            if self.update_today:
                # update-today 模式下处理所有作者，但每个作者只抓取当天文章
                authors_to_process = authors
                logger.info(f"update-today 模式：处理所有 {len(authors)} 个作者")
            else:
                # 普通模式下跳过已处理的作者
                authors_to_process = [author for author in authors if author['id'] not in processed_authors]
                logger.info(f"发现 {len(authors)} 个作者，其中 {len(authors_to_process)} 个需要处理")

            if test_mode:
                authors_to_process = authors_to_process[:3]
                logger.info(f"测试模式：只处理前 {len(authors_to_process)} 个作者")
            elif max_authors:
                authors_to_process = authors_to_process[:max_authors]
                logger.info(f"限制处理前 {len(authors_to_process)} 个作者")

            logger.info(f"开始处理 {len(authors_to_process)} 个作者...")
            logger.info("开始逐个处理作者...")

            total_articles = 0
            for i, author in enumerate(authors_to_process):
                logger.info(f"\n{'='*60}")
                logger.info(f"正在处理第 {i+1}/{len(authors_to_process)} 个作者: {author['name']}")
                logger.info(f"作者ID: {author['id']}")
                logger.info(f"{'='*60}\n")
                
                try:
                    articles = self.get_author_articles(author)
                    total_articles += len(articles)
                    logger.info(f"作者 {author['name']} 处理完成，获得 {len(articles)} 篇文章")
                except Exception as e:
                    logger.error(f"处理作者 {author['name']} 时出错: {e}")
                    continue

            logger.info(f"\n{'='*60}")
            logger.info(f"所有抓取完成！")
            logger.info(f"处理了 {len(authors_to_process)} 个作者")
            logger.info(f"共保存 {total_articles} 篇文章")
            logger.info(f"文章保存在: {self.base_dir.absolute()}")
            logger.info(f"{'='*60}\n")

        finally:
            logger.info("正在关闭浏览器...")
            self.driver.quit()
            logger.info("浏览器已关闭")


def main():
    parser = argparse.ArgumentParser(description='雪球大V文章抓取工具 (Selenium版本)')
    parser.add_argument('--mode', type=str, default='full', 
                       choices=['full', 'test', 'count'],
                       help='运行模式: full(全部), test(测试3个), count(指定数量)')
    parser.add_argument('--count', type=int, default=3,
                       help='指定抓取作者数量（仅当mode=count时生效）')
    parser.add_argument('--headless', action='store_true', default=True,
                       help='使用无头模式运行浏览器')
    parser.add_argument('--update-today', action='store_true', default=True,
                       help='只更新当天发布的文章')
    parser.add_argument('--skip-login', action='store_true', default=True,
                       help='跳过登录，使用已保存的cookies')
    
    args = parser.parse_args()

    scraper = XueqiuSeleniumScraper(headless=args.headless)
    scraper.update_today = False if not args.update_today else True

    logger.info("雪球大V文章抓取工具 (Selenium版本)")
    logger.info("="*60)
    logger.info("使用说明：")
    logger.info("1. 程序会自动保存登录 Cookies")
    logger.info("2. 文章按作者分目录保存")
    logger.info("3. 基于文件存在判断自动去重")
    logger.info("4. 文件名格式：标题_时间戳.md")
    logger.info(f"当前运行模式：{args.mode}")
    logger.info(f"当前headless模式：{'启用' if args.headless else '禁用'}")
    logger.info(f"当前update-today模式：{'启用' if scraper.update_today else '禁用'}")
    logger.info(f"当前skip-login模式：{'启用' if args.skip_login else '禁用'}")


    test_mode = False
    max_authors = None

    if args.mode == 'full':
        test_mode = False
        max_authors = None
        logger.info("模式：抓取所有关注作者")
    elif args.mode == 'test':
        test_mode = True
        max_authors = None
        logger.info("模式：测试模式（前3个作者）")
    elif args.mode == 'count':
        max_authors = args.count
        test_mode = False
        logger.info(f"模式：抓取前 {max_authors} 个作者")

    try:
        scraper.run(max_authors=max_authors, test_mode=test_mode, skip_login=args.skip_login)
    except KeyboardInterrupt:
        logger.info("\n用户中断，正在退出...")
    except Exception as e:
        logger.error(f"程序运行出错: {e}")


if __name__ == "__main__":
    main()
