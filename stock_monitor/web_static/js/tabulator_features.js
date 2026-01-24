// 通用Tabulator表格功能实现
// 用于股票监控系统中的所有表格排序和展示功能

// 通用日期排序函数
function dateSorter(a, b, aRow, bRow, column, dir, sorterParams) {
    // 自定义日期排序函数，处理可能的日期格式问题
    if (!a || a === '' || a === '--') return 1; // 将空值移到最后
    if (!b || b === '' || b === '--') return -1; // 将空值移到最后
    
    // 尝试解析日期字符串
    let dateA, dateB;
    try {
        // 尝试多种日期格式
        if (a.includes(' ')) {
            // 如果包含时间部分，只取日期部分
            dateA = new Date(a.split(' ')[0]);
        } else {
            dateA = new Date(a);
        }
        
        if (b.includes(' ')) {
            // 如果包含时间部分，只取日期部分
            dateB = new Date(b.split(' ')[0]);
        } else {
            dateB = new Date(b);
        }
    } catch (e) {
        console.warn('日期解析错误:', a, b);
        return 0;
    }
    
    // 比较日期
    if (dateA < dateB) return -1;
    if (dateA > dateB) return 1;
    return 0;
}

// Tabulator表格配置和初始化函数
function initTabulatorTable(containerId, data, columns, options = {}) {
    // 默认选项
    const defaultOptions = {
        height: "100%",
        layout: "fitColumns",
        pagination: true,
        paginationSize: 25,
        paginationSizeSelector: [10, 25, 50, 100],
        movableColumns: true,
        resizableRows: true,
        columnMinWidth: 80,
        tooltips: true,
        columnHeaderVertAlign: "bottom",
        ...options
    };

    // 创建Tabulator实例
    const table = new Tabulator(`#${containerId}`, {
        data: data,
        columns: columns,
        ...defaultOptions
    });

    return table;
}

// 通用表格数据加载和初始化函数
function loadAndInitTable(apiEndpoint, containerId, columns, options = {}) {
    // 显示加载状态
    document.getElementById(containerId).innerHTML = '<div class="loading">加载中...</div>';

    fetch(apiEndpoint)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 清空加载状态
                document.getElementById(containerId).innerHTML = '';
                
                // 创建表格容器
                const tableContainer = document.createElement('div');
                tableContainer.id = `${containerId}-tabulator`;
                tableContainer.style.height = 'calc(100vh - 200px)'; // 自适应高度
                document.getElementById(containerId).appendChild(tableContainer);

                // 初始化Tabulator表格
                const table = initTabulatorTable(`${containerId}-tabulator`, data.data, columns, options);
                
                // 返回表格实例以供后续操作
                return table;
            } else {
                document.getElementById(containerId).innerHTML = `<div class="error">加载数据失败: ${data.message}</div>`;
            }
        })
        .catch(error => {
            document.getElementById(containerId).innerHTML = `<div class="error">加载数据失败: ${error.message}</div>`;
        });
}

// 为最近更新的股票数据创建Tabulator表格
function initRecentlyUpdatedStocksTable(data) {
    const container = document.getElementById('analyst-data-container');
    
    // 创建数据摘要
    let summaryHtml = `
        <div class="analyst-summary">
            <h3>最近更新股票数据摘要</h3>
            <p>符合条件的股票总数: ${data.length}</p>
        </div>
    `;
    container.innerHTML = summaryHtml;

    // 创建表格容器
    const tableContainer = document.createElement('div');
    tableContainer.id = 'recently-updated-stocks-table';
    tableContainer.style.height = 'calc(100vh - 250px)';
    container.appendChild(tableContainer);

    // 定义列
    const columns = [
        {title: "分析师名称", field: "analyst_name", width: 120, headerSort: true},
        {title: "分析师行业", field: "analyst_industry", width: 120, headerSort: true},
        {title: "股票代码", field: "股票代码", width: 100, headerSort: true},
        {title: "股票名称", field: "股票名称", width: 120, headerSort: true},
        {title: "调入日期", field: "调入日期", width: 100, headerSort: true, sorter: dateSorter},
        {title: "最新评级日期", field: "最新评级日期", width: 120, headerSort: true, sorter: dateSorter},
        {title: "成交价格(前复权)", field: "成交价格(前复权)", width: 140, headerSort: true, sorter: "number"},
        {title: "最新价格", field: "最新价格", width: 100, headerSort: true, sorter: "number"},
        {title: "阶段涨跌幅", field: "阶段涨跌幅", width: 120, headerSort: true, sorter: "number", formatter: "money", formatterParams: {precision: 2, symbol: "%"}},
        {title: "当前评级名称", field: "当前评级名称", width: 120, headerSort: true},
        {title: "分析师3个月收益率", field: "analyst_period_3m_return", width: 160, headerSort: true, sorter: "number", formatter: "money", formatterParams: {precision: 2, symbol: "%"}},
        {title: "分析师6个月收益率", field: "analyst_period_6m_return", width: 160, headerSort: true, sorter: "number", formatter: "money", formatterParams: {precision: 2, symbol: "%"}},
        {title: "分析师12个月收益率", field: "analyst_period_12m_return", width: 170, headerSort: true, sorter: "number", formatter: "money", formatterParams: {precision: 2, symbol: "%"}}
    ];

    // 初始化表格
    const table = initTabulatorTable('recently-updated-stocks-table', data, columns, {
        layout: "fitDataStretch",
        pagination: true,
        paginationSize: 25,
        paginationSizeSelector: [10, 25, 50, 100, true],
        movableColumns: true,
        columnHeaderVertAlign: "bottom",
        initialSort: [
            {column: "最新评级日期", dir: "desc"} // 默认按最新评级日期降序排列
        ]
    });

    return table;
}

