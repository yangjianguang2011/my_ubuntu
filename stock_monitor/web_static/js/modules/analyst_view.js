// 分析师数据页面的JavaScript功能模块

// 缓存工具函数
const AnalystCache = {
    // 生成缓存键
    generateKey: function(baseKey, params) {
        const paramString = Object.keys(params).sort().map(key => `${key}=${params[key]}`).join('&');
        return `${baseKey}?${paramString}`;
    },

    // 获取缓存数据
    get: function(key) {
        try {
            const cached = localStorage.getItem(key);
            if (cached) {
                const parsed = JSON.parse(cached);
                // 检查是否过期
                const now = new Date().getTime();
                if (now < parsed.expiry) {
                    console.log(`从缓存获取数据: ${key}`);
                    return parsed.data;
                } else {
                    // 缓存过期，删除它
                    localStorage.removeItem(key);
                    console.log(`缓存已过期并删除: ${key}`);
                }
            }
        } catch (e) {
            console.warn('读取缓存失败:', e);
            // 如果解析失败，删除损坏的缓存
            try {
                localStorage.removeItem(key);
            } catch (removeErr) {
                console.error('删除损坏缓存失败:', removeErr);
            }
        }
        return null;
    },

    // 设置缓存数据
    set: function(key, data, ttlMinutes = 5) { // 默认30分钟过期
        try {
            const expiry = new Date().getTime() + (ttlMinutes * 60 * 1000);
            const cacheItem = {
                data: data,
                expiry: expiry
            };
            localStorage.setItem(key, JSON.stringify(cacheItem));
            console.log(`数据已缓存: ${key}, 过期时间: ${ttlMinutes}分钟`);
        } catch (e) {
            console.warn('设置缓存失败，可能是存储空间不足:', e);
        }
    },

    // 清除特定缓存
    clear: function(key) {
        try {
            localStorage.removeItem(key);
            console.log(`缓存已清除: ${key}`);
        } catch (e) {
            console.error('清除缓存失败:', e);
        }
    },

    // 清除所有分析师相关缓存
    clearAll: function() {
        try {
            Object.keys(localStorage).forEach(key => {
                if (key.startsWith('analyst_')) {
                    localStorage.removeItem(key);
                }
            });
            console.log('所有分析师缓存已清除');
        } catch (e) {
            console.error('清除所有缓存失败:', e);
        }
    }
};

//========================================================================================
// 渲染分析师重点关注股票数据 - 使用Tabulator
function renderAnalystFocusStocks(focusStocksData) {
    const analystContainer = document.getElementById('analyst-focus-stocks-container');

    // 显示分析师重点关注股票
    if (focusStocksData.success && focusStocksData.data && focusStocksData.data.top_focus_stocks) {
        // 获取当前页面参数
        const periodSelect = document.getElementById('analyst-period-select');
        const topStocksSelect = document.getElementById('analyst-top-stocks-select');
        const selectedTopAnalystsSelect = document.getElementById('analyst-top-analysts-select');

        const period = periodSelect ? periodSelect.value : '3个月';
        const topStocks = topStocksSelect ? topStocksSelect.value : 50;
        const topAnalysts = selectedTopAnalystsSelect ? selectedTopAnalystsSelect.value : 50;

        const displayLimit = Math.min(100, parseInt(topStocks) || 50);
        const topFocusStocks = focusStocksData.data.top_focus_stocks.slice(0, displayLimit); // 只显示指定数量的股票

        if (topFocusStocks.length > 0) {
            // 创建带统计信息的布局，将统计信息移到表格上方
            analystContainer.innerHTML = `
                <div class="analyst-full-width-panel">
                    <div class="analyst-summary">
                        <h3>重点关注股票摘要</h3>
                        <p><strong>算法说明：</strong>统计所选分析师范围内，被最多分析师跟踪的股票，按关注数量排序；历史跟踪数据是基于默认参数计算的分析师个数</p>
                        <p><strong>数据统计：</strong>处理分析师: ${focusStocksData.data.total_analysts_processed || 0} |
                           跟踪股票总数: ${focusStocksData.data.latest_unique_stocks || 0} |
                           多人关注股票: ${focusStocksData.data.latest_focus_stocks || 0}</p>
                    </div>
                    <div class="analyst-data-panel">
                        <div id="focus-stocks-table-container"></div>
                    </div>
                </div>
            `;

            // 初始化Tabulator表格
            initFocusStocksTable(topFocusStocks);
        } else {
            analystContainer.innerHTML = '<div class="analyst-focus-stocks-section"><p>暂无重点关注股票数据</p></div>';
        }
    } else {
        analystContainer.innerHTML = `<div class="analyst-focus-stocks-section"><p class="error">获取分析师重点关注股票失败: ${focusStocksData.message || '未知错误'}</p></div>`;
    }
}

