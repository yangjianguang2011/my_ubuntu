"""
增强版Cookies处理器
集成到雪球爬虫系统中
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from cookie_manager import CookieStateManager, AdvancedCookieValidator
from config import setup_logger

logger = setup_logger("enhanced_cookie_handler")


class EnhancedCookieHandler:
    """增强版Cookies处理器"""
    
    def __init__(self, cookies_file: str = "xueqiu_cookies.txt"):
        self.cookies_file = cookies_file
        self.state_manager = CookieStateManager()
        self.validator = AdvancedCookieValidator()
        self.last_successful_validation = None
    
    def load_and_validate_cookies(self, driver: webdriver.Chrome) -> bool:
        """加载并验证Cookies"""
        logger.info("开始加载并验证Cookies...")
        
        # 首先尝试从文件加载Cookies
        if not self._load_cookies_from_file(driver):
            logger.error("无法从文件加载Cookies")
            return False
        
        # 验证Cookies有效性
        validation_result = self.state_manager.validate_and_manage(driver)
        
        if validation_result:
            logger.info("Cookies验证通过，状态正常")
            self.last_successful_validation = time.time()
            return True
        else:
            logger.warning("Cookies验证失败")
            return False
    
    def _load_cookies_from_file(self, driver: webdriver.Chrome) -> bool:
        """从文件加载Cookies，支持标准Netscape格式和简单格式"""
        if not Path(self.cookies_file).exists():
            logger.warning(f"Cookies文件不存在: {self.cookies_file}")
            return False
        
        try:
            # 访问域名以设置cookies上下文
            driver.get("https://xueqiu.com")
            time.sleep(2)
            
            with open(self.cookies_file, "r", encoding="utf-8") as f:
                content = f.read()
                
                # 检查是否为标准Netscape格式（包含注释行）
                is_netscape_format = content.strip().startswith('# Netscape HTTP Cookie File')
                
                if is_netscape_format:
                    # 解析标准Netscape格式
                    logger.info("检测到标准Netscape格式cookies文件")
                    cookie_pairs = self._parse_netscape_cookies(content)
                else:
                    # 解析简单格式（key1=value1; key2=value2 或 key1=value1\nkey2=value2）
                    logger.info("检测到简单格式cookies文件")
                    cookie_pairs = self._parse_simple_cookies(content)
                
                # 添加cookies到浏览器
                loaded_count = 0
                for cookie in cookie_pairs:
                    try:
                        driver.add_cookie(cookie)
                        loaded_count += 1
                    except Exception as e:
                        logger.warning(f"添加cookie失败: {e} - {cookie.get('name', 'unknown')}")
                
                logger.info(f"从文件加载了 {loaded_count} 个cookies")
                return loaded_count > 0
        
        except Exception as e:
            logger.error(f"加载cookies文件失败: {e}")
        
        return False

    def _parse_netscape_cookies(self, content: str) -> List[Dict]:
        """解析标准Netscape格式的cookies"""
        cookie_pairs = []
        
        for line in content.strip().split('\n'):
            line = line.strip()
            # 跳过注释行和空行
            if not line or line.startswith('#'):
                continue
                
            # Netscape格式：domain flag path secure expiration name value
            parts = line.split('\t')
            if len(parts) >= 7:  # 至少需要7个字段
                try:
                    domain = parts[0].strip()
                    path = parts[2].strip()
                    name = parts[5].strip()
                    value = parts[6].strip()
                    
                    cookie = {
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": path,
                    }
                    
                    # 处理secure标志
                    secure_flag = parts[3].strip()
                    if secure_flag.upper() == 'TRUE':
                        cookie["secure"] = True
                    
                    # 处理expiration（可选）
                    try:
                        expires = int(parts[4].strip())
                        if expires > 0:
                            cookie["expiry"] = expires
                    except (ValueError, IndexError):
                        pass  # 忽略无效的过期时间
                    
                    cookie_pairs.append(cookie)
                except Exception as e:
                    logger.debug(f"解析Netscape格式cookie行失败: {e} - {line}")
        
        return cookie_pairs

    def _parse_simple_cookies(self, content: str) -> List[Dict]:
        """解析简单格式的cookies（支持分号分隔或换行分隔）"""
        cookie_pairs = []
        
        # 检查是否为分号分隔的格式
        if ';' in content:
            cookie_parts = content.split(';')
        else:
            # 按换行分割
            cookie_parts = content.strip().split('\n')
        
        for cookie_str in cookie_parts:
            cookie_str = cookie_str.strip()
            if '=' in cookie_str:
                try:
                    # 分离名称和值
                    pos = cookie_str.find('=')
                    name = cookie_str[:pos].strip()
                    value = cookie_str[pos+1:].strip()
                    
                    # 清理引号
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    cookie = {
                        "name": name,
                        "value": value,
                        "domain": ".xueqiu.com",
                        "path": "/"
                    }
                    
                    cookie_pairs.append(cookie)
                except Exception as e:
                    logger.debug(f"解析简单格式cookie失败: {e} - {cookie_str}")
        
        return cookie_pairs
    
    def save_cookies_safely(self, driver: webdriver.Chrome) -> bool:
        """安全地保存Cookies（仅在验证通过时）"""
        try:
            # 验证当前登录状态
            validation_result = self.validator.validate_cookies(driver, level='standard')
            
            if not validation_result['valid']:
                logger.warning("当前登录状态无效，跳过保存Cookies")
                return False
            
            # 获取有效的cookies
            cookies = driver.get_cookies()
            xueqiu_cookies = [c for c in cookies if "xueqiu" in c.get("domain", "") or "snowball" in c.get("domain", "")]
            
            if not xueqiu_cookies:
                logger.warning("没有找到雪球相关的cookies，不保存")
                return False
            
            # 保存为文本格式
            cookie_strings = []
            for cookie in xueqiu_cookies:
                cookie_strings.append(f"{cookie['name']}={cookie['value']}")
            
            cookie_text = "; ".join(cookie_strings)
            
            with open(self.cookies_file, "w", encoding="utf-8") as f:
                f.write(cookie_text)
            
            logger.info(f"成功保存 {len(xueqiu_cookies)} 个cookies到 {self.cookies_file}")
            
            # 同时创建备份
            self.state_manager.backup_manager.create_backup(xueqiu_cookies)
            
            return True
            
        except Exception as e:
            logger.error(f"保存cookies失败: {e}")
            return False
    
    def handle_expired_cookies(self, driver: webdriver.Chrome) -> bool:
        """处理过期的Cookies"""
        logger.info("检测到Cookies过期，开始处理...")
        
        # 尝试智能恢复
        recovery_success = self.state_manager.validate_and_manage(driver)
        
        if recovery_success:
            logger.info("Cookies恢复成功")
            return True
        else:
            logger.error("Cookies恢复失败，需要手动登录")
            return False
    
    def get_cookies_status(self) -> Dict:
        """获取Cookies状态信息"""
        status = {
            'cookies_file_exists': Path(self.cookies_file).exists(),
            'last_validation': self.state_manager.state.get('last_validation'),
            'validation_result': self.state_manager.state.get('validation_result'),
            'recovery_attempts': self.state_manager.state.get('recovery_attempts', 0),
            'last_backup_time': self.state_manager.state.get('last_backup_time'),
            'available_backups': len(self.state_manager.backup_manager.get_available_backups())
        }
        
        return status


class EnhancedBrowserManager:
    """增强版浏览器管理器，集成Cookies管理"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = None
        self.wait = None
        self.cookie_handler = EnhancedCookieHandler()
    
    def init_driver(self) -> webdriver.Chrome:
        """初始化浏览器驱动"""
        options = Options()
        
        if self.headless:
            options.add_argument("--headless=new")
        
        # 基础配置
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        if self.headless:
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-plugins")
            options.add_argument("--disable-images")
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.add_argument("--lang=zh-CN")
            options.add_argument("--window-size=1920,1080")
        else:
            options.add_argument("--start-maximized")
        
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            logger.info("浏览器初始化成功")
            self.wait = WebDriverWait(self.driver, 5)
            return self.driver
        except Exception as e:
            logger.error(f"浏览器初始化失败: {e}")
            raise
    
    def get_driver(self) -> webdriver.Chrome:
        """获取浏览器驱动实例"""
        if not self.driver:
            self.init_driver()
        return self.driver
    
    def quit(self) -> None:
        """关闭浏览器"""
        if self.driver:
            # 安全地保存cookies
            self.cookie_handler.save_cookies_safely(self.driver)
            try:
                self.driver.quit()
                logger.info("浏览器已关闭")
            except Exception as e:
                logger.error(f"关闭浏览器时出错: {e}")


