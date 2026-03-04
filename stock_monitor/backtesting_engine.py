"""
趋势交易回测引擎
用于验证趋势交易策略的有效性
使用 TrendTradingAnalyzer 的综合信号逻辑，确保回测与前端显示一致
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from logger_config import logger
from trend_trading_analyzer import TrendTradingAnalyzer


class BacktestingEngine:
    """
    回测引擎
    使用分析器的综合信号逻辑生成买卖信号
    """
    
    def __init__(self, initial_capital=100000, transaction_fee=0.001, position_size=0.1):
        """
        初始化回测引擎
        :param initial_capital: 初始资金
        :param transaction_fee: 交易手续费率
        :param position_size: 单次仓位大小（占总资产的比例）
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.transaction_fee = transaction_fee
        self.position_size = position_size
        # 使用分析器 V2 生成信号
        self.analyzer = TrendTradingAnalyzer()
        self.trades = []
        self.portfolio_history = []
        self.last_trade_date = None
        logger.info(f"回测引擎初始化完成，初始资金：{initial_capital}, 手续费率：{transaction_fee}")

    def _calculate_position_size(self, price, capital):
        """计算持仓数量"""
        return int((capital * self.position_size) / price)

    def _apply_slippage(self, price, order_type):
        """模拟滑点影响"""
        slippage = 0.0005  # 0.05% 滑点
        if order_type == 'BUY':
            return price * (1 + slippage)
        else:
            return price * (1 - slippage)

    def run_backtest(self, historical_data, start_date=None, end_date=None):
        """
        运行回测
        :param historical_data: 历史数据
        :param start_date: 开始日期
        :param end_date: 结束日期
        """
        # 过滤日期范围
        if start_date or end_date:
            df = pd.DataFrame(historical_data)
            df['date'] = pd.to_datetime(df['date'])
            if start_date:
                start_date = pd.to_datetime(start_date)
                df = df[df['date'] >= start_date]
            if end_date:
                end_date = pd.to_datetime(end_date)
                df = df[df['date'] <= end_date]
            historical_data = df.to_dict('records')

        logger.info(f"开始回测，数据点数：{len(historical_data)}, 日期范围：{historical_data[0]['date']} - {historical_data[-1]['date']}")

        # 重置状态
        self.current_capital = self.initial_capital
        self.trades = []
        self.portfolio_history = []

        # 持仓状态
        position = 0
        position_cost = 0
        in_position = False

        # 遍历历史数据
        for i in range(60, len(historical_data)):
            current_data = historical_data[:i+1]
            current_bar = historical_data[i]
            current_date = current_bar.get('date', f'Day_{i}')
            current_price = current_bar['close']

            # 转换为 DataFrame 用于分析器
            df = pd.DataFrame(current_data)
            df = df.sort_values('date')
            numeric_columns = ['open', 'close', 'high', 'low', 'volume']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 计算均线
            if 'ma5' not in df.columns:
                df['ma5'] = df['close'].rolling(window=5).mean()
            if 'ma20' not in df.columns:
                df['ma20'] = df['close'].rolling(window=20).mean()
            if 'ma60' not in df.columns:
                df['ma60'] = df['close'].rolling(window=60).mean()
            if 'ma120' not in df.columns:
                df['ma120'] = df['close'].rolling(window=120).mean()

            # 使用分析器 V2 生成信号
            # 执行完整分析流程
            analysis = self.analyzer._run_full_analysis(df)
            signals = self.analyzer._generate_trading_signals(analysis)

            # 检查买入信号
            buy_signal = False
            for signal in signals['buy_signals']:
                if signal['strength'] in ['STRONG', 'MEDIUM']:
                    buy_signal = True
                    break

            # 检查卖出信号
            sell_signal = False
            for signal in signals['sell_signals']:
                if signal['strength'] in ['STRONG', 'MEDIUM']:
                    sell_signal = True
                    break

            # 执行交易逻辑
            if not in_position and buy_signal:
                if self.last_trade_date != current_date:
                    shares_to_buy = self._calculate_position_size(current_price, self.current_capital)
                    if shares_to_buy > 0:
                        execution_price = self._apply_slippage(current_price, 'BUY')
                        cost = shares_to_buy * execution_price
                        fee = cost * self.transaction_fee

                        if cost + fee <= self.current_capital:
                            position = shares_to_buy
                            position_cost = execution_price
                            self.current_capital -= (cost + fee)
                            in_position = True
                            self.last_trade_date = current_date
                            
                            # 获取触发交易的信号详情
                            triggered_signal = signals['buy_signals'][0]  # 取第一个信号
                            
                            self.trades.append({
                                'date': current_date,
                                'action': 'BUY',
                                'price': execution_price,
                                'shares': shares_to_buy,
                                'fee': fee,
                                'capital_after': self.current_capital,
                                # 信号信息
                                'signal_name': triggered_signal.get('signal', 'Unknown'),
                                'signal_strength': triggered_signal.get('strength', 'UNKNOWN'),
                                'trend_direction': triggered_signal.get('trend_direction', 'UNKNOWN'),
                                'health_score': triggered_signal.get('health_score', 0),
                                'stop_loss': triggered_signal.get('stop_loss'),
                                'target_price': triggered_signal.get('target_price'),
                                'conditions_met': triggered_signal.get('conditions_met', []),
                                'description': triggered_signal.get('description', '')
                            })

                            logger.info(f"买入信号执行：{current_date}, 信号：{triggered_signal.get('signal')}, 价格：{execution_price}, 数量：{shares_to_buy}")

            elif in_position and sell_signal:
                if self.last_trade_date != current_date:
                    if position > 0:
                        execution_price = self._apply_slippage(current_price, 'SELL')
                        income = position * execution_price
                        fee = income * self.transaction_fee
                        net_income = income - fee

                        self.current_capital += net_income
                        profit_loss = (execution_price - position_cost) * position
                        profit_loss_pct = (execution_price - position_cost) / position_cost * 100

                        in_position = False
                        position = 0
                        position_cost = 0
                        self.last_trade_date = current_date
                        
                        # 获取触发交易的信号详情
                        triggered_signal = signals['sell_signals'][0]  # 取第一个信号

                        self.trades.append({
                            'date': current_date,
                            'action': 'SELL',
                            'price': execution_price,
                            'shares': position,
                            'fee': fee,
                            'profit_loss': profit_loss,
                            'profit_loss_pct': profit_loss_pct,
                            'capital_after': self.current_capital,
                            # 信号信息
                            'signal_name': triggered_signal.get('signal', 'Unknown'),
                            'signal_strength': triggered_signal.get('strength', 'UNKNOWN'),
                            'trend_direction': triggered_signal.get('trend_direction', 'UNKNOWN'),
                            'health_score': triggered_signal.get('health_score', 0),
                            'conditions_met': triggered_signal.get('conditions_met', []),
                            'description': triggered_signal.get('description', '')
                        })

                        logger.info(f"卖出信号执行：{current_date}, 信号：{triggered_signal.get('signal')}, 价格：{execution_price}, 数量：{position}, 盈亏：{profit_loss:.2f}")

            # 记录投资组合历史
            portfolio_value = self.current_capital
            if in_position:
                portfolio_value += position * current_price

            self.portfolio_history.append({
                'date': current_date,
                'portfolio_value': portfolio_value,
                'cash': self.current_capital,
                'position_value': position * current_price if in_position else 0,
                'total_return': (portfolio_value - self.initial_capital) / self.initial_capital * 100
            })

        # ===== 回测结束，如果还有持仓，按收盘价清仓 =====
        if in_position and position > 0:
            final_price = current_price
            execution_price = self._apply_slippage(final_price, 'SELL')
            income = position * execution_price
            fee = income * self.transaction_fee
            net_income = income - fee

            self.current_capital += net_income
            profit_loss = (execution_price - position_cost) * position
            profit_loss_pct = (execution_price - position_cost) / position_cost * 100

            logger.info(f"[清仓] 回测结束，强制平仓：价格={execution_price:.2f}, 数量={position}, 盈亏={profit_loss:.2f} ({profit_loss_pct:.2f}%)")

            self.trades.append({
                'date': current_date,
                'action': 'SELL',
                'price': execution_price,
                'shares': position,
                'fee': fee,
                'profit_loss': profit_loss,
                'profit_loss_pct': profit_loss_pct,
                'capital_after': self.current_capital,
                # 信号信息
                'signal_name': '回测结束清仓',
                'signal_strength': 'N/A',
                'trend_direction': 'N/A',
                'health_score': 0,
                'conditions_met': ['回测结束', '强制平仓'],
                'description': '回测结束，按收盘价强制清仓'
            })

            in_position = False
            position = 0
            position_cost = 0

        logger.info(f"回测完成，总交易次数：{len(self.trades)}")
        report = self.generate_performance_report()
        return report

    def generate_performance_report(self):
        """生成绩效报告"""
        if not self.portfolio_history:
            return {'error': '没有回测数据'}

        final_portfolio_value = self.portfolio_history[-1]['portfolio_value']
        total_return = (final_portfolio_value - self.initial_capital) / self.initial_capital * 100

        buy_trades = [t for t in self.trades if t['action'] == 'BUY']
        sell_trades = [t for t in self.trades if t['action'] == 'SELL']

        profitable_trades = [t for t in self.trades if 'profit_loss' in t and t['profit_loss'] > 0]
        losing_trades = [t for t in self.trades if 'profit_loss' in t and t['profit_loss'] < 0]

        portfolio_values = [h['portfolio_value'] for h in self.portfolio_history]
        running_max = portfolio_values[0]
        max_drawdown = 0
        for value in portfolio_values:
            if value > running_max:
                running_max = value
            drawdown = (running_max - value) / running_max * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        returns = [h['total_return'] for h in self.portfolio_history]
        if len(returns) > 1:
            daily_returns = [(returns[i] - returns[i-1])/100 if i > 0 else 0 for i in range(len(returns))]
            excess_returns = [r - 0.03/252 for r in daily_returns]
            if np.std(excess_returns) != 0:
                sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0

        if len(self.portfolio_history) > 0:
            total_days = (pd.to_datetime(self.portfolio_history[-1]['date']) -
                         pd.to_datetime(self.portfolio_history[0]['date'])).days
            if total_days > 0:
                annual_return = (final_portfolio_value / self.initial_capital) ** (365 / total_days) - 1
                annual_return *= 100
            else:
                annual_return = total_return
        else:
            annual_return = 0

        total_trades_with_pl = len([t for t in self.trades if 'profit_loss' in t])
        win_rate = len(profitable_trades) / total_trades_with_pl * 100 if total_trades_with_pl > 0 else 0

        report = {
            'summary': {
                'initial_capital': self.initial_capital,
                'final_capital': final_portfolio_value,
                'total_return_pct': total_return,
                'annual_return_pct': annual_return,
                'total_trades': len(self.trades),
                'winning_trades': len(profitable_trades),
                'losing_trades': len(losing_trades),
                'max_drawdown_pct': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'win_rate': win_rate
            },
            'trade_stats': {
                'total_buy_orders': len(buy_trades),
                'total_sell_orders': len(sell_trades),
                'win_rate': win_rate,
                'avg_profit_per_win': float(np.mean([t['profit_loss'] for t in profitable_trades])) if profitable_trades else 0,
                'avg_loss_per_loss': float(np.mean([t['profit_loss'] for t in losing_trades])) if losing_trades else 0
            },
            'portfolio_history': self.portfolio_history,
            'trades': self.trades
        }

        return report

    def optimize_parameters(self, historical_data, param_grid):
        """
        参数优化
        :param historical_data: 历史数据
        :param param_grid: 参数网格
        """
        best_params = {}
        best_return = float('-inf')
        results = []

        import itertools

        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        for param_combination in itertools.product(*param_values):
            params = dict(zip(param_names, param_combination))

            engine = BacktestingEngine(
                initial_capital=params.get('initial_capital', self.initial_capital),
                transaction_fee=params.get('transaction_fee', self.transaction_fee),
                position_size=params.get('position_size', self.position_size)
            )

            report = engine.run_backtest(historical_data)
            total_return = report['summary']['total_return_pct']

            results.append({
                'params': params,
                'return': total_return
            })

            if total_return > best_return:
                best_return = total_return
                best_params = params

        return {
            'best_params': best_params,
            'best_return': best_return,
            'all_results': results
        }


# 全局实例
backtesting_engine = BacktestingEngine()


def run_strategy_backtest(historical_data, start_date=None, end_date=None,
                         initial_capital=100000, transaction_fee=0.001, position_size=0.1):
    """
    运行策略回测的便捷函数
    """
    engine = BacktestingEngine(initial_capital, transaction_fee, position_size)
    return engine.run_backtest(historical_data, start_date, end_date)