// 为分析师重点关注股票创建Tabulator表格
function initAnalystFocusStocksTable(data) {
    const container = document.getElementById('analyst-data-container');
    
    // 创建表格容器
    const tableContainer = document.createElement('div');
    tableContainer.id = 'analyst-focus-stocks-table';
    tableContainer.style.height = 'calc(100vh - 20px)';
    container.appendChild(tableContainer);

    // 定义列
    const columns = [
        {title: "分析师关注数量", field: "analyst_count", width: 140, headerSort: true, sorter: "number"},
        {title: "股票代码", field: "stock_code", width: 100, headerSort: true},
        {title: "股票名称", field: "stock_name", width: 120, headerSort: true},
        {title: "平均成交价格", field: "avg_price", width: 140, headerSort: true, sorter: "number", formatter: "money", formatterParams: {precision: 2, symbol: "¥"}},
        {title: "最高成交价格", field: "max_price", width: 140, headerSort: true, sorter: "number", formatter: "money", formatterParams: {precision: 2, symbol: "¥"}},
        {title: "最低成交价格", field: "min_price", width: 140, headerSort: true, sorter: "number", formatter: "money", formatterParams: {precision: 2, symbol: "¥"}},
        {title: "最新价格", field: "latest_price", width: 100, headerSort: true, sorter: "number", formatter: "money", formatterParams: {precision: 2, symbol: "¥"}}
    ];

    // 初始化表格
    const table = initTabulatorTable('analyst-focus-stocks-table', data, columns, {
        layout: "fitDataStretch",
        pagination: true,
        paginationSize: 25,
        paginationSizeSelector: [10, 25, 50, 100, true],
        movableColumns: true,
        columnHeaderVertAlign: "bottom",
        initialSort: [
            {column: "analyst_count", dir: "desc"} // 默认按分析师关注数量降序排列
        ]
    });

    return table;
}

// 为最新跟踪成份股创建Tabulator表格
function initLatestTrackingTable(data) {
    const container = document.getElementById('analyst-data-container');
    
    // 创建表格容器
    const tableContainer = document.createElement('div');
    tableContainer.id = 'latest-tracking-table';
    tableContainer.style.height = 'calc(100vh - 200px)';
    container.appendChild(tableContainer);

    // 定义列
    const columns = [
        {title: "分析师名称", field: "analyst_name", width: 120, headerSort: true},
        {title: "分析师排名", field: "analyst_rank", width: 120, headerSort: true, sorter: "number"},
        {title: "股票代码", field: "股票代码", width: 100, headerSort: true},
        {title: "股票名称", field: "股票名称", width: 120, headerSort: true},
        {title: "调入日期", field: "调入日期", width: 100, headerSort: true, sorter: dateSorter},
        {title: "成交价格(前复权)", field: "成交价格(前复权)", width: 140, headerSort: true, sorter: "number"},
        {title: "最新价格", field: "最新价格", width: 100, headerSort: true, sorter: "number"},
        {title: "阶段涨跌幅", field: "阶段涨跌幅", width: 120, headerSort: true, sorter: "number", formatter: "money", formatterParams: {precision: 2, symbol: "%"}},
        {title: "当前评级名称", field: "当前评级名称", width: 120, headerSort: true}
    ];

    // 初始化表格
    const table = initTabulatorTable('latest-tracking-table', data, columns, {
        layout: "fitDataStretch",
        pagination: true,
        paginationSize: 25,
        paginationSizeSelector: [10, 25, 50, 100, true],
        movableColumns: true,
        columnHeaderVertAlign: "bottom",
        initialSort: [
            {column: "调入日期", dir: "desc"} // 默认按调入日期降序排列
        ]
    });

    return table;
}