def integrate_with_existing_scraper():
    """与现有爬虫集成的示例"""
    logger.info("开始集成增强版Cookies管理到现有爬虫系统...")
    
    # 创建增强版浏览器管理器
    browser_manager = EnhancedBrowserManager(headless=True)
    driver = browser_manager.get_driver()
    
    # 使用增强版Cookies处理器
    cookie_handler = EnhancedCookieHandler()
    
    try:
        # 加载并验证Cookies
        if not cookie_handler.load_and_validate_cookies(driver):
            logger.error("Cookies验证失败，需要处理过期情况")
            
            # 处理过期的Cookies
            if not cookie_handler.handle_expired_cookies(driver):
                logger.error("无法恢复Cookies，需要手动登录")
                return False
        
        # 继续执行原有的爬虫逻辑
        logger.info("Cookies验证通过，可以继续执行爬虫逻辑")
        
        # 这里可以调用原有的爬虫功能
        # ...
        
        return True
        
    except Exception as e:
        logger.error(f"集成过程中出错: {e}")
        return False
    finally:
        browser_manager.quit()


if __name__ == "__main__":
    # 示例：测试增强版Cookies管理
    success = integrate_with_existing_scraper()
    if success:
        print("增强版Cookies管理集成成功！")
    else:
        print("集成失败，请检查配置。")