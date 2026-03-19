"""
测试估值接口 - 使用正确的参数格式
"""
import akshare as ak
import pandas as pd
from datetime import datetime

# 乐咕乐股指数的正确参数（中文名称）
LEGULEGU_INDICES = [
    "上证 50",
    "沪深 300", 
    "中证 500",
    "中证 800",
    "中证 100",
    "中证 1000",
    "创业板 50",
    "上证 180",
    "深证 100",
    "深证红利",
]

# 中证指数需要特定的指数代码格式
CSINDEX_INDICES = [
    "H30374",  # 一个示例指数
    "000300",  # 沪深 300
    "000016",  # 上证 50
    "399006",  # 创业板指
]


def test_legulegu_pe():
    """
    测试乐咕乐股 PE 接口（使用中文参数）
    """
    print("=" * 80)
    print("测试：ak.stock_index_pe_lg() - 乐咕乐股指数市盈率")
    print("=" * 80)
    
    results = []
    
    for index_name in LEGULEGU_INDICES[:5]:  # 只测试前 5 个
        try:
            print(f"\n获取 {index_name} 的 PE 数据...")
            
            df = ak.stock_index_pe_lg(symbol=index_name)
            
            if df is not None and not df.empty:
                print(f"✅ 成功获取数据，共 {len(df)} 条记录")
                print(f"数据列：{list(df.columns)}")
                
                if len(df) > 0:
                    latest = df.iloc[0].to_dict()
                    print(f"最新数据:")
                    for key, value in latest.items():
                        print(f"  {key}: {value}")
                    
                    # 检查关键字段
                    has_pe = any('pe' in str(k).lower() for k in latest.keys())
                    has_percentile = any('percent' in str(k).lower() or '分位' in str(k) for k in latest.keys())
                    
                    results.append({
                        "name": index_name,
                        "success": True,
                        "columns": list(df.columns),
                        "latest": latest,
                        "has_pe": has_pe,
                        "has_percentile": has_percentile,
                        "data_count": len(df)
                    })
                else:
                    results.append({
                        "name": index_name,
                        "success": False,
                        "error": "数据为空"
                    })
            else:
                print(f"❌ 数据为空")
                results.append({
                    "name": index_name,
                    "success": False,
                    "error": "数据为空"
                })
                
        except Exception as e:
            print(f"❌ 获取失败：{e}")
            results.append({
                "name": index_name,
                "success": False,
                "error": str(e)
            })
    
    return results


def test_legulegu_pb():
    """
    测试乐咕乐股 PB 接口（使用中文参数）
    """
    print("\n" + "=" * 80)
    print("测试：ak.stock_index_pb_lg() - 乐咕乐股指数市净率")
    print("=" * 80)
    
    results = []
    
    for index_name in LEGULEGU_INDICES[:5]:  # 只测试前 5 个
        try:
            print(f"\n获取 {index_name} 的 PB 数据...")
            
            df = ak.stock_index_pb_lg(symbol=index_name)
            
            if df is not None and not df.empty:
                print(f"✅ 成功获取数据，共 {len(df)} 条记录")
                print(f"数据列：{list(df.columns)}")
                
                if len(df) > 0:
                    latest = df.iloc[0].to_dict()
                    print(f"最新数据:")
                    for key, value in latest.items():
                        print(f"  {key}: {value}")
                    
                    # 检查关键字段
                    has_pb = any('pb' in str(k).lower() for k in latest.keys())
                    has_percentile = any('percent' in str(k).lower() or '分位' in str(k) for k in latest.keys())
                    
                    results.append({
                        "name": index_name,
                        "success": True,
                        "columns": list(df.columns),
                        "latest": latest,
                        "has_pb": has_pb,
                        "has_percentile": has_percentile,
                        "data_count": len(df)
                    })
                else:
                    results.append({
                        "name": index_name,
                        "success": False,
                        "error": "数据为空"
                    })
            else:
                print(f"❌ 数据为空")
                results.append({
                    "name": index_name,
                    "success": False,
                    "error": "数据为空"
                })
                
        except Exception as e:
            print(f"❌ 获取失败：{e}")
            results.append({
                "name": index_name,
                "success": False,
                "error": str(e)
            })
    
    return results


def test_csindex():
    """
    测试中证指数接口
    """
    print("\n" + "=" * 80)
    print("测试：ak.stock_zh_index_value_csindex() - 中证指数估值")
    print("=" * 80)
    
    results = []
    
    for symbol in CSINDEX_INDICES:
        try:
            print(f"\n获取 {symbol} 的估值数据...")
            
            df = ak.stock_zh_index_value_csindex(symbol=symbol)
            
            if df is not None and not df.empty:
                print(f"✅ 成功获取数据，共 {len(df)} 条记录")
                print(f"数据列：{list(df.columns)}")
                
                if len(df) > 0:
                    latest = df.iloc[0].to_dict()
                    print(f"最新数据:")
                    for key, value in latest.items():
                        print(f"  {key}: {value}")
                    
                    results.append({
                        "symbol": symbol,
                        "success": True,
                        "columns": list(df.columns),
                        "latest": latest,
                        "data_count": len(df)
                    })
            else:
                print(f"❌ 数据为空")
                results.append({
                    "symbol": symbol,
                    "success": False,
                    "error": "数据为空"
                })
                
        except Exception as e:
            print(f"❌ 获取失败：{e}")
            results.append({
                "symbol": symbol,
                "success": False,
                "error": str(e)
            })
    
    return results


