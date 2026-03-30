// 行业板块页面的JavaScript功能模块

// 缓存工具函数
const IndustryCache = {
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
                    console.log(`从缓存获取行业数据: ${key}`);
                    return parsed.data;
                } else {
                    // 缓存过期，删除它
                    localStorage.removeItem(key);
                    console.log(`行业缓存已过期并删除: ${key}`);
                }
            }
        } catch (e) {
            console.warn('读取行业缓存失败:', e);
            // 如果解析失败，删除损坏的缓存
            try {
                localStorage.removeItem(key);
            } catch (removeErr) {
                console.error('删除损坏的行业缓存失败:', removeErr);
            }
        }
        return null;
    },

    // 设置缓存数据
    set: function(key, data, ttlMinutes = 5) { // 默认5分钟过期
        try {
            const expiry = new Date().getTime() + (ttlMinutes * 60 * 1000);
            const cacheItem = {
                data: data,
                expiry: expiry
            };
            localStorage.setItem(key, JSON.stringify(cacheItem));
            console.log(`行业数据已缓存: ${key}, 过期时间: ${ttlMinutes}分钟`);
        } catch (e) {
            console.warn('设置行业缓存失败，可能是存储空间不足:', e);
        }
    },

    // 清除特定缓存
    clear: function(key) {
        try {
            localStorage.removeItem(key);
            console.log(`行业缓存已清除: ${key}`);
        } catch (e) {
            console.error('清除行业缓存失败:', e);
        }
    },

    // 清除所有行业相关缓存
    clearAll: function() {
        try {
            Object.keys(localStorage).forEach(key => {
                if (key.startsWith('industry_')) {
                    localStorage.removeItem(key);
                }
            });
            console.log('所有行业缓存已清除');
        } catch (e) {
            console.error('清除所有行业缓存失败:', e);
        }
    }
};

// ==================== 行业图表功能 ====================

// 全局变量
let industryChart = null;
let allIndustryNames = [];


// 初始化行业图表页面
function initIndustryChartPage() {
    // 绑定时间周期按钮事件
    const periodBtns = document.querySelectorAll('.period-btn');
    periodBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // 移除其他按钮的active状态
            periodBtns.forEach(b => b.classList.remove('active'));
            // 添加当前按钮的active状态
            this.classList.add('active');
        });
    });

    // 绑定生成图表按钮事件
    const renderBtn = document.getElementById('render-chart-btn');
    if (renderBtn) {
        renderBtn.addEventListener('click', renderIndustryChart);
    }

    // 绑定清除选择按钮事件
    const clearBtn = document.getElementById('clear-selection-btn');
    if (clearBtn) {
        clearBtn.addEventListener('click', clearIndustrySelection);
    }

    // 加载行业列表
    loadIndustryNamesForChart();
}

// 加载行业名称列表（用于图表选择）
function loadIndustryNamesForChart() {
    const container = document.getElementById('industry-checkboxes');
    if (!container) return;

    container.innerHTML = '<div class="loading">加载行业列表...</div>';

    // 获取当前页面中设置的周期和topN值
    const periodSelect = document.getElementById('industry-period-select');
    const topNInput = document.getElementById('top-n-input');
    const selectedPeriod = periodSelect ? periodSelect.value : '30';
    const topN = topNInput ? topNInput.value || 20 : 20;

    fetch(`/api/industry/ranking_data?period=${selectedPeriod}&sector=all&top_n=${topN}`)
    .then(response => response.json())
    .then(data => {
        if (data.success && data.data) {
            // 从行业排行数据中提取行业名称 - 只包括涨幅前N的行业
            const industries = new Set();
            data.data.top_gainers.forEach(item => {
                if (item.industry_name) {
                    industries.add(item.industry_name);
                }
            });

            allIndustryNames = Array.from(industries);

            // 生成复选框
            displayIndustryCheckboxes(allIndustryNames);
        } else {
            container.innerHTML = '<p class="error">加载行业列表失败</p>';
        }
    })
    .catch(error => {
        console.error('加载行业列表失败:', error);
        container.innerHTML = '<p class="error">加载行业列表失败</p>';
    });
}

