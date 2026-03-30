import json
import os
import time
from datetime import datetime, timedelta

from config import get_path, setup_logger

# 导入自定义模块
from ..data_fetchers.stock_data_fetcher import get_stock_info
from .notification import send_stock_alert, send_system_notification

logger = setup_logger(__name__)
from .config_manager import config_manager


class StockMonitor:
    def __init__(self):
        self.notified_stocks = {}  # 记录已发送通知的股票状态，避免重复通知
        self.stocks = config_manager.get_all_stocks()
        self.check_interval = config_manager.get_check_interval()
        self.global_notification_enabled = (
            config_manager.get_global_notification_enabled()
        )
        # 注册为配置管理器的观察者
        config_manager.add_observer(self)

    def on_config_change(self, change_type, data):
        """处理配置变更通知"""
        try:
            if change_type == "settings_update":
                # 更新系统设置
                if "check_interval" in data:
                    self.check_interval = data["check_interval"]
                    logger.info(f"监控检查间隔已更新为: {self.check_interval}秒")
                if "global_notification_enabled" in data:
                    self.global_notification_enabled = data[
                        "global_notification_enabled"
                    ]
                    logger.info(
                        f"全局通知开关已更新为: {self.global_notification_enabled}"
                    )
            elif change_type == "stock_add":
                # 添加新股票
                new_stock = data
                # 检查股票是否已存在
                existing_stock = next(
                    (s for s in self.stocks if s["code"] == new_stock["code"]), None
                )
                if not existing_stock:
                    self.stocks.append(new_stock)
                    logger.info(
                        f"新股票 {new_stock['name']}({new_stock['code']}) 已添加到监控列表"
                    )
            elif change_type == "stock_update":
                # 更新股票配置
                code = data["code"]
                updates = data["updates"]
                for i, stock in enumerate(self.stocks):
                    if stock["code"] == code:
                        # 合并更新
                        self.stocks[i] = {**stock, **updates}
                        logger.info(f"股票 {stock['name']}({code}) 配置已更新")
                        break
            elif change_type == "stock_delete":
                # 删除股票
                code = data["code"]
                self.stocks = [stock for stock in self.stocks if stock["code"] != code]
                # 清除该股票的相关通知状态
                keys_to_remove = [
                    key
                    for key in self.notified_stocks.keys()
                    if key.startswith(f"{code}_")
                ]
                for key in keys_to_remove:
                    del self.notified_stocks[key]
                logger.info(f"股票 {code} 已从监控列表中删除")
        except Exception as e:
            logger.error(f"处理配置变更通知时出错: {e}")

    def start_monitoring(self):
        """
        开始监控所有股票
        """
        logger.info("开始股票价格监控...")
        logger.info(f"监控间隔: {self.check_interval} 秒")
        logger.info(f"监控股票数量: {len(self.stocks)}")
        logger.info(f"全局消息设置：{self.global_notification_enabled}")

        # 发送系统启动通知
        startup_msg = f"股票价格监控系统已启动\n监控股票数量: {len(self.stocks)}\n检查间隔: {self.check_interval}秒"
        send_system_notification("股票监控系统启动", startup_msg)
        try:
            while True:
                current_time = datetime.now()

                # 检查是否为指定的报告时间（开市后5分钟或闭市后5分钟）
                report_type = is_market_open_time_specific(current_time)
                if report_type:
                    self.send_market_summary_report(report_type)

                # 检查是否在开市时间内
                if is_market_open(current_time):
                    try:
                        logger.info("=" * 50)
                        logger.info(
                            f"开始新一轮股票价格检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )

                        # 计算每只股票的检查间隔时间
                        if len(self.stocks) > 0:
                            per_stock_interval = self.check_interval / len(self.stocks)
                        else:
                            per_stock_interval = (
                                self.check_interval
                            )  # 如果没有股票，使用完整间隔

                        for i, stock in enumerate(self.stocks):
                            current_price, status = self.check_single_stock(stock)

                            if status == "price_fetch_failed":
                                logger.warning(
                                    f"无法获取 {stock['name']}({stock['code']}) 的价格"
                                )
                            elif status in [
                                "low_alert_sent",
                                "high_alert_sent",
                                "limit_up_alert_sent",
                                "limit_down_alert_sent",
                                "key_price_alert_sent",
                                "change_pct_alert_sent",
                            ]:
                                logger.info(
                                    f"已发送 {status} 给 {stock['name']}({stock['code']})"
                                )
                            elif status == "normal":
                                logger.debug(
                                    f"{stock['name']}({stock['code']}) 价格正常"
                                )
                            elif status == "error":
                                logger.error(
                                    f"检查 {stock['name']}({stock['code']}) 时发生错误"
                                )

                            # 如果不是最后一只股票，等待分配的时间间隔
                            if i < len(self.stocks) - 1:
                                logger.debug(
                                    f"等待 {per_stock_interval:.2f} 秒后检查下一只股票"
                                )
                                time.sleep(per_stock_interval)

                        logger.info(f"本轮检查完成，所有股票检查完毕")

                    except KeyboardInterrupt:
                        logger.info("用户中断监控")
                        # 发送系统停止通知
                        stop_msg = "股票价格监控系统已停止"
                        send_system_notification("股票监控系统停止", stop_msg)
                        break
                    except Exception as e:
                        logger.error(f"监控过程中发生错误: {str(e)}")
                        time.sleep(60)  # 出错后等待1分钟再继续
                else:
                    # 不在开市时间，但仍然需要检查报告时间，所以不能休眠太长时间
                    # logger.info(f"当前时间 {current_time.strftime('%H:%M:%S')} 不在开市时间，但继续监控报告时间...")

                    # 检查是否是收市时间，如果是，则清除所有报警状态
                    # 收市时间是16:00之后到第二天9:30之前
                    # 检查是否为工作日（周一到周五）
                    if current_time.weekday() < 5:  # 0是周一，4是周五
                        if (
                            current_time.time()
                            > datetime.strptime("16:00", "%H:%M").time()
                        ):
                            # 如果当前时间在16:00之后，表示是收市时间，清除所有报警状态
                            self.notified_stocks.clear()
                            # logger.info("收市时间，已清除所有报警状态")
                        elif (
                            current_time.time()
                            < datetime.strptime("09:30", "%H:%M").time()
                        ):
                            # 如果当前时间在9:30之前，也表示是收市时间，清除所有报警状态
                            self.notified_stocks.clear()
                            # logger.info("收市时间，已清除所有报警状态")

                    # 不再等待到下一个开市时间，而是短暂休眠后继续检查报告时间
                    # 这样可以确保在闭市后5分钟（例如16:05）能发送闭市报告
                    time.sleep(60)  # 休眠1分钟后继续检查
        finally:
            # 程序结束，无需关闭浏览器，因为现在使用API方式获取数据
            logger.info("程序结束")

    def check_single_stock(self, stock):
        """
        检查单个股票的价格
        :param stock: 股票配置字典
        :return: 当前价格和状态信息
        """
        try:
            # 获取当前价格 - 使用股票对象
            stock_info = get_stock_info(stock)
            current_price = stock_info.get("price")
            if current_price is None:
                logger.warning(f"无法获取 {stock['name']}({stock['code']}) 的价格")
                return None, "price_fetch_failed"

            # logger.info(f"{stock['name']}({stock['code']}) 当前价格: {current_price}")

            # 检查是否需要发送低价警报
            if stock["low_alert_price"] and current_price <= stock["low_alert_price"]:
                alert_key = f"{stock['code']}_low_{stock['low_alert_price']}"
                # 检查是否需要发送重复报警
                should_send = False
                if not self.notified_stocks.get(alert_key):
                    # 首次报警
                    should_send = True
                else:
                    # 检查是否达到重发时间
                    last_alert_time = self.notified_stocks[alert_key]["time"]
                    alert_count = self.notified_stocks[alert_key]["count"]  # 已发送次数
                    # 计算下次发送间隔：1小时，2小时，4小时...，以2的幂次递增
                    next_interval = (
                        timedelta(hours=2 ** (alert_count - 1))
                        if alert_count >= 1
                        else timedelta(hours=1)
                    )
                    if datetime.now() - last_alert_time >= next_interval:
                        should_send = True

                if should_send:
                    logger.info(
                        f"发现低价警报: {stock['name']}({stock['code']}) 当前价格 {current_price} <= 目标价格 {stock['low_alert_price']}"
                    )
                    # 检查全局和单个股票的消息发送开关
                    # if self.global_notification_enabled and self.stock_notification_enabled.get(stock['code'], True):
                    if self.global_notification_enabled and stock.get(
                        "notification_enabled", True
                    ):
                        result = send_stock_alert(
                            stock["name"],
                            stock["code"],
                            current_price,
                            stock["low_alert_price"],
                            "low",
                        )
                        if result["success"]:
                            # 更新通知状态，包含时间戳和发送次数
                            if self.notified_stocks.get(alert_key):
                                count = self.notified_stocks[alert_key]["count"] + 1
                            else:
                                count = 1
                            self.notified_stocks[alert_key] = {
                                "time": datetime.now(),
                                "count": count,
                            }
                        return current_price, "low_alert_sent"
                    else:
                        logger.info(f"消息发送已关闭: {stock['name']}({stock['code']})")
                        return current_price, "normal"

            # 检查是否需要发送高价警报
            if stock["high_alert_price"] and current_price >= stock["high_alert_price"]:
                alert_key = f"{stock['code']}_high_{stock['high_alert_price']}"
                # 检查是否需要发送重复报警
                should_send = False
                if not self.notified_stocks.get(alert_key):
                    # 首次报警
                    should_send = True
                else:
                    # 检查是否达到重发时间
                    last_alert_time = self.notified_stocks[alert_key]["time"]
                    alert_count = self.notified_stocks[alert_key]["count"]  # 已发送次数
                    # 计算下次发送间隔：1小时，2小时，4小时...，以2的幂次递增
                    next_interval = (
                        timedelta(hours=2 ** (alert_count - 1))
                        if alert_count >= 1
                        else timedelta(hours=1)
                    )
                    if datetime.now() - last_alert_time >= next_interval:
                        should_send = True

                if should_send:
                    logger.info(
                        f"发现高价警报: {stock['name']}({stock['code']}) 当前价格 {current_price} >= 目标价格 {stock['high_alert_price']}"
                    )
                    # 检查全局和单个股票的消息发送开关
                    if self.global_notification_enabled and stock.get(
                        "notification_enabled", True
                    ):
                        result = send_stock_alert(
                            stock["name"],
                            stock["code"],
                            current_price,
                            stock["high_alert_price"],
                            "high",
                        )
                        if result["success"]:
                            # 更新通知状态，包含时间戳和发送次数
                            if self.notified_stocks.get(alert_key):
                                count = self.notified_stocks[alert_key]["count"] + 1
                            else:
                                count = 1
                            self.notified_stocks[alert_key] = {
                                "time": datetime.now(),
                                "count": count,
                            }
                        return current_price, "high_alert_sent"
                    else:
                        logger.info(f"消息发送已关闭: {stock['name']}({stock['code']})")
                        return current_price, "normal"

            # 检查关键价位警报
            if stock["key_price_alerts"]:
                for key_price_info in stock["key_price_alerts"]:
                    key_price = key_price_info["price"]
                    price_type = key_price_info["type"]

                    # 检查价格是否接近关键价位（在1%范围内）
                    if abs(current_price - key_price) / key_price <= 0.01:
                        alert_key = f"{stock['code']}_key_price_{key_price}"
                        # 检查是否需要发送重复报警
                        should_send = False
                        if not self.notified_stocks.get(alert_key):
                            # 首次报警
                            should_send = True
                        else:
                            # 检查是否达到重发时间
                            last_alert_time = self.notified_stocks[alert_key]["time"]
                            alert_count = self.notified_stocks[alert_key][
                                "count"
                            ]  # 已发送次数
                            # 计算下次发送间隔：1小时，2小时，4小时...，以2的幂次递增
                            next_interval = (
                                timedelta(hours=2 ** (alert_count - 1))
                                if alert_count >= 1
                                else timedelta(hours=2)
                            )
                            if datetime.now() - last_alert_time >= next_interval:
                                should_send = True

                        if should_send:
                            logger.info(
                                f"发现关键价位警报: {stock['name']}({stock['code']}) 当前价格 {current_price} 接近{price_type} {key_price}"
                            )
                            # 检查全局和单个股票的消息发送开关
                            if self.global_notification_enabled and stock.get(
                                "notification_enabled", True
                            ):
                                result = send_stock_alert(
                                    stock["name"],
                                    stock["code"],
                                    current_price,
                                    key_price,
                                    "key_price",
                                )
                                if result["success"]:
                                    # 更新通知状态，包含时间戳和发送次数
                                    if self.notified_stocks.get(alert_key):
                                        count = (
                                            self.notified_stocks[alert_key]["count"] + 1
                                        )
                                    else:
                                        count = 1
                                    self.notified_stocks[alert_key] = {
                                        "time": datetime.now(),
                                        "count": count,
                                    }
                                return current_price, "key_price_alert_sent"
                            else:
                                logger.info(
                                    f"消息发送已关闭: {stock['name']}({stock['code']})"
                                )
                                return current_price, "normal"

            # 检查涨跌幅警报
            if stock["change_pct_alerts"]:
                # stock_info = get_stock_info(stock)
                change_pct = stock_info.get("change_pct")

                if change_pct is not None:
                    for change_pct_info in stock["change_pct_alerts"]:
                        threshold_pct = change_pct_info["pct"]
                        pct_type = change_pct_info["type"]

                        # 检查是否超过涨跌幅阈值
                        # 如果阈值为正数，表示上涨或下跌的绝对值超过该值时报警
                        # 如果阈值为负数，表示下跌超过该绝对值时报警
                        should_alert = False
                        if threshold_pct >= 0:
                            # 正阈值：当涨跌幅绝对值超过阈值时报警（上涨或下跌都可能触发）
                            should_alert = abs(change_pct) >= threshold_pct
                        else:
                            # 负阈值：当跌幅超过阈值绝对值时报警（仅下跌触发）
                            should_alert = change_pct <= threshold_pct

                        if should_alert:
                            alert_key = f"{stock['code']}_change_pct_{threshold_pct}"
                            # 检查是否需要发送重复报警
                            should_send = False
                            if not self.notified_stocks.get(alert_key):
                                # 首次报警
                                should_send = True
                            else:
                                # 检查是否达到重发时间
                                last_alert_time = self.notified_stocks[alert_key][
                                    "time"
                                ]
                                alert_count = self.notified_stocks[alert_key][
                                    "count"
                                ]  # 已发送次数
                                # 计算下次发送间隔：1小时，2小时，4小时...，以2的幂次递增
                                next_interval = (
                                    timedelta(hours=2 ** (alert_count - 1))
                                    if alert_count >= 1
                                    else timedelta(hours=1)
                                )
                                if datetime.now() - last_alert_time >= next_interval:
                                    should_send = True

                            if should_send:
                                alert_direction = (
                                    "上涨"
                                    if change_pct > 0
                                    else "下跌" if change_pct < 0 else "无变化"
                                )
                                logger.info(
                                    f"发现涨跌幅警报: {stock['name']}({stock['code']}) {alert_direction}{abs(change_pct):.2f}%，超过阈值{threshold_pct}%"
                                )
                                # 检查全局和单个股票的消息发送开关
                                if self.global_notification_enabled and stock.get(
                                    "notification_enabled", True
                                ):
                                    result = send_stock_alert(
                                        stock["name"],
                                        stock["code"],
                                        current_price,
                                        threshold_pct,
                                        "change_pct",
                                        change_pct=change_pct,  # 传递实际的涨跌幅数据
                                    )
                                    if result["success"]:
                                        # 更新通知状态，包含时间戳和发送次数
                                        if self.notified_stocks.get(alert_key):
                                            count = (
                                                self.notified_stocks[alert_key]["count"]
                                                + 1
                                            )
                                        else:
                                            count = 1
                                        self.notified_stocks[alert_key] = {
                                            "time": datetime.now(),
                                            "count": count,
                                        }
                                    return (
                                        current_price,
                                        f"change_pct_alert_sent_{pct_type}",
                                    )
                                else:
                                    logger.info(
                                        f"消息发送已关闭: {stock['name']}({stock['code']})"
                                    )
                                    return current_price, "normal"

            # 检查涨跌停情况（如果配置了涨跌停报警）
            if stock["limit_alert"]:
                # stock_info = get_stock_info(stock)
                change_pct = stock_info.get("change_pct")

                if change_pct is not None:
                    # 检查涨停（涨幅超过9.8%）
                    if change_pct >= 9.8:
                        alert_key = f"{stock['code']}_limit_up"
                        # 检查是否需要发送重复报警
                        should_send = False
                        if not self.notified_stocks.get(alert_key):
                            # 首次报警
                            should_send = True
                        else:
                            # 检查是否达到重发时间
                            last_alert_time = self.notified_stocks[alert_key]["time"]
                            alert_count = self.notified_stocks[alert_key][
                                "count"
                            ]  # 已发送次数
                            # 计算下次发送间隔：1小时，2小时，4小时...，以2的幂次递增
                            next_interval = (
                                timedelta(hours=2 ** (alert_count - 1))
                                if alert_count >= 1
                                else timedelta(hours=1)
                            )
                            if datetime.now() - last_alert_time >= next_interval:
                                should_send = True

                        if should_send:
                            logger.info(
                                f"发现涨停警报: {stock['name']}({stock['code']}) 涨幅 {change_pct}%"
                            )
                            # 检查全局和单个股票的消息发送开关
                            if self.global_notification_enabled and stock.get(
                                "notification_enabled", True
                            ):
                                result = send_stock_alert(
                                    stock["name"],
                                    stock["code"],
                                    current_price,
                                    0,
                                    "limit_up",
                                )
                                if result["success"]:
                                    # 更新通知状态，包含时间戳和发送次数
                                    if self.notified_stocks.get(alert_key):
                                        count = (
                                            self.notified_stocks[alert_key]["count"] + 1
                                        )
                                    else:
                                        count = 1
                                    self.notified_stocks[alert_key] = {
                                        "time": datetime.now(),
                                        "count": count,
                                    }
                                return current_price, "limit_up_alert_sent"
                            else:
                                logger.info(
                                    f"消息发送已关闭: {stock['name']}({stock['code']})"
                                )
                                return current_price, "normal"

                    # 检查跌停（跌幅超过-9.8%）
                    elif change_pct <= -9.8:
                        alert_key = f"{stock['code']}_limit_down"
                        # 检查是否需要发送重复报警
                        should_send = False
                        if not self.notified_stocks.get(alert_key):
                            # 首次报警
                            should_send = True
                        else:
                            # 检查是否达到重发时间
                            last_alert_time = self.notified_stocks[alert_key]["time"]
                            alert_count = self.notified_stocks[alert_key][
                                "count"
                            ]  # 已发送次数
                            # 计算下次发送间隔：1小时，2小时，4小时...，以2的幂次递增
                            next_interval = (
                                timedelta(hours=2 ** (alert_count - 1))
                                if alert_count >= 1
                                else timedelta(hours=1)
                            )
                            if datetime.now() - last_alert_time >= next_interval:
                                should_send = True

                        if should_send:
                            logger.info(
                                f"发现跌停警报: {stock['name']}({stock['code']}) 跌幅 {change_pct}%"
                            )
                            # 检查全局和单个股票的消息发送开关
                            if self.global_notification_enabled and stock.get(
                                "notification_enabled", True
                            ):
                                result = send_stock_alert(
                                    stock["name"],
                                    stock["code"],
                                    current_price,
                                    0,
                                    "limit_down",
                                )
                                if result["success"]:
                                    # 更新通知状态，包含时间戳和发送次数
                                    if self.notified_stocks.get(alert_key):
                                        count = (
                                            self.notified_stocks[alert_key]["count"] + 1
                                        )
                                    else:
                                        count = 1
                                    self.notified_stocks[alert_key] = {
                                        "time": datetime.now(),
                                        "count": count,
                                    }
                                return current_price, "limit_down_alert_sent"
                            else:
                                logger.info(
                                    f"消息发送已关闭: {stock['name']}({stock['code']})"
                                )
                                return current_price, "normal"

            # 如果价格在正常范围内，清除相关的警报状态（允许重新通知）
            # 仅在价格回到正常范围后一段时间才重置，避免频繁通知
            if stock["low_alert_price"] and current_price > stock["low_alert_price"]:
                alert_key = f"{stock['code']}_low_{stock['low_alert_price']}"
                if self.notified_stocks.get(alert_key):
                    # 清除低价警报状态，允许重新通知
                    del self.notified_stocks[alert_key]

            if stock["high_alert_price"] and current_price < stock["high_alert_price"]:
                alert_key = f"{stock['code']}_high_{stock['high_alert_price']}"
                if self.notified_stocks.get(alert_key):
                    # 清除高价警报状态，允许重新通知
                    del self.notified_stocks[alert_key]

            if stock["key_price_alerts"]:
                for key_price_info in stock["key_price_alerts"]:
                    key_price = key_price_info["price"]
                    alert_key = f"{stock['code']}_key_price_{key_price}"
                    # 检查价格是否远离关键价位（超过1%范围）
                    if abs(current_price - key_price) / key_price > 0.01:
                        if self.notified_stocks.get(alert_key):
                            # 清除关键价位警报状态，允许重新通知
                            del self.notified_stocks[alert_key]

            if stock["change_pct_alerts"]:
                stock_info = get_stock_info(stock)
                change_pct = stock_info.get("change_pct")
                if change_pct is not None:
                    for change_pct_info in stock["change_pct_alerts"]:
                        threshold_pct = change_pct_info["pct"]
                        alert_key = f"{stock['code']}_change_pct_{threshold_pct}"
                        # 检查涨跌幅是否低于阈值
                        # 如果阈值为正数，当涨跌幅绝对值低于阈值时清除警报状态
                        # 如果阈值为负数，当涨跌幅大于阈值时清除警报状态
                        should_clear = False
                        if threshold_pct >= 0:
                            # 正阈值：当涨跌幅绝对值低于阈值时清除警报状态
                            should_clear = abs(change_pct) < threshold_pct
                        else:
                            # 负阈值：当涨跌幅大于阈值时清除警报状态
                            should_clear = change_pct > threshold_pct

                        if should_clear:
                            if self.notified_stocks.get(alert_key):
                                # 清除涨跌幅警报状态，允许重新通知
                                del self.notified_stocks[alert_key]

            # 清除涨跌停警报状态（当涨跌幅回到正常范围时）
            if stock["limit_alert"]:
                stock_info = get_stock_info(stock)
                change_pct = stock_info.get("change_pct")
                if change_pct is not None:
                    # 检查是否不在涨跌停状态（涨跌幅小于9.8%）
                    if abs(change_pct) < 9.8:
                        # 清除涨停警报状态
                        limit_up_key = f"{stock['code']}_limit_up"
                        if self.notified_stocks.get(limit_up_key):
                            del self.notified_stocks[limit_up_key]

                        # 清除跌停警报状态
                        limit_down_key = f"{stock['code']}_limit_down"
                        if self.notified_stocks.get(limit_down_key):
                            del self.notified_stocks[limit_down_key]

            return current_price, "normal"

        except Exception as e:
            logger.error(f"检查股票 {stock['name']}({stock['code']}) 时出错: {str(e)}")
            return None, "error"

    def send_market_summary_report(self, report_type):
        """
        发送市场汇总报告
        :param report_type: 报告类型 ('open_report' for 开市后报告, 'close_report' for 闭市后报告)
        """
        try:
            logger.info(
                f"发送{('开市后' if report_type == 'open_report' else '闭市后')}汇总报告"
            )
            report_title = (
                f"【{'开市后' if report_type == 'open_report' else '闭市后'}汇总报告】"
            )
            report_content = f"【{'开市后' if report_type == 'open_report' else '闭市后'}市场汇总报告】\n\n"
            report_content += (
                f"报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )

            for stock in self.stocks:
                # 检查股票配置中的关键字段是否为None
                stock_name = (
                    stock.get("name")
                    if isinstance(stock.get("name"), str)
                    else (stock["name"] if "name" in stock else "未知股票")
                )
                stock_code = (
                    stock.get("code")
                    if isinstance(stock.get("code"), str)
                    else (stock["code"] if "code" in stock else "未知代码")
                )

                stock_info = get_stock_info(stock)
                current_price = stock_info.get("price")
                change_pct = stock_info.get("change_pct", 0)

                if current_price is not None:
                    # 确保所有要格式化的值都不是None
                    price_value = current_price if current_price is not None else 0.0
                    change_pct_value = change_pct if change_pct is not None else 0.0

                    report_content += f"股票名称: {stock_name}\n"
                    report_content += f"股票代码: {stock_code}\n"
                    report_content += f"当前价格: {price_value:.2f}\n"
                    report_content += f"涨跌幅: {change_pct_value:.2f}%\n\n"
                else:
                    report_content += (
                        f"股票名称: {stock_name} ({stock_code}) - 价格获取失败\n\n"
                    )

            # 发送汇总报告
            send_system_notification(report_title, report_content)
            logger.info(
                f"{('开市后' if report_type == 'open_report' else '闭市后')}汇总报告发送完成"
            )
        except Exception as e:
            logger.error(f"发送汇总报告时出错: {str(e)}")


def is_market_open(current_time=None):
    """
    判断当前是否为开市时间
    开市时间：9:30 - 12:00, 13:00 - 16:00，周一到周五
    :param current_time: 当前时间，默认为当前系统时间
    :return: True if market is open, False otherwise
    """
    if current_time is None:
        current_time = datetime.now()

    # 检查是否为周末（周六=5, 周日=6）
    if current_time.weekday() >= 5:  # 0是周一，6是周日
        return False

    # 获取当前时间的小时和分钟
    current_hour = current_time.hour
    current_minute = current_time.minute

    # 将时间转换为分钟数进行比较
    current_minutes = current_hour * 60 + current_minute
    morning_open_minutes = 9 * 60 + 30  # 9:30
    morning_close_minutes = 12 * 60  # 12:00
    afternoon_open_minutes = 13 * 60  # 13:00
    afternoon_close_minutes = 16 * 60  # 16:00

    # 检查是否在上午或下午的开市时间内
    morning_session = morning_open_minutes <= current_minutes <= morning_close_minutes
    afternoon_session = (
        afternoon_open_minutes <= current_minutes <= afternoon_close_minutes
    )

    return morning_session or afternoon_session


def is_market_open_time_specific(current_time=None):
    """
    判断当前是否为指定的报告时间（开市后5分钟和闭市后5分钟）
    :param current_time: 当前时间，默认为当前系统时间
    :return: 'open_report' if 开市后5分钟, 'close_report' if 闭市后5分钟, None otherwise
    """
    if current_time is None:
        current_time = datetime.now()

    # 检查是否为周末（周六=5, 周日=6）
    if current_time.weekday() >= 5:  # 0是周一，6是周日
        return None

    # 从配置管理器获取开市和闭市时间
    from .config_manager import config_manager

    try:
        # 使用配置管理器获取市场时间设置
        market_times = config_manager.get_market_times()
        open_time_str = market_times.get("market_open_start", "09:30")
        close_time_str = market_times.get("market_open_end", "16:00")
    except Exception as e:
        logger.warning(f"从配置管理器获取市场时间失败: {str(e)}，使用默认值")
        # 如果从配置管理器获取失败，使用默认值
        open_time_str = "09:30"
        close_time_str = "16:00"

    try:
        open_time = datetime.strptime(open_time_str, "%H:%M").time()
        close_time = datetime.strptime(close_time_str, "%H:%M").time()
    except ValueError:
        # 如果时间格式错误，使用默认时间
        logger.warning(f"时间格式错误，使用默认开市时间: 09:30, 闭市时间: 16:00")
        open_time = datetime.strptime("09:30", "%H:%M").time()
        close_time = datetime.strptime("16:00", "%H:%M").time()

    # 计算开市后5分钟和闭市后5分钟的时间
    open_plus_5 = datetime.combine(current_time.date(), open_time) + timedelta(
        minutes=5
    )
    close_plus_5 = datetime.combine(current_time.date(), close_time) + timedelta(
        minutes=5
    )

    # 检查是否为开市后5分钟（允许1分钟的误差范围）
    if (
        (open_plus_5 - timedelta(minutes=1)).time()
        <= current_time.time()
        <= (open_plus_5 + timedelta(minutes=1)).time()
    ):
        return "open_report"
    # 检查是否为闭市后5分钟（允许1分钟的误差范围）
    elif (
        (close_plus_5 - timedelta(minutes=1)).time()
        <= current_time.time()
        <= (close_plus_5 + timedelta(minutes=1)).time()
    ):
        return "close_report"
    else:
        return None


def main():
    """
    主函数
    """
    try:
        # 创建监控器实例
        monitor = StockMonitor()

        # 检查是否有配置的股票
        if not monitor.stocks:
            logger.error("没有配置任何监控股票，程序退出")
            return

        # 开始监控
        monitor.start_monitoring()

    except Exception as e:
        logger.error(f"程序运行出错: {str(e)}")
        # 发送错误通知
        error_msg = f"股票监控程序发生错误: {str(e)}"
        send_system_notification("股票监控系统错误", error_msg)


if __name__ == "__main__":
    main()
