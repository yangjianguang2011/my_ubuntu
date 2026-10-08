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

产物
----
* `{类别}_{期间}_{日期}.xlsx` ——「最新跟踪」「历史跟踪」两个工作表（带自动筛选、冻结首行）
* `{类别}_{期间}_{日期}.html` ——「分析师重点关注股票」+「最新跟踪成份股」，表头可点击排序
  （历史跟踪只进 Excel，不进 HTML）
"""
from __future__ import annotations

import html as html_lib
import json
import os
import sys
from string import Template

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pandas as pd  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from config import setup_logger  # noqa: E402
from em_config import (  # noqa: E402
    DETAIL_TABLES,
    MANIFEST_NAME,
    TOP_STOCKS_LIMIT,
    category_display,
    period_display,
    report_stem,
)

logger = setup_logger("eastmoney_analyst")

# Excel/HTML 的首选列顺序（实际只输出数据里出现过的列，不产生空列）
PREFERRED_ORDER = [
    "分析师名称",
    "分析师排名",
    "股票代码",
    "股票名称",
    "股票链接",
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

# 仅供聚合/关联、不写进 HTML 表格的内部列
HTML_EXCLUDE_COLUMNS = ("股票类型", "类别", "期间", "分析师链接")

# 表头排序：按语义指定排序类型，避免前端靠正则猜列含义
NUMERIC_COLUMNS = {
    "分析师个数",
    "分析师排名",
    "平均成交价格",
    "最高成交价格",
    "最低成交价格",
    "最新价格",
    "成交价格(前复权)",
}
PERCENT_COLUMNS = {"阶段涨跌幅", "累计涨跌幅"}
# 该列不参与点击排序（链接列排序无意义）
NO_SORT_COLUMNS = {"股票链接"}

TOP_STOCK_HEADERS = [
    "分析师个数",
    "股票代码",
    "股票名称",
    "股票链接",
    "平均成交价格",
    "最高成交价格",
    "最低成交价格",
    "最新价格",
]

# ---------------------------------------------------------------- HTML 模板

_CSS = """
        body {
            font-family: Arial, "Microsoft YaHei", sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background-color: #fff;
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
        td.num, th.num {
            text-align: right;
        }
        th.sortable {
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
        }
        th.sortable:hover {
            background-color: #e6e6e6;
        }
        th.sortable::after {
            content: "\\21C5"; /* ⇅ 未排序 */
            color: #bbb;
            font-size: 11px;
            margin-left: 4px;
        }
        th[data-dir="asc"]::after {
            content: "\\25B2"; /* ▲ */
            color: #2196F3;
        }
        th[data-dir="desc"]::after {
            content: "\\25BC"; /* ▼ */
            color: #2196F3;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        tr:hover {
            background-color: #f0f7ff;
        }
        .stock-link {
            color: #1976D2;
            text-decoration: none;
        }
        .stock-link:hover {
            text-decoration: underline;
        }
        .no-data {
            text-align: center;
            padding: 20px;
            color: #666;
            font-style: italic;
        }
        .summary {
            background-color: #e8f5e8;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .summary h3 {
            margin-top: 0;
            color: #2e7d32;
        }
        .summary p {
            margin: 5px 0;
        }
        .source-link {
            text-align: center;
            margin-bottom: 20px;
        }
        .source-link a {
            color: #1976D2;
            text-decoration: none;
            font-size: 16px;
            font-weight: bold;
        }
        .source-link a:hover {
            text-decoration: underline;
        }
"""

# 点击表头排序：读取 th[data-sort] 指定的类型（num/pct/text），空值恒排最后。
_SORT_JS = """
(function () {
    function parseValue(td, type) {
        var text = (td.textContent || "").trim();
        if (!text || text === "--") return null;
        if (type === "num") {
            var n = parseFloat(text);
            return isNaN(n) ? null : n;
        }
        if (type === "pct") {
            var p = parseFloat(text.replace("%", ""));
            return isNaN(p) ? null : p;
        }
        return text.toLowerCase();
    }

    function compare(a, b, asc) {
        if (a === null && b === null) return 0;
        if (a === null) return 1;   // 空值无论升降序都排最后
        if (b === null) return -1;
        var r = (typeof a === "number" && typeof b === "number")
            ? a - b
            : String(a).localeCompare(String(b), "zh");
        return asc ? r : -r;
    }

    function makeSortable(table) {
        var headRow = table.tHead && table.tHead.rows[0];
        var body = table.tBodies[0];
        if (!headRow || !body) return;
        var ths = headRow.cells;
        for (var i = 0; i < ths.length; i++) {
            (function (index) {
                var th = ths[index];
                var type = th.getAttribute("data-sort");
                if (!type) return;
                th.classList.add("sortable");
                th.addEventListener("click", function () {
                    var asc = th.getAttribute("data-dir") !== "asc";
                    for (var j = 0; j < ths.length; j++) ths[j].removeAttribute("data-dir");
                    th.setAttribute("data-dir", asc ? "asc" : "desc");
                    var rows = Array.prototype.slice.call(body.rows);
                    rows.sort(function (r1, r2) {
                        return compare(
                            parseValue(r1.cells[index], type),
                            parseValue(r2.cells[index], type),
                            asc
                        );
                    });
                    for (var k = 0; k < rows.length; k++) body.appendChild(rows[k]);
                });
            })(i);
        }
    }

    var tables = document.querySelectorAll("table");
    for (var t = 0; t < tables.length; t++) makeSortable(tables[t]);
})();
"""

_PAGE_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>$title</title>
    <style>
$css
    </style>
</head>
<body>
    <div class="container">
        <h1>$title</h1>

        <div class="source-link">
            <a href="https://data.eastmoney.com/invest/invest/list.html" target="_blank">东方财富分析师数据源</a>
        </div>

        <div class="summary">
            <h3>数据摘要</h3>
            <p><strong>数据口径：</strong>$scope_line</p>
            <p>总记录数: $total_count（最新跟踪 $current_count 条 + 历史跟踪 $history_count 条）</p>
            <p>分析师数量: $analyst_count 个</p>
            <hr style="border:none;border-top:1px solid #e0e0e0;margin:12px 0;">
            <p><strong>统计方法</strong></p>
            <ul style="margin:6px 0 0 18px;padding:0;color:#555;font-size:13px;line-height:1.9;">
                <li><strong>数据来源</strong>：东方财富「分析师指数」列表页 → 逐个分析师详情页（Selenium 采集）</li>
                <li><strong>记录范围</strong>：详情页两张表的全部数据行 —— 最新跟踪成分股、历史跟踪成分股（历史跟踪仅写入 Excel）</li>
                <li><strong>总记录数</strong>：两张表的行数合计（每条 = 一位分析师 × 一只股票）</li>
                <li><strong>分析师数量</strong>：本次成功提取到成份股的分析师<b>去重</b>计数</li>
                <li><strong>重点关注股票</strong>：只统计「最新跟踪」表；按被多少位<b>不同</b>分析师持有排序（同一分析师对同一股票只计一次），取前 $limit 名</li>
                <li><strong>价格列</strong>：平均 / 最高 / 最低成交价取自各分析师记录的「成交价格(前复权)」；「最新价格」取该股票第一条非空值</li>
                <li><strong>列排序</strong>：点击表头切换升序 / 降序，空值恒排最后；「股票链接」列不参与排序</li>
            </ul>
        </div>

        <h2>分析师重点关注股票（按分析师持有数量排序，前 $limit 名）</h2>
$top_table
        <h2>最新跟踪成份股</h2>
$current_table
    </div>
    <script>
$js
    </script>
</body>
</html>
""")