// 初始化重点关注股票表格
function initFocusStocksTable(data) {
    const container = document.getElementById('focus-stocks-table-container');
    
    // 定义列
    const columns = [
        {title: "分析师关注数量", field: "analyst_count", width: 140, headerSort: true,
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                return value;
            }
        },
        {title: "股票代码", field: "stock_code", width: 100, headerSort: true},
        {title: "股票名称", field: "stock_name", width: 120, headerSort: true},
        {title: "平均成交价格", field: "avg_price", width: 140, headerSort: true, 
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                return value != null ? value.toFixed(2) : 'N/A';
            }
        },
        {title: "最高成交价格", field: "max_price", width: 140, headerSort: true, 
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                return value != null ? value.toFixed(2) : 'N/A';
            }
        },
        {title: "最低成交价格", field: "min_price", width: 140, headerSort: true, 
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                return value != null ? value.toFixed(2) : 'N/A';
            }
        },
        {title: "最新价格", field: "latest_price", width: 100, headerSort: true, 
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                return value != null ? (typeof value === 'number' ? value.toFixed(2) : value) : 'N/A';
            }
        },
        {title: "同行比较", field: "stock_code", width: 120, headerSort: false, 
            formatter: function(cell, formatterParams, onRendered) {
                const stockCode = cell.getValue();
                return `<button onclick="openEastMoneyPeerComparison('${stockCode}')">同行比较</button>`;
            }
        },
        {title: "历史跟踪", field: "stock_code", width: 150, headerSort: false, 
            formatter: function(cell, formatterParams, onRendered) {
                const stockCode = cell.getValue();
                return `<button onclick="showAnalystHistoryChart('${stockCode}')">历史跟踪</button>`;
            }
        }
    ];

    // 创建Tabulator实例
    const table = new Tabulator(container, {
        data: data,
        columns: columns,
        layout: "fitDataStretch",
        pagination: false, // 关闭分页
        movableColumns: true,
        columnHeaderVertAlign: "bottom",
        initialSort: [
            {column: "analyst_count", dir: "desc"} // 默认按关注数量降序排列
        ],
        rowFormatter: function(row) {
            // 为行添加颜色编码 - 使用与行业板块一致的蓝色系
            // 这里我们可以使用一个统一的基准，比如根据分析师关注数量来设置背景色
            const rowData = row.getData();
            const analystCount = rowData.analyst_count || 0;
            // 使用一个合理的基准值，比如最大预期关注数为20
            const intensity = Math.min(analystCount / 20, 1); // 假设最大关注数为20
            const bgColor = `rgba(52, 152, 219, ${0.1 + intensity * 0.3})`; // 蓝色系，与行业板块一致
            row.getElement().style.backgroundColor = bgColor;
        }
    });

    return table;
}

