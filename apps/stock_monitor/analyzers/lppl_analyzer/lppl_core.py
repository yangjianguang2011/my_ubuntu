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
warnings.filterwarnings('ignore')

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
        print(f"开始拟合LPPL模型，数据点数: {len(t_norm)}")
        
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
            print(f"  使用 {method_name} 算法进行优化...")
            
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
                        print(f"    ✓ {method_name} (guess {i+1}) 优化成功! MSE: {best_mse:.8f}")
                    else:
                        print(f"    - {method_name} (guess {i+1}) 未找到更优解或失败")
                        
                except Exception as e:
                    print(f"    ✗ {method_name} (guess {i+1}) 优化出错: {e}")
                    continue
        
        # 如果局部优化都失败，尝试差分进化（使用较少的迭代）
        if best_params is None:
            print("  所有局部优化方法失败，尝试差分进化算法...")
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
                    print(f"    ✓ 差分进化优化成功! MSE: {best_mse:.8f}")
                    
            except Exception as e:
                print(f"    ✗ 差分进化过程中出错: {e}")
        
        if best_params is not None:
            self.fitted_params = best_params
            self.mse = best_mse
            self.success = True
            print(f"\n✓ 最优解已找到! 最终MSE: {self.mse:.8f}")
            
            # 打印参数
            tc, m, w, a, b, c, phi = self.fitted_params
            print(f"  参数: tc={tc:.2f}, m={m:.4f}, w={w:.4f}")
            print(f"        a={a:.4f}, b={b:.4f}, c={c:.4f}, phi={phi:.4f}")
            
            return True
        else:
            print("✗ 所有优化算法都失败了")
            return False
    
    def assess_bubble(self):
        """
        评估泡沫状态
        """
        if self.fitted_params is None:
            return None
            
        tc, m, w, a, b, c, phi = self.fitted_params
        # 计算泡沫指标 - 多维度综合评分
        bubble_score = 0
        
        # 1. B 参数（泡沫强度）
        if b > 0:
            bubble_score += 0.5 * min(b, 1.0)
            if b > 1.0:
                bubble_score += 0.2 * min((b - 1.0), 2.0)
        elif b < -0.5:
            bubble_score += 0.2 * min(abs(b), 1.0)
        
        # 2. 振荡频率 w
        if w > 6:
            bubble_score += 0.15 * min((w - 6) / 6, 1.0)
        
        # 3. m 参数（加速）
        if m < 0.5:
            bubble_score += 0.2 * (0.5 - m) / 0.5
        elif m > 0.9:
            bubble_score += 0.1 * (m - 0.9) / 0.1
        
        # 4. 振荡幅度 c
        if abs(c) > 0.05:
            bubble_score += 0.15 * min(abs(c) / 0.5, 1.0)
        
        bubble_score = min(bubble_score, 1.0)
        
        # 风险等级
        if bubble_score >= 0.6:
            risk_level = "高风险"
        elif bubble_score >= 0.35:
            risk_level = "中风险"
        elif bubble_score >= 0.15:
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
            'fitted_values': fitted_values.tolist() if hasattr(fitted_values, 'tolist') else list(fitted_values),  # 转换为列表
            'actual_values': log_prices.tolist() if hasattr(log_prices, 'tolist') else list(log_prices),  # 转换为列表
            'mse': float(self.mse)  # 确保是Python原生float类型
        }


def analyze_index_with_lppl(index_data, index_name="Index"):
    """
    对指数数据进行LPPL分析
    :param index_data: 包含'date'和'close'列的DataFrame
    :return: LPPL分析结果
    """
    # 数据预处理
    df = index_data.copy()
    df = df.sort_values('date').reset_index(drop=True)
    
    # 计算对数价格
    df['log_close'] = np.log(df['close'])
    
    # 时间标准化 (从0开始)
    df['t_norm'] = np.arange(len(df))
    t_norm = df['t_norm'].values
    log_prices = df['log_close'].values
    
    # 创建并拟合LPPL模型
    model = LPPLAnalyzer()
    success = model.fit_with_multiple_methods(t_norm, log_prices)
    
    if not success:
        return {
            'success': False,
            'error': 'LPPL模型拟合失败'
        }
    
    # 评估泡沫状态
    bubble_info = model.assess_bubble()
    
    # 生成残差分析，传递原始日期
    original_dates = df['date'].tolist()  # 提取原始日期
    residual_analysis = model.generate_residual_analysis(t_norm, log_prices, original_dates)
    
    # 准备返回结果
    result = {
        'success': True,
        'model_params': {
            'critical_time': float(model.fitted_params[0]) if model.fitted_params else None,
            'acceleration_param': float(model.fitted_params[1]) if model.fitted_params else None,
            'frequency_param': float(model.fitted_params[2]) if model.fitted_params else None,
            'offset_param': float(model.fitted_params[3]) if model.fitted_params else None,
            'bubble_strength': float(model.fitted_params[4]) if model.fitted_params else None,
            'oscillation_strength': float(model.fitted_params[5]) if model.fitted_params else None,
            'phi_param': float(model.fitted_params[6]) if model.fitted_params else None,
        },
        'bubble_info': bubble_info,
        'fitting_error': float(model.mse),
        'residual_analysis': residual_analysis
    }
    
    return result