// 为行业数据创建Tabulator表格
function initIndustryTable(data, tableType = 'gainers') {
    const container = document.getElementById('industry-data-container');
    
    // 创建表格容器
    const tableContainer = document.createElement('div');
    tableContainer.id = `industry-${tableType}-table`;
    tableContainer.style.height = 'calc(100vh - 200px)';
    container.appendChild(tableContainer);

    // 根据表格类型定义列
    let title, initialSort;
    if (tableType === 'gainers') {
        title = '涨幅行业';
        initialSort = {column: "change_pct", dir: "desc"};
    } else {
        title = '跌幅行业';
        initialSort = {column: "change_pct", dir: "asc"};
    }

    const columns = [
        {title: "排名", field: "rank", width: 60, headerSort: true, formatter: "rownum"},
        {title: "行业名称", field: "industry_name", width: 150, headerSort: true},
        {title: "涨跌幅", field: "change_pct", width: 100, headerSort: true, sorter: "number", formatter: "money", formatterParams: {precision: 2, symbol: "%"}},
        {title: "起始价格", field: "start_price", width: 100, headerSort: true, sorter: "number", formatter: "money", formatterParams: {precision: 2, symbol: "¥"}},
        {title: "结束价格", field: "end_price", width: 100, headerSort: true, sorter: "number", formatter: "money", formatterParams: {precision: 2, symbol: "¥"}},
        {title: "起始日期", field: "start_date", width: 10, headerSort: true, sorter: "date", sorterParams: {format: "YYYY-MM-DD"}},
        {title: "结束日期", field: "end_date", width: 100, headerSort: true, sorter: "date", sorterParams: {format: "YYYY-MM-DD"}},
        {title: "操作", field: "industry_name", width: 120, headerSort: false, formatter: function(cell, formatterParams, onRendered) {
            const industryName = cell.getValue();
            return `<button onclick="showIndustryConstituents('${industryName}')">查看成份股</button>`;
        }}
    ];

    // 初始化表格
    const table = initTabulatorTable(`industry-${tableType}-table`, data, columns, {
        layout: "fitDataStretch",
        pagination: true,
        paginationSize: 25,
        paginationSizeSelector: [10, 25, 50, 100, true],
        movableColumns: true,
        columnHeaderVertAlign: "bottom",
        initialSort: [initialSort]
    });

    return table;
}

// 为行业成份股创建Tabulator表格
function initIndustryConstituentsTable(data, industryName) {
    const container = document.getElementById('industry-data-container');
    
    // 创建数据摘要和返回按钮
    let headerHtml = `
        <div class="industry-summary">
            <h3>${industryName} - 成份股列表</h3>
            <button onclick="showCachedIndustryData()" style="margin-bottom: 15px;">返回行业排行</button>
        </div>
        <p>共 ${data.length} 个成份股</p>
    `;
    container.innerHTML = headerHtml;

    // 创建表格容器
    const tableContainer = document.createElement('div');
    tableContainer.id = 'industry-constituents-table';
    tableContainer.style.height = 'calc(100vh - 300px)';
    container.appendChild(tableContainer);

    // 定义列
    const columns = [
        {title: "序号", field: "index", width: 60, headerSort: true, formatter: "rownum"},
        {title: "股票代码", field: "代码", width: 100, headerSort: true},
        {title: "股票名称", field: "名称", width: 120, headerSort: true},
        {title: "涨跌幅", field: "涨跌幅", width: 100, headerSort: true, sorter: "number", formatter: function(cell, formatterParams, onRendered) {
            const value = cell.getValue();
            const numValue = parseFloat(value);
            const displayValue = !isNaN(numValue) ? numValue.toFixed(2) + '%' : 'N/A';
            const changeClass = !isNaN(numValue) && numValue >= 0 ? 'positive' : 'negative';
            return `<span class="industry-change ${changeClass}">${displayValue}</span>`;
        }},
        {title: "价格", field: "最新价", width: 100, headerSort: true, sorter: "number", formatter: "money", formatterParams: {precision: 2, symbol: "¥"}},
        {title: "成交量", field: "成交量", width: 120, headerSort: true, sorter: "number"},
        {title: "流通市值", field: "流通市值", width: 120, headerSort: true}
    ];

    // 初始化表格
    const table = initTabulatorTable('industry-constituents-table', data, columns, {
        layout: "fitDataStretch",
        pagination: true,
        paginationSize: 25,
        paginationSizeSelector: [10, 25, 50, 100, true],
        movableColumns: true,
        columnHeaderVertAlign: "bottom",
        initialSort: [
            {column: "涨跌幅", dir: "desc"} // 默认按涨跌幅降序排列
        ]
    });

    // 添加返回按钮
    const returnButton = document.createElement('button');
    returnButton.textContent = '返回行业排行';
    returnButton.onclick = function() { showCachedIndustryData(); };
    returnButton.style.marginTop = '15px';
    container.appendChild(returnButton);

    return table;
}