// 加载分析师重点关注股票数据
function loadAnalystFocusStocks() {
    console.log('正在加载分析师重点关注股票数据...');

    // 获取选择的参数
    const periodSelect = document.getElementById('analyst-period-select');
    const topStocksSelect = document.getElementById('analyst-top-stocks-select');
    const selectedTopAnalystsSelect = document.getElementById('analyst-top-analysts-select');

    const period = periodSelect ? periodSelect.value : '3个月';
    const topStocks = topStocksSelect ? topStocksSelect.value : 50;
    const topAnalysts = selectedTopAnalystsSelect ? selectedTopAnalystsSelect.value : 50;

    // 显示加载状态
    const analystContainer = document.getElementById('analyst-focus-stocks-container');
    analystContainer.innerHTML = '<div class="loading">正在加载分析师重点关注股票数据...</div>';

    // 构建API请求URL
    const apiUrl = `/api/analyst/focus_stocks?period=${encodeURIComponent(period)}&top_analysts=${encodeURIComponent(topAnalysts)}&top_stocks=${encodeURIComponent(topStocks)}`;

    // 调用API获取数据
    fetch(apiUrl)
    .then(response => response.json())
    .then(data => {
        console.log('收到分析师重点关注股票数据:', data);
        // 调用渲染函数
        renderAnalystFocusStocks(data);
    })
    .catch(error => {
        console.error('加载分析师重点关注股票数据时出错:', error);
        analystContainer.innerHTML = `<div class="error">加载分析师重点关注股票数据失败: ${error.message}</div>`;
    });
}

//========================================================================================
// 加载最近更新的股票数据
function loadAnalystUpdatedStocks() {
    console.log('正在加载最近更新的股票数据...');
    // 检查Tabulator是否已加载，如果没有则加载
    if (typeof Tabulator === 'undefined') {
        console.error('Tabulator库未加载');
        const analystContainer = document.getElementById('analyst-latest-tracking-container');
        analystContainer.innerHTML = '<div class="error">Tabulator库未加载，请检查网络连接或联系管理员</div>';
        return;
    }

    // Tabulator已加载，继续执行
    const analystContainer = document.getElementById('analyst-latest-tracking-container');
    analystContainer.innerHTML = '<div class="loading">正在加载最近更新的股票数据... <span id="recently-updated-progress">0%</span></div>';

    // 获取天数输入
    const daysInput = document.getElementById('date-threshold-input').value;
    let days = 30; // 默认值
    if (daysInput) {
        const parsedDays = parseInt(daysInput);
        if (!isNaN(parsedDays) && parsedDays > 0) {
            days = parsedDays;
        }
    }
    console.log(`请求最近更新的股票数据，天数: ${days}`);

    // 生成缓存键
    const recentlyUpdatedCacheKey = AnalystCache.generateKey('analyst_recently_updated_stocks', {days: days});

    // 尝试从缓存获取数据
    const cachedData = AnalystCache.get(recentlyUpdatedCacheKey);
    if (cachedData) {
        console.log('使用缓存的最近更新股票数据');
        renderRecentlyUpdatedStocks(cachedData, analystContainer);
        return;
    }

    // 更新进度 - 检查元素是否存在
    const updateProgress = (percentage) => {
        const progressElement = document.getElementById('recently-updated-progress');
        if (progressElement) {
            progressElement.textContent = percentage;
        } else {
            console.log(`进度: ${percentage}`); // 如果元素不存在，记录到控制台
        }
    };

    // 更新进度
    updateProgress('20%');

    // 构建API请求URL
    const apiUrl = `/api/analyst/updated_stocks?days=${days}`;

    // 调用API获取最近更新的股票数据
    fetch(apiUrl)
    .then(response => {
        updateProgress('50%');
        return response.json();
    })
    .then(data => {
        updateProgress('100%');
        console.log('收到最近更新的股票数据:', data);

        if (data.success) {
            // 缓存数据
            AnalystCache.set(recentlyUpdatedCacheKey, data, 15); // 15分钟缓存

            // 使用Tabulator功能显示数据
            renderRecentlyUpdatedStocks(data, analystContainer);
        } else {
            analystContainer.innerHTML = `<div class="error">获取最近更新的股票数据失败: ${data.message}</div>`;
        }
    })
    .catch(error => {
        console.error('加载最近更新的股票数据时出错:', error);
        analystContainer.innerHTML = `<div class="error">加载最近更新的股票数据失败: ${error.message}</div>`;
    });
}

