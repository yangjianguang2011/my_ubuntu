"""
LPPL分析器模块 - 兼容stock_monitor系统
"""

from .lppl_core import analyze_index_with_lppl, LPPLAnalyzer

# 检查函数是否存在
visualize_available = False
sanddance_available = False

# 尝试导入可视化函数
try:
    from .lppl_core import visualize_lppl_results
    visualize_available = True
except ImportError:
    pass  # 如果导入失败，就不添加该功能

# 尝试导入SandDance数据准备函数
try:
    from .lppl_core import get_sanddance_ready_data
    sanddance_available = True
except ImportError:
    pass  # 如果导入失败，就不添加该功能

# 导出可用的函数
__all__ = ['analyze_index_with_lppl', 'LPPLAnalyzer']

if visualize_available:
    __all__.append('visualize_lppl_results')
    
if sanddance_available:
    __all__.append('get_sanddance_ready_data')