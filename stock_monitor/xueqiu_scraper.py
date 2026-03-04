"""
雪球大V文章抓取工具 - 模块化版本（语法修正版）
功能：
1. 自动登录雪球（保存 Cookies）
2. 获取所有关注的人（处理分页）
3. 遍历每个关注的人，获取所有原发文章
4. 按作者分目录保存为 HTML 文件
5. 基于文件存在判断去重
"""

import argparse
import json
import re
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webelement import WebElement

from logger_config import setup_logger, gconfig
from xueqiu_utils import (
    parse_relative_time, convert_to_absolute_time, sanitize_filename,
    human_like_delay, get_month_from_time, is_content_truncated, find_expand_button
)

logger = setup_logger('xueqiu_scraper')


class BrowserManager:
    """浏览器管理器"""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = None
        self.wait = None

    def init_driver(self) -> None:
        """初始化 Chrome 驱动"""
        options = Options()

        # 无头模式配置
        if self.headless:
            options.add_argument('--headless=new')

        # 基础配置
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # 无头模式专用配置
        if self.headless:
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-images')
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
            self.driver = webdriver.Chrome(options=options)
            # 修改 navigator.webdriver 属性
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("浏览器初始化成功")
            self.wait = WebDriverWait(self.driver, 5)
        except Exception as e:
            logger.error(f"浏览器初始化失败: {e}")
            logger.error("请确保已安装Chrome浏览器和对应的ChromeDriver")
            raise

    def quit(self) -> None:
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("浏览器已关闭")
            except Exception as e:
                logger.error(f"关闭浏览器时出错: {e}")

    def get_driver(self) -> webdriver.Chrome:
        """获取驱动实例"""
        if not self.driver:
            self.init_driver()
        return self.driver