// 渲染最近更新的股票数据
function renderRecentlyUpdatedStocks(data, container) {
    // 计算统计信息
    const analystsSet = new Set();
    const stocksSet = new Set();
    const stockAnalystCount = {}; // 记录每个股票被多少个分析师跟踪

    data.data.forEach(item => {
        // 统计分析师
        if (item.analyst_name) {
            analystsSet.add(item.analyst_name);
        }

        // 统计股票
        if (item['股票代码']) {
            stocksSet.add(item['股票代码']);

            // 记录每个股票被多少个分析师跟踪
            if (!stockAnalystCount[item['股票代码']]) {
                stockAnalystCount[item['股票代码']] = 0;
            }
            stockAnalystCount[item['股票代码']]++;
        }
    });

    // 计算被多个分析师跟踪的股票数量
    const multiAnalystStocks = Object.values(stockAnalystCount).filter(count => count > 1).length;

    // 清空容器并添加数据摘要，将统计信息移到表格上方
    let formattedHtml = `
        <div class="analyst-full-width-panel">
            <div class="analyst-summary">
                <h3>最近更新股票数据摘要</h3>
                <p><strong>算法说明：</strong>筛选最近${data.days}天内有更新的分析师，获取其跟踪的最新股票</p>
                <p><strong>参数设置：</strong>时间范围: 最近${data.days}天</p>
                <p><strong>数据统计：</strong>符合条件分析师: ${analystsSet.size} |
                   符合条件股票: ${data.data.length} |
                   唯一股票: ${stocksSet.size} |
                   多人关注: ${multiAnalystStocks}</p>
                <p><strong>数据密度：</strong>人均跟踪: ${(data.data.length/analystsSet.size).toFixed(1)}只 |
                   重复度: ${(multiAnalystStocks/stocksSet.size*100).toFixed(1)}%</p>
            </div>
            <div class="analyst-data-panel">
                <div id="recently-updated-stocks-table-container"></div>
            </div>
        </div>
    `;
    container.innerHTML = formattedHtml;

    // 初始化Tabulator表格
    initRecentlyUpdatedStocksTable(data.data);
}

