# -*- coding: utf-8 -*-
"""东方财富分析师 —— 后处理层：读 manifest → 解析详情页 → 生成 HTML/Excel 报告。

数据来源与关联方式
------------------
采集阶段（`em_scraper`）会在处理目录里写 `manifest.json`，记录本次的类别/期间与
分析师清单（含各自详情页文件路径）。本模块**直接读 manifest**，不再靠解析 HTML 文件名
（旧实现用 `split('_')` 反解 rank/name，命名规则一变或姓名含下划线就会静默错位）。

详情页结构（稳定 id，见 `em_config` docstring）::

    <div class="content" id="news_table">    <table class="table-model">…</table></div>
    <div class="content" id="history_table"> <table class="table-model">…</table></div>
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pandas as pd  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from config import setup_logger  # noqa: E402
from em_config import (  # noqa: E402
    DETAIL_TABLES,
    MANIFEST_NAME,
    category_display,
    period_display,
    report_stem,
)

logger = setup_logger("eastmoney_analyst")

# Excel 报告的首选列顺序（实际只输出数据里出现过的列，不产生空列）
PREFERRED_ORDER = [
    "分析师名称",
    "分析师排名",
    "股票代码",
    "股票名称",
    "股票链接",
    "股票类型",
    "调入日期",
    "调出日期",
    "最新评级日期",
    "调入时评级名称",
    "当前评级名称",
    "调出原因",
    "成交价格(前复权)",
    "最新价格",
    "阶段涨跌幅",
    "累计涨跌幅",
]


def load_manifest(processed_dir):
    """读取采集阶段写下的 manifest.json。"""
    path = os.path.join(processed_dir, MANIFEST_NAME)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"未找到 {MANIFEST_NAME}（{processed_dir}）——请先运行采集阶段"
        )
    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)
    if not manifest.get("analysts"):
        raise RuntimeError(f"{MANIFEST_NAME} 里没有分析师记录：{path}")
    return manifest


def _fix_stock_url(cell) -> str:
    """取单元格内 <a> 的 href 并补全为绝对地址（空则返回空串）。"""
    a = cell.find("a")
    if not a or not a.get("href"):
        return ""
    href = a["href"]
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return "https://data.eastmoney.com" + href
    return href


def extract_analyst_tracking_stocks(analyst_name, html_file_path):
    """从分析师详情页 HTML 提取「最新跟踪 / 历史跟踪」两张成份股表。

    按**表头中文名**映射字段（不依赖列下标），两张表列数不同（10 / 9 列）也不受影响。
    """
    if not (html_file_path and os.path.exists(html_file_path)):
        raise FileNotFoundError(f"详情页 HTML 不存在：{html_file_path}")

    with open(html_file_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    tracking_data = []
    for table_id, table_type in DETAIL_TABLES:
        holder = soup.find("div", id=table_id)
        if holder is None:
            logger.warning(f"{analyst_name}：详情页缺少 #{table_id}")
            continue
        table = holder.find("table", class_="table-model")
        if table is None:
            logger.warning(f"{analyst_name}：#{table_id} 内没有 table-model")
            continue

        rows = table.find_all("tr")
        if not rows:
            continue
        headers = [c.get_text().strip() for c in rows[0].find_all(["th", "td"])]

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) != len(headers):
                continue
            info = {"分析师名称": analyst_name, "股票类型": table_type}
            for header, cell in zip(headers, cells):
                text = cell.get_text().strip()
                if header == "序号":
                    continue
                if header in ("股票代码", "股票名称"):
                    info[header] = text
                    if not info.get("股票链接"):
                        info["股票链接"] = _fix_stock_url(cell)
                elif header == "相关链接":
                    continue  # 股吧/资金流等，不是行情链接
                else:
                    info[header] = text
            if info.get("股票代码") or info.get("股票名称"):
                tracking_data.append(info)

    logger.info(f"{analyst_name}：提取到 {len(tracking_data)} 条跟踪成份股")
    return tracking_data


def save_data_to_html(data, filename_prefix, output_dir, meta=None):
    """保存数据到HTML文件，包含最新跟踪和历史跟踪两个表格，以及分析师重点关注股票。

    :param meta: 可选元信息（category/period/scraped_at），用于在「数据摘要」里说明口径。
    """
    try:
        meta = meta or {}
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        if not data:
            logger.warning("没有数据可保存")
            return None

        # 按股票类型分组，并剔除仅中间文件才需要的列
        current_tracking_data, history_tracking_data = split_tracking_data(
            data, ("股票类型", "类别", "期间", "分析师链接", "数据来源文件")
        )

        # 统计最新跟踪成份股，按股票代码分组
        stock_stats = {}
        for item in current_tracking_data:
            stock_code = item.get("股票代码", "")
            if stock_code:
                if stock_code not in stock_stats:
                    stock_stats[stock_code] = {
                        "analyst_count": 0,
                        "stock_name": item.get("股票名称", ""),
                        "stock_url": item.get("股票链接", ""),
                        "trade_prices": [],
                        "latest_price": "",  # 只取第一个最新价格
                        "analysts": [],
                    }

                # 更新分析师数量和列表
                analyst_name = item.get("分析师名称", "")
                if analyst_name not in stock_stats[stock_code]["analysts"]:
                    stock_stats[stock_code]["analysts"].append(analyst_name)
                    stock_stats[stock_code]["analyst_count"] += 1

                # 收集成交价格
                trade_price_str = item.get("成交价格(前复权)", "")
                if (
                    trade_price_str
                    and trade_price_str != ""
                    and trade_price_str != "--"
                ):
                    try:
                        trade_price = float(trade_price_str)
                        stock_stats[stock_code]["trade_prices"].append(trade_price)
                    except ValueError:
                        pass  # 如果无法转换为数字则跳过

                # 只取第一个最新价格，如果还没有设置的话
                latest_price_str = item.get("最新价格", "")
                if (
                    latest_price_str
                    and latest_price_str != ""
                    and latest_price_str != "--"
                    and not stock_stats[stock_code]["latest_price"]
                ):
                    stock_stats[stock_code]["latest_price"] = latest_price_str

        # 计算统计信息并按分析师数量排序
        stock_stats_list = []
        for stock_code, stats in stock_stats.items():
            if stats["trade_prices"]:
                avg_trade_price = sum(stats["trade_prices"]) / len(
                    stats["trade_prices"]
                )
                max_trade_price = max(stats["trade_prices"])
                min_trade_price = min(stats["trade_prices"])
            else:
                avg_trade_price = 0
                max_trade_price = 0
                min_trade_price = 0

            # 使用第一个最新价格
            latest_price = stats["latest_price"] if stats["latest_price"] else ""

            stock_info = {
                "分析师个数": stats["analyst_count"],
                "股票代码": stock_code,
                "股票名称": stats["stock_name"],
                "股票链接": stats["stock_url"],
                "平均成交价格": (
                    round(avg_trade_price, 2) if avg_trade_price != 0 else 0
                ),
                "最高成交价格": max_trade_price,
                "最低成交价格": min_trade_price,
                "最新价格": latest_price,
            }
            stock_stats_list.append(stock_info)

        # 按分析师个数从大到小排序，取前20名
        stock_stats_list.sort(key=lambda x: x["分析师个数"], reverse=True)
        top_20_stocks = stock_stats_list[:20]

        # 生成时间戳
        html_file = os.path.join(output_dir, f"{filename_prefix}.html")

        # 数据口径说明（用于「数据摘要」）
        scope_line = " · ".join(
            f"{label} {meta.get(key)}"
            for label, key in (("类别", "category"), ("期间", "period"), ("采集时间", "scraped_at"))
            if meta.get(key)
        ) or "—"

        # 生成HTML内容
        html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #3;
            text-align: center;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #5;
            margin-top: 30px;
            border-left: 4px solid #2196F3;
            padding-left: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 14px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
            word-wrap: break-word;
        }}
        th {{
            background-color: #f2f2f2;
            font-weight: bold;
            position: sticky;
            top: 0;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        tr:hover {{
            background-color: #f5f5;
        }}
        .stock-link {{
            color: #1976D2;
            text-decoration: none;
        }}
        .stock-link:hover {{
            text-decoration: underline;
        }}
        .no-data {{
            text-align: center;
            padding: 20px;
            color: #66;
            font-style: italic;
        }}
        .summary {{
            background-color: #e8f5e8;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .summary h3 {{
            margin-top: 0;
            color: #2e7d32;
        }}
        .summary p {{
            margin: 5px 0;
        }}
        .data-link {{
            text-align: center;
            margin-bottom: 20px;
        }}
        .data-link a {{
            color: #1976D2;
            text-decoration: none;
            font-size: 16px;
            font-weight: bold;
        }}
        .data-link a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>

        <div class="data-source-link" style="text-align: center; margin-bottom: 20px;">
            <a href="https://data.eastmoney.com/invest/invest/list.html" target="_blank" style="color: #1976D2; text-decoration: none; font-size: 16px; font-weight: bold;">东方财富分析师数据源</a>
        </div>

        <div class="summary">
            <h3>数据摘要</h3>
            <p><strong>数据口径：</strong>{scope_line}</p>
            <p>总记录数: {total_count}（最新跟踪 {current_count} 条 + 历史跟踪 {history_count} 条）</p>
            <p>分析师数量: {analyst_count} 个</p>
            <hr style="border:none;border-top:1px solid #e0e0e0;margin:12px 0;">
            <p><strong>统计方法</strong></p>
            <ul style="margin:6px 0 0 18px;padding:0;color:#555;font-size:13px;line-height:1.9;">
                <li><strong>数据来源</strong>：东方财富「分析师指数」列表页 → 逐个分析师详情页（Selenium 采集）</li>
                <li><strong>记录范围</strong>：详情页两张表的全部数据行 —— 最新跟踪成分股、历史跟踪成分股</li>
                <li><strong>总记录数</strong>：两张表的行数合计（每条 = 一位分析师 × 一只股票）</li>
                <li><strong>分析师数量</strong>：本次成功提取到成份股的分析师<b>去重</b>计数</li>
                <li><strong>重点关注股票</strong>：只统计「最新跟踪」表；按被多少位<b>不同</b>分析师持有排序（同一分析师对同一股票只计一次），取前 20 名</li>
                <li><strong>价格列</strong>：平均 / 最高 / 最低成交价取自各分析师记录的「成交价格(前复权)」；「最新价格」取该股票第一条非空值</li>
            </ul>
        </div>

        <h2>分析师重点关注股票（按分析师持有数量排序，前20名）</h2>
        <table>
            <thead>
                <tr>
                    <th>分析师个数</th>
                    <th>股票代码</th>
                    <th>股票名称</th>
                    <th>股票链接</th>
                    <th>平均成交价格</th>
                    <th>最高成交价格</th>
                    <th>最低成交价格</th>
                    <th>最新价格</th>
                </tr>
            </thead>
            <tbody>
""".format(
            title=f"{filename_prefix} - 分析师跟踪成份股数据",
            scope_line=scope_line,
            total_count=len(data),
            current_count=len(current_tracking_data),
            history_count=len(history_tracking_data),
            analyst_count=len(set([item["分析师名称"] for item in data])),
        )

        # 添加分析师重点关注股票表格数据
        for stock in top_20_stocks:
            html_content += f"""                <tr>
                    <td>{stock['分析师个数']}</td>
                    <td>{stock['股票代码']}</td>
                    <td>{stock['股票名称']}</td>
                    <td><a href="{stock['股票链接']}" target="_blank" class="stock-link">{stock['股票链接']}</a></td>
                    <td>{stock['平均成交价格']}</td>
                    <td>{stock['最高成交价格']}</td>
                    <td>{stock['最低成交价格']}</td>
                    <td>{stock['最新价格']}</td>
                </tr>
"""

        html_content += """            </tbody>
        </table>
"""

        # 添加最新跟踪数据表格
        if current_tracking_data:
            html_content += """
        <h2>最新跟踪成份股</h2>
        <table>
            <thead>
                <tr>
"""
            # 获取列名并生成表头
            if current_tracking_data:
                fieldnames = sorted(
                    set().union(*(d.keys() for d in current_tracking_data))
                )
                for field in fieldnames:
                    html_content += f"                    <th>{field}</th>\n"

            html_content += """                </tr>
            </thead>
            <tbody>
"""
            # 添加数据行
            for item in current_tracking_data:
                html_content += "                <tr>\n"
                for field in fieldnames:
                    value = item.get(field, "")
                    if field == "股票链接" and value:
                        html_content += f'                    <td><a href="{value}" target="_blank" class="stock-link">{value}</a></td>\n'
                    elif field == "数据来源文件" and value:
                        html_content += f'                    <td><a href="{value}" target="_blank" class="stock-link">{os.path.basename(value)}</a></td>\n'
                    else:
                        html_content += f"                    <td>{value}</td>\n"
                html_content += "                </tr>\n"

            html_content += """            </tbody>
        </table>
"""
        else:
            html_content += """
        <h2>最新跟踪成份股</h2>
        <div class="no-data">暂无最新跟踪成份股数据</div>
"""

        # 添加历史跟踪数据表格
        if history_tracking_data:
            html_content += """
        <h2>历史跟踪成份股</h2>
        <table>
            <thead>
                <tr>
"""
            # 获取列名并生成表头
            if history_tracking_data:
                fieldnames = sorted(
                    set().union(*(d.keys() for d in history_tracking_data))
                )
                for field in fieldnames:
                    html_content += f"                    <th>{field}</th>\n"

            html_content += """                </tr>
            </thead>
            <tbody>
"""
            # 添加数据行
            for item in history_tracking_data:
                html_content += "                <tr>\n"
                for field in fieldnames:
                    value = item.get(field, "")
                    if field == "股票链接" and value:
                        html_content += f'                    <td><a href="{value}" target="_blank" class="stock-link">{value}</a></td>\n'
                    elif field == "数据来源文件" and value:
                        html_content += f'                    <td><a href="{value}" target="_blank" class="stock-link">{os.path.basename(value)}</a></td>\n'
                    else:
                        html_content += f"                    <td>{value}</td>\n"
                html_content += "                </tr>\n"

            html_content += """            </tbody>
        </table>
"""
        else:
            html_content += """
        <h2>历史跟踪成份股</h2>
        <div class="no-data">暂无历史跟踪成份股数据</div>
"""

        html_content += """
    </div>
</body>
</html>
"""

        # 写入HTML文件
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"HTML文件已成功保存到: {html_file}")
        return html_file

    except Exception as e:
        logger.error(f"保存HTML数据时出错: {str(e)}")
        return None


