"""
趋势交易 AI 分析器 V2
基于趋势交易理论，实现独立的 AI 分析功能
不依赖外部 AI 服务，使用内置规则和模式识别

核心理念：
- 买入点只有两种：突破密集成交区、稳定上涨回踩
- 时钟方向判断考虑：均线排列 + 趋势斜率 + 持续时长 + 趋势稳定性
- 密集成交区 = 3 点钟方向长期持续（≥60 天）
"""

import pandas as pd
import numpy as np
from datetime import datetime
from logger_config import logger
from stock_data_fetcher import get_enhanced_stock_info, _fetch_historical_data, get_stock_info, get_stock_cached_data, set_stock_cache_data


class TrendTradingAnalyzer:
    """
    趋势交易 AI 分析器 V2

    核心改进：
    1. 趋势方向判断增加斜率因子
    2. 趋势方向判断增加时长因子
    3. 趋势方向判断增加稳定性因子
    4. 密集成交区统一为 3 点钟方向特例
    5. 买入信号简化为 2 种
    """

    def __init__(self):
        logger.debug("趋势交易分析器初始化完成")

    # ==================== 公共入口 ====================

    def analyze_stock_trend(self, stock_code, stock_name):
        """
        分析股票趋势，基于趋势交易理论

        :param stock_code: 股票代码
        :param stock_name: 股票名称
        :return: dict {
            'success': True,
            'timestamp': str,
            'current_data': dict,
            'trend_analysis': dict,
            'trading_signals': dict,
            'report': str
        }
        """
        try:
            cache_key = f"trend_analysis_{stock_code}"
            cached_data = get_stock_cached_data(cache_key, cache_duration=60*60)  # 缓存 1 小时
            if cached_data is not None:
                logger.info(f"从缓存获取 {stock_code} 的趋势分析结果")
                cached_data['cached'] = True
                return cached_data

            # 获取历史数据
            historical_data = _fetch_historical_data(stock_code, days=365)
            if not historical_data or len(historical_data) < 120:
                return {'success': False, 'message': '无法获取足够的历史数据进行趋势分析'}

            df = pd.DataFrame(historical_data)
            df = df.sort_values('date')

            # 数据预处理
            df = self._prepare_data(df)
            latest = df.iloc[-1]

            # 获取实时价格
            real_time_price = None
            stock_obj = {'code': stock_code, 'name': stock_name}
            real_time_info = get_stock_info(stock_obj)
            if real_time_info:
                real_time_price = real_time_info.get('price')

            # 执行趋势分析
            analysis = self._run_full_analysis(df)

            # 生成交易信号
            trading_signals = self._generate_trading_signals(analysis)

            # 生成分析报告
            report = self._generate_report(stock_code, stock_name, latest, analysis, trading_signals)

            # 返回结构化数据
            return {
                'success': True,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                # 当前价格数据 - 优先使用实时价格
                'current_data': {
                    'price': float(real_time_price) if real_time_price is not None else float(latest['close']),
                    'ma5': float(latest['ma5']),
                    'ma20': float(latest['ma20']),
                    'ma60': float(latest['ma60']),
                    'ma120': float(latest['ma120'])
                },
                # 趋势分析数据
                'trend_analysis': {
                    'direction': analysis['trend_direction'],
                    'health_score': analysis['stability']['health_score'],
                    'status': analysis['stability']['status'],
                    'slopes': {
                        'price': float(analysis['slopes'].get('price', 0)),
                        'ma20': float(analysis['slopes'].get('ma20', 0)),
                        'ma60': float(analysis['slopes'].get('ma60', 0)),
                        'ma120': float(analysis['slopes'].get('ma120', 0))
                    },
                    'duration': {
                        'bullish': analysis['duration']['bullish'],
                        'bearish': analysis['duration']['bearish'],
                        'consolidation': analysis['duration']['consolidation']
                    },
                    'consolidation': {
                        'status': analysis['consolidation']['status_str'],
                        'is_zone': analysis['consolidation']['is_consolidation_zone'],
                        'upper_bound': float(analysis['consolidation']['upper_bound']) if analysis['consolidation']['upper_bound'] else None,
                        'lower_bound': float(analysis['consolidation']['lower_bound']) if analysis['consolidation']['lower_bound'] else None
                    },
                    'construction': analysis['construction'],
                    # 稳定性详细得分
                    'stability': analysis['stability']
                },
                # 交易信号（结构化）
                'trading_signals': {
                    'buy_signals': [{
                        'type': 'BUY',
                        'signal': signal['signal'],
                        'strength': signal['strength'],
                        'description': signal['description'],
                        'stop_loss': float(signal['stop_loss']) if signal.get('stop_loss') else None,
                        'target_price': [
                            float(signal['target_price'][0]) if signal['target_price'][0] != float('inf') else None,
                            float(signal['target_price'][1]) if signal['target_price'][1] != float('inf') else None
                        ] if signal.get('target_price') else None,
                        'conditions_met': signal.get('conditions_met', []),
                        'trend_direction': signal.get('trend_direction'),
                        'health_score': signal.get('health_score')
                    } for signal in trading_signals['buy_signals']],
                    'sell_signals': [{
                        'type': 'SELL',
                        'signal': signal['signal'],
                        'strength': signal['strength'],
                        'description': signal['description'],
                        'trend_direction': signal.get('trend_direction'),
                        'health_score': signal.get('health_score'),
                        'conditions_met': signal.get('conditions_met', [])
                    } for signal in trading_signals['sell_signals']]
                },
                # 文本报告（保持兼容）
                'report': report
            }

            # 缓存结果
            set_stock_cache_data(cache_key, result)
            logger.info(f"趋势分析结果已缓存：{stock_code}")

        except Exception as e:
            logger.error(f"分析失败：{e}")
            return {'success': False, 'message': f'分析失败：{str(e)}'}

    # ==================== 数据预处理 ====================

    def _prepare_data(self, df):
        """
        数据预处理：计算均线

        :param df: 原始数据
        :return: 包含均线的 DataFrame
        """
        df = df.copy()
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma60'] = df['close'].rolling(window=60).mean()
        df['ma120'] = df['close'].rolling(window=120).mean()
        return df

    # ==================== 趋势分析工具 ====================

    def _calculate_trend_slope(self, df, window=20):
        """
        计算趋势斜率

        使用线性回归计算最近 window 天的价格和各均线斜率

        :param df: DataFrame，包含价格和均线数据
        :param window: 计算窗口（默认 20 天）
        :return: dict {
            'price': 价格斜率 (%/日),
            'ma5': MA5 斜率,
            'ma20': MA20 斜率,
            'ma60': MA60 斜率
        }
        """
        slopes = {}
        recent = df.tail(window)

        # 计算价格斜率
        if 'close' in recent.columns and len(recent) > 1:
            x = np.arange(len(recent))
            y = np.log(recent['close'].values)
            slope, _ = np.polyfit(x, y, 1)
            slopes['price'] = slope * 100  # 转换为百分比

        # 计算均线斜率
        for ma_col in ['ma5', 'ma20', 'ma60']:
            if ma_col in recent.columns and len(recent) > 1:
                x = np.arange(len(recent))
                y = recent[ma_col].values
                slope, _ = np.polyfit(x, y, 1)
                avg = y.mean()
                slopes[ma_col] = (slope / avg) * 100 if avg != 0 else 0

        return slopes

    def _calculate_trend_duration(self, df):
        """
        计算趋势持续时间

        从最新一天向前追溯，计算各趋势连续持续的天数

        注意：此处的"多头/空头趋势"使用 MA20>MA60>MA120 判断（3 条均线）
        与报告中的"均线排列状态"保持一致，区别于 MA5>MA20>MA60>MA120（4 均线）

        :param df: DataFrame，包含均线数据
        :return: dict {
            'bullish': 多头趋势持续天数 (MA20>MA60>MA120),
            'bearish': 空头趋势持续天数 (MA20<MA60<MA120),
            'consolidation': 横盘持续天数
        }
        """
        bullish_days = 0
        bearish_days = 0
        consolidation_days = 0

        # 从最新一天向前追溯
        for i in range(len(df) - 1, -1, -1):
            row = df.iloc[i]

            # 检查均线排列
            if self._is_bullish_arrangement(row):
                bullish_days += 1
                if bearish_days > 0 or consolidation_days > 0:
                    break  # 趋势中断
            elif self._is_bearish_arrangement(row):
                bearish_days += 1
                if bullish_days > 0 or consolidation_days > 0:
                    break  # 趋势中断
            else:
                consolidation_days += 1
                if bullish_days > 0 or bearish_days > 0:
                    break  # 趋势中断

        return {
            'bullish': bullish_days,
            'bearish': bearish_days,
            'consolidation': consolidation_days
        }

    def _assess_trend_stability(self, df):
        """
        评估趋势稳定性（健康度评分）

        评分维度：
        - 趋势方向（多头/空头排列）
        - 趋势持续时间
        - 均线间距
        - 波动率

        :param df: DataFrame，包含均线数据
        :return: dict {
            'health_score': 0-100,
            'status': '多头趋势' | '空头趋势' | '震荡整理',
            'volatility': 60 日波动率,
            'ma_concentration': 均线集中度
        }
        """
        if len(df) < 60:
            return {'health_score': 0, 'status': '数据不足'}

        latest = df.iloc[-1]

        # 检查均线排列
        is_bullish = self._is_bullish_arrangement(latest)
        is_bearish = self._is_bearish_arrangement(latest)

        # 计算均线间距
        ma5_ma20_gap = abs(latest['ma5'] - latest['ma20']) / latest['ma20'] * 100 if latest['ma20'] != 0 else 0
        ma20_ma60_gap = abs(latest['ma20'] - latest['ma60']) / latest['ma60'] * 100 if latest['ma60'] != 0 else 0

        # 计算 60 日波动率
        recent_60 = df.tail(60)
        volatility = (recent_60['high'].max() - recent_60['low'].min()) / recent_60['close'].mean() * 100

        # 计算均线集中度
        ma_data = recent_60[['ma5', 'ma20', 'ma60']]
        ma_spread = ma_data.max(axis=1) - ma_data.min(axis=1)
        ma_concentration = (ma_spread.mean() / ma_data.mean(axis=1).mean()) * 100

        # 计算趋势持续时间
        duration = self._calculate_trend_duration(df)
        trend_duration = duration['bullish'] if is_bullish else duration['bearish'] if is_bearish else 0

        # 健康度评分（基础分 50）
        health_score = 50
        
        # 各维度得分细节
        trend_direction_score = 0
        duration_score = 0
        gap_score = 0
        volatility_score = 0

        # 趋势方向（+20）
        if is_bullish or is_bearish:
            health_score += 20
            trend_direction_score = 20

        # 趋势持续时间（+15）
        if trend_duration > 10:
            health_score += 15
            duration_score = 15

        # 均线间距适中（+10）：1%-10% 之间
        if 1 < ma5_ma20_gap < 10:
            health_score += 10
            gap_score = 10

        # 波动率低（+5）：MA5 波动率<2%
        ma5_std = df['ma5'].tail(20).std() / df['ma5'].tail(20).mean() * 100
        if ma5_std < 2:
            health_score += 5
            volatility_score = 5

        # 确定趋势状态
        if is_bullish:
            status = '多头趋势'
        elif is_bearish:
            status = '空头趋势'
        else:
            status = '震荡整理'

        return {
            'health_score': min(health_score, 100),
            'status': status,
            'volatility': volatility,
            'ma_concentration': ma_concentration,
            'ma5_ma20_gap': ma5_ma20_gap,
            'ma20_ma60_gap': ma20_ma60_gap,
            'trend_duration': trend_duration,
            # 各维度得分细节
            'trend_direction_score': trend_direction_score,
            'duration_score': duration_score,
            'gap_score': gap_score,
            'volatility_score': volatility_score,
            'ma5_std': ma5_std
        }

    def _identify_consolidation_zone(self, df, window=60):
        """
        识别密集成交区

        密集成交区 = 3 点钟方向（横盘）

        判断标准（放宽条件）：
        - 60 日波动率 < 20%
        - 均线集中度 < 5%

        :param df: DataFrame，包含 OHLC 数据
        :param window: 观察窗口（默认 60 天）
        :return: status
                 始终返回窗口内的最高价和最低价
        """

        recent = df.tail(window)

        # 计算波动率（60 日最高价与最低价之间的波动范围）
        price_range = recent['high'].max() - recent['low'].min()
        avg_price = recent['close'].mean()
        volatility = (price_range / avg_price) * 100 if avg_price != 0 else 0

        # 计算均线集中度（MA5/20/60 三条均线的离散程度）
        ma_data = recent[['ma5', 'ma20', 'ma60']]
        ma_spread = ma_data.max(axis=1) - ma_data.min(axis=1)
        ma_concentration = (ma_spread.mean() / ma_data.mean(axis=1).mean()) * 100

        # 始终计算边界值
        upper_bound = recent['high'].max()
        lower_bound = recent['low'].min()

        # 判断是否为密集成交区（放宽条件：波动率<20%，集中度<5%）
        if volatility < 20 and ma_concentration < 5:
            status = {
                "is_consolidation_zone": True,
                "volatility": volatility,
                "ma_concentration": ma_concentration,
                "upper_bound": upper_bound,
                "lower_bound": lower_bound,
                "status_str": f"密集成交区（波动率{volatility:.1f}%, 集中度{ma_concentration:.1f}%, upper_bound={upper_bound:.2f}, lower_bound={lower_bound:.2f}）"
            }
        else:
            status = {
                "is_consolidation_zone": False,
                "volatility": volatility,
                "ma_concentration": ma_concentration,
                "upper_bound": upper_bound,
                "lower_bound": lower_bound,
                "status_str": f"非密集成交区（波动率{volatility:.1f}%, 集中度{ma_concentration:.1f}%, upper_bound={upper_bound:.2f}, lower_bound={lower_bound:.2f}）"
            }

        return status

    def _detect_top_bottom_construction(self, df):
        """
        检测顶底构造

        顶部构造：lower high（高点降低）+ lower low（低点创新低）
        底部构造：higher low（低点抬高）+ higher high（高点创新高）

        :param df: DataFrame，包含 K 线数据
        :return: 构造类型字符串
        """
        if len(df) < 3:
            return "数据不足"

        lookback = min(10, len(df))
        recent = df.tail(lookback)
        highs = recent['high'].values
        lows = recent['low'].values

        constructions = []

        # 多 K 线识别（更可靠）
        if lookback >= 5:
            group_size = min(5, lookback // 2)
            front_high = np.max(highs[:-group_size])
            back_high = np.max(highs[-group_size:])
            front_low = np.min(lows[:-group_size])
            back_low = np.min(lows[-group_size:])

            # 顶部构造：高点降低 + 低点创新低
            if back_high < front_high and back_low < front_low:
                constructions.append("顶部构造（lower high + lower low）")

            # 底部构造：低点抬高 + 高点创新高
            if back_low > front_low and back_high > front_high:
                constructions.append("底部构造（higher low + higher high）")

        # 简化三 K 线检查（补充）
        if not constructions and lookback >= 3:
            k1, k2, k3 = recent.iloc[-3], recent.iloc[-2], recent.iloc[-1]

            if k2['high'] < k1['high'] and k3['low'] < k2['low']:
                constructions.append("顶部构造（简化三 K 线）")

            if k2['low'] > k1['low'] and k3['high'] > k2['high']:
                constructions.append("底部构造（简化三 K 线）")

        if not constructions:
            return "无明显构造"

        return ','.join(constructions)

    # ==================== 趋势方向判断 ====================

    def _identify_trend_direction(self, df):
        """
        判断趋势方向（5 种时钟方向）

        考虑因子：
        - 均线排列
        - 趋势斜率（新增）
        - 趋势持续时间（新增）
        - 趋势稳定性（新增）

        :return: 趋势方向字符串
        """
        if len(df) < 60:
            return "数据不足"

        latest = df.iloc[-1]
        price = latest['close']

        # 获取均线值
        ma5 = latest['ma5']
        ma20 = latest['ma20']
        ma60 = latest['ma60']
        ma120 = latest['ma120']

        # 计算趋势斜率
        slopes = self._calculate_trend_slope(df, window=20)

        # 计算趋势持续时间
        duration = self._calculate_trend_duration(df)

        # 评估趋势稳定性
        stability = self._assess_trend_stability(df)

        # ===== 1. 一点钟方向（加速上涨）=====
        # 条件：MA5>MA20>MA60>MA120 + 价格>MA20 + MA20 斜率>0.3% + 持续≥5 天
        is_1_oclock = (
            ma5 > ma20 > ma60 > ma120 and
            price > ma20 and
            slopes.get('ma20', 0) > 0.3 and
            duration['bullish'] >= 10
        )

        # ===== 2. 两点钟方向（稳定上涨）=====
        # 条件：MA20>MA60>MA120 + 价格>MA60 + MA20 斜率>0.1% + 持续≥5 天 + 健康度≥60
        is_2_oclock = (
            ma20 > ma60 > ma120 and
            price > ma60 and
            slopes.get('ma20', 0) > 0.1 and
            duration['bullish'] >= 5 and  # 放宽：10→5 天
            stability['health_score'] >= 60
        )

        # ===== 3. 四点钟方向（稳定下跌）=====
        # 条件：MA20<MA60<MA120 + 价格<MA60 + MA20 斜率<-0.1% + 持续≥5 天
        is_4_oclock = (
            ma20 < ma60 < ma120 and
            price < ma60 and
            slopes.get('ma20', 0) < -0.01 and
            duration['bearish'] >= 5
        )

        # ===== 4. 五点钟方向（加速下跌）=====
        # 条件：MA5<MA20<MA60 + 价格<MA20 + MA5 斜率<-0.5% + 持续≥5 天
        is_5_oclock = (
            ma5 < ma20 < ma60 and
            price < ma20 and
            slopes.get('ma5', 0) < -0.01 and
            duration['bearish'] >= 5
        )

        # ===== 5. 三点钟方向（横盘整理）=====
        # 条件：波动率<15% + 均线集中度<2%
        is_3_oclock = (
            stability['volatility'] < 15 and
            stability['ma_concentration'] < 2
        )

        # 综合判断（按优先级）
        if is_1_oclock:
            return "一点钟方向（加速上涨）"
        elif is_2_oclock:
            return "两点钟方向（稳定上涨）"
        elif is_4_oclock:
            return "四点钟方向（稳定下跌）"
        elif is_5_oclock:
            return "五点钟方向（加速下跌）"
        elif is_3_oclock:
            return "三点钟方向（横盘整理）"
        else:
            return "三点钟方向（横盘整理）"

    # ==================== 辅助判断方法 ====================

    def _is_bullish_arrangement(self, row, tolerance=0.05):
        """检查是否为多头排列（MA20>MA60>MA120）"""
        return (
            row['ma20'] > row['ma60'] > row['ma120'] and
            row['ma20'] > row['ma120'] * (1 + tolerance)  # MA20 与 MA120 间距至少 tolerance
        )

    def _is_bearish_arrangement(self, row, tolerance=0.05):
        """检查是否为空头排列（MA20<MA60<MA120）"""
        return (
            row['ma20'] < row['ma60'] < row['ma120'] and
            row['ma20'] < row['ma120'] * (1 - tolerance)  # MA20 与 MA120 间距至少 tolerance
        )

    def _is_near_price(self, price, target, tolerance=0.05):
        """检查价格是否在目标价格的 tolerance 范围内（默认±5%）"""
        return target * (1 - tolerance) <= price <= target * (1 + tolerance)

    # ==================== 完整分析流程 ====================

    def _run_full_analysis(self, df):
        """
        执行完整趋势分析

        :param df: DataFrame，包含价格和均线数据
        :return: analysis dict，包含所有分析结果
        """
        latest = df.iloc[-1]

        # 1. 判断趋势方向
        trend_direction = self._identify_trend_direction(df)

        # 2. 计算趋势斜率
        slopes = self._calculate_trend_slope(df)

        # 3. 计算趋势持续时间
        duration = self._calculate_trend_duration(df)

        # 4. 评估趋势稳定性
        stability = self._assess_trend_stability(df)

        # 5. 识别密集成交区
        consolidation_status = self._identify_consolidation_zone(df)

        # 6. 检测顶底构造
        construction = self._detect_top_bottom_construction(df)

        # 7. 判断是否为密集成交区（3 点钟方向）
        # 密集成交区已经是基于 60 天窗口计算的状态，不需要再要求持续时间

        return {
            'df': df,
            # 价格数据归入 prices 结构
            'prices': {
                'price': latest['close'],
                'ma5': latest['ma5'],
                'ma20': latest['ma20'],
                'ma60': latest['ma60'],
                'ma120': latest['ma120']
            },
            'trend_direction': trend_direction,
            'slopes': slopes,
            'duration': duration,
            'stability': stability,  # health_score 在其中
            'consolidation': consolidation_status,  # 统一用 consolidation 结构
            'construction': construction
        }

    # ==================== 信号生成 ====================

    def _generate_trading_signals(self, analysis):
        """
        基于分析结果生成买卖信号

        买入信号（4 种）：
        1. 密集成交区突破
        2. 稳定上涨回踩 MA20
        3. 趋势转折买入（新增）- 均线金叉 + 趋势向好
        4. 底部构造买入（新增）- higher low + higher high

        卖出信号（5 种）：
        1. 顶部构造 + 趋势走弱
        2. 趋势转折完成（空头排列）
        3. 跌破重要支撑
        4. 高位偏离卖出（新增）- 价格远离均线
        5. 趋势放缓卖出（新增）- 上涨趋势中健康度下降

        :param analysis: dict，包含所有分析结果
        :return: signals dict {buy_signals: [], sell_signals: []}
        """
        signals = {'buy_signals': [], 'sell_signals': []}

        prices = analysis['prices']
        price = prices['price']
        ma5 = prices['ma5']
        ma20 = prices['ma20']
        ma60 = prices['ma60']
        ma120 = prices['ma120']
        trend_direction = analysis['trend_direction']
        health_score = analysis['stability']['health_score']
        construction = analysis['construction']
        slopes = analysis['slopes']
        df = analysis['df']

        # ===== 买入信号 1：密集成交区突破 =====
        # 不依赖趋势方向，只要识别出密集成交区且突破就触发（左侧交易）
        consolidation = analysis['consolidation']
        if consolidation.get('is_consolidation_zone', False):
            upper_bound = consolidation.get('upper_bound', 0)
            if upper_bound and price > upper_bound * 1.005:  # 突破 0.5% 以上
                stop_loss = self._calculate_stop_loss(price, '密集区突破', ma20=ma20, upper_bound=upper_bound)

                signals['buy_signals'].append({
                    'type': 'BUY',
                    'signal': '密集成交区突破',
                    'strength': 'MEDIUM',
                    'price': price,
                    'stop_loss': stop_loss,
                    'target_price': [stop_loss, float('inf')],
                    'trend_direction': trend_direction,
                    'health_score': health_score,
                    'description': f'价格突破密集成交区上边界 ({upper_bound:.2f})',
                    'conditions_met': [
                        '密集成交区',
                        f'突破>{upper_bound*1.005:.2f}',
                        f'当前趋势：{trend_direction}'
                    ]
                })

        # ===== 买入信号 2：稳定上涨回踩 =====
        # 只在两点钟方向（稳定上涨）时考虑回踩买点
        if trend_direction == "两点钟方向（稳定上涨）" and health_score >= 60:
            ma20_slope_up = slopes.get('ma20', 0) > 0.03
            ma60_slope_up = slopes.get('ma60', 0) > 0
            ma120_not_down = slopes.get('ma120', 0) > -0.05

            all_mas_up = ma20_slope_up and ma60_slope_up

            if all_mas_up and ma20 > ma120:
                tolerance = 0.15
                if self._is_near_price(price, ma20, tolerance=tolerance):
                    stop_loss = self._calculate_stop_loss(price, '回踩买点', ma20=ma20, ma60=ma60)

                    signals['buy_signals'].append({
                        'type': 'BUY',
                        'signal': '回踩 MA20',
                        'strength': 'MEDIUM',
                        'price': price,
                        'stop_loss': stop_loss,
                        'target_price': [stop_loss, float('inf')],
                        'trend_direction': trend_direction,
                        'health_score': health_score,
                        'description': f'上涨趋势中价格回踩 20 日均线 ({ma20:.2f})',
                        'conditions_met': [
                            '趋势向上',
                            f'健康度{health_score}',
                            '底部构造' if '底部构造' in construction else '无明显构造',
                            'MA20/MA60 向上',
                            'MA20>MA120',
                            f'回踩 MA20±15%'
                        ]
                    })

        # ===== 买入信号 3：趋势转折买入（新增）=====
        # 条件：均线金叉 + 价格站上 MA20 + 趋势向好
        if len(df) >= 3:
            # 检查 MA5 是否上穿 MA20（金叉）
            ma5_cross_ma20 = (
                df['ma5'].iloc[-1] > df['ma20'].iloc[-1] and
                df['ma5'].iloc[-2] <= df['ma20'].iloc[-2]
            )

            # 检查价格是否站上 MA20
            price_above_ma20 = price > ma20 * 1.02  # 站上 2%

            # 检查 MA20 是否拐头向上
            ma20_turn_up = (
                len(df) >= 5 and
                df['ma20'].iloc[-1] > df['ma20'].iloc[-5]
            )

            # 检查是否从下跌趋势转好
            trend_improving = (
                trend_direction in ["三点钟方向（横盘整理）", "两点钟方向（稳定上涨）"]
            )

            if ma5_cross_ma20 and price_above_ma20 and ma20_turn_up and trend_improving:
                stop_loss = self._calculate_stop_loss(price, '趋势转折', ma20=ma20, ma60=ma60)

                signals['buy_signals'].append({
                    'type': 'BUY',
                    'signal': '趋势转折买入',
                    'strength': 'MEDIUM',
                    'price': price,
                    'stop_loss': stop_loss,
                    'target_price': [stop_loss, float('inf')],
                    'trend_direction': trend_direction,
                    'health_score': health_score,
                    'description': f'MA5 上穿 MA20 形成金叉，价格站上{ma20:.2f}',
                    'conditions_met': [
                        'MA5 上穿 MA20（金叉）',
                        f'价格站上 MA20+2%',
                        'MA20 拐头向上',
                        f'趋势：{trend_direction}'
                    ]
                })

        # ===== 买入信号 4：底部构造买入（新增）=====
        # 条件：识别到底部构造 + 健康度提升 + 趋势向好
        if '底部构造' in construction and health_score >= 60:  # 提高健康度阈值到 60
            # 检查是否不再创新低
            if len(df) >= 5:
                recent_lows = df['low'].tail(5).values
                prev_lows = df['low'].tail(10).head(5).values

                no_new_low = min(recent_lows) >= min(prev_lows) * 0.97  # 允许 3% 误差（放宽）

                # 检查是否有放量迹象
                volume_confirm = False
                if 'volume' in df.columns:
                    recent_vol = df['volume'].tail(3).mean()
                    prev_vol = df['volume'].tail(10).head(5).mean()
                    volume_confirm = recent_vol > prev_vol * 1.15  # 放量 15%（提高要求）

                # 检查趋势是否向好（横盘或上涨）
                trend_improving = trend_direction in ["三点钟方向（横盘整理）", "两点钟方向（稳定上涨）"]

                # 要求：不再创新低 + (放量 或 趋势向好)
                if no_new_low and (volume_confirm or trend_improving):
                    stop_loss = self._calculate_stop_loss(price, '底部构造', ma20=ma20, ma60=ma60)

                    signals['buy_signals'].append({
                        'type': 'BUY',
                        'signal': '底部构造买入',
                        'strength': 'MEDIUM',
                        'price': price,
                        'stop_loss': stop_loss,
                        'target_price': [stop_loss, float('inf')],
                        'trend_direction': trend_direction,
                        'health_score': health_score,
                        'description': f'识别到底部构造（不再创新低），健康度{health_score}分',
                        'conditions_met': [
                            '底部构造（higher low）',
                            '不再创新低',
                            f'健康度≥60',
                            '放量' if volume_confirm else '未放量',
                            f'趋势：{trend_direction}'
                        ]
                    })

        # ===== 卖出信号 1：顶部构造 + 趋势走弱 =====
        if trend_direction in ["四点钟方向（稳定下跌）", "五点钟方向（加速下跌）"]:
            if health_score < 50 and "顶部构造" in construction:
                strength = "STRONG" if health_score < 40 else "MEDIUM"
                signals['sell_signals'].append({
                    'type': 'SELL',
                    'signal': '顶部构造 + 趋势走弱',
                    'strength': strength,
                    'trend_direction': trend_direction,
                    'health_score': health_score,
                    'description': f'{trend_direction}，健康度{health_score}分，顶部构造完成，建议逢高减仓',
                    'conditions_met': [
                        f'趋势：{trend_direction}',
                        f'健康度{health_score}',
                        '顶部构造'
                    ]
                })

        # ===== 卖出信号 2：趋势转折完成（空头排列） =====
        if '排列：形成空头排列' in construction and health_score < 50:
            signals['sell_signals'].append({
                'type': 'SELL',
                'signal': '趋势转折完成',
                'strength': 'STRONG',
                'trend_direction': trend_direction,
                'health_score': health_score,
                'description': '均线空头排列形成，下跌趋势确认',
                'conditions_met': [
                    '趋势转折完成',
                    '空头排列',
                    f'健康度{health_score}'
                ]
            })

        # ===== 卖出信号 3：跌破重要支撑 =====
        ma20_break = (
            ma20 > 0 and
            price < ma20 * 0.95 and
            len(df) >= 5 and df['ma20'].iloc[-1] < df['ma20'].iloc[-5]
        )
        ma60_break = (
            ma60 > 0 and
            price < ma60 * 0.95 and
            len(df) >= 10 and df['ma60'].iloc[-1] < df['ma60'].iloc[-10]
        )

        if trend_direction in ["四点钟方向（稳定下跌）", "五点钟方向（加速下跌）"]:
            if ma20_break or ma60_break:
                strength = "STRONG" if ma60_break else "MEDIUM"
                support_level = "MA60" if ma60_break else "MA20"
                signals['sell_signals'].append({
                    'type': 'SELL',
                    'signal': f'跌破{support_level}',
                    'strength': strength,
                    'trend_direction': trend_direction,
                    'health_score': health_score,
                    'description': f'价格跌破{support_level}重要支撑',
                    'conditions_met': [
                        f'跌破{support_level}',
                        f'{support_level}向下拐头',
                        f'趋势：{trend_direction}'
                    ]
                })

        # ===== 卖出信号 4：高位偏离卖出（新增）=====
        # 条件：价格远离 MA5（乖离率过大）- 提高阈值到 10%
        if ma5 > 0:
            bias_rate = (price - ma5) / ma5 * 100
            if bias_rate > 10:  # 乖离率超过 10%（原 8%）
                signals['sell_signals'].append({
                    'type': 'SELL',
                    'signal': '高位偏离卖出',
                    'strength': 'MEDIUM',
                    'trend_direction': trend_direction,
                    'health_score': health_score,
                    'description': f'价格偏离 MA5 达{bias_rate:.1f}%，存在回调风险',
                    'conditions_met': [
                        f'乖离率{bias_rate:.1f}%',
                        '远离均线',
                        '可能回调'
                    ]
                })

        # ===== 卖出信号 5：趋势放缓卖出（新增）=====
        # 条件：上涨趋势中健康度大幅下降 - 提高阈值
        if trend_direction in ["一点钟方向（加速上涨）", "两点钟方向（稳定上涨）"]:
            # 检查健康度是否大幅下降（从高位下降超过 25 分）
            if len(df) >= 10:
                # 计算 10 天前的健康度（简化：用均线排列判断）
                prev_row = df.iloc[-10]
                prev_bullish = self._is_bullish_arrangement(prev_row)

                # 如果之前是多头排列，现在健康度<55，说明趋势放缓（原 60）
                if prev_bullish and health_score < 55:
                    signals['sell_signals'].append({
                        'type': 'SELL',
                        'signal': '趋势放缓卖出',
                        'strength': 'MEDIUM',
                        'trend_direction': trend_direction,
                        'health_score': health_score,
                        'description': f'上涨趋势中健康度降至{health_score}分，趋势可能放缓',
                        'conditions_met': [
                            f'健康度下降',
                            f'当前健康度{health_score}',
                            '趋势可能转弱'
                        ]
                    })

        return signals

    def _calculate_stop_loss(self, current_price, signal_type, ma20=None, ma60=None, upper_bound=None):
        """
        计算止损价（方案 C：固定比例 + 技术位，取更宽松的）

        :param current_price: 当前价格
        :param signal_type: 信号类型
        :param ma20: 20 日均线
        :param ma60: 60 日均线
        :param upper_bound: 密集区上边界
        :return: 止损价
        """
        # 方案 1：固定比例止损（-8%）
        fixed_stop = current_price * 0.92

        # 方案 2：技术位止损
        technical_stop = current_price
        if signal_type == '密集区突破' and upper_bound:
            technical_stop = upper_bound * 0.98  # 跌破密集区 2%
        elif ma60 and ma60 > 0:
            technical_stop = ma60 * 0.95  # 跌破 MA60 5%
        elif ma20 and ma20 > 0:
            technical_stop = ma20 * 0.95  # 跌破 MA20 5%

        # 取更宽松的（更高的）止损价
        return max(fixed_stop, technical_stop)

    # ==================== 交易建议与报告 ====================
    def _generate_report(self, stock_code, stock_name, latest, analysis, trading_signals):
        """
        生成分析报告

        :return: 分析报告字符串
        """

        # 基于信号生成建议
        if trading_signals['buy_signals']:
            recommendation = "✅ 有买入信号，可考虑介入"
        elif trading_signals['sell_signals']:
            recommendation = "⚠️ 有卖出信号，建议减仓或观望"
        else:
            recommendation = "😐 无明显信号，继续观望"

        # 判断均线排列状态
        # 使用 MA20/MA60/MA120 三条均线判断趋势（与趋势持续时间保持一致）
        # MA5 作为短期均线波动较大，不参与趋势排列判断
        ma5 = latest['ma5']
        ma20 = latest['ma20']
        ma60 = latest['ma60']
        ma120 = latest['ma120']

        if self._is_bullish_arrangement(latest):
            ma_alignment = "多头排列 ✅"
            alignment_icon = "📈"
        elif self._is_bearish_arrangement(latest):
            ma_alignment = "空头排列 ⚠️"
            alignment_icon = "📉"
        else:
            ma_alignment = "均线缠绕 😐"
            alignment_icon = "➡️"

        # 健康度图标
        health_score = analysis['stability']['health_score']
        if health_score >= 70:
            health_icon = "✅"
        elif health_score >= 50:
            health_icon = "😐"
        else:
            health_icon = "⚠️"

        # 趋势方向图标
        trend_direction = analysis['trend_direction']
        if "上涨" in trend_direction:
            trend_icon = "📈"
        elif "下跌" in trend_direction:
            trend_icon = "📉"
        else:
            trend_icon = "➡️"

        report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 趋势交易 AI 分析报告 V2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏷️ 股票：{stock_name}({stock_code})
⏰ 分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 当前价格：{latest['close']:.2f} 元

📈 均线系统
┌─────────┬─────────┬─────────┬─────────┬────────────┐
│  MA5    │  MA20   │  MA60   │  MA120  │  排列状态  │
├─────────┼─────────┼─────────┼─────────┼────────────┤
│{ma5:>8.2f}│{ma20:>8.2f}│{ma60:>8.2f}│{ma120:>8.2f}│{ma_alignment:>11s}│
└─────────┴─────────┴─────────┴─────────┴────────────┘

{trend_icon} 趋势方向：{analysis['trend_direction']}
   • 趋势斜率：价格 {analysis['slopes'].get('price', 0):.4f}%/日 | MA20: {analysis['slopes'].get('ma20', 0):.2f}%
   • 持续时间：多头 {analysis['duration']['bullish']} 天 | 空头 {analysis['duration']['bearish']} 天 | 横盘 {analysis['duration']['consolidation']} 天

{health_icon} 趋势健康度：{analysis['stability']['health_score']} 分 ({analysis['stability']['status']})
   • 趋势方向：+{analysis['stability'].get('trend_direction_score', 0)} 分 (多头/空头排列)
   • 持续时间：+{analysis['stability'].get('duration_score', 0)} 分 (趋势持续 {analysis['stability'].get('trend_duration', 0)} 天)
   • 均线间距：+{analysis['stability'].get('gap_score', 0)} 分 (MA5-MA20: {analysis['stability'].get('ma5_ma20_gap', 0):.2f}%)
   • 波动率：+{analysis['stability'].get('volatility_score', 0)} 分 (MA5 波动：{analysis['stability'].get('ma5_std', 0):.2f}%)

🎯 密集成交区：{analysis['consolidation']['status_str']}
📐 顶底构造：{analysis['construction']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔔 交易信号
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        if trading_signals['buy_signals']:
            report += "✅ 买入信号:\n"
            for i, signal in enumerate(trading_signals['buy_signals'], 1):
                report += f"   {i}. {signal['signal']}: {signal['description']}\n"
        else:
            report += "   无买入信号\n"

        report += "\n"

        if trading_signals['sell_signals']:
            report += "⚠️ 卖出信号:\n"
            for i, signal in enumerate(trading_signals['sell_signals'], 1):
                report += f"   {i}. {signal['signal']}: {signal['description']}\n"
        else:
            report += "   无卖出信号\n"

        report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 交易建议
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{recommendation}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 风险提示：趋势交易分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。
"""

        return report


    # ==================== K 线图表数据 ====================

    def get_kline_chart_data(self, stock_code, stock_name, period=365):
        """
        获取 K 线图表数据（用于 ECharts 展示）

        :param stock_code: 股票代码
        :param stock_name: 股票名称
        :param period: 返回的天数（默认 365 天）
        :return: dict {
            'success': True,
            'data': {
                'stock_code': str,
                'current_price': float,
                'dates': list,
                'kline': list,  # [open, close, low, high]
                'volumes': list,  # [index, volume, direction]
                'ma5': list,
                'ma20': list,
                'ma60': list,
                'ma120': list,
                'buy_signals': list,
                'sell_signals': list,
                'consolidation_zone': dict,
                'trend_direction': str,
                'health_score': int
            }
        }
        """
        try:
            import pandas as pd

            # 获取历史数据（多获取一些用于计算均线）
            historical_data = _fetch_historical_data(stock_code, days=period)
            if not historical_data or len(historical_data) < 60:
                return {
                    'success': False,
                    'message': '历史数据不足，无法生成 K 线图'
                }

            # 转换为 DataFrame 并计算均线
            df = pd.DataFrame(historical_data)
            df = df.sort_values('date')

            # 计算均线
            df['ma5'] = df['close'].rolling(window=5).mean()
            df['ma20'] = df['close'].rolling(window=20).mean()
            df['ma60'] = df['close'].rolling(window=60).mean()
            df['ma120'] = df['close'].rolling(window=120).mean()

            # 获取实时价格
            stock_obj = {'code': stock_code, 'name': stock_name}
            real_time_info = get_stock_info(stock_obj)
            current_price = real_time_info.get('price') if real_time_info else None

            # 使用趋势分析器获取买卖信号和密集成交区
            analysis_result = self.analyze_stock_trend(stock_code, stock_name)

            # 提取买卖信号
            buy_signals = []
            sell_signals = []
            if analysis_result.get('success') and analysis_result.get('trading_signals'):
                for signal in analysis_result['trading_signals'].get('buy_signals', []):
                    signal_price = signal.get('price')
                    if signal_price:
                        # 找到最接近信号价格的日期
                        closest_idx = (df['close'] - signal_price).abs().idxmin()
                        buy_signals.append({
                            'date': df.loc[closest_idx, 'date'],
                            'price': float(signal_price),
                            'signal': signal.get('signal', '买入'),
                            'strength': signal.get('strength', 'MEDIUM')
                        })

                for signal in analysis_result['trading_signals'].get('sell_signals', []):
                    signal_price = signal.get('price')
                    if signal_price:
                        closest_idx = (df['close'] - signal_price).abs().idxmin()
                        sell_signals.append({
                            'date': df.loc[closest_idx, 'date'],
                            'price': float(signal_price),
                            'signal': signal.get('signal', '卖出'),
                            'strength': signal.get('strength', 'MEDIUM')
                        })

            # 准备 ECharts 格式的数据
            kline_data = []
            volumes = []
            dates = []
            ma5_data = []
            ma20_data = []
            ma60_data = []
            ma120_data = []

            # 只返回最近 period 天的数据
            recent_df = df.tail(period)

            for _, row in recent_df.iterrows():
                # K 线数据：[open, close, low, high]
                kline_data.append([
                    round(row['open'], 2) if pd.notna(row.get('open')) else 0,
                    round(row['close'], 2) if pd.notna(row['close']) else 0,
                    round(row['low'], 2) if pd.notna(row.get('low')) else 0,
                    round(row['high'], 2) if pd.notna(row.get('high')) else 0
                ])

                # 成交量：[index, volume, direction]
                volumes.append([
                    len(dates),
                    round(row['volume'], 2) if pd.notna(row.get('volume')) and row.get('volume') else 0,
                    1 if pd.notna(row.get('close')) and pd.notna(row.get('open')) and row['close'] >= row['open'] else -1
                ])

                # 日期
                dates.append(row['date'])

                # 均线数据
                ma5_data.append(round(row['ma5'], 2) if pd.notna(row.get('ma5')) else None)
                ma20_data.append(round(row['ma20'], 2) if pd.notna(row.get('ma20')) else None)
                ma60_data.append(round(row['ma60'], 2) if pd.notna(row.get('ma60')) else None)
                ma120_data.append(round(row['ma120'], 2) if pd.notna(row.get('ma120')) else None)

            # 准备密集成交区信息
            consolidation_zone = None
            if analysis_result.get('success') and analysis_result.get('trend_analysis'):
                trend_analysis = analysis_result['trend_analysis']
                if trend_analysis.get('consolidation', {}).get('is_zone'):
                    consolidation_zone = {
                        'upper_bound': trend_analysis['consolidation'].get('upper_bound'),
                        'lower_bound': trend_analysis['consolidation'].get('lower_bound'),
                        'status': trend_analysis['consolidation'].get('status')
                    }

            return {
                'success': True,
                'data': {
                    'stock_code': stock_code,
                    'current_price': current_price,
                    'dates': dates,
                    'kline': kline_data,
                    'volumes': volumes,
                    'ma5': ma5_data,
                    'ma20': ma20_data,
                    'ma60': ma60_data,
                    'ma120': ma120_data,
                    'buy_signals': buy_signals,
                    'sell_signals': sell_signals,
                    'consolidation_zone': consolidation_zone,
                    'trend_direction': analysis_result.get('trend_analysis', {}).get('direction', ''),
                    'health_score': analysis_result.get('trend_analysis', {}).get('health_score', 0)
                },
                'message': f'获取 {stock_code} 的 K 线数据成功'
            }

        except Exception as e:
            logger.error(f"获取股票 {stock_code} K 线图表数据失败：{str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'获取 K 线数据失败：{str(e)}'
            }