// 显示行业复选框
function displayIndustryCheckboxes(industries) {
    const container = document.getElementById('industry-checkboxes');
    if (!container) return;

    if (!industries || industries.length === 0) {
        container.innerHTML = '<p>暂无行业数据</p>';
        return;
    }

    let html = '';
    industries.forEach((industry, index) => {
        html += `
            <label class="industry-checkbox-item">
                <input type="checkbox" value="${industry}" onchange="updateSelectedCount()">
                <span>${industry}</span>
            </label>
        `;
    });

    container.innerHTML = html;
    updateSelectedCount();
}

// 更新已选择的行业数量
function updateSelectedCount() {
    const checkboxes = document.querySelectorAll('#industry-checkboxes input[type="checkbox"]:checked');
    const count = checkboxes.length;
    const countSpan = document.getElementById('selected-count');
    if (countSpan) {
        countSpan.textContent = `已选择: ${count} 个行业`;
        countSpan.style.color = count > 10 ? '#ff4d4f' : (count > 0 ? '#52c41a' : '#666');
    }

    // 如果超过10个，禁用更多选择
    const allCheckboxes = document.querySelectorAll('#industry-checkboxes input[type="checkbox"]');
    allCheckboxes.forEach(cb => {
        if (!cb.checked && count >= 10) {
            cb.disabled = true;
        } else {
            cb.disabled = false;
        }
    });
}

// 清除行业选择
function clearIndustrySelection() {
    const checkboxes = document.querySelectorAll('#industry-checkboxes input[type="checkbox"]');
    checkboxes.forEach(cb => {
        cb.checked = false;
        cb.disabled = false;
    });
    updateSelectedCount();
}

// 获取选中的行业
function getSelectedIndustries() {
    const checkboxes = document.querySelectorAll('#industry-checkboxes input[type="checkbox"]:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

// 获取当前选中的时间周期
function getSelectedPeriod() {
    const activeBtn = document.querySelector('.period-btn.active');
    return activeBtn ? activeBtn.getAttribute('data-period') : '365';
}

// 渲染行业指数图表
function renderIndustryChart() {
    const industries = getSelectedIndustries();
    const period = getSelectedPeriod();

    if (industries.length === 0) {
        showMessage('请至少选择一个行业', 'error');
        return;
    }

    if (industries.length > 10) {
        showMessage('最多只能选择10个行业', 'error');
        return;
    }

    // 显示加载状态
    const chartContainer = document.getElementById('industry-chart-container');
    chartContainer.innerHTML = '<div class="loading">正在加载图表数据...</div>';

    // 获取图表数据
    fetch('/api/industry/char_data', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            industries: industries,
            period: period + 'D', // 添加'D'后缀表示天数
            use_growth_rate: true // 默认使用增长率
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            initECharts(data.data, period);
        } else {
            chartContainer.innerHTML = `<div class="error">加载图表数据失败: ${data.message}</div>`;
            showMessage(data.message, 'error');
        }
    })
    .catch(error => {
        console.error('加载图表数据异常:', error);
        chartContainer.innerHTML = `<div class="error">加载图表数据异常: ${error.message}</div>`;
        showMessage('加载图表数据异常', 'error');
    });
}

// 初始化ECharts图表
let resizeHandlerIndustry = null;