// 为监控股票列表创建Tabulator表格
function initStocksTable(data) {
    const container = document.getElementById('stocks-list');
    
    // 创建表格容器
    const tableContainer = document.createElement('div');
    tableContainer.id = 'stocks-monitor-table';
    tableContainer.style.height = 'calc(100vh - 200px)';
    container.appendChild(tableContainer);

    // 定义列
    const columns = [
        {title: "股票名称", field: "name", width: 120, headerSort: true},
        {title: "股票代码", field: "code", width: 100, headerSort: true},
        {title: "当前价格", field: "current_price", width: 10, headerSort: true, formatter: "money", formatterParams: {precision: 2, symbol: "¥"}},
        {title: "涨跌幅", field: "change_pct", width: 100, headerSort: true, formatter: function(cell, formatterParams, onRendered) {
            const value = cell.getValue();
            const numValue = parseFloat(value);
            const displayValue = !isNaN(numValue) ? (numValue >= 0 ? '+' : '') + numValue.toFixed(2) + '%' : 'N/A';
            const changeClass = !isNaN(numValue) && numValue >= 0 ? 'positive' : 'negative';
            return `<span class="stock-change ${changeClass}">${displayValue}</span>`;
        }},
        {title: "低价报警", field: "low_alert_price", width: 100, headerSort: true, formatter: "money", formatterParams: {precision: 2, symbol: "¥"}},
        {title: "高价报警", field: "high_alert_price", width: 100, headerSort: true, formatter: "money", formatterParams: {precision: 2, symbol: "¥"}},
        {title: "涨跌停报警", field: "limit_alert", width: 100, headerSort: true, formatter: "tickCross"},
        {title: "操作", field: "code", width: 250, headerSort: false, formatter: function(cell, formatterParams, onRendered) {
            const code = cell.getValue();
            return `
                <button class="refresh-btn" onclick="refreshStockData('${code}')">刷新</button>
                <button class="update-btn" onclick="editStock('${code}')">编辑</button>
                <button class="delete-btn" onclick="deleteStock('${code}')">删除</button>
                <button id="toggle-stock-${code}" class="toggle-btn toggle-on" onclick="toggleStockNotification('${code}')">关闭消息</button>
            `;
        }}
    ];

    // 初始化表格
    const table = initTabulatorTable('stocks-monitor-table', data, columns, {
        layout: "fitDataStretch",
        pagination: true,
        paginationSize: 25,
        paginationSizeSelector: [10, 25, 50, 100, true],
        movableColumns: true,
        columnHeaderVertAlign: "bottom",
        initialSort: [
            {column: "change_pct", dir: "desc"} // 默认按涨跌幅降序排列
        ]
    });

    return table;
}

// 动态加载Tabulator功能（如果未加载）
function loadTabulatorFeatures() {
    return new Promise((resolve, reject) => {
        // 检查Tabulator是否已加载
        if (typeof Tabulator !== 'undefined') {
            console.log('Tabulator已加载');
            resolve();
        } else {
            // 创建一个脚本加载器，但Tabulator已经通过HTML的script标签引入
            // 这里主要是为了兼容性处理
            console.log('Tabulator已通过HTML引入，等待其加载完成');
            let attempts = 0;
            const maxAttempts = 20; // 最多等待10秒（20次 * 500毫秒）
            
            const checkTabulator = () => {
                if (typeof Tabulator !== 'undefined') {
                    console.log('Tabulator加载完成');
                    resolve();
                } else if (attempts < maxAttempts) {
                    attempts++;
                    setTimeout(checkTabulator, 500); // 每500毫秒检查一次
                } else {
                    console.error('Tabulator加载超时');
                    reject(new Error('Tabulator加载超时'));
                }
            };
            
            checkTabulator();
        }
    });
}
