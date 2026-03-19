"""
测试估值相关 API 接口的实际数据
验证：
1. stock_zh_index_value_csindex 能否获取真实 PE/PB 数据
2. 是否有盈利增长因子相关接口
"""
import akshare as ak
import pandas as pd
from datetime import datetime

# 测试用的指数代码
TEST_INDICES = [
    {"symbol": "sh000300", "name": "沪深 300"},
    {"symbol": "sh000016", "name": "上证 50"},
    {"symbol": "sz399006", "name": "创业板指"},
    {"symbol": "sh000688", "name": "科创 50"},
    {"symbol": "sh000905", "name": "中证 500"},
]


def test_csindex_valuation():
    """
    测试中证指数估值接口
    文档：https://akshare.akfamily.xyz/data/stock/stock.html#stock-zh-index-value-csindex
    """
    print("=" * 80)
    print("测试 1: ak.stock_zh_index_value_csindex() - 中证指数估值数据")
    print("=" * 80)
    
    results = []
    
    for idx in TEST_INDICES:
        symbol = idx["symbol"]
        name = idx["name"]
        
        try:
            # 中证指数官网数据（需要去掉 sh/sz 前缀）
            clean_symbol = symbol.replace("sh", "").replace("sz", "")
            print(f"\n获取 {name} ({clean_symbol}) 的估值数据...")
            
            df = ak.stock_zh_index_value_csindex(symbol=clean_symbol)
            
            if df is not None and not df.empty:
                print(f"✅ 成功获取数据，共 {len(df)} 条记录")
                print(f"\n数据列：{list(df.columns)}")
                print(f"\n最新数据 (第一条):")
                latest = df.iloc[0].to_dict()
                for key, value in latest.items():
                    print(f"  {key}: {value}")
                
                results.append({
                    "symbol": symbol,
                    "name": name,
                    "success": True,
                    "columns": list(df.columns),
                    "latest": latest,
                    "data_count": len(df)
                })
            else:
                print(f"❌ 数据为空")
                results.append({
                    "symbol": symbol,
                    "name": name,
                    "success": False,
                    "error": "数据为空"
                })
                
        except Exception as e:
            print(f"❌ 获取失败：{e}")
            results.append({
                "symbol": symbol,
                "name": name,
                "success": False,
                "error": str(e)
            })
    
    return results


def test_other_valuation_apis():
    """
    测试其他可能的估值数据接口
    """
    print("\n" + "=" * 80)
    print("测试 2: 其他估值相关接口")
    print("=" * 80)
    
    # 测试接口列表
    apis_to_test = [
        {
            "name": "stock_zh_index_daily",
            "desc": "新浪指数日线数据",
            "func": lambda: ak.stock_zh_index_daily(symbol="sh000300")
        },
        {
            "name": "index_value_hist_em",
            "desc": "东方财富指数估值历史",
            "func": lambda: ak.index_value_hist_em(symbol="sh000300")
        },
        {
            "name": "index_value_analysis_em",
            "desc": "东方财富指数估值分析",
            "func": lambda: ak.index_value_analysis_em(symbol="sh000300")
        },
    ]
    
    results = []
    
    for api in apis_to_test:
        print(f"\n测试接口：{api['name']} - {api['desc']}")
        try:
            df = api["func"]()
            if df is not None and not df.empty:
                print(f"✅ 成功获取数据，共 {len(df)} 条记录")
                print(f"数据列：{list(df.columns)[:10]}...")  # 只显示前 10 列
                if len(df) > 0:
                    print(f"最新数据示例:")
                    latest = df.iloc[0].to_dict()
                    for key, value in list(latest.items())[:5]:
                        print(f"  {key}: {value}")
                results.append({
                    "name": api["name"],
                    "success": True,
                    "columns": list(df.columns),
                    "sample": dict(list(df.iloc[0].to_dict().items())[:5])
                })
            else:
                print(f"❌ 数据为空")
                results.append({
                    "name": api["name"],
                    "success": False,
                    "error": "数据为空"
                })
        except Exception as e:
            print(f"❌ 获取失败：{e}")
            results.append({
                "name": api["name"],
                "success": False,
                "error": str(e)
            })
    
    return results


def test_earnings_growth_apis():
    """
    测试盈利增长相关接口
    """
    print("\n" + "=" * 80)
    print("测试 3: 盈利增长因子相关接口")
    print("=" * 80)
    
    # 可能的盈利增长接口
    apis_to_test = [
        {
            "name": "stock_financial_analysis_indicator",
            "desc": "股票财务分析指标",
            "func": lambda: ak.stock_financial_analysis_indicator(symbol="000001", start_year="2020")
        },
        {
            "name": "index_stock_info",
            "desc": "指数成分股信息",
            "func": lambda: ak.index_stock_info(symbol="000300")
        },
        {
            "name": "index_stock_cons",
            "desc": "指数成分股列表",
            "func": lambda: ak.index_stock_cons(symbol="000300")
        },
        {
            "name": "stock_report_disclosure",
            "desc": "股票财报披露",
            "func": lambda: ak.stock_report_disclosure(symbol="000001")
        },
    ]
    
    results = []
    
    for api in apis_to_test:
        print(f"\n测试接口：{api['name']} - {api['desc']}")
        try:
            df = api["func"]()
            if df is not None and not df.empty:
                print(f"✅ 成功获取数据，共 {len(df)} 条记录")
                print(f"数据列：{list(df.columns)[:15]}...")
                results.append({
                    "name": api["name"],
                    "success": True,
                    "columns": list(df.columns),
                    "has_earnings_data": any(col in str(df.columns).lower() for col in ['earn', 'profit', 'growth', '净利', '营收', '增长'])
                })
            else:
                print(f"❌ 数据为空")
                results.append({
                    "name": api["name"],
                    "success": False,
                    "error": "数据为空"
                })
        except Exception as e:
            print(f"❌ 获取失败：{e}")
            results.append({
                "name": api["name"],
                "success": False,
                "error": str(e)
            })
    
    return results


