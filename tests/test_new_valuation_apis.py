"""
测试新发现的估值接口：stock_index_pe_lg 和 stock_index_pb_lg
"""
import akshare as ak
import pandas as pd
from datetime import datetime

TEST_INDICES = [
    {"symbol": "000300", "name": "沪深 300"},
    {"symbol": "000016", "name": "上证 50"},
    {"symbol": "399006", "name": "创业板指"},
    {"symbol": "000688", "name": "科创 50"},
    {"symbol": "000905", "name": "中证 500"},
]


def test_stock_index_pe_lg():
    """
    测试 stock_index_pe_lg 接口
    """
    print("=" * 80)
    print("测试：ak.stock_index_pe_lg() - 指数 PE 数据")
    print("=" * 80)
    
    results = []
    
    for idx in TEST_INDICES:
        symbol = idx["symbol"]
        name = idx["name"]
        
        try:
            print(f"\n获取 {name} ({symbol}) 的 PE 数据...")
            
            df = ak.stock_index_pe_lg(symbol=symbol)
            
            if df is not None and not df.empty:
                print(f"✅ 成功获取数据，共 {len(df)} 条记录")
                print(f"\n数据列：{list(df.columns)}")
                print(f"\n最新数据 (第一条):")
                latest = df.iloc[0].to_dict()
                for key, value in latest.items():
                    print(f"  {key}: {value}")
                
                # 检查是否有百分位数据
                has_percentile = any('percent' in str(k).lower() or '分位' in str(k) for k in latest.keys())
                print(f"\n是否包含百分位数据：{'✅ 是' if has_percentile else '❌ 否'}")
                
                results.append({
                    "symbol": symbol,
                    "name": name,
                    "success": True,
                    "columns": list(df.columns),
                    "latest": latest,
                    "has_percentile": has_percentile,
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


def test_stock_index_pb_lg():
    """
    测试 stock_index_pb_lg 接口
    """
    print("\n" + "=" * 80)
    print("测试：ak.stock_index_pb_lg() - 指数 PB 数据")
    print("=" * 80)
    
    results = []
    
    for idx in TEST_INDICES:
        symbol = idx["symbol"]
        name = idx["name"]
        
        try:
            print(f"\n获取 {name} ({symbol}) 的 PB 数据...")
            
            df = ak.stock_index_pb_lg(symbol=symbol)
            
            if df is not None and not df.empty:
                print(f"✅ 成功获取数据，共 {len(df)} 条记录")
                print(f"\n数据列：{list(df.columns)}")
                print(f"\n最新数据 (第一条):")
                latest = df.iloc[0].to_dict()
                for key, value in latest.items():
                    print(f"  {key}: {value}")
                
                # 检查是否有百分位数据
                has_percentile = any('percent' in str(k).lower() or '分位' in str(k) for k in latest.keys())
                print(f"\n是否包含百分位数据：{'✅ 是' if has_percentile else '❌ 否'}")
                
                results.append({
                    "symbol": symbol,
                    "name": name,
                    "success": True,
                    "columns": list(df.columns),
                    "latest": latest,
                    "has_percentile": has_percentile,
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


def test_csindex_with_different_params():
    """
    测试 stock_zh_index_value_csindex 的不同参数
    """
    print("\n" + "=" * 80)
    print("测试：ak.stock_zh_index_value_csindex() - 尝试不同参数")
    print("=" * 80)
    
    # 尝试不同的 symbol 格式
    test_symbols = [
        "000300",
        "399006", 
        "000016",
        "000300.XSHG",  # 聚宽格式
        "399006.XSHE",  # 聚宽格式
    ]
    
    for symbol in test_symbols:
        try:
            print(f"\n尝试 symbol={symbol}...")
            df = ak.stock_zh_index_value_csindex(symbol=symbol)
            if df is not None and not df.empty:
                print(f"✅ 成功！数据列：{list(df.columns)[:10]}")
                return {"success": True, "symbol": symbol, "columns": list(df.columns)}
            else:
                print(f"❌ 数据为空")
        except Exception as e:
            print(f"❌ 失败：{e}")
    
    return {"success": False, "error": "所有尝试都失败"}


def test_earnings_growth_api():
    """
    测试盈利增长 API
    """
    print("\n" + "=" * 80)
    print("测试：盈利增长因子接口")
    print("=" * 80)
    
    # 测试沪深 300 成分股的财务数据
    try:
        print("\n获取沪深 300 成分股列表...")
        # 先获取指数成分股
        df_cons = ak.index_stock_cons(symbol="000300")
        print(f"成分股数量：{len(df_cons)}")
        
        if len(df_cons) > 0:
            # 取前几只股票测试
            test_stocks = df_cons.head(3)['品种代码'].tolist()
            print(f"测试股票：{test_stocks}")
            
            for stock_code in test_stocks:
                try:
                    print(f"\n获取 {stock_code} 的财务指标...")
                    df_fin = ak.stock_financial_analysis_indicator(symbol=stock_code, start_year="2023")
                    if df_fin is not None and not df_fin.empty:
                        print(f"✅ 成功获取 {len(df_fin)} 条记录")
                        print(f"数据列：{list(df_fin.columns)[:15]}")
                        
                        # 查找增长相关指标
                        growth_cols = [c for c in df_fin.columns if '增长' in str(c) or 'growth' in str(c).lower()]
                        if growth_cols:
                            print(f"📊 增长相关指标：{growth_cols}")
                        
                        # 显示最新数据
                        latest = df_fin.iloc[0].to_dict()
                        print(f"最新数据示例:")
                        for k, v in list(latest.items())[:8]:
                            print(f"  {k}: {v}")
                            
                except Exception as e:
                    print(f"❌ {stock_code} 获取失败：{e}")
                    
    except Exception as e:
        print(f"❌ 测试失败：{e}")


if __name__ == "__main__":
    print(f"测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"AkShare 版本：{ak.__version__}")
    
    # 测试 PE 接口
    pe_results = test_stock_index_pe_lg()
    
    # 测试 PB 接口
    pb_results = test_stock_index_pb_lg()
    
    # 测试中证指数接口的不同参数
    csindex_result = test_csindex_with_different_params()
    
    # 测试盈利增长接口
    test_earnings_growth_api()
    
    # 汇总报告
    print("\n" + "=" * 80)
    print("📊 测试汇总报告")
    print("=" * 80)
    
    pe_success = sum(1 for r in pe_results if r["success"])
    pb_success = sum(1 for r in pb_results if r["success"])
    
    print(f"\n【PE 接口】成功：{pe_success}/{len(pe_results)}")
    for r in pe_results:
        status = "✅" if r["success"] else "❌"
        percentile_info = "📊 含百分位" if r.get("has_percentile") else ""
        print(f"  {status} {r['name']} ({r['symbol']}) {percentile_info}")
        if r["success"]:
            print(f"      关键列：{[c for c in r['columns'] if any(x in str(c).lower() for x in ['pe', 'percent', '估值', 'date'])]}")
    
    print(f"\n【PB 接口】成功：{pb_success}/{len(pb_results)}")
    for r in pb_results:
        status = "✅" if r["success"] else "❌"
        percentile_info = "📊 含百分位" if r.get("has_percentile") else ""
        print(f"  {status} {r['name']} ({r['symbol']}) {percentile_info}")
        if r["success"]:
            print(f"      关键列：{[c for c in r['columns'] if any(x in str(c).lower() for x in ['pb', 'percent', '估值', 'date'])]}")
    
    print(f"\n【中证指数接口】")
    if csindex_result.get("success"):
        print(f"  ✅ 可用，symbol 格式：{csindex_result['symbol']}")
        print(f"      数据列：{csindex_result['columns']}")
    else:
        print(f"  ❌ 不可用")
    
    print("\n" + "=" * 80)
    print("💡 结论与建议")
    print("=" * 80)
    
    if pe_success > 0 and pb_success > 0:
        print("\n✅ 发现可用的 PE/PB 接口！")
        print("   - stock_index_pe_lg: 获取指数 PE 数据")
        print("   - stock_index_pb_lg: 获取指数 PB 数据")
        print("\n   建议：")
        print("   1. 优先使用这两个接口获取真实 PE/PB 数据")
        print("   2. 检查是否包含百分位数据，如有则直接使用")
        print("   3. 如无百分位数据，用历史数据自行计算")
    else:
        print("\n❌ PE/PB 接口不可用，需要继续使用估算模型")
    
    # 检查是否有百分位数据
    has_percentile = any(r.get("has_percentile") for r in pe_results + pb_results if r["success"])
    if has_percentile:
        print("\n✅ 接口直接提供百分位数据！")
        print("   可以废弃当前的估算模型，直接使用 API 数据")
    else:
        print("\n⚠️ 接口不提供百分位数据")
        print("   需要：获取历史 PE/PB 数据 → 自行计算百分位")