# ---------------------------------------------------------------- 工具函数


def _esc(value) -> str:
    """把任意值转成 HTML 安全的字符串。"""
    return html_lib.escape(str(value), quote=True)


def _to_float(value):
    """把单元格文本转成 float；空、`--`、非数字一律返回 None。"""
    text = str(value).strip() if value is not None else ""
    if not text or text == "--":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _column_type(field: str) -> str:
    """列的排序类型：num / pct / text。"""
    if field in NUMERIC_COLUMNS:
        return "num"
    if field in PERCENT_COLUMNS:
        return "pct"
    return "text"


def _fieldnames(rows, exclude=()) -> list:
    """列名：首选顺序里出现过的 + 其余实际存在的键（按名称排序）。"""
    present = {k for row in rows for k in row} - set(exclude)
    ordered = [k for k in PREFERRED_ORDER if k in present]
    return ordered + sorted(present - set(ordered))


# ---------------------------------------------------------------- 解析详情页


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
                continue  # 空表占位行（colspan="N 暂无数据"）列数不符，跳过
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


def split_tracking_data(data):
    """按「股票类型」把数据拆成 (最新跟踪, 历史跟踪) 两组（不删列，列选择交给渲染层）。"""
    current, history = [], []
    for item in data:
        kind = item.get("股票类型")
        if kind == "最新跟踪":
            current.append(item)
        elif kind == "历史跟踪":
            history.append(item)
    return current, history