def test_em_index_valuation_detail():
    """
    测试东方财富指数估值详细数据
    """
    print("\n" + "=" * 80)
    print("测试 4: 东方财富指数估值详细接口")
    print("=" * 80)
    
    # 东方财富指数估值接口
    em_apis = [
        {
            "name": "index_value_hist_em",
            "desc": "指数估值历史 (含百分位)",
            "func": lambda: ak.index_value_hist_em(symbol="000300", period="10y")
        },
        {
            "name": "index_pe_and_pb_em",
            "desc": "指数 PE/PB 数据",
            "func": lambda: ak.index_pe_and_pb_em(symbol="000300", index_name="沪深 300")
        },
    ]
    
    results = []
    
    for api in em_apis:
        print(f"\n测试接口：{api['name']} - {api['desc']}")
        try:
            df = api["func"]()
            if df is not None and not df.empty:
                print(f"✅ 成功获取数据，共 {len(df)} 条记录")
                print(f"数据列：{list(df.columns)}")
                if len(df) > 0:
                    print(f"最新数据:")
                    latest = df.iloc[0].to_dict()
                    for key, value in latest.items():
                        print(f"  {key}: {value}")
                results.append({
                    "name": api["name"],
                    "success": True,
                    "columns": list(df.columns),
                    "latest": df.iloc[0].to_dict() if len(df) > 0 else None
                })
            else:
                print(f"❌ 数据为空")
                results.append({
                    "name": api["name"],
                    "success": False,
                    "error": "数据为空"
                })
        except Exception as e:
            print(f"❌ 获取失败：{e}")
            results.append({
                "name": api["name"],
                "success": False,
                "error": str(e)
            })
    
    return results


if __name__ == "__main__":
    print(f"测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"AkShare 版本：{ak.__version__}")
    
    # 测试 1: 中证指数估值接口
    csindex_results = test_csindex_valuation()
    
    # 测试 2: 其他估值接口
    other_valuation_results = test_other_valuation_apis()
    
    # 测试 3: 盈利增长接口
    earnings_growth_results = test_earnings_growth_apis()
    
    # 测试 4: 东方财富指数估值
    em_valuation_results = test_em_index_valuation_detail()
    
    # 汇总报告
    print("\n" + "=" * 80)
    print("测试汇总报告")
    print("=" * 80)
    
    print("\n【中证指数估值接口】")
    for r in csindex_results:
        status = "✅" if r["success"] else "❌"
        print(f"  {status} {r['name']} ({r['symbol']})")
        if r["success"]:
            print(f"      数据列：{r['columns']}")
    
    print("\n【其他估值接口】")
    for r in other_valuation_results:
        status = "✅" if r["success"] else "❌"
        print(f"  {status} {r['name']}")
        if r["success"]:
            print(f"      关键列：{[c for c in r['columns'] if any(k in str(c).lower() for k in ['pe', 'pb', 'percentile', '估值'])]}")
    
    print("\n【盈利增长接口】")
    for r in earnings_growth_results:
        status = "✅" if r["success"] else "❌"
        has_data = "📊 含盈利相关数据" if r.get("has_earnings_data") else ""
        print(f"  {status} {r['name']} {has_data}")
        if r["success"]:
            print(f"      关键列：{[c for c in r['columns'][:10]]}")
    
    print("\n【东方财富指数估值】")
    for r in em_valuation_results:
        status = "✅" if r["success"] else "❌"
        print(f"  {status} {r['name']}")
        if r["success"] and r.get("latest"):
            print(f"      关键数据：{[(k, v) for k, v in r['latest'].items() if any(x in str(k).lower() for x in ['pe', 'pb', 'percent', '估值'])]}")
    
    print("\n" + "=" * 80)
    print("结论与建议")
    print("=" * 80)
    
    # 分析结果
    csindex_success = sum(1 for r in csindex_results if r["success"])
    em_success = sum(1 for r in em_valuation_results if r["success"])
    
    if csindex_success > 0:
        print("\n✅ 中证指数估值接口可用！")
        print("   建议：优先使用 stock_zh_index_value_csindex 获取真实 PE/PB 数据")
    else:
        print("\n❌ 中证指数估值接口不可用")
        print("   需要继续使用估算模型或寻找替代数据源")
    
    if em_success > 0:
        print("\n✅ 东方财富指数估值接口可用！")
        print("   建议：可以作为备用数据源，或用于验证中证数据")
    else:
        print("\n❌ 东方财富指数估值接口不可用")
    
    earnings_available = any(r.get("has_earnings_data") for r in earnings_growth_results if r["success"])
    if earnings_available:
        print("\n✅ 发现盈利增长相关数据接口！")
        print("   建议：可以引入盈利增长因子改进 PE 估算模型")
    else:
        print("\n❌ 未找到直接的盈利增长数据接口")
        print("   建议：可能需要通过财报数据间接计算，或继续使用简化模型")