def visualize_lppl_results(lppl_result, index_name="指数"):
    """
    可视化LPPL分析结果
    """
    if not lppl_result['success']:
        print("无法可视化失败的分析结果")
        return None
    
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    
    # 设置中文字体
    rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
    rcParams['axes.unicode_minus'] = False
    
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    
    # 获取数据
    residual_data = lppl_result['residual_analysis']
    dates = residual_data['dates']
    actual_values = residual_data['actual_values']
    fitted_values = residual_data['fitted_values']
    residuals = residual_data['residuals']
    
    # 子图1: 价格拟合对比
    axes[0].plot(dates, np.exp(actual_values), label='实际价格', linewidth=1.5, color='blue')
    axes[0].plot(dates, np.exp(fitted_values), label='LPPL拟合价格', linewidth=1.5, color='red', linestyle='--')
    axes[0].set_title(f'LPPL模型拟合结果 - {index_name}', fontsize=14, fontweight='bold')
    axes[0].set_ylabel('价格')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[0].tick_params(axis='x', rotation=45)
    
    # 子图2: 对数价格对比
    axes[1].plot(dates, actual_values, label='实际对数价格', linewidth=1.2, color='blue', alpha=0.8)
    axes[1].plot(dates, fitted_values, label='LPPL拟合曲线', linewidth=1.5, color='red', linestyle='--', alpha=0.8)
    axes[1].set_title('对数价格拟合对比', fontsize=12)
    axes[1].set_ylabel('对数价格')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    axes[1].tick_params(axis='x', rotation=45)
    
    # 子图3: 残差分析
    axes[2].plot(dates, residuals, label='拟合残差', color='purple', alpha=0.7)
    axes[2].axhline(y=0, color='black', linestyle='-', alpha=0.5)
    axes[2].axhline(y=np.std(residuals), color='orange', linestyle='--', alpha=0.5, label='±1标准差')
    axes[2].axhline(y=-np.std(residuals), color='orange', linestyle='--', alpha=0.5)
    axes[2].set_title('拟合残差分析', fontsize=12)
    axes[2].set_xlabel('日期')
    axes[2].set_ylabel('残差')
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)
    axes[2].tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    
    return fig

def visualize_lppl_results(lppl_result, index_name="Index", save_path=None):
    """Visualize LPPL analysis results"""
    if not lppl_result['success']:
        logger.error("Cannot visualize failed analysis")
        return None
    
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    residual_data = lppl_result['residual_analysis']
    dates = residual_data['dates']
    actual_prices = residual_data['actual_values']
    fitted_prices = residual_data['fitted_values']
    residuals = residual_data['residuals']
    
    axes[0].plot(dates, actual_prices, label='Actual Price', linewidth=1.5, color='blue')
    axes[0].plot(dates, fitted_prices, label='LPPL Fitted', linewidth=1.5, color='red', linestyle='--')
    axes[0].set_title(f'LPPL Model Fit - {index_name}', fontsize=14, fontweight='bold')
    axes[0].set_ylabel('Price')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[0].tick_params(axis='x', rotation=45)
    
    actual_log = np.log(actual_prices)
    fitted_log = np.log(fitted_prices)
    axes[1].plot(dates, actual_log, label='Actual Log Price', linewidth=1.2, color='blue', alpha=0.8)
    axes[1].plot(dates, fitted_log, label='LPPL Fit', linewidth=1.5, color='red', linestyle='--', alpha=0.8)
    axes[1].set_title('Log Price Comparison', fontsize=12)
    axes[1].set_ylabel('Log Price')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    axes[1].tick_params(axis='x', rotation=45)
    
    axes[2].plot(dates, residuals, label='Residuals', color='purple', alpha=0.7)
    axes[2].axhline(y=0, color='black', linestyle='-', alpha=0.5)
    std = np.std(residuals)
    axes[2].axhline(y=std, color='red', linestyle='--', alpha=0.7, linewidth=2, label=f'+1σ ({std:.4f})')
    axes[2].axhline(y=-std, color='red', linestyle='--', alpha=0.7, linewidth=2, label=f'-1σ ({-std:.4f})')
    axes[2].set_title('Residual Analysis', fontsize=12)
    axes[2].set_xlabel('Date')
    axes[2].set_ylabel('Residual')
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)
    axes[2].tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Chart saved to: {save_path}")
    return fig


