// 分析师数据页面的JavaScript功能模块

// 加载分析师数据
function loadAnalystData() {
    const analystContainer = document.getElementById('analyst-data-container');
    analystContainer.innerHTML = '<div class="loading">正在加载分析师数据... <span id="analyst-progress">0%</span></div>';
    
    const selectedPeriod = document.getElementById('analyst-period-select').value;
    const selectedTopAnalysts = document.getElementById('analyst-top-analysts-select').value;
    const selectedTopStocks = document.getElementById('analyst-top-stocks-select').value;
    console.log(`请求分析师数据，时间周期: ${selectedPeriod}, 前${selectedTopAnalysts}名分析师, 前${selectedTopStocks}只股票`);
    
    // 更新进度 - 检查元素是否存在
    const updateProgress = (percentage) => {
        const progressElement = document.getElementById('analyst-progress');
        if (progressElement) {
            progressElement.textContent = percentage;
        } else {
            console.log(`进度: ${percentage}`); // 如果元素不存在，记录到控制台
        }
    };
    
    // 更新进度
    updateProgress('10%');
    
    // 串行请求两个API端点（取消并行请求）
    // 首先请求分析师重点关注股票数据
    fetch(`/api/analyst/focus_stocks?period=${encodeURIComponent(selectedPeriod)}&top_analysts=${selectedTopAnalysts}&top_stocks=${selectedTopStocks}`)
    .then(focusStocksResponse => {
        updateProgress('50%');
        return focusStocksResponse.json();
    })
    .then(focusStocksData => {
        // 然后请求最新跟踪数据（串行执行）
        return fetch(`/api/analyst/latest_tracking?period=${encodeURIComponent(selectedPeriod)}&top_analysts=${selectedTopAnalysts}`)
        .then(latestTrackingResponse => {
            updateProgress('80%');
            return Promise.all([Promise.resolve(focusStocksData), latestTrackingResponse.json()]);
        });
    })
    .then(([focusStocksData, latestTrackingData]) => {
        updateProgress('100%');
        console.log('收到分析师重点关注股票数据:', focusStocksData);
        console.log('收到最新跟踪数据:', latestTrackingData);
        
        let formattedHtml = '<div class="analyst-content">';
        
        // 添加数据摘要
        formattedHtml += `
            <div class="analyst-summary">
                <h3>数据摘要</h3>
                <p>所有分析师按所选时间段的收益率排名，按前N名分析师所持股重复次数排名</p>
                <p>实际处理分析师数量: ${focusStocksData.data ? focusStocksData.data.total_analysts_processed : 0}</p>
                <p>最新跟踪成份唯一股票数量: ${focusStocksData.data ? focusStocksData.data.latest_unique_stocks : 0}</p>
                <p>多个分析师跟踪的股票数量: ${focusStocksData.data ? focusStocksData.data.latest_focus_stocks : 0}</p>
                <p>最新跟踪成份总的股票数量: ${latestTrackingData.success ? latestTrackingData.data.length : 0}</p>
            </div>
        `;
        
        // 显示分析师重点关注股票
        if (focusStocksData.success && focusStocksData.data && focusStocksData.data.top_focus_stocks) {
            // 根据选择的股票数量决定显示数量，最多显示100只
            const displayLimit = Math.min(100, parseInt(selectedTopStocks) || 50);
            const topFocusStocks = focusStocksData.data.top_focus_stocks.slice(0, displayLimit); // 只显示指定数量的股票
            if (topFocusStocks.length > 0) {
                formattedHtml += `
                    <h3>分析师重点关注股票（前${topFocusStocks.length}只）</h3>
                    <table class="analyst-table">
                        <thead>
                            <tr>
                                <th>分析师关注数量</th>
                                <th>股票代码</th>
                                <th>股票名称</th>
                                <th>平均成交价格</th>
                                <th>最高成交价格</th>
                                <th>最低成交价格</th>
                                <th>最新价格</th>
                                <th>同行比较</th>
                                <th>历史跟踪图表</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                topFocusStocks.forEach(stock => {
                    formattedHtml += `
                        <tr>
                            <td>${stock.analyst_count || 0}</td>
                            <td>${stock.stock_code || ''}</td>
                            <td>${stock.stock_name || ''}</td>
                            <td>${stock.avg_price != null ? stock.avg_price.toFixed(2) : 'N/A'}</td>
                            <td>${stock.max_price != null ? stock.max_price.toFixed(2) : 'N/A'}</td>
                            <td>${stock.min_price != null ? stock.min_price.toFixed(2) : 'N/A'}</td>
                            <td>${stock.latest_price != null ? (typeof stock.latest_price === 'number' ? stock.latest_price.toFixed(2) : stock.latest_price) : 'N/A'}</td>
                            <td><button onclick="openEastMoneyPeerComparison('${stock.stock_code}')">同行比较</button></td>
                            <td><button onclick="showAnalystHistoryChart('${stock.stock_code}')">历史跟踪图表</button></td>
                        </tr>
                    `;
                });
                formattedHtml += '</tbody></table>';
            } else {
                formattedHtml += '<p>暂无重点关注股票数据</p>';
            }
        } else {
            formattedHtml += `<p class="error">获取分析师重点关注股票失败: ${focusStocksData.message || '未知错误'}</p>`;
        }
        
        // 显示最新跟踪成份股数据
        if (latestTrackingData.success && latestTrackingData.data) {
            if (latestTrackingData.data.length > 0) {
                // 使用Tabulator表格显示最新跟踪成份股数据
                formattedHtml += `
                    <h3>最新跟踪成份股</h3>
                    <div id="latest-tracking-table-container"></div>
                `;
            } else {
                formattedHtml += '<p>暂无最新跟踪成份股数据</p>';
            }
        } else {
            formattedHtml += `<p class="error">获取最新跟踪成份股数据失败: ${latestTrackingData.message || '未知错误'}</p>`;
        }
        
        formattedHtml += '</div>';
        analystContainer.innerHTML = formattedHtml;
        
        // 如果有最新跟踪数据，初始化Tabulator表格
        if (latestTrackingData.success && latestTrackingData.data && latestTrackingData.data.length > 0) {
            // 等待DOM更新后初始化表格
            setTimeout(() => {
                initLatestTrackingTable(latestTrackingData.data);
            }, 100);
        }
    })
    .catch(error => {
        console.error('加载分析师数据时出错:', error);
        analystContainer.innerHTML = `<div class="error">加载分析师数据失败: ${error.message}</div>`;
    });
}

// 初始化最新跟踪成份股表格（使用Tabulator）
function initLatestTrackingTable(data) {
    const container = document.getElementById('latest-tracking-table-container');
    if (!container) return;
    
    // 定义列
    const columns = [
        {title: "分析师名称", field: "analyst_name", width: 120, headerSort: true},
        {title: "分析师行业", field: "analyst_industry", width: 120, headerSort: true},
        {title: "期间收益", field: "analyst_period_return", width: 100, headerSort: true, sorter: "number"},
        {title: "25总收益", field: "analyst_total_return", width: 100, headerSort: true, sorter: "number"},
        {title: "股票代码", field: "股票代码", width: 100, headerSort: true},
        {title: "股票名称", field: "股票名称", width: 120, headerSort: true},
        {title: "调入日期", field: "调入日期", width: 100, headerSort: true, sorter: "date", sorterParams: {format: "YYYY-MM-DD"}},
        {title: "成交价格(前复权)", field: "成交价格(前复权)", width: 140, headerSort: true, sorter: "number"},
        {title: "最新价格", field: "最新价格", width: 100, headerSort: true, sorter: "number"},
        {title: "阶段涨跌幅", field: "阶段涨跌幅", width: 120, headerSort: true, sorter: "number", formatter: "money", formatterParams: {precision: 2, symbol: "%"}},
        {title: "当前评级名称", field: "当前评级名称", width: 120, headerSort: true},
        {title: "同行比较", field: "股票代码", width: 100, headerSort: false, formatter: function(cell, formatterParams, onRendered) {
            const stockCode = cell.getValue();
            return `<button onclick="openEastMoneyPeerComparison('${stockCode}')">同行比较</button>`;
        }}
    ];

    // 初始化Tabulator表格
    const table = new Tabulator("#latest-tracking-table-container", {
        data: data,
        columns: columns,
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
}

// 加载最近更新的股票数据
function loadRecentlyUpdatedStocks() {
    console.log('正在加载最近更新的股票数据...');
    // 检查Tabulator是否已加载，如果没有则加载
    if (typeof Tabulator === 'undefined') {
        console.error('Tabulator库未加载');
        const analystContainer = document.getElementById('analyst-data-container');
        analystContainer.innerHTML = '<div class="error">Tabulator库未加载，请检查网络连接或联系管理员</div>';
        return;
    }

    // Tabulator已加载，继续执行
    const analystContainer = document.getElementById('analyst-data-container');
    analystContainer.innerHTML = '<div class="loading">正在加载最近更新的股票数据... <span id="recently-updated-progress">0%</span></div>';
    
    // 获取天数输入
    const daysInput = document.getElementById('date-threshold-input').value;
    let days = 7; // 默认值
    if (daysInput) {
        const parsedDays = parseInt(daysInput);
        if (!isNaN(parsedDays) && parsedDays > 0) {
            days = parsedDays;
        }
    }
    console.log(`请求最近更新的股票数据，天数: ${days}`);
    
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
    const apiUrl = `/api/analyst/recently_updated_stocks?days=${days}`;
    
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
            // 使用Tabulator功能显示数据
            if (typeof initRecentlyUpdatedStocksTable !== 'undefined') {
                // 清空容器并添加数据摘要
                let formattedHtml = `
                    <div class="analyst-summary">
                        <h3>最近更新股票数据摘要</h3>
                        <p>日期阈值: ${data.days}天</p>
                        <p>符合条件的股票总数: ${data.data.length}</p>
                    </div>
                `;
                analystContainer.innerHTML = formattedHtml;
                // 初始化Tabulator表格
                initRecentlyUpdatedStocksTable(data.data);
            } else {
                console.error('initRecentlyUpdatedStocksTable函数未定义');
                analystContainer.innerHTML = `<div class="error">initRecentlyUpdatedStocksTable函数未定义</div>`;
            }
        } else {
            analystContainer.innerHTML = `<div class="error">获取最近更新的股票数据失败: ${data.message}</div>`;
        }
    })
    .catch(error => {
        console.error('加载最近更新的股票数据时出错:', error);
        analystContainer.innerHTML = `<div class="error">加载最近更新的股票数据失败: ${error.message}</div>`;
    });
}

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

// 加载标签页数据
function loadTabData(symbol, tabName) {
    const contentDiv = document.getElementById(`${tabName}-comparison-${symbol}`);
    if (contentDiv.innerHTML.includes('正在加载')) {
        // 防止重复加载
        fetch(`/api/analyst/stock_${tabName}_comparison?symbol=${encodeURIComponent(symbol)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const comparisonData = data.data;
                if (comparisonData && comparisonData.length > 0) {
                    // 创建表格显示数据
                    let tableHtml = '<table class="peer-comparison-table">';
                    // 添加表头
                    tableHtml += '<thead><tr>';
                    const firstRow = comparisonData[0];
                    for (const key in firstRow) {
                        tableHtml += `<th>${key}</th>`;
                    }
                    tableHtml += '</tr></thead>';
                    
                    // 添加数据行
                    tableHtml += '<tbody>';
                    comparisonData.forEach(row => {
                        tableHtml += '<tr>';
                        for (const key in firstRow) {
                            const value = row[key] !== undefined ? row[key] : '';
                            tableHtml += `<td>${value}</td>`;
                        }
                        tableHtml += '</tr>';
                    });
                    tableHtml += '</tbody></table>';
                    
                    contentDiv.innerHTML = tableHtml;
                } else {
                    contentDiv.innerHTML = '<p>暂无数据</p>';
                }
            } else {
                contentDiv.innerHTML = `<p class="error">加载${tabName === 'growth' ? '成长性' : tabName === 'valuation' ? '估值' : '杜邦分析'}比较数据失败: ${data.message}</p>`;
            }
        })
        .catch(error => {
            contentDiv.innerHTML = `<p class="error">加载${tabName === 'growth' ? '成长性' : tabName === 'valuation' ? '估值' : '杜邦分析'}比较数据异常: ${error.message}</p>`;
        });
    }
}

// 显示同行比较数据（保留原函数以备后用）
function showPeerComparison(symbol) {
    console.log(`显示股票 ${symbol} 的同行比较数据`);
    
    // 创建模态框
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'block';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 90%; max-height: 90vh; overflow: auto;">
            <span class="close" style="float: right; font-size: 28px; font-weight: bold; cursor: pointer;">&times;</span>
            <h3>股票 ${symbol} 同行比较数据</h3>
            <div id="peer-comparison-tabs-${symbol}" class="peer-comparison-tabs">
                <button class="tab-button active" data-tab="growth">成长性比较</button>
                <button class="tab-button" data-tab="valuation">估值比较</button>
                <button class="tab-button" data-tab="dupont">杜邦分析</button>
            </div>
            <div id="peer-comparison-content-${symbol}" class="peer-comparison-content">
                <div id="growth-comparison-${symbol}" class="tab-content active">
                    <div class="loading">正在加载成长性比较数据...</div>
                </div>
                <div id="valuation-comparison-${symbol}" class="tab-content">
                    <div class="loading">正在加载估值比较数据...</div>
                </div>
                <div id="dupont-comparison-${symbol}" class="tab-content">
                    <div class="loading">正在加载杜邦分析数据...</div>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    
    // 添加模态框关闭事件
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
    
    // 添加标签页切换功能
    const tabButtons = modal.querySelectorAll('.tab-button');
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            // 移除所有活动标签
            tabButtons.forEach(btn => btn.classList.remove('active'));
            const tabContents = modal.querySelectorAll('.tab-content');
            tabContents.forEach(content => content.classList.remove('active'));
            // 激活当前标签
            this.classList.add('active');
            document.getElementById(`${tabName}-comparison-${symbol}`).classList.add('active');
            // 加载数据（如果尚未加载）
            loadTabData(symbol, tabName);
        });
    });
    
    // 首次加载成长性比较数据
    loadTabData(symbol, 'growth');
}

// 显示消息提示
function showMessage(message, type) {
    // 创建消息元素
    const messageDiv = document.createElement('div');
    messageDiv.className = type;
    messageDiv.textContent = message;

    // 添加到页面顶部
    document.querySelector('.container').insertBefore(messageDiv, document.querySelector('.container').firstChild);

    // 3秒后自动移除
    setTimeout(() => {
        messageDiv.remove();
    }, 3000); // 修复：应该是3000毫秒，不是300毫秒
}

// 行业板块页面的初始化函数
function initializeAnalystPage() {
    console.log('分析师数据页面初始化完成');
}