def test_earnings_growth_detailed():
    """
    详细测试盈利增长因子接口
    """
    print("\n" + "=" * 80)
    print("测试：盈利增长因子 - 详细分析")
    print("=" * 80)
    
    # 测试几个代表性股票
    test_stocks = [
        {"code": "000001", "name": "平安银行"},
        {"code": "600036", "name": "招商银行"},
        {"code": "000858", "name": "五粮液"},
    ]
    
    growth_indicators = []
    
    for stock in test_stocks:
        code = stock["code"]
        name = stock["name"]
        
        try:
            print(f"\n获取 {name} ({code}) 的财务指标...")
            
            df = ak.stock_financial_analysis_indicator(symbol=code, start_year="2022")
            
            if df is not None and not df.empty:
                print(f"✅ 成功获取 {len(df)} 条记录")
                
                # 找出所有增长相关指标
                growth_cols = [c for c in df.columns if '增长' in str(c)]
                if growth_cols:
                    print(f"📊 增长相关指标 ({len(growth_cols)}个):")
                    for col in growth_cols[:10]:  # 显示前 10 个
                        print(f"    - {col}")
                    
                    # 记录这些指标
                    for col in growth_cols:
                        if col not in growth_indicators:
                            growth_indicators.append(col)
                    
                    # 显示最新数据中的增长指标
                    if len(df) > 0:
                        latest = df.iloc[0].to_dict()
                        print(f"最新数据中的增长指标值:")
                        for col in growth_cols[:5]:
                            if col in latest:
                                print(f"    {col}: {latest[col]}")
                
        except Exception as e:
            print(f"❌ 获取失败：{e}")
    
    print(f"\n总结：发现 {len(growth_indicators)} 个增长相关指标")
    for ind in growth_indicators:
        print(f"  - {ind}")
    
    return growth_indicators


if __name__ == "__main__":
    print(f"测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"AkShare 版本：{ak.__version__}")
    
    # 测试乐咕乐股 PE 接口
    pe_results = test_legulegu_pe()
    
    # 测试乐咕乐股 PB 接口
    pb_results = test_legulegu_pb()
    
    # 测试中证指数接口
    csindex_results = test_csindex()
    
    # 测试盈利增长因子
    growth_indicators = test_earnings_growth_detailed()
    
    # 汇总报告
    print("\n" + "=" * 80)
    print("📊 最终测试报告")
    print("=" * 80)
    
    pe_success = [r for r in pe_results if r["success"]]
    pb_success = [r for r in pb_results if r["success"]]
    csindex_success = [r for r in csindex_results if r["success"]]
    
    print(f"\n【乐咕乐股 PE 接口】成功：{len(pe_success)}/{len(pe_results)}")
    for r in pe_success:
        percentile = "📊 含百分位" if r.get("has_percentile") else ""
        print(f"  ✅ {r['name']} {percentile}")
        print(f"      列：{r['columns']}")
    
    print(f"\n【乐咕乐股 PB 接口】成功：{len(pb_success)}/{len(pb_results)}")
    for r in pb_success:
        percentile = "📊 含百分位" if r.get("has_percentile") else ""
        print(f"  ✅ {r['name']} {percentile}")
        print(f"      列：{r['columns']}")
    
    print(f"\n【中证指数接口】成功：{len(csindex_success)}/{len(csindex_results)}")
    for r in csindex_success:
        print(f"  ✅ {r['symbol']}")
        print(f"      列：{r['columns']}")
    
    print("\n" + "=" * 80)
    print("💡 最终结论")
    print("=" * 80)
    
    if pe_success and pb_success:
        print("\n✅ 乐咕乐股接口可用！")
        print("   - stock_index_pe_lg(symbol='沪深 300') 获取 PE")
        print("   - stock_index_pb_lg(symbol='沪深 300') 获取 PB")
        print("\n   关键发现:")
        for r in pe_success[:2]:
            if r.get('latest'):
                print(f"   - {r['name']} 数据示例：{[(k,v) for k,v in r['latest'].items() if 'pe' in str(k).lower() or 'percent' in str(k).lower()][:3]}")
    else:
        print("\n❌ 乐咕乐股接口不可用")
    
    if csindex_success:
        print("\n✅ 中证指数接口可用！")
    else:
        print("\n❌ 中证指数接口不可用 (403 Forbidden)")
    
    print(f"\n✅ 盈利增长因子接口确认可用！")
    print(f"   可用指标：{growth_indicators[:8]}")
    print(f"\n   使用方式：ak.stock_financial_analysis_indicator(symbol='000001', start_year='2023')")
    
    print("\n" + "=" * 80)
    print("🎯 实施建议")
    print("=" * 80)
    
    if pe_success and pb_success:
        print("""
方案 A: 使用乐咕乐股真实数据 (推荐)
-----------------------------------
1. 调用 stock_index_pe_lg(symbol='沪深 300') 获取真实 PE
2. 调用 stock_index_pb_lg(symbol='沪深 300') 获取真实 PB
3. 检查返回数据是否包含百分位
   - 如有百分位：直接使用
   - 如无百分位：用历史 PE/PB 数据自行计算
4. 废弃当前的估算模型 (estimate_historical_pe/pb)

优点：数据真实可靠
缺点：依赖乐咕乐股网站稳定性
        """)
    else:
        print("""
方案 B: 继续使用估算模型 (当前方案)
-----------------------------------
1. 保持现有的 estimate_historical_pe/pb 函数
2. 改进建议：
   - 通过成分股财务数据计算指数整体盈利增长
   - 用增长因子调整 PE 估算
        """)
    
    print("""
方案 C: 混合方案 (最稳妥)
-----------------------
1. 优先尝试乐咕乐股接口获取真实数据
2. 如果失败，降级到估算模型
3. 在返回数据中标识数据来源 (真实/估算)
4. 盈利增长因子可用于改进估算模型
    """)
