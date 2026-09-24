"""金属/碳酸锂价格抓取与消息构建 —— telegram / wechat 两个入口的公共实现。

由 `get_combined_prices_telegram.py` 与 `get_metal_prices_wechat.py` 共用（两者原本几乎完全重复，仅推送渠道不同）。
"""
#!/usr/bin/env python3
"""
获取多种金属价格和碳酸锂价格的综合脚本
包含贵金属、加密货币、工业金属以及碳酸锂价格，并计算每日涨跌幅
"""

import requests
import json
from datetime import datetime, timedelta
from pathlib import Path
import os
import time
import re

try:
    from ._bootstrap import ensure_project_root
except ImportError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from config import get_path, setup_logger
from stock_monitor.core.notification import send_system_notification

# 历史价格文件：放在数据目录（容器内 /data，随数据卷持久化；不再写进镜像内的脚本目录）
_DATA_DIR = get_path("stock_monitor", "stock_monitor_data_dir", "/data/stock_monitor_data")
_PRICES_FILE = os.path.join(_DATA_DIR, "prices_history.txt")


def get_supported_symbols():
    """获取API支持的所有符号"""
    try:
        response = requests.get("https://api.gold-api.com/symbols", timeout=10)
        if response.status_code == 200:
            symbols = response.json()
            return {item['symbol']: item['name'] for item in symbols}
    except Exception as e:
        print(f"获取支持的符号列表失败: {e}")
        # 返回默认支持的符号
        return {
            "XAU": "Gold",
            "XAG": "Silver", 
            "XPD": "Palladium",
            "XPT": "Platinum",
            "BTC": "Bitcoin",
            "ETH": "Ethereum",
            "HG": "Copper"
        }
    return {}


def get_price_for_symbol(symbol, currency="USD"):
    """获取指定符号的价格"""
    try:
        url = f"https://api.gold-api.com/price/{symbol}/{currency}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data
    except Exception as e:
        print(f"获取 {symbol} 价格失败: {e}")
    return None