function initECharts(chartData, period) {
    const chartContainer = document.getElementById('industry-chart-container');

    // 检查容器是否仍然存在于DOM中
    if (!chartContainer) {
        console.warn('行业图表容器不存在，无法初始化图表');
        return;
    }

    // 销毁现有的图表实例
    if (industryChart) {
        try {
            if (typeof industryChart.isDisposed === 'function' && !industryChart.isDisposed()) {
                industryChart.dispose();
            } else if (typeof industryChart.isDisposed === 'undefined') {
                industryChart.dispose();
            }
        } catch (error) {
            console.warn('销毁行业图表实例时出错:', error);
        }
        industryChart = null;
    }

    // 移除之前的resize事件监听器
    if (resizeHandlerIndustry) {
        window.removeEventListener('resize', resizeHandlerIndustry);
        resizeHandlerIndustry = null;
    }

    // 清空容器
    chartContainer.innerHTML = '';
    chartContainer.style.height = '600px';

    // 创建ECharts实例
    try {
        industryChart = echarts.init(chartContainer);
    } catch (error) {
        console.error('初始化行业ECharts实例失败:', error);
        return;
    }

    // 获取日期和系列数据
    const dates = chartData.dates || [];
    const seriesData = chartData.series || {};

    // 构建ECharts配置
    const colors = [
        '#ff4d4f', '#1890ff', '#52c41a', '#faad14', '#722ed1',
        '#eb2f96', '#13c2c2', '#fa8c16', '#a0d911', '#2f54eb'
    ];

    const series = Object.entries(seriesData).map(([name, data], index) => ({
        name: name,
        type: 'line',
        data: data,
        smooth: true,
        symbol: 'none',
        lineStyle: {
            width: 2
        },
        emphasis: {
            focus: 'series'
        }
    }));

    const option = {
        title: {
            text: '行业指数走势对比',
            left: 'center'
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            },
            formatter: function(params) {
                let result = `<div style="font-weight: bold; margin-bottom: 5px;">${params[0].axisValue}</div>`;
                params.forEach(param => {
                    const value = param.value !== null ? param.value.toFixed(2) : 'N/A';
                    result += `<div style="display: flex; align-items: center; margin: 2px 0;">
                        <span style="display: inline-block; width: 10px; height: 10px; background: ${param.color}; margin-right: 5px; border-radius: 50%;"></span>
                        <span style="margin-right: 10px;">${param.seriesName}:</span>
                        <span style="font-weight: bold;">${value}</span>
                    </div>`;
                });
                return result;
            }
        },
        legend: {
            type: 'scroll',
            orient: 'horizontal',
            bottom: 10,
            data: Object.keys(seriesData)
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '15%',
            top: '10%',
            containLabel: true
        },
        toolbox: {
            feature: {
                saveAsImage: {
                    title: '保存图片'
                },
                dataZoom: {
                    title: {
                        zoom: '区域缩放',
                        back: '还原'
                    }
                },
                restore: {
                    title: '还原'
                }
            }
        },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: dates,
            axisLabel: {
                formatter: function(value) {
                    // 简化日期显示
                    const date = new Date(value);
                    return `${date.getMonth() + 1}/${date.getDate()}`;
                }
            }
        },
        yAxis: {
            type: 'value',
            name: '指数',
            axisLabel: {
                formatter: function(value) {
                    return value.toFixed(0);
                }
            }
        },
        dataZoom: [
            {
                type: 'inside',
                start: 0,
                end: 100
            },
            {
                type: 'slider',
                start: 0,
                end: 100
            }
        ],
        series: series
    };

    // 设置图表配置
    industryChart.setOption(option);

    // 创建resize事件处理器
    resizeHandlerIndustry = function() {
        if (industryChart && typeof industryChart.resize === 'function' && !industryChart.isDisposed()) {
            industryChart.resize();
        }
    };

    // 响应窗口大小变化
    window.addEventListener('resize', resizeHandlerIndustry);

    showMessage(`成功加载 ${Object.keys(seriesData).length} 个行业的图表数据`, 'success');
}


