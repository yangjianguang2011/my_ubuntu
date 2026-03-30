"""
LPPL分析器模块
将ultimate_lppl_model中的功能适配到stock_monitor系统
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import minimize, differential_evolution
from datetime import datetime, timedelta
import warnings
import logging

from config import setup_logger

warnings.filterwarnings('ignore')

# 创建logger
#logger = logging.getLogger(__name__)
logger = setup_logger(__name__)

class LPPLAnalyzer:
    def __init__(self):
        self.fitted_params = None
        self.mse = float('inf')
        self.success = False
        
    def lppl_equation(self, t, tc, m, w, a, b, c, phi):
        """
        LPPL方程
        P(t) = A + B*(tc - t)^m + C*(tc - t)^m * cos(w*ln(tc - t) - phi)
        """
        try:
            if tc <= np.max(t) or m <= 0 or w <= 0:
                return np.full_like(t, np.inf)
            
            if np.any(tc - t <= 0):
                return np.full_like(t, np.inf)
                
            power_term = np.power(tc - t, m)
            cos_term = np.cos(w * np.log(tc - t) - phi)
            
            result = a + b * power_term + c * power_term * cos_term
            return result
        except:
            return np.full_like(t, np.inf)
    
    def objective_function(self, params, t, observed_log_prices):
        """
        目标函数：最小化拟合误差
        """
        tc, m, w, a, b, c, phi = params
        
        # 参数边界检查
        if m <= 0 or m >= 1.5 or w <= 0 or w > 50 or tc <= np.max(t):
            return 1e10  # 返回大值表示无效参数
            
        fitted_values = self.lppl_equation(t, tc, m, w, a, b, c, phi)
        
        if np.any(np.isnan(fitted_values)) or np.any(np.isinf(fitted_values)):
            return 1e10
            
        # 检查数值是否过大
        if np.any(np.abs(fitted_values) > 1e6):
            return 1e10
            
        squared_errors = np.power(observed_log_prices - fitted_values, 2)
        mse = np.mean(squared_errors)
        
        # 添加正则化项防止过拟合
        reg_term = 0.001 * (abs(b) + abs(c))
        return mse + reg_term
    
    def fit_with_multiple_methods(self, t_norm, log_prices):
        """
        使用多种方法拟合LPPL模型
        """
        logger.info(f"开始拟合LPPL模型，数据点数: {len(t_norm)}")
        
        # 定义参数边界
        bounds = [
            (np.max(t_norm) + 1, np.max(t_norm) + 365),  # tc: 临界时间
            (0.01, 1.0),                                 # m: 加速参数
            (1.0, 25.0),                                 # w: 振荡频率
            (np.min(log_prices) - 5, np.max(log_prices) + 5),  # a: 偏移
            (-10, 10),                                   # b: 幂数幅度
            (-5, 5),                                     # c: 振荡幅度
            (-2*np.pi, 2*np.pi)                          # phi: 相位
        ]
        
        # 尝试多种优化算法
        methods = [
            ('L-BFGS-B', {'maxiter': 2000}),
            ('Powell', {'maxiter': 1000}),
            ('Nelder-Mead', {'maxiter': 1000})
        ]
        
        best_result = None
        best_mse = float('inf')
        best_params = None
        
        for method_name, options in methods:
            logger.info(f"  使用 {method_name} 算法进行优化...")
            
            # 尝试多个初始猜测
            initial_guesses = [
                [np.max(t_norm) + 30, 0.5, 5.0, np.mean(log_prices), -0.1, 0.05, 0.0],
                [np.max(t_norm) + 60, 0.3, 8.0, np.mean(log_prices), 0.05, -0.02, 1.0],
                [np.max(t_norm) + 90, 0.7, 3.0, np.mean(log_prices), 0.2, 0.03, -1.0],
                [np.max(t_norm) + 120, 0.4, 10.0, np.mean(log_prices), -0.05, 0.02, 0.5],
                [np.max(t_norm) + 180, 0.6, 6.0, np.mean(log_prices), 0.1, -0.03, -0.5]
            ]
            
            for i, initial_guess in enumerate(initial_guesses):
                try:
                    result = minimize(
                        self.objective_function,
                        initial_guess,
                        args=(t_norm, log_prices),
                        method=method_name,
                        bounds=bounds,
                        options=options
                    )
                    
                    if result.success and result.fun < best_mse:
                        best_mse = result.fun
                        best_params = result.x
                        best_result = result
                        logger.info(f"    ✓ {method_name} (guess {i+1}) 优化成功! MSE: {best_mse:.8f}")
                    else:
                        logger.info(f"    - {method_name} (guess {i+1}) 未找到更优解或失败")
                        
                except Exception as e:
                    logger.error(f"    ✗ {method_name} (guess {i+1}) 优化出错: {e}")
                    continue
        
        # 如果局部优化都失败，尝试差分进化（使用较少的迭代）
        if best_params is None:
            logger.info("  所有局部优化方法失败，尝试差分进化算法...")
            try:
                result = differential_evolution(
                    self.objective_function,
                    bounds,
                    args=(t_norm, log_prices),
                    maxiter=25,  # 减少迭代次数
                    popsize=10,   # 减少种群大小
                    seed=42,
                    disp=False
                )
                
                if result.success and result.fun < best_mse:
                    best_mse = result.fun
                    best_params = result.x
                    logger.info(f"    ✓ 差分进化优化成功! MSE: {best_mse:.8f}")
                    
            except Exception as e:
                logger.error(f"    ✗ 差分进化过程中出错: {e}")
        
        if best_params is not None:
            self.fitted_params = best_params
            self.mse = best_mse
            self.success = True
            logger.info(f"\n✓ 最优解已找到! 最终MSE: {self.mse:.8f}")
            
            # 打印参数
            tc, m, w, a, b, c, phi = self.fitted_params
            logger.info(f"  参数: tc={tc:.2f}, m={m:.4f}, w={w:.4f}")
            logger.info(f"        a={a:.4f}, b={b:.4f}, c={c:.4f}, phi={phi:.4f}")
            
            return True
        else:
            logger.error("✗ 所有优化算法都失败了")
            return False
    
    def assess_bubble(self):
        """
        评估泡沫状态
        """
        if self.fitted_params is None:
            return None
            
        tc, m, w, a, b, c, phi = self.fitted_params
        
        # 计算泡沫指标
        bubble_score = 0
        if b > 0:  # B为正表示泡沫
            bubble_score += 0.4 * min(abs(b), 2.0)  # 泡沫强度
        if abs(c) > 0.1:  # 振荡强度
            bubble_score += 0.3 * min(abs(c), 2.0)
        if m > 0.3:  # 加速参数
            bubble_score += 0.3 * min(m, 1.0)
            
        bubble_score = min(bubble_score, 1.0)  # 限制在0-1之间
        
        # 风险等级
        if bubble_score > 0.7:
            risk_level = "高风险"
        elif bubble_score > 0.4:
            risk_level = "中风险"
        elif bubble_score > 0.1:
            risk_level = "低风险"
        else:
            risk_level = "无明显泡沫"
        
        return {
            'bubble_score': bubble_score,
            'risk_level': risk_level,
            'bubble_strength': b,
            'oscillation_strength': c,
            'acceleration_param': m,
            'frequency_param': w,
            'critical_time': tc,
            'phi_param': phi
        }
    
    def generate_residual_analysis(self, t_norm, log_prices, original_dates=None):
        """
        生成残差分析数据
        """
        if self.fitted_params is None:
            return None
            
        tc, m, w, a, b, c, phi = self.fitted_params
        fitted_values = self.lppl_equation(t_norm, tc, m, w, a, b, c, phi)
        
        if fitted_values is None or np.any(np.isinf(fitted_values)):
            return None
        
        residuals = log_prices - fitted_values
        
        # 使用原始日期，如果没有提供则生成默认日期
        if original_dates is not None and len(original_dates) == len(t_norm):
            dates = original_dates
        else:
            # 如果没有提供原始日期，生成默认日期（保留原来的行为作为备用）
            dates = pd.date_range(start='2010-01-01', periods=len(t_norm), freq='D')
            # 只保留工作日
            dates = dates[dates.weekday < 5][:len(t_norm)]
        
        # 将numpy数组和pandas对象转换为JSON可序列化的格式
        return {
            'dates': [str(pd.to_datetime(date).date()) for date in dates],  # 使用pandas转换确保兼容性并转换为字符串列表
            'residuals': residuals.tolist() if hasattr(residuals, 'tolist') else list(residuals),  # 转换为列表
            'fitted_values': np.exp(fitted_values).tolist() if hasattr(fitted_values, 'tolist') else list(np.exp(fitted_values)),  # 实际价格
            'actual_values': np.exp(log_prices).tolist() if hasattr(log_prices, 'tolist') else list(np.exp(log_prices)),  # 实际价格
            'mse': float(self.mse)  # 确保是Python原生float类型
        }


def analyze_index_with_lppl(index_data, index_name="未知指数"):
    """
    对指数数据进行LPPL分析
    :param index_data: 包含'date'和'close'列的DataFrame
    :param index_name: 指数名称
    :return: LPPL分析结果
    """
    logger.info(f"开始对指数 {index_name} 进行LPPL分析，数据点数量: {len(index_data)}")
    
    # 数据预处理
    df = index_data.copy()
    
    # 检查并处理数据格式
    if 'date' not in df.columns:
        # 如果没有date列，可能是索引是日期
        if isinstance(df.index, pd.DatetimeIndex):
            df['date'] = df.index
        else:
            # 尝试从其他列名获取日期
            date_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
            if date_cols:
                df = df.rename(columns={date_cols[0]: 'date'})
            else:
                # 如果仍然没有日期列，使用索引
                df['date'] = pd.to_datetime(df.index)
    
    # 确保date列是datetime类型
    df['date'] = pd.to_datetime(df['date'])
    
    # 按日期排序
    df = df.sort_values('date').reset_index(drop=True)
    
    logger.info(f"数据预处理完成，日期范围: {df['date'].min()} 至 {df['date'].max()}")
    
    # 检查并处理价格列
    price_col = 'close'
    if 'close' not in df.columns:
        # 尝试其他可能的价格列名
        possible_price_cols = ['close', '收盘', '收盘价', 'price', 'adj_close', 'adjusted_close']
        for col in possible_price_cols:
            if col in df.columns:
                price_col = col
                break
        else:
            # 如果没有找到标准列名，尝试使用包含'close'或'price'的列
            price_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['close', 'price', '收盘'])]
            if price_cols:
                price_col = price_cols[0]
            else:
                logger.error(f"数据中未找到价格列，可用列: {list(df.columns)}")
                raise ValueError(f"数据中未找到价格列，可用列: {list(df.columns)}")
    
    logger.info(f"使用价格列: {price_col}")
    
    # 计算对数价格
    df['log_close'] = np.log(df[price_col])
    
    # 时间标准化 (从0开始)
    df['t_norm'] = np.arange(len(df))
    t_norm = df['t_norm'].values
    log_prices = df['log_close'].values
    
    logger.info(f"数据转换完成，时间范围: {t_norm.min()} - {t_norm.max()}，对数价格范围: {log_prices.min():.4f} - {log_prices.max():.4f}")
    
    # 创建并拟合LPPL模型
    logger.info("开始创建并拟合LPPL模型...")
    model = LPPLAnalyzer()
    success = model.fit_with_multiple_methods(t_norm, log_prices)
    
    if not success:
        logger.error(f"LPPL模型拟合失败，指数: {index_name}")
        return {
            'success': False,
            'error': 'LPPL模型拟合失败',
            'index_name': index_name
        }
    
    logger.info(f"LPPL模型拟合成功，MSE: {model.mse:.6f}")
    
    # 评估泡沫状态
    bubble_info = model.assess_bubble()
    logger.info(f"泡沫评估完成，风险等级: {bubble_info['risk_level'] if bubble_info else 'N/A'}")
    
    # 生成残差分析，传递原始日期
    logger.info("生成残差分析数据...")
    original_dates = df['date'].tolist()  # 提取原始日期
    residual_analysis = model.generate_residual_analysis(t_norm, log_prices, original_dates)
    logger.info(f"残差分析生成完成，数据点数: {len(residual_analysis['dates']) if residual_analysis else 0}")
    
    # 准备返回结果
    result = {
        'success': True,
        'index_name': index_name,
        'model_params': {
            'critical_time': float(model.fitted_params[0]) if model.fitted_params is not None and len(model.fitted_params) > 0 else None,
            'acceleration_param': float(model.fitted_params[1]) if model.fitted_params is not None and len(model.fitted_params) > 1 else None,
            'frequency_param': float(model.fitted_params[2]) if model.fitted_params is not None and len(model.fitted_params) > 2 else None,
            'offset_param': float(model.fitted_params[3]) if model.fitted_params is not None and len(model.fitted_params) > 3 else None,
            'bubble_strength': float(model.fitted_params[4]) if model.fitted_params is not None and len(model.fitted_params) > 4 else None,
            'oscillation_strength': float(model.fitted_params[5]) if model.fitted_params is not None and len(model.fitted_params) > 5 else None,
            'phi_param': float(model.fitted_params[6]) if model.fitted_params is not None and len(model.fitted_params) > 6 else None,
        },
        'bubble_info': bubble_info,
        'fitting_error': float(model.mse),
        'residual_analysis': residual_analysis,
        'index_name': index_name
    }
    
    logger.info(f"指数 {index_name} LPPL分析完成")
    return result



def visualize_lppl_results(lppl_result, index_name="指数", save_path=None):
    """
    可视化 LPPL 分析结果
    :param lppl_result: LPPL 分析结果字典
    :param index_name: 指数名称
    :param save_path: 图片保存路径，如果为 None 则不保存
    :return: matplotlib figure 对象
    """
    if not lppl_result['success']:
        logger.error("无法可视化失败的分析结果")
        return None
    
    from matplotlib import rcParams
    
    # 设置中文字体
    rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
    rcParams['axes.unicode_minus'] = False
    
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    
    # 获取数据
    residual_data = lppl_result['residual_analysis']
    dates = residual_data['dates']
    actual_prices = residual_data['actual_values']  # 已经是实际价格
    fitted_prices = residual_data['fitted_values']  # 已经是实际价格
    residuals = residual_data['residuals']
    
    # 子图 1: 价格拟合对比
    axes[0].plot(dates, actual_prices, label='实际价格', linewidth=1.5, color='blue')
    axes[0].plot(dates, fitted_prices, label='LPPL 拟合价格', linewidth=1.5, color='red', linestyle='--')
    axes[0].set_title(f'LPPL 模型拟合结果 - {index_name}', fontsize=14, fontweight='bold')
    axes[0].set_ylabel('价格')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[0].tick_params(axis='x', rotation=45)
    
    # 子图 2: 对数价格对比（用于分析）
    actual_log = np.log(actual_prices)
    fitted_log = np.log(fitted_prices)
    axes[1].plot(dates, actual_log, label='实际对数价格', linewidth=1.2, color='blue', alpha=0.8)
    axes[1].plot(dates, fitted_log, label='LPPL 拟合曲线', linewidth=1.5, color='red', linestyle='--', alpha=0.8)
    axes[1].set_title('对数价格拟合对比', fontsize=12)
    axes[1].set_ylabel('对数价格')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    axes[1].tick_params(axis='x', rotation=45)
    
    # 子图 3: 残差分析
    axes[2].plot(dates, residuals, label='拟合残差', color='purple', alpha=0.7)
    axes[2].axhline(y=0, color='black', linestyle='-', alpha=0.5)
    std = np.std(residuals)
    axes[2].axhline(y=std, color='orange', linestyle='--', alpha=0.5, label=f'+1 标准差 ({std:.4f})')
    axes[2].axhline(y=-std, color='orange', linestyle='--', alpha=0.5, label=f'-1 标准差 ({-std:.4f})')
    axes[2].set_title('拟合残差分析', fontsize=12)
    axes[2].set_xlabel('日期')
    axes[2].set_ylabel('残差')
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)
    axes[2].tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"图表已保存至：{save_path}")
    
    return fig


def main():
    """
    主函数 - 运行 LPPL 分析并保存图片
    """
    import sys
    
    # 配置参数
    INDEX_CONFIGS = {
        '上证指数': {
            'symbol': 'sh000001',
            'name': '上证指数',
            'period': '3Y'  # 3 年数据
        },
        '创业板指': {
            'symbol': 'sz399006',
            'name': '创业板指',
            'period': '3Y'
        },
        '沪深 300': {
            'symbol': 'sh000300',
            'name': '沪深 300',
            'period': '3Y'
        },
        '中证 500': {
            'symbol': 'sh000905',
            'name': '中证 500',
            'period': '3Y'
        }
    }
    
    # 从命令行参数获取指数名称，默认使用上证指数
    if len(sys.argv) > 1:
        index_name = sys.argv[1]
    else:
        index_name = '上证指数'
    
    if index_name not in INDEX_CONFIGS:
        logger.error(f"未知的指数：{index_name}")
        logger.info(f"可用的指数：{', '.join(INDEX_CONFIGS.keys())}")
        sys.exit(1)
    
    config = INDEX_CONFIGS[index_name]
    
    print("="*70)
    print(f"           LPPL 模型市场泡沫检测系统")
    print(f"           分析指数：{config['name']} ({config['symbol']})")
    print("="*70)
    
    # 获取指数数据
    try:
        # 使用 akshare 直接获取指数数据
        import akshare as ak
        logger.info(f"使用 akshare 获取指数 {config['symbol']} 的历史数据...")
        
        # 获取指数历史数据
        df = ak.stock_zh_index_daily(symbol=config['symbol'])
        # akshare 返回的列名直接就是'date'
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        if df.empty:
            logger.error(f"指数 {config['symbol']} 无历史数据")
            print(f"❌ 无法获取指数 {config['name']} 的数据")
            sys.exit(1)
        
        index_data = df[['date', 'close']].dropna()
        logger.info(f"获取到 {len(index_data)} 条历史数据")
        
        if index_data.empty:
            logger.error(f"指数 {config['symbol']} 无历史数据")
            print(f"❌ 无法获取指数 {config['name']} 的数据")
            sys.exit(1)
        
        logger.info(f"获取到 {len(index_data)} 条历史数据")
        print(f"✓ 获取到 {len(index_data)} 条历史数据")
        print(f"  数据范围：{index_data['date'].min()} 至 {index_data['date'].max()}")
        
    except Exception as e:
        logger.error(f"获取数据失败：{e}", exc_info=True)
        print(f"❌ 获取数据失败：{e}")
        sys.exit(1)
    
    # 进行 LPPL 分析
    print("\n开始 LPPL 分析...")
    result = analyze_index_with_lppl(index_data, config['name'])
    
    if not result['success']:
        print(f"❌ LPPL 分析失败：{result.get('error', '未知错误')}")
        sys.exit(1)
    
    # 打印分析结果
    print("\n" + "="*70)
    print("           分析结果")
    print("="*70)
    
    bubble_info = result.get('bubble_info', {})
    print(f"\n风险等级：{bubble_info.get('risk_level', 'N/A')}")
    print(f"泡沫评分：{bubble_info.get('bubble_score', 0):.3f}")
    print(f"拟合误差 (MSE): {result.get('fitting_error', 0):.10f}")
    
    model_params = result.get('model_params', {})
    print(f"\n模型参数:")
    print(f"  临界时间 (tc): {model_params.get('critical_time', 'N/A')}")
    print(f"  加速参数 (m): {model_params.get('acceleration_param', 'N/A')}")
    print(f"  振荡频率 (w): {model_params.get('frequency_param', 'N/A')}")
    print(f"  泡沫强度 (B): {model_params.get('bubble_strength', 'N/A')}")
    print(f"  振荡强度 (C): {model_params.get('oscillation_strength', 'N/A')}")
    
    # 生成可视化图表
    print("\n生成可视化图表...")
    save_path = f"./lppl_analysis_{config['symbol']}.png"
    fig = visualize_lppl_results(result, config['name'], save_path=save_path)
    
    if fig:
        print(f"✓ 图表已保存至：{save_path}")
    
    print("\n" + "="*70)
    print("           分析完成")
    print("="*70)
    
    plt.close(fig)


if __name__ == "__main__":
    main()
