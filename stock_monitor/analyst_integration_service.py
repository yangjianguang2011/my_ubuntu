"""
东方财富分析师数据与股票监控系统整合服务
提供API接口，将分析师数据与股票监控系统进行整合
"""
import os
import json
import glob
from datetime import datetime
from bs4 import BeautifulSoup
import re
from logger_config import logger,gconfig

def find_latest_analyst_files_by_period(period="3个月排行"):
    """
    根据时间段查找最新的分析师数据文件
    :param period: 时间段，如 "3个月排行", "6个月排行", "年度排行" 等
    :return: 最新文件路径或None
    """
    analyst_files_dir = gconfig['analyst_data_dir']
    logger.info(f"分析师文件路径: {analyst_files_dir}")

    search_paths = [
		analyst_files_dir,
        "/data/eastmoney",
    ]
    
    logger.info(f"搜索分析师文件的路径列表: {search_paths} for period: {period}")
    # 将时间段转换为文件名格式
    period_for_filename = period.replace(' ', '_').replace('：', '_')
    
    # 生成文件名模式
    if period == "3个月排行":
        pattern = f"全部_3个月排行_*.html"
    elif period == "6个月排行":
        pattern = f"全部_6个月排行_*.html"
    elif period == "12个月排行":
        pattern = f"全部_12个月排行_*.html"
    elif period == "最新总排行":
        pattern = f"全部_最新总排行_*.html"
    elif period == "2025 年度排行":
        pattern = f"全部_2025年度排行_*.html"
    else:
        # 如果不是预定义的周期，则尝试匹配最接近的
        pattern = f"*{period_for_filename}*.html"
    
    all_matching_files = []
    
    for search_path in search_paths:
        if os.path.exists(search_path):
            files = glob.glob(os.path.join(search_path, pattern))
            for file_path in files:
                all_matching_files.append({
                    'file_path': file_path,
                    'modified_time': datetime.fromtimestamp(os.path.getmtime(file_path)),
                    'file_name': os.path.basename(file_path)
                })
    
    if not all_matching_files:
        return None
    
    # 按修改时间排序，返回最新的文件
    latest_file_info = max(all_matching_files, key=lambda x: x['modified_time'])
    return latest_file_info['file_path']


