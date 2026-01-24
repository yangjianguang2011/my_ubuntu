import requests
from datetime import datetime
from logger_config import logger, gconfig

SERVER = gconfig.get('message_server', 'https://message.yourdomain.cn:5555')
USERNAME = gconfig.get('message_username', 'root')
TOKEN = gconfig.get('message_token', '12123121')
CHANNEL = gconfig.get('message_channel', 'wechat')  

def send_message(title, description, content, channel=None):
    """
    使用自定义消息推送服务器发送消息
    :param title: 消息标题
    :param description: 消息描述
    :param content: 消息内容
    :param channel: 推送渠道，默认使用环境变量配置
    :return: 推送结果
    """
    try:
        # 使用环境变量中的配置
        push_channel = channel or CHANNEL
        
        # 构建GET请求URL
        url = f"{SERVER}/push/{USERNAME}?title={title}&description={description}&content={content}&token={TOKEN}&channel={push_channel}"
        
        if gconfig['platform'] == 'windows':
            #do net send request in windows way, just for testing purpose
            logger.info("send message in windows way")
            result = {"success": True, "message": "测试模式下的推送成功", "data": {}}
        else:
            response = requests.get(url, timeout=10)
            result = response.json()
# POST 方式
# result = requests.post(f"{SERVER}/push/{USERNAME}", json={
#     "title": title,
#     "description": description,
#     "content": content,
#     "token": TOKEN
# })

        if result.get("success"):
            logger.info(f"消息推送成功: {title}")
            return {"success": True, "message": "推送成功", "data": result}
        else:
            error_msg = result.get("message", "未知错误")
            logger.error(f"消息推送失败: {error_msg}")
            return {"success": False, "message": error_msg, "data": result}
    
    except Exception as e:
        logger.error(f"发送消息推送时出错: {str(e)}")
        return {"success": False, "message": f"推送异常: {str(e)}"}


def send_stock_alert(stock_name, stock_code, current_price, target_price, alert_type, change_pct=None):
    """
    发送股票价格警报
    :param stock_name: 股票名称
    :param stock_code: 股票代码
    :param current_price: 当前价格
    :param target_price: 目标价格（报警价格）或阈值百分比
    :param alert_type: 报警类型 ('low' 表示低于目标价, 'high' 表示高于目标价)
    :param change_pct: 实际涨跌幅百分比（可选，仅用于change_pct类型的警报）
    :return: 推送结果
    """
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if alert_type == 'low':
            title = f"【低价警报】{stock_name}({stock_code})"
            content = f"""【股票价格警报】
            
股票名称: {stock_name}
股票代码: {stock_code}
当前价格: {current_price:.2f}元
目标价格: {target_price:.2f}元
价格已跌破目标价格！
时间: {current_time}

请及时关注！
"""
        elif alert_type == 'high':
            title = f"【高价警报】{stock_name}({stock_code})"
            content = f"""【股票价格警报】
            
股票名称: {stock_name}
股票代码: {stock_code}
当前价格: {current_price:.2f}元
目标价格: {target_price:.2f}元
价格已超过目标价格！
时间: {current_time}

请及时关注！
"""
        elif alert_type == 'limit_up':
            title = f"【涨停警报】{stock_name}({stock_code})"
            content = f"""【股票涨停警报】
            
股票名称: {stock_name}
股票代码: {stock_code}
当前价格: {current_price:.2f}元
股票已涨停！
时间: {current_time}

请及时关注！
"""
        elif alert_type == 'limit_down':
            title = f"【跌停警报】{stock_name}({stock_code})"
            content = f"""【股票跌停警报】
            
股票名称: {stock_name}
股票代码: {stock_code}
当前价格: {current_price:.2f}元
股票已跌停！
时间: {current_time}

请及时关注！
"""
        elif alert_type == 'key_price':
            title = f"【关键价位警报】{stock_name}({stock_code})"
            content = f"""【股票关键价位警报】
            
股票名称: {stock_name}
股票代码: {stock_code}
当前价格: {current_price:.2f}元
目标价位: {target_price:.2f}元
价格已接近关键价位！
时间: {current_time}

请及时关注！
"""
        elif alert_type == 'change_pct':
            # 使用实际的涨跌幅数据，如果没有提供则使用target_price（阈值）作为备选
            actual_change_pct = change_pct if change_pct is not None else target_price
            direction = "上涨" if actual_change_pct > 0 else "下跌" if actual_change_pct < 0 else "持平"
            title = f"【涨跌幅警报】{stock_name}({stock_code})"
            
            # 确保所有要格式化的值都不是None
            price_value = current_price if current_price is not None else 0.0
            change_pct_value = actual_change_pct if actual_change_pct is not None else 0.0
            target_pct_value = target_price if target_price is not None else 0.0
            
            content = f"""【股票涨跌幅警报】
            
股票名称: {stock_name}
股票代码: {stock_code}
当前价格: {price_value:.2f}元
涨跌幅: {change_pct_value:.2f}%
股票{direction}超过{target_pct_value:.2f}%！
时间: {current_time}

请及时关注！
"""
        else:
            logger.error(f"未知的警报类型: {alert_type}")
            return {"success": False, "message": "未知的警报类型"}
        
        # 发送推送，使用新的消息推送函数
        description = f"股票价格警报: {stock_name}({stock_code})"
        return send_message(title, description, content)
    
    except Exception as e:
        logger.error(f"发送股票警报时出错: {str(e)}")
        return {"success": False, "message": f"发送警报异常: {str(e)}"}


def send_system_notification(title, content):
    """
    发送系统通知
    :param title: 通知标题
    :param content: 通知内容
    :return: 推送结果
    """
    try:
        # 发送推送，使用新的消息推送函数
        description = title  # 使用标题作为描述
        return send_message(title, description, content)
    
    except Exception as e:
        logger.error(f"发送系统通知时出错: {str(e)}")
        return {"success": False, "message": f"发送通知异常: {str(e)}"}


if __name__ == "__main__":
    # 测试通知功能
    logger.info("测试通知功能...")
    
    # 测试发送股票警报
    result = send_stock_alert("测试股票", "0001", 10.5, 10.0, 'low')
    logger.info(f"测试警报结果: {result}")
    
    # 测试发送系统通知
    result = send_system_notification("测试标题", "这是一条测试消息")
    logger.info(f"测试通知结果: {result}")