function showIndustryConstituents(industryName) {
    // 显示行业成份股
    const industryContainer = document.getElementById('industry-data-container');
    industryContainer.innerHTML = '<div class="loading">加载行业成份股数据中...</div>';
    console.log(`请求行业成份股数据，行业名称: ${industryName}`);

    fetch(`/api/industry/constituents?industry_name=${encodeURIComponent(industryName)}`)
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('收到行业成份股数据响应:', data);
            displayIndustryConstituents(data.data, industryName);
        } else {
            console.error('加载行业成份股数据失败:', data.message);
            industryContainer.innerHTML = `<div class="error">加载行业成份股数据失败: ${data.message}</div>`;
            // 提供返回按钮
            setTimeout(() => {
                showCachedIndustryData(); // 返回到行业排行页面
            }, 300);
        }
    })
    .catch(error => {
        industryContainer.innerHTML = `<div class="error">加载行业成份股数据异常: ${error.message}</div>`;
        // 提供返回按钮
        setTimeout(() => {
            showCachedIndustryData(); // 返回到行业排行页面
        }, 3000);
    });
}

function displayIndustryConstituents(constituents, industryName) {
    const industryContainer = document.getElementById('industry-data-container');

    let htmlContent = `
        <div class="industry-split-layout">
            <div class="industry-control-panel">
                <div class="industry-summary">
                    <h3>${industryName}</h3>
                    <p>行业成份股列表</p>
                </div>
                <div style="margin-top: 20px;">
                    <button onclick="showCachedIndustryData()" class="return-btn">返回行业排行</button>
                </div>
            </div>
            <div class="industry-data-panel">
                <h3>${industryName} - 成份股列表</h3>
    `;

    if (constituents && constituents.length > 0) {
        htmlContent += `
            <p>共 ${constituents.length} 个成份股</p>
            <div id="industry-constituents-table-container"></div>
        `;
        htmlContent += `</div></div>`;
        
        industryContainer.innerHTML = htmlContent;
        
        // 初始化Tabulator表格
        initIndustryConstituentsTable(constituents);
    } else {
        htmlContent += `<p>暂无成份股数据</p>`;
        htmlContent += `</div></div>`;
        industryContainer.innerHTML = htmlContent;
    }
}

function initIndustryConstituentsTable(data) {
    const container = document.getElementById('industry-constituents-table-container');
    
    const columns = [
        {title: "序号", field: "index", width: 60, headerSort: true, 
            formatter: "rownum",
            hozAlign: "center"
        },
        {title: "股票代码", field: "代码", width: 100, headerSort: true},
        {title: "股票名称", field: "名称", width: 120, headerSort: true},
        {title: "涨跌幅", field: "涨跌幅", width: 100, headerSort: true, 
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                const numValue = parseFloat(value);
                const displayValue = !isNaN(numValue) ? numValue.toFixed(2) + '%' : 'N/A';
                const changeClass = !isNaN(numValue) && numValue >= 0 ? 'positive' : 'negative';
                return `<span class="industry-change ${changeClass}">${displayValue}</span>`;
            }
        },
        {title: "价格", field: "最新价", width: 100, headerSort: true, 
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                const numValue = parseFloat(value);
                return !isNaN(numValue) ? numValue.toFixed(2) : 'N/A';
            }
        },
        {title: "成交量", field: "成交量", width: 120, headerSort: true, 
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                return value || 'N/A';
            }
        },
        {title: "流通市值", field: "流通市值", width: 120, headerSort: true,
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                return value || 'N/A';
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
            {column: "涨跌幅", dir: "desc"} // 默认按涨跌幅降序排列
        ],
        rowFormatter: function(row) {
            // 为行添加颜色编码
            const rowData = row.getData();
            const changeValue = rowData['涨跌幅'];
            const changeFloat = changeValue != null && changeValue !== 'NaN' && changeValue !== '' ? parseFloat(changeValue) : NaN;
            if (!isNaN(changeFloat)) {
                const intensity = Math.min(Math.abs(changeFloat) / 10, 1); // 限制在0-1之间
                const bgColor = `rgba(52, 152, 219, ${0.1 + intensity * 0.3})`; // 蓝色系，与分析师表格一致
                row.getElement().style.backgroundColor = bgColor;
            }
        }
    });

    return table;
}