def extract_analyst_top_stocks(html_file_path, limit=20):
    """
    从HTML文件中提取分析师重点关注的股票（按分析师持有数量排序，前20名）
    :param html_file_path: HTML文件路径
    :param limit: 返回股票数量限制
    :return: 股票列表
    """
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        logger.info(f"正在从 {html_file_path} 提取分析师重点关注股票...")
        
        # 查找标题为"分析师重点关注股票（按分析师持有数量排序，前20名）"的表格
        target_heading = soup.find('h2', string=re.compile(r'分析师重点关注股票.*?按分析师持有数量排序'))
        if not target_heading:
            logger.warning("未找到目标表格标题")
            return []
        
        # 获取标题下的表格
        table = target_heading.find_next('table')
        if not table:
            logger.warning("未找到目标表格")
            return []
        
        # 获取表头
        headers = [th.get_text().strip() for th in table.find_all('th')]
        logger.info(f"目标表格头部: {headers}")
        
        # 验证表头是否符合预期
        expected_headers = ['分析师个数', '股票代码', '股票名称', '股票链接', '平均成交价格', '最高成交价格', '最低成交价格', '最新价格']
        if not all(h in headers for h in expected_headers):
            logger.warning(f"表头不符合预期: {headers}")
            return []
        
        result_stocks = []
        rows = table.find_all('tr')[1:]  # 跳过表头
        for row_idx, row in enumerate(rows):
            cells = row.find_all(['td'])
            if cells and len(cells) >= len(expected_headers):
                stock_info = {}
                for i, header in enumerate(expected_headers):
                    if i < len(cells):
                        cell_content = cells[i]
                        # 如果单元格包含链接，提取链接和文本
                        link = cell_content.find('a')
                        if link:
                            stock_info[f'{header}_url'] = link.get('href', '')
                            stock_info[header] = link.get_text().strip()
                        else:
                            stock_info[header] = cell_content.get_text().strip()
                
                # 确保包含必要信息
                if '股票代码' in stock_info and '股票名称' in stock_info and '分析师个数' in stock_info:
                    # 尝试将分析师个数转换为整数
                    try:
                        analyst_count_str = str(stock_info['分析师个数']).strip()
                        if analyst_count_str.isdigit():
                            stock_info['分析师个数'] = int(analyst_count_str)
                        else:
                            # 如果不是纯数字，尝试从中提取数字
                            match = re.search(r'\d+', analyst_count_str)
                            if match:
                                stock_info['分析师个数'] = int(match.group())
                            else:
                                stock_info['分析师个数'] = 0
                    except ValueError:
                        stock_info['分析师个数'] = 0
                    
                    result_stocks.append(stock_info)
                    logger.info(f"提取股票: {stock_info['股票名称']} ({stock_info['股票代码']}) - 分析师个数: {stock_info['分析师个数']}")
            else:
                logger.warning(f"行数据不完整，跳过 (cells: {len(cells)}, expected: {len(expected_headers)})")
        
        # 按分析师个数降序排序并返回前limit个
        sorted_result_stocks = sorted(result_stocks, key=lambda x: x.get('分析师个数', 0), reverse=True)[:limit]

        logger.info(f"成功提取到前 {len(sorted_result_stocks)} 支分析师重点关注股票 from {html_file_path}")

        return sorted_result_stocks
        
    except Exception as e:
        logger.error(f"提取分析师重点关注股票失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def extract_analyst_recommendations(html_file_path):
    """
    从HTML文件中提取分析师的推荐股票数据
    :param html_file_path: HTML文件路径
    :return: 推荐股票数据列表
    """
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        logger.info(f"正在从 {html_file_path} 提取分析师推荐股票数据...")
        
        # 查找包含最新跟踪的表格（不再包含历史跟踪数据）
        recommendations = []
        
        # 查找最新跟踪表格
        current_tracking_heading = soup.find('h2', string=re.compile(r'最新跟踪成份股'))
        if current_tracking_heading:
            logger.info(f"找到最新跟踪标题: {current_tracking_heading.get_text().strip()}")
            current_table = current_tracking_heading.find_next('table')
            if current_table:
                headers = [th.get_text().strip() for th in current_table.find_all('th')]
                logger.info(f"最新跟踪表格头部: {headers}")
                rows = current_table.find_all('tr')[1:]  # 跳过表头
                
                for row_idx, row in enumerate(rows):
                    cells = row.find_all(['td'])
                    if cells and len(cells) >= len(headers):
                        stock_rec = {}
                        for i, header in enumerate(headers):
                            if i < len(cells):
                                cell_content = cells[i]
                                # 如果单元格包含链接，提取链接和文本
                                link = cell_content.find('a')
                                if link:
                                    stock_rec[f'{header}_url'] = link.get('href', '')
                                    stock_rec[header] = link.get_text().strip()
                                    logger.info(f"提取最新跟踪链接 - {header}: {link.get_text().strip()}, URL: {link.get('href', '')}")
                                else:
                                    stock_rec[header] = cell_content.get_text().strip()
                                    logger.info(f"提取最新跟踪文本 - {header}: {cell_content.get_text().strip()}")
                        
                        if '股票代码' in stock_rec and '股票名称' in stock_rec:
                            stock_rec['跟踪类型'] = '最新跟踪'
                            recommendations.append(stock_rec)
                            logger.info(f"添加最新跟踪股票: {stock_rec['股票名称']} ({stock_rec['股票代码']})")
                    else:
                        logger.warning(f"最新跟踪行数据不完整，跳过 (cells: {len(cells)}, headers: {len(headers)})")
        
        logger.info(f"总共提取到 {len(recommendations)} 条最新跟踪数据")
        return recommendations
        
    except Exception as e:
        logger.error(f"提取分析师推荐股票失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def get_analyst_data_summary(html_file_path):
    """
    获取分析师数据摘要信息
    :param html_file_path: HTML文件路径
    :return: 摘要信息字典
    """
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 查找摘要信息
        summary_div = soup.find('div', class_='analyst-summary') or soup.find('div', class_='summary')
        summary_info = {}
        
        if summary_div:
            summary_text = summary_div.get_text()
            # 使用正则表达式提取各种统计数据
            total_records_match = re.search(r'总记录数[:：]\s*(\d+)', summary_text)
            current_tracking_match = re.search(r'最新跟踪[:：]\s*(\d+)\s*条', summary_text)
            history_tracking_match = re.search(r'历史跟踪[:：]\s*(\d+)\s*条', summary_text)
            analyst_count_match = re.search(r'分析师数量[:：]\s*(\d+)\s*个', summary_text)
            
            summary_info['total_records'] = int(total_records_match.group(1)) if total_records_match else 0
            summary_info['current_tracking_count'] = int(current_tracking_match.group(1)) if current_tracking_match else 0
            summary_info['history_tracking_count'] = int(history_tracking_match.group(1)) if history_tracking_match else 0
            summary_info['analyst_count'] = int(analyst_count_match.group(1)) if analyst_count_match else 0
        else:
            # 如果没有找到摘要div，尝试从页面中提取基本统计信息
            tables = soup.find_all('table')
            total_records = 0
            for table in tables:
                rows = table.find_all('tr')
                total_records += len(rows) - 1  # 减去表头行
            summary_info['total_records'] = total_records
            summary_info['current_tracking_count'] = 0
            summary_info['history_tracking_count'] = 0
            summary_info['analyst_count'] = 0
        
        return summary_info
        
    except Exception as e:
        logger.error(f"获取分析师数据摘要失败: {str(e)}")
        return {}


def format_analyst_data_for_api(html_file_path, period="3个月排行"):
    """
    格式化分析师数据以供API使用
    :param html_file_path: HTML文件路径
    :param period: 时间段
    :return: 格式化的数据字典
    """
    if not html_file_path or not os.path.exists(html_file_path):
        logger.warning(f"分析师数据文件不存在: {html_file_path}")
        return None
    
    logger.info(f"正在格式化分析师数据，文件: {html_file_path}, 时间段: {period}")
    
    # 获取数据摘要
    summary = get_analyst_data_summary(html_file_path)
    
    # 获取分析师重点关注股票
    top_stocks = extract_analyst_top_stocks(html_file_path, limit=20)
    
    # 获取分析师推荐股票（仅最新跟踪，已移除历史跟踪）
    recommendations = extract_analyst_recommendations(html_file_path)
    # 读取原始HTML内容
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    result = {
        'success': True,
        'summary': summary,
        'top_stocks': top_stocks,
        'recommendations': recommendations,  # 这里现在只包含最新跟踪数据
        'current_holdings': [r for r in recommendations if r.get('跟踪类型') == '最新跟踪'],  # 明确分离最新跟踪数据
        'html_content': html_content,
        'file_path': html_file_path,
        'period': period,
        'last_updated': datetime.fromtimestamp(os.path.getmtime(html_file_path)).isoformat(),
        'extract_time': datetime.now().isoformat()
    }
    
    logger.info(f"格式化完成，top_stocks数量: {len(top_stocks)}, current_holdings数量: {len(result['current_holdings'])}")
    return result


def get_all_available_periods():
    """
    获取所有可用的时间段
    :return: 可用时间段列表
    """
    search_paths = [
        "/data/news/eastmoney/",
        "run/news/eastmoney/"
    ]
    
    periods = set()
    
    for search_path in search_paths:
        if os.path.exists(search_path):
            files = glob.glob(os.path.join(search_path, "*_东方财富分析师跟踪成份股_*.html"))
            for file_path in files:
                filename = os.path.basename(file_path)
                # 从文件名中提取时间段信息
                # 文件名格式: {category}_{period}_东方财富分析师跟踪成份股_{timestamp}.html
                parts = filename.split('_东方财富分析师跟踪成份股_')
                if parts:
                    prefix = parts[0]
                    period_parts = prefix.split('_')
                    if len(period_parts) >= 2:
                        # 重构时间段（跳过类别部分）
                        period = '_'.join(period_parts[1:])
                        # 将下划线替换回空格和冒号
                        period = period.replace('_', ' ').replace('_：', '：')
                        if period:
                            periods.add(period)
    
    # 添加默认时间段
    default_periods = [
        "3个月排行",
        "6个月排行", 
        "12个月排行",
        "最新总排行",
        "2025 年度排行"
    ]
    
    all_periods = list(periods) + [p for p in default_periods if p not in periods]
    
    return sorted(all_periods, key=lambda x: ('年度' in x, '个月' in x, x), reverse=True)


def get_formatted_analyst_data(period="3个月排行"):
    """
    获取格式化的分析师数据
    :param period: 时间段
    :return: 格式化的分析师数据
    """
    html_file_path = find_latest_analyst_files_by_period(period)
    if not html_file_path:
        logger.warning(f"未找到时间段 {period} 的分析师数据文件")
        return {
            'success': False,
            'message': f'未找到时间段 "{period}" 的分析师数据文件',
            'period': period
        }
    logger.info(f"找到分析师数据文件: {html_file_path} 对应时间段: {period}")
    return format_analyst_data_for_api(html_file_path, period)
