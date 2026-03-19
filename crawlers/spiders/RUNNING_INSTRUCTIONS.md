# 雪球爬虫系统 - 运行说明

## 系统概述

这是一个功能完备的雪球网数据爬虫系统，具有先进的Cookies管理机制，能够自动处理登录状态验证、Cookies失效检测和智能恢复。

## 文件结构

```
crawlers/spiders/
├── xueqiu_scraper.py           # 主爬虫脚本（已增强）
├── enhanced_cookie_handler.py  # 增强版Cookies处理器
├── cookie_manager.py          # Cookies管理核心模块
├── xueqiu_utils.py            # 工具函数
├── xueqiu_cookies.txt         # Cookies存储文件
├── run_xueqiu.sh              # 运行脚本
└── COOKIES_SYSTEM_README.md   # 系统说明
```

## 运行方式

### 1. 直接运行（推荐）
```bash
cd /home/jgyang/.openclaw/workspace/my-ubuntu/crawlers/spiders
python xueqiu_scraper.py --mode=full
```

### 2. 使用运行脚本
```bash
cd /home/jgyang/.openclaw/workspace/my-ubuntu/crawlers/spiders
bash run_xueqiu.sh
```

## 命令行参数

- `--mode full|test` - 运行模式（完整或测试）
- `--no-headless` - 显示浏览器窗口
- `--all-history` - 抓取所有历史文章
- `--force-login` - 强制重新登录

## 高级功能

### Cookies管理
- 自动验证Cookies有效性
- 智能恢复失效的Cookies
- 安全的Cookies保存机制
- 多重验证确保准确性

### 运行示例

```bash
# 完整运行
python xueqiu_scraper.py --mode=full

# 测试模式
python xueqiu_scraper.py --mode=test

# 显示浏览器窗口
python xueqiu_scraper.py --no-headless

# 强制重新登录
python xueqiu_scraper.py --force-login
```

## 系统特性

1. **智能验证** - 四层验证机制确保登录状态准确性
2. **安全保存** - 只在验证通过时保存Cookies，防止保存无效状态
3. **自动恢复** - 失效时自动尝试多种恢复策略
4. **状态监控** - 实时追踪Cookies状态变化
5. **向后兼容** - 保留原有功能，平滑升级

## 维护说明

- Cookies文件: `xueqiu_cookies.txt`
- 日志文件: 程序会自动记录详细日志
- 备份: 系统会自动管理Cookies备份

## 注意事项

- 首次运行需要手动登录并保存Cookies
- 系统会自动处理Cookies过期问题
- 在Docker环境中运行已优化
- 保持网络连接稳定以确保最佳效果