function showCachedIndustryData() {
    // 使用缓存的数据来显示行业排行，避免重新请求API
    const industryContainer = document.getElementById('industry-data-container');

    // 获取当前页面参数
    const periodSelect = document.getElementById('industry-period-select');
    const sectorSelect = document.getElementById('industry-sector-select');
    const topNInput = document.getElementById('top-n-input');

    const selectedPeriod = periodSelect ? periodSelect.value : '30';
    const selectedSector = sectorSelect ? sectorSelect.value : 'all';
    const topN = topNInput ? topNInput.value || 20 : 20;

    // 生成缓存键
    const cacheParams = {
        period: selectedPeriod,
        sector: selectedSector,
        top_n: topN
    };
    const industryCacheKey = IndustryCache.generateKey('industry_data', cacheParams);

    // 检查是否有缓存的行业排行数据且未过期
    const cachedData = IndustryCache.get(industryCacheKey);
    if (cachedData) {
        console.log('使用缓存的行业数据返回行业排行页面');
        displayIndustryData(cachedData, selectedPeriod);

        // 恢复"显示跌幅行业"复选框的状态
        const showLoserCheckbox = document.getElementById('show-loser-industries');
        if (showLoserCheckbox) {
            // 获取当前URL参数或其他方式确定是否应该显示跌幅行业
            // 这里假设我们从某个地方获取这个状态
            // 为了演示，我们保持当前状态
        }
    } else {
        // 如果缓存已过期或不存在，则重新加载数据
        console.log('缓存已过期或不存在，重新加载行业数据');
        loadIndustryData();
    }
}

// 加载行业数据
function loadIndustryData() {
    console.log('正在加载行业数据...');

    // 获取当前页面参数
    const periodSelect = document.getElementById('industry-period-select');
    const sectorSelect = document.getElementById('industry-sector-select');
    const topNInput = document.getElementById('top-n-input');

    const selectedPeriod = periodSelect ? periodSelect.value : '30';
    const selectedSector = sectorSelect ? sectorSelect.value : 'all';
    const topN = topNInput ? topNInput.value || 20 : 20;

    // 显示加载状态
    const industryContainer = document.getElementById('industry-data-container');
    industryContainer.innerHTML = '<div class="loading">正在加载行业数据...</div>';

    // 生成缓存键
    const cacheParams = {
        period: selectedPeriod,
        sector: selectedSector,
        top_n: topN
    };
    const industryCacheKey = IndustryCache.generateKey('industry_data', cacheParams);

    // 尝试从缓存获取数据
    const cachedData = IndustryCache.get(industryCacheKey);
    if (cachedData) {
        console.log('使用缓存的行业数据');
        displayIndustryData(cachedData, selectedPeriod);
        return;
    }

    // 构建API请求URL
    const apiUrl = `/api/industry/ranking_data?period=${selectedPeriod}&sector=${selectedSector}&top_n=${topN}`;

    // 调用API获取数据
    fetch(apiUrl)
    .then(response => response.json())
    .then(data => {
        console.log('收到行业数据:', data);
        if (data.success) {
            // 缓存数据
            IndustryCache.set(industryCacheKey, data.data, 5); // 5分钟缓存

            // 显示数据
            displayIndustryData(data.data, selectedPeriod);
        } else {
            industryContainer.innerHTML = `<div class="error">加载行业数据失败: ${data.message}</div>`;
        }
    })
    .catch(error => {
        console.error('加载行业数据时出错:', error);
        industryContainer.innerHTML = `<div class="error">加载行业数据失败: ${error.message}</div>`;
    });
}