# ---------------------------------------------------------------- 重点关注股票


def compute_top_stocks(current_rows, limit=TOP_STOCKS_LIMIT):
    """聚合「最新跟踪」表 → 按被多少位不同分析师持有排序的前 N 只股票。

    规则（与旧实现一致）：
    * 「分析师个数」= 持有该股票的**去重**分析师数；
    * 平均 / 最高 / 最低成交价取自各记录的「成交价格(前复权)」，无有效价时记 0；
    * 「最新价格」取该股票第一条非空值；
    * 并列时按股票代码升序，保证结果可复现。
    """
    stats = {}
    for item in current_rows:
        code = str(item.get("股票代码") or "").strip()
        if not code:
            continue
        stat = stats.get(code)
        if stat is None:
            stat = stats[code] = {
                "analysts": set(),
                "stock_name": item.get("股票名称", ""),
                "stock_url": item.get("股票链接", ""),
                "trade_prices": [],
                "latest_price": "",
            }
        stat["analysts"].add(item.get("分析师名称", ""))

        price = _to_float(item.get("成交价格(前复权)"))
        if price is not None:
            stat["trade_prices"].append(price)

        if not stat["latest_price"]:
            latest = item.get("最新价格", "")
            if latest and latest != "--":
                stat["latest_price"] = latest

    top = []
    for code, stat in stats.items():
        prices = stat["trade_prices"]
        top.append({
            "分析师个数": len(stat["analysts"]),
            "股票代码": code,
            "股票名称": stat["stock_name"],
            "股票链接": stat["stock_url"],
            "平均成交价格": round(sum(prices) / len(prices), 2) if prices else 0,
            "最高成交价格": max(prices) if prices else 0,
            "最低成交价格": min(prices) if prices else 0,
            "最新价格": stat["latest_price"],
        })

    top.sort(key=lambda s: (-s["分析师个数"], s["股票代码"]))
    return top[:limit]


# ---------------------------------------------------------------- HTML 渲染


def _render_table(headers, rows) -> str:
    """把表头与行渲染成可排序的 HTML 表格（表头带 data-sort，空值在 JS 里排最后）。"""
    parts = ["<table>\n<thead>\n<tr>\n"]
    for header in headers:
        if header in NO_SORT_COLUMNS:
            parts.append(f"<th>{_esc(header)}</th>\n")
            continue
        col_type = _column_type(header)
        cls = f' class="sortable{" num" if col_type != "text" else ""}"'
        parts.append(f'<th{cls} data-sort="{col_type}">{_esc(header)}</th>\n')
    parts.append("</tr>\n</thead>\n<tbody>\n")

    for row in rows:
        parts.append("<tr>\n")
        for header in headers:
            value = row.get(header, "")
            cls = ' class="num"' if _column_type(header) != "text" else ""
            if header == "股票链接" and value:
                parts.append(
                    f'<td><a href="{_esc(value)}" target="_blank" class="stock-link">'
                    f"{_esc(value)}</a></td>\n"
                )
            else:
                parts.append(f"<td{cls}>{_esc(value)}</td>\n")
        parts.append("</tr>\n")
    parts.append("</tbody>\n</table>\n")
    return "".join(parts)