// 初始化最近更新股票表格
function initRecentlyUpdatedStocksTable(data) {
    const container = document.getElementById('recently-updated-stocks-table-container');
    
    const columns = [
        {title: "分析师名称", field: "analyst_name", width: 120, headerSort: true},
        {title: "分析师行业", field: "analyst_industry", width: 120, headerSort: true},
        {title: "股票代码", field: "股票代码", width: 100, headerSort: true},
        {title: "股票名称", field: "股票名称", width: 120, headerSort: true},
        {title: "调入日期", field: "调入日期", width: 100, headerSort: true, sorter: "string"},
        {title: "最新评级日期", field: "最新评级日期", width: 120, headerSort: true, sorter: "string"},
        {title: "成交价格(前复权)", field: "成交价格(前复权)", width: 140, headerSort: true, sorter: "number"},
        {title: "最新价格", field: "最新价格", width: 100, headerSort: true, sorter: "number"},
        {title: "阶段涨跌幅", field: "阶段涨跌幅", width: 120, headerSort: true,
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                const numValue = typeof value === 'number' ? value : parseFloat(value);
                const displayValue = isNaN(numValue) ? value : (numValue >= 0 ? '+' : '') + numValue.toFixed(2) + '%';
                if(!isNaN(numValue)) {
                    cell.getElement().style.color = numValue >= 0 ? '#28a745' : '#dc3545'; // 绿色表示正值，红色表示负值
                }
                return displayValue;
            }
        },
        {title: "当前评级名称", field: "当前评级名称", width: 120, headerSort: true},
        {title: "分析师3个月收益率", field: "analyst_period_3m_return", width: 160, headerSort: true, sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                const numValue = typeof value === 'number' ? value : parseFloat(value);
                const displayValue = isNaN(numValue) ? value : (numValue >= 0 ? '+' : '') + numValue.toFixed(2) + '%';
                if(!isNaN(numValue)) {
                    cell.getElement().style.color = numValue >= 0 ? '#28a745' : '#dc3545'; // 绿色表示正值，红色表示负值
                }
                return displayValue;
            }
        },
        {title: "分析师6个月收益率", field: "analyst_period_6m_return", width: 160, headerSort: true, sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                const numValue = typeof value === 'number' ? value : parseFloat(value);
                const displayValue = isNaN(numValue) ? value : (numValue >= 0 ? '+' : '') + numValue.toFixed(2) + '%';
                if(!isNaN(numValue)) {
                    cell.getElement().style.color = numValue >= 0 ? '#28a745' : '#dc3545'; // 绿色表示正值，红色表示负值
                }
                return displayValue;
            }
        },
        {title: "分析师12个月收益率", field: "analyst_period_12m_return", width: 170, headerSort: true, sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                const numValue = typeof value === 'number' ? value : parseFloat(value);
                const displayValue = isNaN(numValue) ? value : (numValue >= 0 ? '+' : '') + numValue.toFixed(2) + '%';
                if(!isNaN(numValue)) {
                    cell.getElement().style.color = numValue >= 0 ? '#28a745' : '#dc3545'; // 绿色表示正值，红色表示负值
                }
                return displayValue;
            }
        }
    ];

    // 创建Tabulator实例
    const table = new Tabulator(container, {
        data: data,
        columns: columns,
        layout: "fitDataStretch",
        pagination: false, // 关闭分页
        movableColumns: true,
        columnHeaderVertAlign: "bottom",
        initialSort: [
            {column: "最新评级日期", dir: "desc"} // 默认按最新评级日期降序排列
        ],
        rowFormatter: function(row) {
            // 为行添加颜色编码 - 使用与行业板块一致的蓝色系
            const rowData = row.getData();
            const changeValue = rowData['阶段涨跌幅'];
            const numChange = typeof changeValue === 'number' ? changeValue : parseFloat(changeValue);
            if (!isNaN(numChange)) {
                // 使用统一的基准值，比如最大涨跌幅为10%
                const intensity = Math.min(Math.abs(numChange) / 10, 1); // 限制在0-1之间，假设10%为最大强度
                const bgColor = `rgba(52, 152, 219, ${0.1 + intensity * 0.3})`; // 蓝色系，与行业板块一致
                row.getElement().style.backgroundColor = bgColor;
            }
        }
    });

    return table;
}

//========================================================================================
// 打开东方财富同行比较页面
function openEastMoneyPeerComparison(symbol) {
    // 确保股票代码格式正确（对于上海市场股票，需要在代码前加'sh'，深圳市场加'sz'）
    let formattedSymbol = symbol;
    if (symbol.startsWith('6')) {
        // 上海股票
        formattedSymbol = 'sh' + symbol;
    } else if (symbol.startsWith('0') || symbol.startsWith('3')) {
        // 深圳股票
        formattedSymbol = 'sz' + symbol;
    }

    // 构建东方财富同行比较页面URL
    const url = `https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=${formattedSymbol}&color=b#/thbj`;

    // 在新窗口中打开URL
    window.open(url, '_blank');
}

//========================================================================================
// 显示股票历史分析师跟踪图表
function showAnalystHistoryChart(stockCode) {
    // 显示加载状态
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content" style="width: 90%; height: 90%; max-width: 1200px; max-height: 800px;">
            <span class="close">&times;</span>
            <h3>股票 ${stockCode} 历史分析师跟踪数据</h3>
            <div id="analyst-history-chart-${stockCode}" style="width: 100%; height: 600px;"></div>
            <div style="margin-top: 10px; text-align: center;">
                <label for="history-days-${stockCode}">显示天数:</label>
                <select id="history-days-${stockCode}" style="margin: 0 10px;">
                    <option value="360" selected>360天</option>
                </select>
                <button onclick="loadAnalystHistoryData('${stockCode}', ${stockCode})">刷新图表</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    // 关闭按钮事件
    const closeBtn = modal.querySelector('.close');
    closeBtn.onclick = function() {
        modal.remove();
    };

    // 点击模态框外部关闭
    window.onclick = function(event) {
        if (event.target === modal) {
            modal.remove();
        }
    };

    // 加载历史数据并渲染图表
    loadAnalystHistoryData(stockCode, modal);
}

