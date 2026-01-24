#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成HTML报告脚本
用于生成分析师数据和行业板块数据的HTML报告文件
"""

import os
import json
from datetime import datetime
from analyst_data_fetcher import get_combined_analyst_data
from industry_data_fetcher import get_industry_ranking, get_industry_constituents
from analyst_data_fetcher import get_recently_updated_stocks
from logger_config import logger, gconfig

OUTPUT_DIR = gconfig.get('analyst_data_dir', 'reports')

def create_html_report(data, title, report_type, output_dir=OUTPUT_DIR):
    """
    创建HTML报告
    :param data: 要展示的数据
    :param title: 报告标题
    :param report_type: 报告类型 ('analyst' 或 'industry')
    :param output_dir: 输出目录
    :return: 生成的HTML文件路径
    """
    
    # 确保输出目录存在
    #os.makedirs(output_dir, exist_ok=True)
    #os.makedirs(os.path.join(output_dir, report_type), exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if report_type == "recently_updated_stocks":
        # 特殊处理最近更新股票报告的文件名格式
        # 将标题中的空格和特殊字符替换为下划线
        clean_title = title.replace(" ", "_").replace("-", "_").replace("__", "_")
        filename = f"recently_updated_stocks_{clean_title}_{timestamp}.html"
    else:
        filename = f"{report_type}_{title}_{timestamp}.html"
    filepath = os.path.join(output_dir, filename)
    
    # 根据报告类型选择样式
    if report_type == "analyst":
        css_styles = """
        <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }
        h2 {
            color: #555;
            margin-top: 30px;
            border-left: 4px solid #2196F3;
            padding-left: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 14px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
            word-wrap: break-word;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
            position: sticky;
            top: 0;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        tr:hover {
            background-color: #f5f5;
        }
        .analyst-link {
            color: #1976D2;
            text-decoration: none;
        }
        .analyst-link:hover {
            text-decoration: underline;
        }
        .no-data {
            text-align: center;
            padding: 20px;
            color: #666;
            font-style: italic;
        }
        .summary {
            background-color: #e8f4f8;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            border-left: 4px solid #3498db;
        }
        .summary h3 {
            margin-top: 0;
            color: #2980b9;
        }
        .summary p {
            margin: 5px 0;
        }
        .data-source-link {
            text-align: center;
            margin-bottom: 20px;
        }
        .data-source-link a {
            color: #1976D2;
            text-decoration: none;
            font-size: 16px;
            font-weight: bold;
        }
        </style>
        """
    else:  # industry
        css_styles = """
        <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }
        h2 {
            color: #55;
            margin-top: 30px;
            border-left: 4px solid #2196F3;
            padding-left: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 14px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
            word-wrap: break-word;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
            position: sticky;
            top: 0;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .industry-change {
            font-weight: bold;
        }
        .industry-change.positive {
            color: #27ae60; /* 绿色 - 上涨 */
        }
        .industry-change.negative {
            color: #e74c3c; /* 红色 - 下跌 */
        }
        .no-data {
            text-align: center;
            padding: 20px;
            color: #66;
            font-style: italic;
        }
        .summary {
            background-color: #f8f4e8;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .summary h3 {
            margin-top: 0;
            color: #b97f29;
        }
        .summary p {
            margin: 5px 0;
        }
        .data-source-link {
            text-align: center;
            margin-bottom: 20px;
        }
        .data-source-link a {
            color: #1976D2;
            text-decoration: none;
            font-size: 16px;
            font-weight: bold;
        }
        </style>
        """
    
    # 生成HTML内容
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {css_styles}
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        
        <div class="data-source-link">
            <a href="https://data.eastmoney.com/invest/invest/list.html" target="_blank">东方财富分析师数据源</a>
        </div>
        
        <div class="summary">
            <h3>数据摘要</h3>
            <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p>数据类型: {title}</p>
        </div>
    """
    
    if report_type == "analyst":
        # 处理分析师数据
        html_content += generate_analyst_html_content(data)
    elif report_type == "industry":
        # 处理行业数据
        html_content += generate_industry_html_content(data)
    elif report_type == "recently_updated_stocks":
        # 处理最近更新股票数据
        html_content += generate_recently_updated_stocks_html_content(data)
    
    html_content += """
    </div>
</body>
</html>
    """
    
    # 写入HTML文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    logger.info(f"HTML报告已生成: {filepath}")
    return filepath


def generate_analyst_html_content(data):
    """生成分析师数据的HTML内容"""
    html_content = ""
    
    # 添加分析师重点关注股票表格
    if 'top_focus_stocks' in data and data['top_focus_stocks']:
        html_content += """
        <h2>分析师重点关注股票（按分析师持有数量排序）</h2>
        <table>
            <thead>
                <tr>
                    <th>分析师关注数量</th>
                    <th>股票代码</th>
                    <th>股票名称</th>
                    <th>平均成交价格</th>
                    <th>最高成交价格</th>
                    <th>最低成交价格</th>
                    <th>最新价格</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for stock in data['top_focus_stocks']:
            html_content += f"""
                <tr>
                    <td>{stock.get('analyst_count', 0)}</td>
                    <td>{stock.get('stock_code', '')}</td>
                    <td>{stock.get('stock_name', '')}</td>
                    <td>{stock.get('avg_price', 'N/A')}</td>
                    <td>{stock.get('max_price', 'N/A')}</td>
                    <td>{stock.get('min_price', 'N/A')}</td>
                    <td>{stock.get('latest_price', 'N/A')}</td>
                </tr>
            """
        
        html_content += """
            </tbody>
        </table>
        """
    
    # 添加最新跟踪成份股表格
    if 'latest_tracking' in data and data['latest_tracking']:
        html_content += """
        <h2>最新跟踪成份股</h2>
        <table>
            <thead>
                <tr>
                    <th>分析师名称</th>
                    <th>分析师排名</th>
                    <th>股票代码</th>
                    <th>股票名称</th>
                    <th>调入日期</th>
                    <th>成交价格(前复权)</th>
                    <th>最新价格</th>
                    <th>阶段涨跌幅</th>
                    <th>当前评级名称</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for rec in data['latest_tracking']:
            html_content += f"""
                <tr>
                    <td>{rec.get('analyst_name', '')}</td>
                    <td>{rec.get('analyst_rank', '')}</td>
                    <td>{rec.get('股票代码', '')}</td>
                    <td>{rec.get('股票名称', '')}</td>
                    <td>{rec.get('调入日期', '')}</td>
                    <td>{rec.get('成交价格(前复权)', '')}</td>
                    <td>{rec.get('最新价格', '')}</td>
                    <td>{rec.get('阶段涨跌幅', '')}</td>
                    <td>{rec.get('当前评级名称', '')}</td>
                </tr>
            """
        
        html_content += """
            </tbody>
        </table>
        """
    
    return html_content


def generate_industry_html_content(data):
    """生成行业数据的HTML内容"""
    html_content = ""
    
    # 添加涨幅榜表格
    if 'top_gainers' in data and data['top_gainers']:
        html_content += """
        <h2>行业涨幅榜</h2>
        <table>
            <thead>
                <tr>
                    <th>排名</th>
                    <th>行业名称</th>
                    <th>涨跌幅</th>
                    <th>起始价格</th>
                    <th>结束价格</th>
                    <th>起始日期</th>
                    <th>结束日期</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for idx, industry in enumerate(data['top_gainers'], 1):
            change_pct = industry.get('change_pct', 0)
            if change_pct is None:
                change_pct = 0
            try:
                change_pct_float = float(change_pct)
            except (TypeError, ValueError):
                change_pct_float = 0
            
            change_class = "positive" if change_pct_float >= 0 else "negative"
            html_content += f"""
                <tr>
                    <td>{idx}</td>
                    <td>{industry.get('industry_name', '') or ''}</td>
                    <td class="industry-change {change_class}">{change_pct_float}%</td>
                    <td>{industry.get('start_price', 0) or 0}</td>
                    <td>{industry.get('end_price', 0) or 0}</td>
                    <td>{industry.get('start_date', '') or ''}</td>
                    <td>{industry.get('end_date', '') or ''}</td>
                </tr>
            """
        
        html_content += """
            </tbody>
        </table>
        """
    
    # 添加跌幅榜表格
    if 'top_losers' in data and data['top_losers']:
        html_content += """
        <h2>行业跌幅榜</h2>
        <table>
            <thead>
                <tr>
                    <th>排名</th>
                    <th>行业名称</th>
                    <th>涨跌幅</th>
                    <th>起始价格</th>
                    <th>结束价格</th>
                    <th>起始日期</th>
                    <th>结束日期</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for idx, industry in enumerate(data['top_losers'], 1):
            change_pct = industry.get('change_pct', 0)
            if change_pct is None:
                change_pct = 0
            try:
                change_pct_float = float(change_pct)
            except (TypeError, ValueError):
                change_pct_float = 0
            
            change_class = "positive" if change_pct_float >= 0 else "negative"
            html_content += f"""
                <tr>
                    <td>{idx}</td>
                    <td>{industry.get('industry_name', '') or ''}</td>
                    <td class="industry-change {change_class}">{change_pct_float}%</td>
                    <td>{industry.get('start_price', 0) or 0}</td>
                    <td>{industry.get('end_price', 0) or 0}</td>
                    <td>{industry.get('start_date', '') or ''}</td>
                    <td>{industry.get('end_date', '') or ''}</td>
                </tr>
            """
        
        html_content += """
            </tbody>
        </table>
        """
    
    return html_content  # 添加返回语句
    
def generate_recently_updated_stocks_html_content(data):
    """生成最近更新股票数据的HTML内容"""
    html_content = ""
    
    # 添加最近更新股票表格
    if data:
        html_content += """
        <h2>分析师最近更新股票</h2>
        <table>
            <thead>
                <tr>
                    <th>分析师名称</th>
                    <th>分析师行业</th>
                    <th>股票代码</th>
                    <th>股票名称</th>
                    <th>调入日期</th>
                    <th>最新评级日期</th>
                    <th>成交价格(前复权)</th>
                    <th>最新价格</th>
                    <th>阶段涨跌幅</th>
                    <th>当前评级名称</th>
                    <th>分析师3个月收益率</th>
                    <th>分析师6个月收益率</th>
                    <th>分析师12个月收益率</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for stock in data:
            html_content += f"""
                <tr>
                    <td>{stock.get('analyst_name', '')}</td>
                    <td>{stock.get('analyst_industry', '')}</td>
                    <td>{stock.get('股票代码', '')}</td>
                    <td>{stock.get('股票名称', '')}</td>
                    <td>{stock.get('调入日期', '')}</td>
                    <td>{stock.get('最新评级日期', '')}</td>
                    <td>{stock.get('成交价格(前复权)', '')}</td>
                    <td>{stock.get('最新价格', '')}</td>
                    <td>{stock.get('阶段涨跌幅', '')}</td>
                    <td>{stock.get('当前评级名称', '')}</td>
                    <td>{stock.get('analyst_period_3m_return', '')}</td>
                    <td>{stock.get('analyst_period_6m_return', '')}</td>
                    <td>{stock.get('analyst_period_12m_return', '')}</td>
                </tr>
            """
        
        html_content += """
            </tbody>
        </table>
        """
    else:
        html_content += """
        <h2>分析师最近更新股票</h2>
        <p>暂无最近更新的股票数据</p>
        """
    
    return html_content

def generate_analyst_report(top_analysts=20, top_stocks=50, period="3个月"):
    """
    生成分析师数据报告
    :param top_analysts: 前N名分析师
    :param top_stocks: 前N只重点关注股票
    :param period: 时间周期
    :return: 生成的HTML文件路径
    """
    logger.info(f"开始生成分析师数据报告，周期: {period}")
    
    # 获取分析师数据
    analyst_data = get_combined_analyst_data(top_analysts=top_analysts, top_stocks=top_stocks, period=period)
    
    if not analyst_data:
        logger.warning("未能获取分析师数据")
        return None
    
    # 生成HTML报告
    title = f"分析师重点关注股票报告 - {period}周期"
    report_path = create_html_report(analyst_data, title, "analyst")
    
    logger.info(f"分析师数据报告已生成: {report_path}")
    return report_path

def generate_recently_updated_stocks_report(days=30, indicator="最新跟踪成分股"):
    """
    生成分析师最近更新股票报告
    :param days: 天数阈值，默认30天
    :param indicator: 指标类型，默认"最新跟踪成分股"
    :return: 生成的HTML文件路径
    """
    logger.info(f"开始生成分析师最近更新股票报告，天数阈值: {days}天, 指标: {indicator}")
    
    # 获取最近更新的股票数据
    recently_updated_stocks = get_recently_updated_stocks(days=days, indicator=indicator)
    
    if not recently_updated_stocks:
        logger.warning("未能获取最近更新的股票数据")
        return None
    
    # 生成HTML报告
    title = f"分析师最近更新股票报告 - 最近{days}天"
    report_path = create_html_report(recently_updated_stocks, title, 'recently_updated_stocks')
    
    logger.info(f"分析师最近更新股票报告已生成: {report_path}")
    return report_path


def generate_industry_report(period="30"):
    """
    生成行业板块数据报告
    :param period: 时间周期（天数）
    :return: 生成的HTML文件路径
    """
    logger.info(f"开始生成行业板块数据报告，周期: {period}天")
    
    # 获取行业数据
    industry_ranking = get_industry_ranking(period=period)
    
    if not industry_ranking:
        logger.warning("未能获取行业数据")
        return None

    logger.info(f"获取到 {len(industry_ranking)} 条行业数据")
    
    # 按涨跌幅排序，分离涨幅榜和跌幅榜
    # 确保change_pct字段存在且为数值类型，否则设为0
    def safe_get_change_pct(item):
        change_pct = item.get('change_pct', 0)
        if change_pct is None:
            return 0
        try:
            return float(change_pct)
        except (TypeError, ValueError):
            return 0

    sorted_ranking = sorted(industry_ranking, key=safe_get_change_pct, reverse=True)
    
    # 取前20个涨幅最大的行业
    top_gainers = sorted_ranking[:20]
    
    # 取前20个跌幅最大的行业（即涨跌幅最小的）
    top_losers = sorted(industry_ranking, key=safe_get_change_pct)[:20]
    
    # 构造报告数据
    report_data = {
        'top_gainers': top_gainers,
        'top_losers': top_losers,
        'total_count': len(industry_ranking),
        'period': period  # 修复变量名错误
    }
    
    # 生成HTML报告
    title = f"行业板块数据报告 - 最近{period}天"
    logger.info(f"准备生成行业板块数据报告，标题: {title}")
    report_path = create_html_report(report_data, title, "industry")
    
    logger.info(f"行业板块数据报告已生成: {report_path}")
    return report_path


def main():
    """主函数，生成所有报告"""
    logger.info("开始生成HTML报告...")
    
    # 生成分析师报告
    try:
        analyst_report_path = generate_analyst_report()
        if analyst_report_path:
            print(f"✅ 分析师报告已生成: {analyst_report_path}")
        else:
            print("❌ 分析师报告生成失败")
    except Exception as e:
        logger.error(f"生成分析师报告时出错: {str(e)}")
        print(f"❌ 生成分析师报告时出错: {str(e)}")
    
    # 生成行业报告
    try:
        industry_report_path = generate_industry_report()
        if industry_report_path:
            print(f"✅ 行业报告已生成: {industry_report_path}")
        else:
            print("❌ 行业报告生成失败")
    except Exception as e:
        logger.error(f"生成行业报告时出错: {str(e)}")
        print(f"❌ 生成行业报告时出错: {str(e)}")
    
    # 生成最近更新股票报告
    try:
        recently_updated_report_path = generate_recently_updated_stocks_report()
        if recently_updated_report_path:
            print(f"✅ 分析师最近更新股票报告已生成: {recently_updated_report_path}")
        else:
            print("❌ 分析师最近更新股票报告生成失败")
    except Exception as e:
        logger.error(f"生成分析师最近更新股票报告时出错: {str(e)}")
        print(f"❌ 生成分析师最近更新股票报告时出错: {str(e)}")
    
    print("HTML报告生成完成！")


if __name__ == "__main__":
    main()