def save_data_to_html(current_rows, history_rows, filename_prefix, output_dir, meta=None):
    """生成 HTML 报告：「分析师重点关注股票」+「最新跟踪成份股」。

    历史跟踪不写入 HTML（数据仍在 Excel 的「历史跟踪」工作表里）。
    :param meta: 可选元信息（category/period/scraped_at），用于在「数据摘要」里说明口径。
    """
    if not current_rows and not history_rows:
        logger.warning("没有数据可保存")
        return None

    meta = meta or {}
    os.makedirs(output_dir, exist_ok=True)

    top_table = _render_table(TOP_STOCK_HEADERS, compute_top_stocks(current_rows))
    current_headers = [
        f for f in _fieldnames(current_rows) if f not in HTML_EXCLUDE_COLUMNS
    ]
    current_table = (
        _render_table(current_headers, current_rows)
        if current_rows
        else '<div class="no-data">暂无最新跟踪成份股数据</div>'
    )

    title = f"{filename_prefix} - 分析师跟踪成份股数据"
    scope_line = " · ".join(
        f"{label} {meta.get(key)}"
        for label, key in (("类别", "category"), ("期间", "period"), ("采集时间", "scraped_at"))
        if meta.get(key)
    ) or "—"

    html_content = _PAGE_TEMPLATE.safe_substitute(
        title=_esc(title),
        css=_CSS,
        js=_SORT_JS,
        scope_line=_esc(scope_line),
        total_count=len(current_rows) + len(history_rows),
        current_count=len(current_rows),
        history_count=len(history_rows),
        analyst_count=len(
            {row.get("分析师名称", "") for row in current_rows + history_rows}
        ),
        limit=TOP_STOCKS_LIMIT,
        top_table=top_table,
        current_table=current_table,
    )

    html_file = os.path.join(output_dir, f"{filename_prefix}.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info(f"HTML 已保存：{html_file}")
    return html_file


# ---------------------------------------------------------------- Excel 渲染


def _excel_row(item, fieldnames) -> dict:
    """构造一行 Excel 数据，处理「股票代码补零」。"""
    row = {}
    for field in fieldnames:
        value = item.get(field, "")
        if field == "股票代码" and value:
            code = str(value)
            row[field] = code.zfill(6) if len(code) < 6 else code
        else:
            row[field] = value
    return row


def save_data_to_excel(current_rows, history_rows, filename_prefix, output_dir):
    """写 Excel（「最新跟踪」/「历史跟踪」两个工作表，带自动筛选与冻结首行）。"""
    if not current_rows and not history_rows:
        logger.warning("没有数据可保存")
        return None
    os.makedirs(output_dir, exist_ok=True)

    fieldnames = _fieldnames(current_rows + history_rows, exclude=("股票类型",))
    excel_file = os.path.join(output_dir, f"{filename_prefix}.xlsx")

    with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
        for sheet, rows in (("最新跟踪", current_rows), ("历史跟踪", history_rows)):
            if not rows:
                continue
            pd.DataFrame(
                [_excel_row(r, fieldnames) for r in rows], columns=fieldnames
            ).to_excel(writer, sheet_name=sheet, index=False)
            worksheet = writer.sheets[sheet]
            worksheet.auto_filter.ref = worksheet.dimensions  # 表头自动筛选
            worksheet.freeze_panes = "A2"  # 冻结首行
            logger.info(f"「{sheet}」已写入：{len(rows)} 条")

    logger.info(f"Excel 已保存：{excel_file}")
    return excel_file


# ---------------------------------------------------------------- 入口


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

    current_rows, history_rows = split_tracking_data(all_tracking_data)
    stem = report_stem(category, period)
    meta = {
        "category": cat_label,
        "period": per_label,
        "scraped_at": manifest.get("scraped_at", ""),
    }
    excel_file = save_data_to_excel(current_rows, history_rows, stem, output_dir)
    html_file = save_data_to_html(current_rows, history_rows, stem, output_dir, meta=meta)

    analyst_count = len({item["分析师名称"] for item in all_tracking_data})
    logger.info(
        f"报告完成：{analyst_count} 位分析师 / {len(all_tracking_data)} 条成份股记录"
        f"（类别 {cat_label}，期间 {per_label}）"
    )
    logger.info(f"  Excel: {excel_file}")
    logger.info(f"  HTML : {html_file}")
    return all_tracking_data