// 显示行业数据
function displayIndustryData(data, period) {
    const industryContainer = document.getElementById('industry-data-container');

    if (!data || !data.top_gainers || !data.top_losers) {
        industryContainer.innerHTML = '<div class="error">行业数据格式错误</div>';
        return;
    }

    let htmlContent = `
        <div class="industry-full-width-panel">
            <div class="industry-summary">
                <h3>行业板块统计摘要</h3>
                <p>获取东财所有行业板块，按照周期${period}天的涨跌幅排行数据</p>
                <p>共${data.total_count}个行业板块， 显示前${data.top_gainers.length}个</p>
            </div>
            <div class="industry-data-panel">
    `;

    if (data.top_gainers && data.top_gainers.length > 0) {
        htmlContent += `
            <h4>涨幅行业</h4>
            <div id="industry-gainers-table-container"></div>
        `;
    } else {
        htmlContent += `<p>暂无涨幅行业数据</p>`;
    }

    const showLoserIndustriesCheckbox = document.getElementById('show-loser-industries');
    const shouldShowLosers = showLoserIndustriesCheckbox ? showLoserIndustriesCheckbox.checked : false;

    if (shouldShowLosers && data.top_losers && data.top_losers.length > 0) {
        htmlContent += `
            <h4>跌幅行业</h4>
            <div id="industry-losers-table-container"></div>
        `;
    } else {
        htmlContent += `<p>暂无跌幅行业数据</p>`;
    }

    htmlContent += `</div></div>`;
    industryContainer.innerHTML = htmlContent;

    // 初始化涨幅行业表格
    if (data.top_gainers && data.top_gainers.length > 0) {
        initIndustryGainersTable(data.top_gainers);
    }

    // 初始化跌幅行业表格
    if (shouldShowLosers && data.top_losers && data.top_losers.length > 0) {
        initIndustryLosersTable(data.top_losers);
    }
}

// 初始化涨幅行业表格
function initIndustryGainersTable(data) {
    const container = document.getElementById('industry-gainers-table-container');
    
    const columns = [
        {title: "排名", field: "rank", width: 60, headerSort: true, 
            formatter: "rownum",
            hozAlign: "center"
        },
        {title: "行业名称", field: "industry_name", width: 150, headerSort: true},
        {title: "涨跌幅(%)", field: "change_pct", width: 100, headerSort: true, 
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                const numValue = typeof value === 'number' ? value : parseFloat(value);
                const displayValue = isNaN(numValue) ? value : (numValue >= 0 ? '+' : '') + numValue.toFixed(2) + '%';
                const changePercentColor = !isNaN(numValue) && numValue >= 0 ? '#28a745' : '#dc3545';
                cell.getElement().style.color = changePercentColor;
                return displayValue;
            }
        },
        {title: "涨跌额", field: "end_price", width: 100, headerSort: true,
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const row = cell.getRow().getData();
                const startPrice = typeof row.start_price === 'number' ? row.start_price : parseFloat(row.start_price);
                const endPrice = typeof row.end_price === 'number' ? row.end_price : parseFloat(row.end_price);

                if (!isNaN(startPrice) && !isNaN(endPrice)) {
                    const changeAmount = endPrice - startPrice;
                    const displayValue = (changeAmount >= 0 ? '+' : '') + changeAmount.toFixed(2);
                    const changeAmountColor = changeAmount >= 0 ? '#28a745' : '#dc3545';
                    cell.getElement().style.color = changeAmountColor;
                    return displayValue;
                } else {
                    return 'N/A';
                }
            }
        },
        {title: "当前指数", field: "end_price", width: 100, headerSort: true,
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                const numValue = typeof value === 'number' ? value : parseFloat(value);
                return !isNaN(numValue) ? numValue.toFixed(2) : 'N/A';
            }
        },
        {title: "操作", field: "industry_name", width: 100, headerSort: false, 
            formatter: function(cell, formatterParams, onRendered) {
                const industryName = cell.getValue();
                return `<button onclick="showIndustryConstituents('${industryName}')">成份股</button>`;
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
            {column: "change_pct", dir: "desc"} // 默认按涨跌幅降序排列
        ],
        rowFormatter: function(row) {
            // 为行添加颜色编码
            const rowData = row.getData();
            const changePercent = typeof rowData.change_pct === 'number' ? rowData.change_pct : parseFloat(rowData.change_pct);
            const intensity = changePercent ? Math.min(Math.abs(changePercent) / 10, 1) : 0; // 限制在0-1之间，假设10%为最大强度
            const bgColor = `rgba(52, 152, 219, ${0.1 + intensity * 0.3})`; // 蓝色系
            row.getElement().style.backgroundColor = bgColor;
        }
    });

    return table;
}