def split_tracking_data(data, exclude_keys=("股票类型",)):
    """按「股票类型」把数据分成 (最新跟踪, 历史跟踪) 两组，并剔除指定列。"""
    current, history = [], []
    for item in data:
        filtered = {k: v for k, v in item.items() if k not in exclude_keys}
        if item.get("股票类型") == "最新跟踪":
            current.append(filtered)
        elif item.get("股票类型") == "历史跟踪":
            history.append(filtered)
    return current, history


def _fieldnames(data):
    """Excel 列名：首选顺序里出现过的 + 其余实际存在的键（不含「股票类型」，它拆成两个表）。"""
    present = {k for item in data for k in item} - {"股票类型"}
    ordered = [k for k in PREFERRED_ORDER if k in present]
    return ordered + sorted(present - set(ordered))


def save_data_to_excel(data, filename_prefix, output_dir):
    """保存到 Excel（「最新跟踪」/「历史跟踪」两个工作表）。"""
    if not data:
        logger.warning("没有数据可保存")
        return None
    os.makedirs(output_dir, exist_ok=True)

    current, history = split_tracking_data(data)
    fieldnames = _fieldnames(data)
    excel_file = os.path.join(output_dir, f"{filename_prefix}.xlsx")

    with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
        if current:
            pd.DataFrame([create_csv_row(r, fieldnames) for r in current],
                         columns=fieldnames).to_excel(writer, sheet_name="最新跟踪", index=False)
            logger.info(f"「最新跟踪」已写入：{len(current)} 条")
        if history:
            pd.DataFrame([create_csv_row(r, fieldnames) for r in history],
                         columns=fieldnames).to_excel(writer, sheet_name="历史跟踪", index=False)
            logger.info(f"「历史跟踪」已写入：{len(history)} 条")

    logger.info(f"Excel 已保存：{excel_file}")
    return excel_file


