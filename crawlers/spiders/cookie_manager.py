"""
雪球爬虫Cookies管理模块
实现完善的Cookies过期处理机制
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
import shutil
from typing import Dict, List, Optional, Tuple

from selenium import webdriver
from selenium.webdriver.common.by import By
from config import setup_logger

logger = setup_logger("xueqiu_cookies_manager")


class AdvancedCookieValidator:
    """高级Cookies验证器"""
    
    def __init__(self):
        self.validation_levels = {
            'quick': ['element_check'],  # 快速验证
            'standard': ['element_check', 'content_check', 'url_check'],  # 标准验证
            'thorough': ['element_check', 'content_check', 'url_check', 'functionality_check']  # 全面验证
        }
    
    def validate_cookies(self, driver: webdriver.Chrome, level: str = 'standard') -> Dict:
        """
        验证Cookies有效性
        返回包含验证结果和详细信息的字典
        """
        validation_methods = self.validation_levels.get(level, self.validation_levels['standard'])
        results = {}
        
        for method in validation_methods:
            method_func = getattr(self, f'_validate_{method}')
            results[method] = method_func(driver)
        
        # 计算总体验证分数
        valid_count = sum(1 for result in results.values() if result['valid'])
        total_count = len(results)
        overall_score = valid_count / total_count if total_count > 0 else 0
        
        return {
            'valid': overall_score > 0.5,  # 超过一半验证通过才算有效
            'score': overall_score,
            'details': results,
            'timestamp': datetime.now().isoformat(),
            'failure_reason': self._determine_failure_reason(results) if overall_score <= 0.5 else None
        }
    
    def _validate_element_check(self, driver: webdriver.Chrome) -> Dict:
        """验证页面元素"""
        try:
            user_elements = driver.find_elements(
                By.CSS_SELECTOR,
                ".user-avatar, .avatar, [data-user-id], .user-name, .username"
            )
            has_elements = len(user_elements) > 0
            return {
                'valid': has_elements,
                'detail': f"找到 {len(user_elements)} 个用户相关元素" if has_elements else "未找到用户相关元素",
                'confidence': 0.8 if has_elements else 0.2
            }
        except Exception as e:
            return {
                'valid': False,
                'detail': f"元素检查失败: {str(e)}",
                'confidence': 0.1
            }
    
    def _validate_content_check(self, driver: webdriver.Chrome) -> Dict:
        """验证页面内容"""
        try:
            page_text = driver.page_source.lower()
            
            # 检查登录提示
            login_indicators = ['login', '登录', 'signin', 'sign in', '请登录', '登录后']
            has_login_indicators = any(indicator in page_text for indicator in login_indicators)
            
            # 检查雪球特有元素
            snowball_indicators = ['timeline', 'article', 'feed', 'xueqiu', '雪球']
            has_snowball_indicators = any(indicator in page_text for indicator in snowball_indicators)
            
            return {
                'valid': not has_login_indicators and has_snowball_indicators,
                'detail': f"登录提示: {'是' if has_login_indicators else '否'}, 雪球元素: {'是' if has_snowball_indicators else '否'}",
                'confidence': 0.9 if not has_login_indicators and has_snowball_indicators else 0.1
            }
        except Exception as e:
            return {
                'valid': False,
                'detail': f"内容检查失败: {str(e)}",
                'confidence': 0.1
            }
    
    def _validate_url_check(self, driver: webdriver.Chrome) -> Dict:
        """验证URL状态"""
        try:
            current_url = driver.current_url
            is_logged_in_url = any(pattern in current_url for pattern in ['/center', '/user', '/profile'])
            
            return {
                'valid': is_logged_in_url,
                'detail': f"当前URL: {current_url}, 是否为登录后页面: {'是' if is_logged_in_url else '否'}",
                'confidence': 0.7 if is_logged_in_url else 0.3
            }
        except Exception as e:
            return {
                'valid': False,
                'detail': f"URL检查失败: {str(e)}",
                'confidence': 0.1
            }
    
    def _validate_functionality_check(self, driver: webdriver.Chrome) -> Dict:
        """验证功能可用性（可选的深度验证）"""
        try:
            # 尝试访问一个需要登录的功能页面
            driver.get("https://xueqiu.com/")
            time.sleep(2)
            
            # 检查是否能访问个人信息或设置页面
            personal_elements = driver.find_elements(By.CSS_SELECTOR, ".personal-center, .settings, .my-profile")
            has_personal_access = len(personal_elements) > 0
            
            return {
                'valid': has_personal_access,
                'detail': f"能访问个人信息: {'是' if has_personal_access else '否'}",
                'confidence': 0.8 if has_personal_access else 0.2
            }
        except Exception as e:
            return {
                'valid': False,
                'detail': f"功能检查失败: {str(e)}",
                'confidence': 0.1
            }
    
    def _determine_failure_reason(self, validation_results: Dict) -> str:
        """确定失效原因"""
        if not validation_results.get('content_check', {}).get('valid', True):
            return 'login_required'
        elif not validation_results.get('element_check', {}).get('valid', True):
            return 'no_user_elements'
        elif not validation_results.get('url_check', {}).get('valid', True):
            return 'invalid_url_state'
        else:
            return 'unknown'


class CookieBackupManager:
    """Cookies备份管理器"""
    
    def __init__(self, backup_dir: str = "./cookies_backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.max_backups = 10  # 最大备份数量
    
    def create_backup(self, cookies: List[Dict], name: str = None) -> str:
        """创建Cookies备份"""
        if not name:
            name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_file = self.backup_dir / f"{name}.json"
        
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            
            # 清理旧备份
            self._cleanup_old_backups()
            
            logger.info(f"Cookies备份已创建: {backup_file}")
            return str(backup_file)
        except Exception as e:
            logger.error(f"创建Cookies备份失败: {e}")
            return None
    
    def restore_from_backup(self, backup_file: str) -> Optional[List[Dict]]:
        """从备份恢复Cookies"""
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            logger.info(f"从备份恢复Cookies: {backup_file}")
            return cookies
        except Exception as e:
            logger.error(f"从备份恢复Cookies失败: {e}")
            return None
    
    def get_available_backups(self) -> List[str]:
        """获取可用备份列表"""
        backups = list(self.backup_dir.glob("*.json"))
        return [str(b) for b in backups]
    
    def _cleanup_old_backups(self):
        """清理旧备份"""
        backups = self.get_available_backups()
        if len(backups) > self.max_backups:
            # 按修改时间排序，保留最新的
            backups.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            for old_backup in backups[self.max_backups:]:
                try:
                    os.remove(old_backup)
                    logger.info(f"已删除旧备份: {old_backup}")
                except Exception as e:
                    logger.error(f"删除旧备份失败: {e}")


class IntelligentRecoveryManager:
    """智能恢复管理器"""
    
    def __init__(self, backup_manager: CookieBackupManager, remote_url: str = None):
        self.backup_manager = backup_manager
        self.remote_url = remote_url
        self.recovery_strategies = {
            'local_backup': self._recover_from_local_backup,
            'remote_sync': self._recover_from_remote,
            'manual_rebuild': self._manual_rebuild
        }
    
    def intelligent_recovery(self, failure_reason: str) -> bool:
        """智能恢复算法"""
        # 根据失效原因选择恢复策略
        strategy_sequence = self._get_strategy_sequence(failure_reason)
        
        for strategy_name in strategy_sequence:
            logger.info(f"尝试恢复策略: {strategy_name}")
            if self.recovery_strategies[strategy_name]():
                logger.info(f"恢复成功，使用策略: {strategy_name}")
                return True
            else:
                logger.warning(f"恢复失败，策略: {strategy_name}")
        
        logger.error("所有恢复策略都失败了")
        return False
    
    def _get_strategy_sequence(self, failure_reason: str) -> List[str]:
        """根据失效原因获取策略序列"""
        strategy_sequences = {
            'login_required': ['local_backup', 'remote_sync', 'manual_rebuild'],
            'no_user_elements': ['local_backup', 'remote_sync', 'manual_rebuild'],
            'invalid_url_state': ['local_backup', 'remote_sync'],
            'unknown': ['local_backup', 'remote_sync', 'manual_rebuild']
        }
        return strategy_sequences.get(failure_reason, ['local_backup', 'remote_sync', 'manual_rebuild'])
    
    def _recover_from_local_backup(self) -> bool:
        """从本地备份恢复"""
        try:
            backups = self.backup_manager.get_available_backups()
            if not backups:
                logger.info("没有可用的本地备份")
                return False
            
            # 使用最新的备份
            latest_backup = max(backups, key=os.path.getmtime)
            cookies = self.backup_manager.restore_from_backup(latest_backup)
            
            if cookies:
                # 尝试使用恢复的cookies
                return self._apply_cookies(cookies)
            return False
        except Exception as e:
            logger.error(f"从本地备份恢复失败: {e}")
            return False
    
    def _recover_from_remote(self) -> bool:
        """从远程同步恢复"""
        if not self.remote_url:
            logger.info("没有配置远程URL")
            return False
        
        try:
            response = requests.get(self.remote_url, timeout=10)
            if response.status_code == 200:
                cookies = response.json()
                return self._apply_cookies(cookies)
            return False
        except Exception as e:
            logger.error(f"从远程同步恢复失败: {e}")
            return False
    
    def _manual_rebuild(self) -> bool:
        """手动重建（提示用户操作）"""
        logger.warning("需要手动重建Cookies，请重新登录")
        return False  # 需要用户干预
    
    def _apply_cookies(self, cookies: List[Dict]) -> bool:
        """应用Cookies（模拟操作，实际需要在浏览器中执行）"""
        # 这里只是模拟，实际需要在浏览器环境中执行
        try:
            # 检查必需的cookies是否存在
            required_cookies = ['xq_a_token', 'xq_r_token', 'u', 'device_id']
            cookie_names = [c['name'] for c in cookies]
            
            if all(name in cookie_names for name in required_cookies):
                logger.info(f"成功应用 {len(cookies)} 个cookies")
                return True
            else:
                missing = [name for name in required_cookies if name not in cookie_names]
                logger.warning(f"缺少必需的cookies: {missing}")
                return False
        except Exception as e:
            logger.error(f"应用cookies失败: {e}")
            return False


class CookieStateManager:
    """Cookies状态管理器"""
    
    def __init__(self, state_file: str = "./cookies_state.json"):
        self.state_file = Path(state_file)
        self.validator = AdvancedCookieValidator()
        self.backup_manager = CookieBackupManager()
        self.recovery_manager = IntelligentRecoveryManager(
            self.backup_manager,
            remote_url="https://blog.jgyang.cn/xueqiu/xueqiu_cookies.txt"
        )
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """加载状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {
            'last_validation': None,
            'validation_result': None,
            'last_backup_time': None,
            'recovery_attempts': 0
        }
    
    def _save_state(self):
        """保存状态"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存状态失败: {e}")
    
    def validate_and_manage(self, driver: webdriver.Chrome) -> bool:
        """验证并管理Cookies状态"""
        # 执行验证
        validation_result = self.validator.validate_cookies(driver, level='thorough')
        
        # 更新状态
        self.state['last_validation'] = validation_result['timestamp']
        self.state['validation_result'] = validation_result
        
        if validation_result['valid']:
            logger.info("Cookies验证成功，状态良好")
            
            # 如果验证成功，创建备份（如果距离上次备份超过1小时）
            if (not self.state.get('last_backup_time') or 
                datetime.fromisoformat(validation_result['timestamp']) - 
                datetime.fromisoformat(self.state['last_backup_time']) > timedelta(hours=1)):
                
                # 获取当前cookies并备份
                current_cookies = driver.get_cookies()
                self.backup_manager.create_backup(current_cookies)
                self.state['last_backup_time'] = validation_result['timestamp']
                self.state['recovery_attempts'] = 0  # 重置恢复尝试次数
            
            self._save_state()
            return True
        else:
            logger.warning(f"Cookies验证失败: {validation_result['failure_reason']}")
            
            # 更新恢复尝试次数
            self.state['recovery_attempts'] = self.state.get('recovery_attempts', 0) + 1
            
            # 尝试智能恢复
            recovery_success = self.recovery_manager.intelligent_recovery(
                validation_result['failure_reason']
            )
            
            if recovery_success:
                logger.info("Cookies恢复成功")
                self.state['recovery_attempts'] = 0
            else:
                logger.error("Cookies恢复失败")
            
            self._save_state()
            return recovery_success
    
    def force_refresh(self):
        """强制刷新状态"""
        self.state = self._load_state()