def get_all_metals_prices():
    """获取所有贵金属和加密货币的价格"""
    supported_symbols = get_supported_symbols()
    metals_data = {}
    
    # 定义要获取价格的主要金属和加密货币
    symbols_to_fetch = ["XAU", "XAG", "XPD", "XPT", "BTC", "ETH", "HG"]
    
    print("正在获取多种金属和加密货币价格...")
    
    for symbol in symbols_to_fetch:
        if symbol in supported_symbols:
            print(f"获取 {supported_symbols[symbol]} ({symbol}) 价格...")
            data = get_price_for_symbol(symbol)
            if data and 'price' in data:
                metals_data[symbol] = {
                    "name": supported_symbols[symbol],
                    "price": data['price'],
                    "symbol": symbol,
                    "updated_at": (data.get('updatedAtReadable') or data.get('updatedAt')
                              or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                }
            time.sleep(0.5)  # 避免请求过于频繁
    
    return metals_data


def get_lithium_carbonate_price():
    """
    从我的钢铁网获取工业级碳酸锂价格
    """
    url = "https://www.mysteel.com/mmlc/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"❌ 请求失败，状态码: {response.status_code}")
            return None
            
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找包含价格信息的表格
        table = soup.find('table', {'id': 'table-index'})
        if not table:
            print("❌ 未找到价格表格")
            return None
            
        # 查找工业级碳酸锂的行 - 只获取早盘数据
        rows = table.find_all('tr')
        lithium_data = []
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 8:  # 确保有足够的列
                name_cell = cells[0].get_text(strip=True) if cells[0] else ""
                
                # 检查是否是工业级碳酸锂早盘
                if "工业级碳酸锂（早盘）" in name_cell:
                    data = {
                        "name": name_cell,
                        "specifications": cells[1].get_text(strip=True) if cells[1] else "",
                        "lowest_price": cells[2].get_text(strip=True),
                        "highest_price": cells[3].get_text(strip=True),
                        "middle_price": cells[4].get_text(strip=True),
                        "change": cells[5].get_text(strip=True) if len(cells) > 5 else "",
                        "unit": cells[6].get_text(strip=True) if len(cells) > 6 else "",
                        "date": cells[7].get_text(strip=True) if len(cells) > 7 else ""
                    }
                    lithium_data.append(data)
                    break  # 只取早盘
        
        return lithium_data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求异常: {e}")
        return None
    except Exception as e:
        print(f"❌ 解析数据时出错: {e}")
        return None



def save_daily_prices(metals_data, lithium_data):
    """保存当日价格到文本文件"""
    today = datetime.now().strftime("%Y-%m-%d")
    prices_file = Path(_PRICES_FILE)  # 保存在数据目录（随数据卷持久化）
    os.makedirs(prices_file.parent, exist_ok=True)
    
    # 准备今日数据
    today_records = []
    
    # 添加金属和加密货币数据
    for symbol, data in metals_data.items():
        unit = 'USD/oz' if symbol in ['XAU', 'XAG', 'XPD', 'XPT'] else ('USD' if symbol in ['BTC', 'ETH'] else 'USD/lb')
        today_records.append(f"{today}|{symbol}|{data['name']}|{data['price']}|{unit}")
    
    # 添加碳酸锂数据
    if lithium_data:
        for data in lithium_data:
            try:
                price = int(re.sub(r'[^-\d.]', '', str(data['middle_price']))) if data['middle_price'] and data['middle_price'] != '-' else 0
            except:
                price = 0
            today_records.append(f"{today}|Li2CO3|{data['name']}|{price}|{data['unit']}")
    
    # 追加写入文本文件
    with open(prices_file, 'a', encoding='utf-8') as f:
        for record in today_records:
            f.write(record + '\n')
    
    print(f"✅ 已将 {len(today_records)} 条价格记录保存到 {prices_file}")


def load_historical_prices():
    """加载历史价格数据"""
    prices_file = Path(_PRICES_FILE)  # 从数据目录加载
    
    if not prices_file.exists():
        print("⚠️ 历史价格文件不存在，将创建新的")
        # 返回空字典结构
        return []
    
    try:
        with open(prices_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        records = []
        for line in lines:
            line = line.strip()
            if line:
                parts = line.split('|')
                if len(parts) >= 5:
                    record = {
                        'date': datetime.strptime(parts[0], '%Y-%m-%d'),
                        'symbol': parts[1],
                        'name': parts[2],
                        'price': float(parts[3]) if parts[3] else 0,
                        'unit': parts[4]
                    }
                    records.append(record)
        return records
    except Exception as e:
        print(f"❌ 加载历史价格数据失败: {e}")
        return []


def calculate_daily_weekly_changes(historical_records, metals_data, lithium_data):
    """计算每日和每周涨幅"""
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    last_week = today - timedelta(days=7)
    
    changes = {}
    
    # 计算金属和加密货币的涨幅
    for symbol, current_data in metals_data.items():
        current_price = current_data['price']
        
        # 获取昨日价格
        yesterday_records = [record for record in historical_records 
                           if record['symbol'] == symbol and record['date'].date() == yesterday]
        
        # 获取一周前价格
        last_week_records = [record for record in historical_records 
                           if record['symbol'] == symbol and record['date'].date() == last_week]
        
        daily_change = "N/A"
        weekly_change = "N/A"
        
        if yesterday_records:
            prev_price = yesterday_records[0]['price']
            daily_change = calculate_change_percentage(current_price, prev_price)
        
        if last_week_records:
            prev_week_price = last_week_records[0]['price']
            weekly_change = calculate_change_percentage(current_price, prev_week_price)
        
        changes[symbol] = {
            'daily_change': daily_change,
            'weekly_change': weekly_change
        }
    
    # 计算碳酸锂的涨幅
    if lithium_data:
        for li_data in lithium_data:
            try:
                current_price = int(re.sub(r'[^-\d.]', '', str(li_data['middle_price']))) if li_data['middle_price'] and li_data['middle_price'] != '-' else 0
            except:
                current_price = 0
            
            # 查找历史碳酸锂价格
            lithium_hist = [record for record in historical_records 
                           if record['symbol'] == 'Li2CO3' and record['date'].date() == yesterday]
            
            last_week_lithium = [record for record in historical_records 
                               if record['symbol'] == 'Li2CO3' and record['date'].date() == last_week]
            
            daily_change = "N/A"
            weekly_change = "N/A"
            
            if lithium_hist:
                prev_price = lithium_hist[0]['price']
                daily_change = calculate_change_percentage(current_price, prev_price)
            
            if last_week_lithium:
                prev_week_price = last_week_lithium[0]['price']
                weekly_change = calculate_change_percentage(current_price, prev_week_price)
            
            changes['Li2CO3'] = {
                'daily_change': daily_change,
                'weekly_change': weekly_change
            }
    
    return changes


def calculate_change_percentage(current_price, previous_price):
    """计算价格变化百分比"""
    if not current_price or not previous_price or float(previous_price) == 0:
        return "N/A"
    
    current = float(current_price)
    previous = float(previous_price)
    change_pct = ((current - previous) / abs(previous)) * 100
    return f"{change_pct:+.2f}%"


def format_combined_message(metals_data, lithium_data, changes=None):
    """格式化综合价格消息"""
    message = "🟡 国际贵金属、加密货币及碳酸锂价格更新\n\n"
    
    # 贵金属部分
    precious_metals = {}
    crypto_currencies = {}
    industrial_metals = {}
    
    symbol_categories = {
        "XAU": "precious", "XAG": "precious", "XPD": "precious", "XPT": "precious",
        "BTC": "crypto", "ETH": "crypto",
        "HG": "industrial"
    }
    
    for symbol, data in metals_data.items():
        category = symbol_categories.get(symbol, "other")
        if category == "precious":
            precious_metals[symbol] = data
        elif category == "crypto":
            crypto_currencies[symbol] = data
        elif category == "industrial":
            industrial_metals[symbol] = data
    
    # 贵金属部分
    if precious_metals:
        message += "🏆 贵金属价格:\n"
        for symbol in ["XAU", "XAG", "XPD", "XPT"]:
            if symbol in precious_metals:
                data = precious_metals[symbol]
                if symbol == "XAU":  # Gold
                    daily_change = changes.get(symbol, {}).get('daily_change', 'N/A') if changes else 'N/A'
                    weekly_change = changes.get(symbol, {}).get('weekly_change', 'N/A') if changes else 'N/A'
                    message += f"  🟡 {data['name']} ({data['symbol']}): ${data['price']:,.2f}/oz"
                    if daily_change != 'N/A':
                        message += f" ({daily_change} 日, {weekly_change} 周)"
                    message += "\n"
                elif symbol == "XAG":  # Silver
                    daily_change = changes.get(symbol, {}).get('daily_change', 'N/A') if changes else 'N/A'
                    weekly_change = changes.get(symbol, {}).get('weekly_change', 'N/A') if changes else 'N/A'
                    message += f"  ⚪ {data['name']} ({data['symbol']}): ${data['price']:,.2f}/oz"
                    if daily_change != 'N/A':
                        message += f" ({daily_change} 日, {weekly_change} 周)"
                    message += "\n"
                elif symbol == "XPD":  # Palladium
                    daily_change = changes.get(symbol, {}).get('daily_change', 'N/A') if changes else 'N/A'
                    weekly_change = changes.get(symbol, {}).get('weekly_change', 'N/A') if changes else 'N/A'
                    message += f"  🥉 {data['name']} ({data['symbol']}): ${data['price']:,.2f}/oz"
                    if daily_change != 'N/A':
                        message += f" ({daily_change} 日, {weekly_change} 周)"
                    message += "\n"
                elif symbol == "XPT":  # Platinum
                    daily_change = changes.get(symbol, {}).get('daily_change', 'N/A') if changes else 'N/A'
                    weekly_change = changes.get(symbol, {}).get('weekly_change', 'N/A') if changes else 'N/A'
                    message += f"  ✨ {data['name']} ({data['symbol']}): ${data['price']:,.2f}/oz"
                    if daily_change != 'N/A':
                        message += f" ({daily_change} 日, {weekly_change} 周)"
                    message += "\n"
        message += "\n"
    
    # 加密货币部分
    if crypto_currencies:
        message += "🔵 加密货币价格:\n"
        for symbol in ["BTC", "ETH"]:
            if symbol in crypto_currencies:
                data = crypto_currencies[symbol]
                if symbol == "BTC":  # Bitcoin
                    daily_change = changes.get(symbol, {}).get('daily_change', 'N/A') if changes else 'N/A'
                    weekly_change = changes.get(symbol, {}).get('weekly_change', 'N/A') if changes else 'N/A'
                    message += f"  ₿ {data['name']} ({data['symbol']}): ${data['price']:,.2f}"
                    if daily_change != 'N/A':
                        message += f" ({daily_change} 日, {weekly_change} 周)"
                    message += "\n"
                elif symbol == "ETH":  # Ethereum
                    daily_change = changes.get(symbol, {}).get('daily_change', 'N/A') if changes else 'N/A'
                    weekly_change = changes.get(symbol, {}).get('weekly_change', 'N/A') if changes else 'N/A'
                    message += f"  ♚ {data['name']} ({data['symbol']}): ${data['price']:,.2f}"
                    if daily_change != 'N/A':
                        message += f" ({daily_change} 日, {weekly_change} 周)"
                    message += "\n"
        message += "\n"
    
    # 工业金属部分
    if industrial_metals:
        message += "🏭 工业金属价格:\n"
        for symbol in ["HG"]:
            if symbol in industrial_metals:
                data = industrial_metals[symbol]
                if symbol == "HG":  # Copper
                    daily_change = changes.get(symbol, {}).get('daily_change', 'N/A') if changes else 'N/A'
                    weekly_change = changes.get(symbol, {}).get('weekly_change', 'N/A') if changes else 'N/A'
                    message += f"  🟢 {data['name']} ({data['symbol']}): ${data['price']:,.2f}/lb"
                    if daily_change != 'N/A':
                        message += f" ({daily_change} 日, {weekly_change} 周)"
                    message += "\n"
        message += "\n"
    
    # 碳酸锂部分
    if lithium_data:
        message += "🔋 碳酸锂价格:\n"
        for data in lithium_data:
            name = data['name']
            middle_price = data['middle_price']
            change = data['change']
            unit = data['unit']
            
            # 提取数字并格式化
            try:
                middle_numeric = int(re.sub(r'[^\d.]', '', str(middle_price))) if middle_price and middle_price != '-' else 0
                middle_formatted = f"{middle_numeric:,}"
            except:
                middle_formatted = str(middle_price)
            
            # 获取碳酸锂的涨跌数据
            daily_change = changes.get('Li2CO3', {}).get('daily_change', 'N/A') if changes else 'N/A'
            weekly_change = changes.get('Li2CO3', {}).get('weekly_change', 'N/A') if changes else 'N/A'
            
            message += f"  {name}: 中间价{middle_formatted}{unit}"
            if change and change != '-':
                message += f" | 涨跌{change}{unit}"
            if daily_change != 'N/A':
                message += f" ({daily_change} 日, {weekly_change} 周)"
            message += "\n"
        message += "\n"
    
    # 添加时间戳
    all_times = []
    for data in metals_data.values():
        all_times.append(data['updated_at'])
    if lithium_data:
        for data in lithium_data:
            all_times.append(data['date'])
    
    if all_times:
        latest_update = max(all_times)  # 简单取最新时间
        message += f"📅 更新时间: {latest_update}\n"
    
    message += f"📡 数据源: api.gold-api.com & mysteel.com\n\n"
    
    # 添加标签
    all_symbols = list(metals_data.keys())
    tags = []
    if "XAU" in all_symbols: tags.append("#金价")
    if "XAG" in all_symbols: tags.append("#银价")
    if "XPD" in all_symbols: tags.append("#钯金")
    if "XPT" in all_symbols: tags.append("#铂金")
    if "BTC" in all_symbols: tags.append("#比特币")
    if "ETH" in all_symbols: tags.append("#以太坊")
    if "HG" in all_symbols: tags.append("#铜价")
    if lithium_data: tags.extend(["#碳酸锂", "#锂价"])
    tags.append(f"#{datetime.now().strftime('%Y%m%d')}")
    
    message += " ".join(tags)
    
    return message


def send_to_wechat(message):
    try:
        print("try to send message to wechat....")
        ret = send_system_notification("金属价格", message) 
        print(ret)
        return ret.get("success",False)
    except Exception as e:
        print(f"❌ 发送Telegram消息时出错: {e}")
        return False

def send_to_telegram(message):
    """
    通过Telegram发送消息到ibot
    """
    # 开关：默认关闭（ENABLE_TELEGRAM=1 时才真正发送）；代码保留不删除
    if os.getenv("ENABLE_TELEGRAM", "0") != "1":
        print("Telegram 推送已禁用（ENABLE_TELEGRAM != 1），跳过发送")
        return False
    try:
        # 获取Telegram机器人令牌和聊天ID
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("IBOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("IBOT_CHAT_ID")
        
        # 如果环境变量未设置，尝试从OpenClaw配置文件读取
        if not bot_token or not chat_id:
            try:
                with open('/root/.openclaw/openclaw.json', 'r') as f:
                    config = json.load(f)
                    if 'channels' in config and 'telegram' in config['channels']:
                        if not bot_token:
                            bot_token = config['channels']['telegram'].get('botToken')
                        if not chat_id:
                            allow_from_list = config['channels']['telegram'].get('allowFrom', [])
                            if allow_from_list:
                                chat_id = str(allow_from_list[0])
            except FileNotFoundError:
                print("未找到OpenClaw配置文件")
            except json.JSONDecodeError:
                print("OpenClaw配置文件格式错误")
            except Exception as e:
                print(f"读取OpenClaw配置时出错: {e}")
        
        if not bot_token:
            print("警告: 未找到TELEGRAM_BOT_TOKEN环境变量")
            print("为测试目的，将在控制台显示消息内容:")
            print(message)
            return False
        
        if not chat_id:
            print("警告: 未找到TELEGRAM_CHAT_ID环境变量")
            print("为测试目的，将在控制台显示消息内容:")
            print(message)
            return False
        
        # 构建Telegram API URL
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        params = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        # 发送请求
        response = requests.post(url, data=params, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get("ok"):
            print("✅ 综合价格信息已成功发送到Telegram ibot")
            return True
        else:
            print(f"❌ 发送失败: {result}")
            return False
    except Exception as e:
        print(f"❌ 发送Telegram消息时出错: {e}")
        return False