// 初始化跌幅行业表格
function initIndustryLosersTable(data) {
    const container = document.getElementById('industry-losers-table-container');
    
    const columns = [
        {title: "排名", field: "rank", width: 60, headerSort: true, 
            formatter: "rownum",
            hozAlign: "center"
        },
        {title: "行业名称", field: "industry_name", width: 150, headerSort: true},
        {title: "涨跌幅(%)", field: "change_pct", width: 100, headerSort: true, 
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                const numValue = typeof value === 'number' ? value : parseFloat(value);
                const displayValue = isNaN(numValue) ? value : (numValue >= 0 ? '+' : '') + numValue.toFixed(2) + '%';
                const changePercentColor = !isNaN(numValue) && numValue >= 0 ? '#28a745' : '#dc3545';
                cell.getElement().style.color = changePercentColor;
                return displayValue;
            }
        },
        {title: "涨跌额", field: "end_price", width: 100, headerSort: true,
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const row = cell.getRow().getData();
                const startPrice = typeof row.start_price === 'number' ? row.start_price : parseFloat(row.start_price);
                const endPrice = typeof row.end_price === 'number' ? row.end_price : parseFloat(row.end_price);

                if (!isNaN(startPrice) && !isNaN(endPrice)) {
                    const changeAmount = endPrice - startPrice;
                    const displayValue = (changeAmount >= 0 ? '+' : '') + changeAmount.toFixed(2);
                    const changeAmountColor = changeAmount >= 0 ? '#28a745' : '#dc3545';
                    cell.getElement().style.color = changeAmountColor;
                    return displayValue;
                } else {
                    return 'N/A';
                }
            }
        },
        {title: "当前指数", field: "end_price", width: 100, headerSort: true,
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                const numValue = typeof value === 'number' ? value : parseFloat(value);
                return !isNaN(numValue) ? numValue.toFixed(2) : 'N/A';
            }
        },
        {title: "操作", field: "industry_name", width: 100, headerSort: false, 
            formatter: function(cell, formatterParams, onRendered) {
                const industryName = cell.getValue();
                return `<button onclick="showIndustryConstituents('${industryName}')">成份股</button>`;
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
            {column: "change_pct", dir: "asc"} // 跌幅行业按涨跌幅升序排列
        ],
        rowFormatter: function(row) {
            // 为行添加颜色编码
            const rowData = row.getData();
            const changePercent = typeof rowData.change_pct === 'number' ? rowData.change_pct : parseFloat(rowData.change_pct);
            const intensity = changePercent ? Math.min(Math.abs(changePercent) / 10, 1) : 0; // 限制在0-1之间，假设10%为最大强度
            const bgColor = `rgba(52, 152, 219, ${0.1 + intensity * 0.3})`; // 蓝色系
            row.getElement().style.backgroundColor = bgColor;
        }
    });

    return table;
}

// 排序行业表格
function sortIndustryTable(columnIndex) {
    console.log('排序行业表格列:', columnIndex);
    // 这个函数将在后续实现
    console.log('行业表格排序功能待实现');
}