def create_csv_row(item, fieldnames):
    """构造一行数据，处理「股票代码补零」与「数据来源 URL 修正」。"""
    row = {}
    for field in fieldnames:
        value = item.get(field, "")
        if field == "股票代码" and value:
            code = str(value)
            row[field] = code.zfill(6) if len(code) < 6 else code
        elif field == "数据来源" and value:
            match = re.search(r"(data\.eastmoney\.com.*)", str(value))
            row[field] = "https://" + match.group(1) if match else value
        else:
            row[field] = value
    return row


def extract_and_save_analyst_data(processed_dir, output_dir):
    """读 manifest → 逐个详情页提取 → 生成 HTML/Excel 报告。"""
    manifest = load_manifest(processed_dir)
    analysts = manifest["analysts"]
    category, period = manifest["category"], manifest["period"]
    cat_label, per_label = category_display(category), period_display(period)
    logger.info(
        f"===== 报告生成开始 - 类别: {cat_label}, 期间: {per_label}, 分析师: {len(analysts)} ====="
    )

    all_tracking_data = []
    for i, analyst in enumerate(analysts, 1):
        html_file = analyst.get("html_file")
        if not (html_file and os.path.exists(html_file)):
            logger.warning(f"[{i}/{len(analysts)}] {analyst.get('name')}：无详情页文件，跳过")
            continue
        try:
            tracking = extract_analyst_tracking_stocks(analyst["name"], html_file)
        except Exception as e:  # noqa: BLE001
            logger.error(f"[{i}/{len(analysts)}] {analyst.get('name')} 提取失败：{e}")
            continue

        for stock in tracking:
            stock["分析师名称"] = analyst["name"]
            stock["分析师排名"] = analyst.get("rank", "")
            stock["分析师链接"] = analyst.get("url", "")
            stock["类别"] = category
            stock["期间"] = period
        all_tracking_data.extend(tracking)

    if not all_tracking_data:
        raise RuntimeError(f"未提取到任何跟踪成份股数据（类别 {cat_label} / 期间 {per_label}）")

    stem = report_stem(category, period)
    meta = {
        "category": cat_label,
        "period": per_label,
        "scraped_at": manifest.get("scraped_at", ""),
    }
    excel_file = save_data_to_excel(all_tracking_data, stem, output_dir)
    html_file = save_data_to_html(all_tracking_data, stem, output_dir, meta=meta)

    analyst_count = len({item["分析师名称"] for item in all_tracking_data})
    logger.info(
        f"报告完成：{analyst_count} 位分析师 / {len(all_tracking_data)} 条成份股记录"
        f"（类别 {cat_label}，期间 {per_label}）"
    )
    logger.info(f"  Excel: {excel_file}")
    logger.info(f"  HTML : {html_file}")
    return all_tracking_data