class CookieHandler:
    """Cookies处理器"""

    def __init__(self, cookies_file: str = "xueqiu_cookies.json"):
        self.cookies_file = cookies_file

    def load_cookies(self, driver: webdriver.Chrome) -> bool:
        """加载已保存的cookies"""
        if Path(self.cookies_file).exists():
            try:
                # 先访问域名，否则会报域名不匹配错误
                driver.get('https://xueqiu.com')

                with open(self.cookies_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                    for cookie in cookies:
                        try:
                            # 只添加 xueqiu.com 域名的 cookies
                            cookie_copy = cookie.copy()

                            # 移除可能导致问题的属性
                            if 'expiry' in cookie_copy:
                                del cookie_copy['expiry']
                            if 'sameSite' in cookie_copy:
                                del cookie_copy['sameSite']

                            # 只添加 xueqiu.com 域名的 cookies
                            if 'domain' in cookie_copy and 'xueqiu' in cookie_copy['domain']:
                                driver.add_cookie(cookie_copy)
                        except Exception as e:
                            logger.debug(f"添加 cookie 失败: {e}")
                    return True
            except Exception as e:
                logger.warning(f"加载 cookies 失败: {e}")
        return False

    def save_cookies(self, driver: webdriver.Chrome) -> None:
        """保存cookies"""
        try:
            cookies = driver.get_cookies()
            with open(self.cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            logger.info(f"Cookies 已保存到 {self.cookies_file}")
        except Exception as e:
            logger.warning(f"保存 cookies 失败: {e}")


class AuthorExtractor:
    """作者信息提取器"""

    def __init__(self, browser_manager: BrowserManager, output_dir: str):
        self.browser_manager = browser_manager
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.scraped_authors_file = self.output_dir / "scraped_authors.json"
        self.scraped_authors = self._load_scraped_authors()

    def _load_scraped_authors(self) -> Dict[str, dict]:
        """加载已抓取的作者列表"""
        if self.scraped_authors_file.exists():
            try:
                with open(self.scraped_authors_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载已抓取作者列表失败: {e}")
        return {}

    def _save_scraped_authors(self) -> None:
        """保存已抓取的作者列表"""
        try:
            with open(self.scraped_authors_file, 'w', encoding='utf-8') as f:
                json.dump(self.scraped_authors, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存已抓取作者列表失败: {e}")

    def get_following_authors(self) -> List[Dict[str, str]]:
        """获取所有关注的人（处理分页）"""
        logger.info("开始获取关注列表...")
        driver = self.browser_manager.get_driver()

        # 验证登录状态
        if not self._verify_login_status(driver):
            logger.error("登录验证失败，请检查登录状态")
            raise Exception("登录验证失败，请重新登录")

        driver.get('https://xueqiu.com/center/#/friends')
        human_like_delay(2, 5)

        # 等待页面加载完成
        try:
            WebDriverWait(driver, 10).until(
                lambda d: 'friends' in d.current_url or 'center' in d.current_url
            )
            logger.info("页面加载完成")
        except Exception as e:
            logger.warning(f"等待页面加载超时：{e}")

        authors = []
        page_num = 1
        max_pages = 100

        while page_num <= max_pages:
            logger.info(f"正在获取第 {page_num} 页关注列表...")

            human_like_delay(1, 2)

            try:
                # 使用多个 CSS 选择器尝试查找用户卡片
                author_cards = self._find_author_cards(driver)

                if not author_cards or len(author_cards) == 0:
                    logger.warning(f"第 {page_num} 页未找到任何用户卡片")
                    break

                logger.info(f"找到 {len(author_cards)} 个用户卡片")

                new_authors_this_page = 0
                for card in author_cards:
                    try:
                        author_info = self._extract_author_info(card)
                        if author_info and author_info['id'] not in [a['id'] for a in authors]:
                            authors.append(author_info)
                            new_authors_this_page += 1
                            logger.info(f"  找到作者: {author_info['name']} (ID: {author_info['id']})")

                    except Exception as e:
                        logger.debug(f"  解析作者信息失败: {e}")
                        continue

                logger.info(f"第 {page_num} 页获取到 {new_authors_this_page} 个新作者，当前总计 {len(authors)} 个")

                if new_authors_this_page == 0:
                    logger.info("本页没有新作者，可能已到最后一页")
                    break

                page_num += 1
                human_like_delay(1, 2)

                # 查找下一页按钮
                if not self._click_next_page(driver):
                    break

            except Exception as e:
                logger.error(f"获取第 {page_num} 页时出错：{str(e)}")
                break

        logger.info(f"关注列表获取完成，共 {len(authors)} 个作者")
        return authors

    def _find_author_cards(self, driver: webdriver.Chrome) -> List[WebElement]:
        """查找作者卡片元素"""
        css_selectors = [
            '.profiles__user__card',      # 原选择器
            '.user-card',                  # 通用用户卡片
            '.follow-item',                # 关注项
            '.profile-card',               # 个人资料卡片
            '[class*="user-card"]',        # 包含 user-card 的类
            '[class*="profile-card"]',     # 包含 profile-card 的类
            '.user-info',                  # 用户信息
            '.follow-user',                # 关注用户
        ]

        xpath_selectors = [
            '//div[contains(@class, "user") and contains(@class, "card")]',
            '//div[contains(@class, "profile") and contains(@class, "card")]',
            '//div[contains(@class, "follow") and contains(@class, "item")]',
            '//a[contains(@href, "/u/")]',  # 查找包含/u/链接的元素
        ]

        for selector in css_selectors:
            try:
                cards = WebDriverWait(driver, 3).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                if cards and len(cards) > 0:
                    logger.info(f"使用 CSS 选择器 '{selector}' 找到 {len(cards)} 个用户卡片")
                    return cards
            except Exception:
                continue

        # 如果 CSS 选择器都失败，尝试 XPath
        for selector in xpath_selectors:
            try:
                cards = WebDriverWait(driver, 3).until(
                    EC.presence_of_all_elements_located((By.XPATH, selector))
                )
                if cards and len(cards) > 0:
                    logger.info(f"使用 XPath 选择器 '{selector}' 找到 {len(cards)} 个用户卡片")
                    return cards
            except Exception:
                continue

        # 宽泛选择器
        try:
            cards = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/u/"]')
            if cards and len(cards) > 0:
                logger.info(f"使用宽泛选择器找到 {len(cards)} 个用户链接")
                return cards
        except Exception:
            pass

        return []

    def _extract_author_info(self, card: WebElement) -> Optional[Dict[str, str]]:
        """提取作者信息"""
        name = ""
        link = ""

        # 尝试多种方式获取名称
        name_selectors = ['.user-name', '.name', '.nickname', '[class*="name"]']
        for selector in name_selectors:
            try:
                name_elem = card.find_element(By.CSS_SELECTOR, selector)
                name = name_elem.text.strip()
                if name:
                    break
            except:
                continue

        # 如果名称为空，尝试从卡片文本获取
        if not name:
            try:
                name = card.text.strip().split('\n')[0][:50]
            except:
                pass

        # 尝试多种方式获取链接
        link_selectors = ['a.user-name', 'a.name', 'a[href*="/u/"]']
        for selector in link_selectors:
            try:
                link_elem = card.find_element(By.CSS_SELECTOR, selector)
                link = link_elem.get_attribute('href')
                if link:
                    break
            except:
                continue

        if link and not link.startswith('http'):
            link = 'https://xueqiu.com' + link

        if link and name:
            author_id = link.split('/u/')[-1].split('?')[0] if '/u/' in link else link.split('/')[-1]
            return {
                'id': author_id,
                'name': name,
                'link': link
            }
        return None

    def _click_next_page(self, driver: webdriver.Chrome) -> bool:
        """点击下一页按钮"""
        try:
            next_btns = driver.find_elements(By.XPATH, '//a[contains(text(), "下一页")]')

            if next_btns:
                next_btn = next_btns[0]
                class_attr = next_btn.get_attribute('class') or ''
                if 'disabled' not in class_attr:
                    driver.execute_script("arguments[0].click();", next_btn)
                    human_like_delay(1, 2)
                    return True
                else:
                    logger.info("下一页按钮不可用，已到达最后一页")
                    return False
            else:
                logger.info("没有找到下一页按钮，可能已到最后一页")
                return False

        except Exception as e:
            logger.warning(f"点击下一页失败: {e}，可能已到最后一页")
            return False

    def _verify_login_status(self, driver: webdriver.Chrome) -> bool:
        """验证登录状态"""
        try:
            logger.info("正在验证登录状态...")

            # 刷新页面以确保最新的cookies生效
            driver.refresh()
            human_like_delay(2, 3)

            # 尝试查找用户相关的元素来确认登录状态
            user_elements = driver.find_elements(By.CSS_SELECTOR, '.user-avatar, .avatar, [data-user-id], .user-name, .username')

            if user_elements:
                logger.info("登录状态验证成功 - 找到用户相关元素")
                return True

            # 方法2: 检查URL是否在个人中心页面
            current_url = driver.current_url
            if 'center' in current_url or 'user' in current_url:
                logger.info("登录状态验证成功 - 在个人中心页面")
                return True

            return False

        except Exception as e:
            logger.warning(f"登录状态验证过程中出错: {e}")
            return False


class ArticleExtractor:
    """文章提取器"""

    def __init__(self, browser_manager: BrowserManager, author_extractor: AuthorExtractor, output_dir: str):
        self.browser_manager = browser_manager
        self.author_extractor = author_extractor
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.update_today = True  # 默认启用只更新当天模式
        self.test_mode = False  # 测试模式

    def get_author_articles(self, author: Dict[str, str], max_pages: int = 50) -> Tuple[List[Dict], List[Dict]]:
        """获取作者的所有原发文章（处理分页）

        Args:
            author: 作者信息字典
            max_pages: 最大抓取页数

        Returns:
            (文章列表, 更新条目列表)
        """
        logger.info(f"开始获取作者 {author['name']} 的文章...")
        driver = self.browser_manager.get_driver()

        # ========== 配置抓取参数 ==========
        if self.test_mode:
            max_pages = min(max_pages, 2)
            logger.info(f"测试模式：最多抓取 {max_pages} 页文章")

        author_id = author['id']
        author_name = author['name']
        author_dir = self.output_dir / f"{author_id}_{sanitize_filename(author_name)}"
        author_dir.mkdir(exist_ok=True)

        # ========== 访问作者页面并切换到原发视图 ==========
        driver.get(author['link'])
        human_like_delay(1, 3)

        if not self._click_original_tab(driver):
            logger.warning(f"作者 {author_name} 无法切换到原发视图，将抓取所有内容")

        articles = []
        page_num = 1
        update_entries = []

        # ========== 分页抓取文章 ==========
        while page_num <= max_pages:
            logger.info(f"  正在获取第 {page_num} 页文章...")

            human_like_delay(2, 3)

            try:
                # 查找文章元素
                article_elements = self._find_article_elements(driver)

                if not article_elements:
                    logger.info(f"  第 {page_num} 页没有找到文章，可能已到最后一页")
                    break

                new_articles_this_page = 0
                for element in article_elements:
                    try:
                        # 提取文章数据
                        article_data = self._extract_article_data(element, author, driver)
                        if article_data and article_data['content']:
                            # 检查时间过滤（仅限update-today模式）
                            if self.update_today and not self._is_today_article(article_data['time']):
                                continue

                            # 保存文章到按月归档的文件
                            filepath = self._get_month_file_path(article_data, author_id, author_name)
                            self._save_article_to_file(filepath, article_data, author)

                            articles.append(article_data)
                            new_articles_this_page += 1

                            # 添加到汇总列表
                            update_entries.append({
                                'author': author_name,
                                'title': article_data['title'],
                                'time': article_data['time'],
                                'content': article_data['content'],
                                'link': article_data['link']
                            })

                            logger.info(f"    [保存] {filepath.name}")

                    except Exception as e:
                        logger.warning(f"    解析文章失败: {e}")
                        continue

                logger.info(f"  [完成] 第 {page_num} 页保存 {new_articles_this_page} 篇")

                # ========== 处理连续无新文章的情况（仅update-today模式） ==========
                if self.update_today and new_articles_this_page == 0:
                    if not hasattr(self, 'consecutive_zero_pages'):
                        self.consecutive_zero_pages = 0
                    self.consecutive_zero_pages += 1
                    if self.consecutive_zero_pages >= 1:
                        logger.info("  [停止] 连续1页无新文章")
                        break
                elif hasattr(self, 'consecutive_zero_pages'):
                    self.consecutive_zero_pages = 0

                # ========== 翻到下一页 ==========
                page_num += 1
                human_like_delay(1, 2)

                if not self._click_next_page(driver):
                    break

            except Exception as e:
                logger.error(f"  获取第 {page_num} 页时出错: {e}")
                break

        logger.info(f"作者 {author_name} 的文章获取完成，共保存 {len(articles)} 篇")

        # ========== 更新已抓取作者记录 ==========
        if articles:
            self.author_extractor.scraped_authors[author_id] = {
                'name': author_name,
                'link': author['link'],
                'article_count': len(articles),
                'last_scraped': datetime.now().isoformat()
            }
            self.author_extractor._save_scraped_authors()

        return articles, update_entries

    def _find_article_elements(self, driver: webdriver.Chrome) -> List[WebElement]:
        """查找文章元素

        使用多个CSS选择器尝试查找文章列表项
        按优先级尝试不同的选择器

        Args:
            driver: Selenium WebDriver实例

        Returns:
            WebElement列表
        """
        article_selectors = [
            'article.timeline__item',
            '.timeline__item',
            'article.list-item',
            '.list-item',
        ]

        for selector in article_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    #logger.info(f"  使用选择器 '{selector}' 找到 {len(elements)} 个文章项")
                    return elements
            except:
                continue
        return []

    def _extract_article_data(self, element: WebElement, author: Dict[str, str], driver: webdriver.Chrome) -> Optional[Dict[str, str]]:
        """提取文章数据

        Args:
            element: 文章DOM元素
            author: 作者信息字典
            driver: Selenium WebDriver实例

        Returns:
            包含title、content、time、link的字典，如果提取失败返回None
        """
        title = ""
        content = ""
        time_text = ""
        article_link = ""

        # ========== 第一步：提取文章链接 ==========
        try:
            link_elements = element.find_elements(By.CSS_SELECTOR, 'a[href*="/"]')

            for link_elem in link_elements:
                href = link_elem.get_attribute('href')
                if not href:
                    continue

                # 排除用户主页链接和特殊链接
                if '/u/' in href or href.startswith('javascript:') or href == '#':
                    continue

                # 识别文章链接：/数字/数字 格式
                url_path = href.replace('https://xueqiu.com', '').replace('http://xueqiu.com', '')
                parts = url_path.split('/')

                if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
                    article_link = href if href.startswith('http') else 'https://xueqiu.com' + href
                    break

        except Exception as e:
            logger.debug(f"提取文章链接失败: {e}")

        # ========== 第二步：提取发布时间 ==========
        try:
            time_selectors = [
                '.date-and-source',
                '.timeline__item__info .date',
                '.timestamp',
                'span.timestamp',
                '.timeline__item__date',
                'div[class*="time"]',
                'div[class*="date"]'
            ]

            for selector in time_selectors:
                try:
                    time_elem = element.find_element(By.CSS_SELECTOR, selector)
                    time_text = time_elem.text.strip()

                    # 检查是否包含时间相关特征并清理
                    if time_text and len(time_text) < 50:
                        has_date_format = bool(re.search(r'\d{4}-\d{1,2}-\d{1,2}|\d{1,2}-\d{1,2}|小时前|分钟前|昨天|今天|刚刚|修改于', time_text))

                        if has_date_format:
                            # 清理时间文本：移除 "来自" 和后面的内容
                            cleaned_time = time_text
                            if '·' in cleaned_time:
                                cleaned_time = cleaned_time.split('·')[0].strip()
                            if '来自' in cleaned_time:
                                cleaned_time = cleaned_time.split('来自')[0].strip()
                            time_text = cleaned_time
                            break
                        else:
                            time_text = ""
                except:
                    continue

        except Exception as e:
            logger.debug(f"提取时间失败: {e}")

        # ========== 第三步：提取标题 ==========
        try:
            title_selectors = [
                '.timeline__item__title span',
                '.timeline__item__title',
                '.content h3',
                '.content-title'
            ]

            for selector in title_selectors:
                try:
                    title_elem = element.find_element(By.CSS_SELECTOR, selector)
                    title = title_elem.text.strip()
                    if title:
                        break
                except:
                    continue

        except Exception as e:
            logger.debug(f"提取标题失败: {e}")

        # ========== 第四步：提取内容（从列表页） ==========
        try:
            content_selectors = [
                '.timeline__item__content .content',
                '.content--description',
                '.content',
                '.timeline__item__content'
            ]

            for selector in content_selectors:
                try:
                    content_elem = element.find_element(By.CSS_SELECTOR, selector)
                    content = content_elem.text.strip()
                    if content:
                        break
                except:
                    continue

            # 如果内容为空，尝试从整个元素提取
            if not content:
                try:
                    content = element.text.strip()
                    if len(content) > 300:
                        content = content[:300] + "..."
                except:
                    pass

        except Exception as e:
            logger.debug(f"提取内容失败: {e}")

        # ========== 第五步：增强内容提取（处理展开按钮等） ==========
        content = self._enhance_content_extraction(element, content, article_link, driver)

        # ========== 第六步：检查是否成功提取内容 ==========
        if not content:
            logger.warning("未能获取到文章内容，跳过")
            return None

        # ========== 第七步：记录提取结果 ==========
        #logger.info(f"✓ 提取文章: 标题='{title[:30]}...' 内容={len(content)}字 时间={time_text}")

        return {
            'title': title if title else "无标题",
            'content': content,
            'time': time_text,
            'link': article_link if article_link else f"https://xueqiu.com/{author['id']}"
        }

    def _enhance_content_extraction(self, element: WebElement, content: str, article_link: str, driver: webdriver.Chrome) -> Optional[str]:
        """增强内容提取逻辑

        功能：
        1. 点击"展开"按钮获取完整内容
        2. 尝试多种选择器提取更长内容
        3. 检测内容截断情况
        4. 如果内容太短（<100字符），返回None不保存

        Args:
            element: 文章DOM元素
            content: 已提取的内容
            article_link: 文章链接
            driver: Selenium WebDriver实例

        Returns:
            增强后的内容字符串，如果内容太短返回None
        """
        original_url = driver.current_url

        try:
            # ========== 第一步：检查并点击展开按钮 ==========
            expand_btn = find_expand_button(element)
            if expand_btn:
                driver.execute_script("arguments[0].click();", expand_btn)
                human_like_delay(1, 3)
                #logger.info("  [展开] 点击展开按钮")

                # 重新提取展开后的内容
                content_selectors = [
                    '.content--description',
                    '.timeline__item__content',
                    '.timeline__item__bd',
                    'div.content',
                    '.timeline__item__bd__text',
                    'article',
                ]

                for selector in content_selectors:
                    try:
                        content_elem = element.find_element(By.CSS_SELECTOR, selector)
                        new_content = content_elem.text.strip()
                        if new_content and len(new_content) > 50:  # 至少 50 字符才有效
                            content = new_content
                            #logger.info(f"  [展开] 提取内容：{len(content)}字")
                            break
                    except:
                        continue

        except Exception as e:
            logger.debug(f"增强内容提取失败: {e}")
            # 确保返回原页面
            try:
                if driver.current_url != original_url:
                    driver.get(original_url)
                    human_like_delay(1, 2)
            except:
                pass

        return content

    def _is_today_article(self, time_text: str) -> bool:
        """检查文章是否为今天发布"""
        if not time_text:
            logger.debug(f"  时间为空，视为今天")
            return True

        try:
            today = datetime.now().date()

            # 首先尝试标准日期解析 - 优先匹配完整日期格式 "2025-12-21"
            date_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', time_text)
            if date_match:
                year = int(date_match.group(1))
                month = int(date_match.group(2))
                day = int(date_match.group(3))
                article_date = date(year, month, day)
                logger.debug(f"  解析到日期: {article_date}, 今天: {today}")
            else:
                # 尝试解析相对时间
                parsed_time = parse_relative_time(time_text)
                if parsed_time:
                    article_date = parsed_time.date()
                    logger.debug(f"  解析到相对时间: {article_date}, 今天: {today}")
                else:
                    logger.debug(f"  无法解析时间: {time_text}，视为今天")
                    return True  # 无法解析时间

            is_today = article_date == today
            if not is_today:
                logger.debug(f"  文章日期 {article_date} 不是今天 {today}，跳过")
            return is_today
        except Exception as e:
            logger.debug(f"  检查文章时间时出错: {e}，视为今天")
            return True

    def _click_original_tab(self, driver: webdriver.Chrome) -> bool:
        """点击'原发'标签，返回是否成功点击"""
        try:
            human_like_delay(1, 2)

            # 首先检查当前是否已在"原发"视图
            try:
                active_tab = driver.find_element(By.CSS_SELECTOR, "div.timeline__tab__tags a.active")
                if "原发" in active_tab.text:
                    logger.info("当前已处于'原发'视图，无需切换")
                    return True
            except:
                pass  # 未找到激活标签或当前不在原发视图，继续尝试切换

            # 查找原发标签 - 使用更精确的选择器
            tab_selectors = [
                (By.CSS_SELECTOR, 'div.timeline__tab__tags a'),
                (By.XPATH, '//div[contains(@class, "timeline__tab__tags")]//a[contains(text(), "原发")]'),
                (By.XPATH, '//a[contains(text(), "原发")]'),
            ]

            for selector_type, selector_value in tab_selectors:
                try:
                    tabs = driver.find_elements(selector_type, selector_value)
                    for tab in tabs:
                        if "原发" in tab.text:
                            driver.execute_script("arguments[0].click();", tab)
                            logger.info("已成功点击'原发'标签")
                            human_like_delay(0.5, 1.0)
                            return True
                except:
                    continue

            logger.error("未找到'原发'标签，将抓取所有内容（包括转发和回复）")
            return False

        except Exception as e:
            logger.error(f"点击'原发'标签时出错: {e}")
            return False

    def _click_next_page(self, driver: webdriver.Chrome) -> bool:
        """点击下一页按钮"""
        try:
            next_selectors = [
                '.pagination__next:not(.disabled)',
                'a:has-text("下一页"):not(.disabled)',
                '.pagination__next',
            ]

            for selector in next_selectors:
                try:
                    btns = driver.find_elements(By.CSS_SELECTOR, selector)
                    if btns and btns[0].is_displayed() and btns[0].is_enabled():
                        btn = btns[0]
                        logger.info("  找到下一页按钮，准备点击")
                        driver.execute_script("arguments[0].scrollIntoView();", btn)
                        human_like_delay(1, 2)
                        driver.execute_script("arguments[0].click();", btn)
                        human_like_delay(1, 2)
                        return True
                except:
                    continue

            logger.info("  没有找到下一页按钮，可能已到最后一页")
            return False
        except Exception as e:
            logger.warning(f"点击下一页失败: {e}")
            return False

    def _get_month_file_path(self, article_data: Dict[str, str], author_id: str, author_name: str) -> Path:
        """获取月份文件路径

        文件命名规则：{author_id}_{year_month}.html
        例如：3045778209_2026-02.html

        Args:
            article_data: 文章数据（包含时间信息）
            author_id: 作者ID
            author_name: 作者名称

        Returns:
            文件路径对象
        """
        time_text = article_data['time']
        author_dir = self.output_dir / f"{author_id}_{sanitize_filename(author_name)}"
        author_dir.mkdir(exist_ok=True)

        year_month = get_month_from_time(time_text)
        filename = f"{author_id}_{year_month}.html"
        return author_dir / filename

    def _save_article_to_file(self, filepath: Path, article_data: Dict[str, str], author: Dict[str, str]) -> None:
        """保存文章到HTML文件（按月归档）

        Args:
            filepath: 文件路径（不带扩展名）
            article_data: 文章数据字典
            author: 作者信息字典
        """
        try:
            absolute_time = convert_to_absolute_time(article_data['time'])
            article_link = article_data.get('link', author['link'])

            # ========== 生成单篇文章的HTML ==========
            html_content = f"<div class='article'>\n"
            html_content += f"  <div class='header'>\n"
            html_content += f"    <div class='meta-info'>\n"
            html_content += f"      <span class='author'>作者: {author['name']}</span><br>\n"
            html_content += f"      <span class='author-link'>链接: <a href='{article_link}' target='_blank'>{article_link}</a></span><br>\n"
            html_content += f"      <span class='publish-time'>发布时间: {absolute_time}</span>\n"
            html_content += f"    </div>\n"
            html_content += f"  </div>\n"
            html_content += f"  <div class='content'>\n"

            # 转义HTML特殊字符并格式化内容
            content_lines = article_data['content'].replace('<', '&lt;').replace('>', '&gt;').split('\n')
            formatted_content = '<br>'.join(content_lines)
            html_content += f"    {formatted_content}\n"

            html_content += f"  </div>\n"
            html_content += f"  <hr class='divider'>\n"
            html_content += f"</div>\n\n"

            html_filepath = filepath.with_suffix('.html')

            # ========== 读取现有文件内容（追加模式） ==========
            existing_content = ""
            if html_filepath.exists():
                with open(html_filepath, 'r', encoding='utf-8') as f:
                    existing_content = f.read()

            # ========== 如果是新文件，添加HTML头部 ==========
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
            border-radius: 0 10px 0;
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
                font-size: 1.em;
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

            # 将新内容插入到<h1>标签之后
            header_end = existing_content.find("</h1>")
            if header_end != -1:
                insert_pos = header_end + 5
                combined_content = existing_content[:insert_pos] + html_content + existing_content[insert_pos:]
            else:
                insert_pos = existing_content.rfind("</div>")
                combined_content = existing_content[:insert_pos] + html_content + existing_content[insert_pos:]

            # 写入HTML文件
            with open(html_filepath, 'w', encoding='utf-8') as f:
                f.write(combined_content)
            logger.debug(f"成功向文件 {html_filepath.name} 写入文章内容")

        except Exception as e:
            logger.error(f"写入文章到HTML文件失败 {filepath}: {e}")


class SummaryGenerator:
    """汇总报告生成器"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def write_update_summary(self, update_entries: List[Dict]) -> None:
        """写入更新汇总文件"""
        try:
            summary_file = self.output_dir / "update_latest.html"

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
                    border-radius: 0 10px 0;
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

            # 写入每个作者的信息
            for author, entries in authors_dict.items():
                html_content += f"        <div class=\"author-section\">\n"
                html_content += f"            <h2 class=\"author-title\">作者: {author}</h2>\n"

                for entry in entries:
                    absolute_time = convert_to_absolute_time(entry['time'])
                    html_content += f"            <div class=\"article\">\n"
                    html_content += f"                <div class=\"article-header\">\n"
                    html_content += f"                    <h3 class=\"article-title\">{entry['title']}</h3>\n"
                    html_content += f"                    <div class=\"meta-info\">\n"
                    html_content += f"                        <span class=\"publish-time\">发布时间: {absolute_time}</span><br>\n"
                    html_content += f"                        <span class=\"article-link\">链接: <a href=\"{entry['link']}\" target=\"_blank\">{entry['link']}</a></span>\n"
                    html_content += f"                    </div>\n"
                    html_content += f"                </div>\n"
                    html_content += f"                <div class=\"content\">\n"
                    content_lines = entry['content'].replace('<', '&lt;').replace('>', '&gt;').split('\n')
                    formatted_content = '<br>'.join(content_lines)
                    html_content += f"                    {formatted_content}\n"
                    html_content += f"                </div>\n"
                    html_content += f"            </div>\n"

                html_content += f"        </div>\n"

            html_content += """    </div>
</body>
</html>"""

            # 写入HTML文件
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logger.info(f"更新汇总已写入文件: {summary_file}")

        except Exception as e:
            logger.error(f"写入更新汇总文件失败: {e}")


class ScraperOrchestrator:
    """爬虫编排器"""

    def __init__(self, headless: bool = False, output_dir: str = ""):
        self.browser_manager = BrowserManager(headless=headless)
        self.cookie_handler = CookieHandler()
        self.output_dir = output_dir or gconfig.get('xueqiu_data_dir', '/data/stock_monitor/xueqiu_data')
        self.author_extractor = AuthorExtractor(self.browser_manager, self.output_dir)
        self.article_extractor = ArticleExtractor(self.browser_manager, self.author_extractor, self.output_dir)
        self.summary_generator = SummaryGenerator(self.output_dir)
        self.update_today = True

    def run(self, test_mode: bool = False, skip_login: bool = False) -> None:
        """运行抓取流程

        Args:
            test_mode: 测试模式（限制页面数）
            skip_login: 是否跳过登录（使用保存的cookies）
        """
        try:
            logger.info("开始初始化抓取流程...")
            self.article_extractor.test_mode = test_mode
            driver = self.browser_manager.get_driver()

            # ========== 处理登录 ==========
            cookies_loaded = self.cookie_handler.load_cookies(driver)

            if skip_login:
                # 跳过登录，使用已保存的 cookies
                logger.info("跳过登录，使用已保存的 cookies")
                driver.get('https://xueqiu.com')
                human_like_delay(3, 5)

                # 验证 cookies 是否有效
                if cookies_loaded:
                    if not self.author_extractor._verify_login_status(driver):
                        logger.error("Cookies 已失效，请手动更新 cookies 文件")
                        raise Exception("Cookies 已失效，请手动更新 cookies 文件")
            else:
                # 手动登录
                logger.info("请手动登录雪球")
                logger.info("="*60)
                driver.get('https://xueqiu.com')
                input("\n登录完成后，请按回车键继续...")
                self.cookie_handler.save_cookies(driver)
                logger.info("已保存 cookies")

            # ========== 筛选需要处理的作者 ==========
            # 检查是否存在手动编辑的作者列表文件
            authors = []
            authors_file = Path(self.output_dir) / "all_authors.json"
            if authors_file.exists():
                try:
                    with open(authors_file, 'r', encoding='utf-8') as f:
                        authors = json.load(f)
                    logger.info(f"从 {authors_file} 读取到 {len(authors)} 个作者（可手动编辑该文件）")
                except Exception as e:
                    logger.error(f"读取作者列表失败：{e}，使用原始列表")
            else:
                authors = self.author_extractor.get_following_authors()
                logger.info(f"获取到 {len(authors)} 个关注的作者")
                #保存所有 authors 列表
                authors_file = Path(self.output_dir) / "all_authors.json"
                try:
                    with open(authors_file, 'w', encoding='utf-8') as f:
                        json.dump(authors, f, ensure_ascii=False, indent=2)
                    logger.info(f"所有作者列表已保存到：{authors_file}")
                except Exception as e:
                    logger.error(f"保存作者列表失败：{e}")

            authors_to_process = authors

            # 应用测试模式或最大作者数限制
            if test_mode:
                authors_to_process = authors_to_process[:2]


            total_articles = 0
            all_update_entries = []

            for i, author in enumerate(authors_to_process):
                logger.info(f"\n{'='*60}")
                logger.info(f"正在处理第 {i+1}/{len(authors_to_process)} 个作者: {author['name']}")
                logger.info(f"作者ID: {author['id']}")
                logger.info(f"{'='*60}\n")

                try:
                    articles, update_entries = self.article_extractor.get_author_articles(author)
                    total_articles += len(articles)
                    logger.info(f"[完成] 作者 {author['name']} 获得 {len(articles)} 篇文章")

                    # all-history 模式下，如果一个作者一篇文章都没保存，说明出错了
                    if not self.update_today and len(articles) == 0:
                        logger.error(f"[严重错误] all-history 模式下，作者 {author['name']} 一篇文章都未保存，可能哪里出错了")
                        logger.error("请检查：1) 网络连接 2) 登录状态 3) 雪球页面结构是否变化")
                        raise Exception(f"all-history 模式下作者 {author['name']} 未抓取到任何文章")

                    if self.update_today and update_entries:
                        all_update_entries.extend(update_entries)
                except Exception as e:
                    logger.error(f"[错误] 处理作者 {author['name']} 时出错: {e}")
                    raise

            # ========== 生成汇总文件 ==========
            if self.update_today and all_update_entries:
                self.summary_generator.write_update_summary(all_update_entries)

            # ========== 输出汇总信息 ==========
            logger.info(f"\n{'='*60}")
            logger.info(f"所有抓取完成！")
            logger.info(f"处理了 {len(authors_to_process)} 个作者")
            logger.info(f"共保存 {total_articles} 篇文章")
            logger.info(f"文章保存在: {self.output_dir}")
            logger.info(f"{'='*60}\n")

        finally:
            # ========== 清理资源 ==========
            logger.info("正在保存最新的 cookies...")
            self.cookie_handler.save_cookies(self.browser_manager.get_driver())
            self.browser_manager.quit()


def main():
    parser = argparse.ArgumentParser(description='雪球大V文章抓取工具 (Selenium版本)')
    parser.add_argument('--mode', '-m', type=str, default='full',
                       choices=['full', 'test'],
                       help='运行模式: full(全部), test(测试3个)')
    parser.add_argument('--no-headless', action='store_true', default=False,
                       help='显示浏览器窗口 (默认无头模式运行)')
    parser.add_argument('--all-history', action='store_true', default=False,
                       help='抓取所有历史文章 (默认只抓取当天)')
    parser.add_argument('--force-login', action='store_true', default=False,
                       help='强制重新登录 (默认使用保存的cookies)')

    args = parser.parse_args()

    headless = not args.no_headless
    update_today = not args.all_history
    skip_login = not args.force_login

    logger.info("雪球大V文章抓取工具 (Selenium版本)")
    logger.info("="*60)
    logger.info("使用说明：")
    logger.info("1. 程序会自动保存登录 Cookies")
    logger.info("2. 文章按作者分目录保存")
    logger.info("3. 基于文件存在判断自动去重")
    logger.info("4. 文件名格式：作者ID_年月.html")
    logger.info(f"当前运行模式：{args.mode}")
    logger.info(f"当前headless模式：{'启用' if headless else '禁用'}")
    logger.info(f"当前update-today模式：{'启用' if update_today else '禁用'}")
    logger.info(f"当前skip-login模式：{'启用' if skip_login else '禁用'}")

    scraper = ScraperOrchestrator(headless=headless, output_dir=gconfig.get('xueqiu_data_dir', '/data/stock_monitor/xueqiu_data'))
    scraper.update_today = update_today
    scraper.article_extractor.update_today = update_today

    test_mode = False

    if args.mode == 'full':
        test_mode = False
        logger.info("模式：抓取所有关注作者")
    elif args.mode == 'test':
        test_mode = True
        logger.info("模式：测试模式（前3个作者）")

    try:
        scraper.run(test_mode=test_mode, skip_login=skip_login)
    except KeyboardInterrupt:
        logger.info("\n用户中断，正在退出...")
    except Exception as e:
        logger.error(f"程序运行出错: {e}")


if __name__ == "__main__":
    main()