// 加载历史数据并渲染图表
function loadAnalystHistoryData(stockCode, modal) {
    // 获取选择的天数
    //const daysSelect = document.getElementById(`history-days-${stockCode}`);
    const days = 360;

    // 生成缓存键
    const historyCacheKey = AnalystCache.generateKey('analyst_history_tracking', {stock_code: stockCode, days: days});

    // 尝试从缓存获取数据
    const cachedData = AnalystCache.get(historyCacheKey);
    if (cachedData) {
        console.log('使用缓存的历史跟踪数据');
        const chartContainer = document.getElementById(`analyst-history-chart-${stockCode}`);
        if (chartContainer) {
            chartContainer.innerHTML = ''; // 清空加载状态
        }
        renderAnalystHistoryChart(stockCode, cachedData, modal);
        return;
    }

    // 显示加载状态
    const chartContainer = document.getElementById(`analyst-history-chart-${stockCode}`);
    if (chartContainer) {
        chartContainer.innerHTML = '<div class="loading">正在加载历史数据...</div>';
    }

    // 获取历史数据
    fetch(`/api/analyst/history_tracking?stock_code=${stockCode}&days=${days}`)
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // 缓存数据
            AnalystCache.set(historyCacheKey, data.data, 60); // 60分钟缓存
            // 渲染图表
            renderAnalystHistoryChart(stockCode, data.data, modal);
        } else {
            if (chartContainer) {
                chartContainer.innerHTML = `<div class="error">获取历史数据失败: ${data.message}</div>`;
            }
            alert(`获取历史数据失败: ${data.message}`);
        }
    })
    .catch(error => {
        console.error('加载历史数据失败:', error);
        if (chartContainer) {
            chartContainer.innerHTML = `<div class="error">加载历史数据失败: ${error.message}</div>`;
        }
        alert(`加载历史数据失败: ${error.message}`);
    });
}

// 渲染历史分析师跟踪图表
function renderAnalystHistoryChart(stockCode, chartData, modal) {
    const chartContainer = document.getElementById(`analyst-history-chart-${stockCode}`);
    if (!chartContainer) return;

    // 清空容器
    chartContainer.innerHTML = '';

    // 初始化ECharts
    const chart = echarts.init(chartContainer);

    // 构建图表配置
    const option = {
        title: {
            text: `股票 ${stockCode} 历史分析师关注数量`,
            left: 'center'
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            },
            formatter: function(params) {
                const date = params[0].axisValue;
                let result = `<div style="font-weight: bold; margin-bottom: 5px;">${date}</div>`;
                params.forEach(param => {
                    const value = param.value !== null ? param.value : 'N/A';
                    result += `<div style="display: flex; align-items: center; margin: 2px 0;">
                        <span style="display: inline-block; width: 10px; height: 10px; background: ${param.color}; margin-right: 5px; border-radius: 50%;"></span>
                        <span style="margin-right: 10px;">${param.seriesName}:</span>
                        <span style="font-weight: bold;">${value}</span>
                    </div>`;
                });
                return result;
            }
        },
        xAxis: {
            type: 'category',
            data: chartData.dates,
            axisLabel: {
                rotate: 45,
                interval: 0
            }
        },
        yAxis: {
            type: 'value',
            name: '分析师关注数量'
        },
        series: [{
            data: chartData.analyst_counts,
            type: 'line',
            smooth: true,
            name: '关注数量',
            symbolSize: 6,
            lineStyle: {
                width: 2
            },
            itemStyle: {
                color: '#1890ff'
            },
            areaStyle: {
                opacity: 0.3
            }
        }],
        dataZoom: [{
            type: 'inside',
            start: 0,
            end: 100
        }, {
            type: 'slider',
            start: 0,
            end: 100
        }]
    };

    chart.setOption(option);

    // 响应窗口大小变化
    window.addEventListener('resize', function() {
        if (chart && typeof chart.resize === 'function') {
            chart.resize();
        }
    });
}