def main():
    """Main function for LPPL analysis"""
    import sys
    import logging
    logger = logging.getLogger(__name__)
    
    INDEX_CONFIGS = {
        '上证指数': {'symbol': 'sh000001', 'name': '上证指数', 'period': '3Y'},
        '创业板指': {'symbol': 'sz399006', 'name': '创业板指', 'period': '3Y'},
        '沪深 300': {'symbol': 'sh000300', 'name': '沪深 300', 'period': '3Y'},
        '中证 500': {'symbol': 'sh000905', 'name': '中证 500', 'period': '3Y'}
    }
    
    if len(sys.argv) > 1:
        index_name = sys.argv[1]
    else:
        index_name = '上证指数'
    
    if index_name not in INDEX_CONFIGS:
        logger.error(f"Unknown index: {index_name}")
        logger.info(f"Available: {', '.join(INDEX_CONFIGS.keys())}")
        sys.exit(1)
    
    config = INDEX_CONFIGS[index_name]
    print("="*70)
    print(f"           LPPL Model Analysis")
    print(f"           Index: {config['name']} ({config['symbol']})")
    print("="*70)
    
    try:
        import akshare as ak
        logger.info(f"Fetching data for {config['symbol']}...")
        df = ak.stock_zh_index_daily(symbol=config['symbol'])
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        if df.empty:
            logger.error(f"No data for {config['symbol']}")
            print(f"❌ No data available")
            sys.exit(1)
        
        index_data = df[['date', 'close']].dropna()
        logger.info(f"Got {len(index_data)} data points")
        print(f"✓ Got {len(index_data)} data points")
        print(f"  Range: {index_data['date'].min()} to {index_data['date'].max()}")
        
    except Exception as e:
        logger.error(f"Failed to get data: {e}", exc_info=True)
        print(f"❌ Data fetch failed: {e}")
        sys.exit(1)
    
    print("\nStarting LPPL analysis...")
    result = analyze_index_with_lppl(index_data, config['name'])
    
    if not result['success']:
        print(f"❌ Analysis failed: {result.get('error', 'Unknown')}")
        sys.exit(1)
    
    print("\n" + "="*70)
    print("           Results")
    print("="*70)
    
    bubble_info = result.get('bubble_info', {})
    print(f"\nRisk Level: {bubble_info.get('risk_level', 'N/A')}")
    print(f"Bubble Score: {bubble_info.get('bubble_score', 0):.3f}")
    print(f"MSE: {result.get('fitting_error', 0):.10f}")
    
    model_params = result.get('model_params', {})
    print(f"\nModel Parameters:")
    print(f"  Critical Time (tc): {model_params.get('critical_time', 'N/A'):.2f}")
    print(f"  Acceleration (m): {model_params.get('acceleration_param', 'N/A'):.4f}")
    print(f"  Frequency (w): {model_params.get('frequency_param', 'N/A'):.4f}")
    print(f"  Bubble Strength (B): {model_params.get('bubble_strength', 'N/A'):.6f}")
    print(f"  Oscillation (C): {model_params.get('oscillation_strength', 'N/A'):.6f}")
    
    print("\nGenerating chart...")
    save_path = f"./lppl_analysis_{config['symbol']}.png"
    fig = visualize_lppl_results(result, config['name'], save_path=save_path)
    
    if fig:
        print(f"✓ Chart saved to: {save_path}")
    
    print("\n" + "="*70)
    print("           Analysis Complete")
    print("="*70)
    plt.close(fig)


if __name__ == "__main__":
    main()
