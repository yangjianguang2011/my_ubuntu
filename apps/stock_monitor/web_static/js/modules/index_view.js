// 指数统计页面的JavaScript功能模块

// 缓存工具函数
const IndexCache = {
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
                    console.log(`从缓存获取指数数据: ${key}`);
                    return parsed.data;
                } else {
                    // 缓存过期，删除它
                    localStorage.removeItem(key);
                    console.log(`指数缓存已过期并删除: ${key}`);
                }
            }
        } catch (e) {
            console.warn('读取指数缓存失败:', e);
            // 如果解析失败，删除损坏的缓存
            try {
                localStorage.removeItem(key);
            } catch (removeErr) {
                console.error('删除损坏的指数缓存失败:', removeErr);
            }
        }
        return null;
    },

    // 设置缓存数据
    set: function(key, data, ttlMinutes = 1) { // 默认1分钟过期
        try {
            const expiry = new Date().getTime() + (ttlMinutes * 60 * 1000);
            const cacheItem = {
                data: data,
                expiry: expiry
            };
            localStorage.setItem(key, JSON.stringify(cacheItem));
            console.log(`指数数据已缓存: ${key}, 过期时间: ${ttlMinutes}分钟`);
        } catch (e) {
            console.warn('设置指数缓存失败，可能是存储空间不足:', e);
        }
    },

    // 清除特定缓存
    clear: function(key) {
        try {
            localStorage.removeItem(key);
            console.log(`指数缓存已清除: ${key}`);
        } catch (e) {
            console.error('清除指数缓存失败:', e);
        }
    },

    // 清除所有指数相关缓存
    clearAll: function() {
        try {
            Object.keys(localStorage).forEach(key => {
                if (key.startsWith('index_')) {
                    localStorage.removeItem(key);
                }
            });
            console.log('所有指数缓存已清除');
        } catch (e) {
            console.error('清除所有指数缓存失败:', e);
        }
    }
};

// // 加载指数概览
// function loadIndexOverview() {
//     // 尝试从缓存获取数据
//     const cacheKey = IndexCache.generateKey('index_overview', {});
//     const cachedData = IndexCache.get(cacheKey);

//     if (cachedData) {
//         console.log('使用缓存的指数概览数据');
//         updateIndexOverviewDisplay(cachedData);
//         return;
//     }

//     $.get('/api/index/dynamic_list', function(response) {
//         if (response.success) {
//             const indices = response.data;

//             // 缓存数据
//             IndexCache.set(cacheKey, indices, 2); // 2分钟缓存

//             updateIndexOverviewDisplay(indices);
//         }
//     }).fail(function() {
//         console.error('加载指数概览失败');
//     });
// }

// // 更新指数概览显示（基于完整指数列表）
// function updateIndexOverviewDisplay(indices) {
//     // 检查概览元素是否存在，如果不存在则创建
//     let totalIndicesEl = $('#total-indices');
//     let risingIndicesEl = $('#rising-indices');
//     let fallingIndicesEl = $('#falling-indices');

//     if (totalIndicesEl.length === 0 || risingIndicesEl.length === 0 || fallingIndicesEl.length === 0) {
//         // 如果概览元素不存在，创建概览卡片
//         const overviewHtml = `
//             <div class="index-summary">
//                 <h3>指数概览</h3>
//                 <div class="overview-stats">
//                     <div class="stat-item">
//                         <span class="stat-label">总指数数</span>
//                         <span class="stat-value" id="total-indices">${indices.length}</span>
//                     </div>
//                     <div class="stat-item">
//                         <span class="stat-label">上涨指数</span>
//                         <span class="stat-value positive" id="rising-indices">${indices.filter(idx => idx.change_percent > 0).length}</span>
//                     </div>
//                     <div class="stat-item">
//                         <span class="stat-label">下跌指数</span>
//                         <span class="stat-value negative" id="falling-indices">${indices.filter(idx => idx.change_percent < 0).length}</span>
//                     </div>
//                 </div>
//             </div>
//         `;

//         $('.index-control-panel').html(overviewHtml);
//     } else {
//         // 如果元素存在，直接更新数值
//         $('#total-indices').text(indices.length);

//         // 计算上涨和下跌指数数量
//         const rising = indices.filter(idx => idx.change_percent > 0).length;
//         const falling = indices.filter(idx => idx.change_percent < 0).length;

//         $('#rising-indices').text(rising);
//         $('#falling-indices').text(falling);
//     }
// }


// 加载指数排名
function loadIndexRanking() {
    const topN = $('#top-n-index').val();
    const period = $('#index-period-select').val();

    // 处理"all"选项，将其转换为一个大数字
    const actualTopN = topN === 'all' ? 9999 : topN;

    const cacheParams = {
        top_n: actualTopN,
        period: period
    };
    const cacheKey = IndexCache.generateKey('index_ranking', cacheParams);

    // 尝试从缓存获取数据
    const cachedData = IndexCache.get(cacheKey);
    if (cachedData) {
        console.log('使用缓存的指数排名数据');
        renderIndexRankingTable(cachedData);
        return;
    }

    // 显示加载状态
    $('#index-ranking-container').html('<div class="loading">正在加载指数排名数据...</div>');

    // 使用增强的API端点，包含估值数据
    $.get(`/api/index/enhanced_ranking?top_n=${actualTopN}&period=${period}`, function(response) {
        if (response.success) {
            const data = response.data;
            //let rankingData = [...data.top_gainers];

            // 缓存数据
            IndexCache.set(cacheKey, data, 3); // 3分钟缓存

            renderIndexRankingTable(data);
        } else {
            $('#index-ranking-container').html(`<div class="error">加载指数排名失败: ${response.message}</div>`);
        }
    }).fail(function(xhr, status, error) {
        console.error('加载指数排名失败:', error);
        console.log('错误详情:', xhr.responseText);
        $('#index-ranking-container').html(`<div class="error">加载指数排名失败: ${error}</div>`);
    });
}

// 渲染指数排名表格
function renderIndexRankingTable(data) {
    // 获取当前页面参数
    const topN = $('#top-n-index').val();
    const period = $('#index-period-select').val();

    // 处理显示文本，如果topN是9999，则显示"所有"
    const displayTopN = topN === 'all' ? '所有' : data.top_n;

    // 创建带统计信息的布局，将统计信息移到表格上方
    const containerHtml = `
        <div class="index-full-width-panel active-page">
            <div class="index-summary">
                <h3>指数排名统计摘要</h3>
                <p>基于动态选择的指数列表，按照周期 ${period}天的涨跌幅排行数据</p>
                <p>共${data.total_count}个指数， 显示前${displayTopN}个</p>
            </div>
            <div class="index-data-panel">
                <div id="index-ranking-table-container"></div>
            </div>
        </div>
    `;

    $('#index-ranking-container').html(containerHtml);

    let rankingData = [...data.top_gainers];
    // 初始化Tabulator表格
    initIndexRankingTable(rankingData);
}

// 初始化指数排名表格
function initIndexRankingTable(data) {
    const container = document.getElementById('index-ranking-table-container');

    const columns = [
        {title: "排名", field: "rank", width: 60, headerSort: true,
            formatter: "rownum",
            hozAlign: "center"
        },
        {title: "代码", field: "symbol", width: 100, headerSort: true},
        {title: "名称", field: "name", width: 120, headerSort: true},
        {title: "当前价格", field: "current_price", width: 100, headerSort: true,
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                const numValue = typeof value === 'number' ? value : parseFloat(value);
                return !isNaN(numValue) ? numValue.toFixed(2) : 'N/A';
            }
        },
        {title: "涨跌额", field: "change_amount", width: 100, headerSort: true,
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                const numValue = typeof value === 'number' ? value : parseFloat(value);
                const displayValue = isNaN(numValue) ? value : (numValue >= 0 ? '+' : '') + numValue.toFixed(2);
                const changeAmountColor = !isNaN(numValue) && numValue >= 0 ? '#28a745' : '#dc3545';
                cell.getElement().style.color = changeAmountColor;
                return displayValue;
            }
        },
        {title: "涨跌幅(%)", field: "change_percent", width: 100, headerSort: true,
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
        {title: "PE", field: "pe", width: 80, headerSort: true,
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                if (value === null || value === undefined || isNaN(value)) {
                    return 'N/A';
                }
                return parseFloat(value).toFixed(2);
            }
        },
        {title: "PB", field: "pb", width: 80, headerSort: true,
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                if (value === null || value === undefined || isNaN(value)) {
                    return 'N/A';
                }
                return parseFloat(value).toFixed(2);
            }
        },
        {title: "PE百分位", field: "pe_percentile", width: 100, headerSort: true,
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                if (value === null || value === undefined || isNaN(value)) {
                    return 'N/A';
                }
                const percentile = parseFloat(value);
                const displayValue = percentile.toFixed(2) + '%';
                
                // 根据百分位数设置颜色
                let color = '#666'; // 默认灰色
                if (percentile <= 20) {
                    color = '#28a745'; // 绿色 - 低估
                } else if (percentile >= 80) {
                    color = '#dc3545'; // 红色 - 高估
                } else {
                    color = '#ffc107'; // 黄色 - 合理
                }
                
                cell.getElement().style.color = color;
                return displayValue;
            }
        },
        {title: "PB百分位", field: "pb_percentile", width: 100, headerSort: true,
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                if (value === null || value === undefined || isNaN(value)) {
                    return 'N/A';
                }
                const percentile = parseFloat(value);
                const displayValue = percentile.toFixed(2) + '%';
                
                // 根据百分位数设置颜色
                let color = '#666'; // 默认灰色
                if (percentile <= 20) {
                    color = '#28a745'; // 绿色 - 低估
                } else if (percentile >= 80) {
                    color = '#dc3545'; // 红色 - 高估
                } else {
                    color = '#ffc107'; // 黄色 - 合理
                }
                
                cell.getElement().style.color = color;
                return displayValue;
            }
        },
        {title: "估值状态", field: "valuation_status", width: 100, headerSort: true,
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                if (!value || value === '数据不足') {
                    return 'N/A';
                }
                
                // 根据估值状态设置颜色
                let color = '#666'; // 默认灰色
                if (value === '低估') {
                    color = '#28a745'; // 绿色
                } else if (value === '高估') {
                    color = '#dc3545'; // 红色
                } else if (value === '合理') {
                    color = '#ffc107'; // 黄色
                }
                
                cell.getElement().style.color = color;
                return value;
            }
        },
        {title: "LPPL分析", field: "lppl_analysis", width: 120, headerSort: false,
            formatter: function(cell, formatterParams, onRendered) {
                const rowData = cell.getRow().getData();
                const symbol = rowData.symbol;
                const button = document.createElement('button');
                button.innerHTML = 'LPPL分析';
                button.className = 'lppl-analysis-btn';
                button.style.background = 'linear-gradient(45deg, #ff6b6b, #ffa500)';
                button.style.color = 'white';
                button.style.border = 'none';
                button.style.padding = '5px 10px';
                button.style.borderRadius = '4px';
                button.style.cursor = 'pointer';
                button.onclick = function(e) {
                    e.stopPropagation(); // 防止事件冒泡影响表格行的选择
                    runSingleLpplAnalysis(symbol, rowData.name);
                };
                return button;
            },
            cellClick: function(e, cell) {
                // 点击单元格时不执行任何操作，因为按钮有自己的点击事件
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
            {column: "change_percent", dir: "desc"} // 默认按涨跌幅降序排列
        ],
        rowFormatter: function(row) {
            // 为行添加颜色编码
            const rowData = row.getData();
            const changePercent = typeof rowData.change_percent === 'number' ? rowData.change_percent : parseFloat(rowData.change_percent);
            const intensity = changePercent ? Math.min(Math.abs(changePercent) / 10, 1) : 0; // 限制在0-1之间，假设10%为最大强度
            const bgColor = `rgba(52, 152, 219, ${0.1 + intensity * 0.3})`; // 蓝色系，与分析师表格一致
            row.getElement().style.backgroundColor = bgColor;
        }
    });

    return table;
}

// 初始化指数图表页面
function initializeIndexChartPage() {
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
    const renderBtn = document.getElementById('render-index-chart-btn');
    if (renderBtn) {
        renderBtn.addEventListener('click', renderIndexChart);
    }

    // 绑定清除选择按钮事件
    const clearBtn = document.getElementById('clear-index-selection-btn');
    if (clearBtn) {
        clearBtn.addEventListener('click', clearIndexSelection);
    }

    // 加载指数列表
    loadIndexNamesForChart();
}

// 初始化指数图表
function initializeIndexChart() {
    // 这是一个空函数，用于兼容性
    // 在index页面中，图表初始化由initIndexECharts函数处理
    console.log('initializeIndexChart: 为兼容性定义的空函数');
}

// 加载指数名称列表（用于图表选择）
function loadIndexNamesForChart() {
    const container = document.getElementById('index-checkboxes');
    if (!container) return;

    // 尝试从缓存获取数据
    const cacheKey = IndexCache.generateKey('index_list_for_chart', {sort: 'change_desc'});
    const cachedData = IndexCache.get(cacheKey);
    if (cachedData) {
        console.log('使用缓存的指数列表数据');
        displayIndexCheckboxes(cachedData);
        return;
    }

    container.innerHTML = '<div class="loading">加载指数列表...</div>';

    // 从API获取主要指数列表，按涨跌幅降序排列
    $.get('/api/index/dynamic_list?sort=change_desc', function(response) {
        if (response.success) {
            const indices = response.data;

            // 缓存数据
            IndexCache.set(cacheKey, indices, 2); // 2分钟缓存

            displayIndexCheckboxes(indices);
        } else {
            container.innerHTML = '<p class="error">加载指数列表失败</p>';
        }
    }).fail(function() {
        console.error('加载指数列表失败');
        container.innerHTML = '<p class="error">加载指数列表失败</p>';
    });
}

// 显示指数复选框
function displayIndexCheckboxes(indices) {
    const container = document.getElementById('index-checkboxes');
    if (!container) return;

    if (!indices || indices.length === 0) {
        container.innerHTML = '<p>暂无指数数据</p>';
        return;
    }

    let html = '';
    indices.forEach((index, indexNum) => {
        html += `
            <label class="industry-checkbox-item">
                <input type="checkbox" value="${index.symbol}" onchange="updateIndexSelectedCount()">
                <span>${index.name} (${index.symbol})</span>
            </label>
        `;
    });

    container.innerHTML = html;
    updateIndexSelectedCount();
}

// 更新已选择的指数数量
function updateIndexSelectedCount() {
    const checkboxes = document.querySelectorAll('#index-checkboxes input[type="checkbox"]:checked');
    const count = checkboxes.length;
    const countSpan = document.getElementById('index-selected-count');
    if (countSpan) {
        countSpan.textContent = `已选择: ${count} 个指数`;
        countSpan.style.color = count > 10 ? '#ff4d4f' : (count > 0 ? '#52c41a' : '#666');
    }

    // 如果超过10个，禁用更多选择
    const allCheckboxes = document.querySelectorAll('#index-checkboxes input[type="checkbox"]');
    allCheckboxes.forEach(cb => {
        if (!cb.checked && count >= 10) {
            cb.disabled = true;
        } else {
            cb.disabled = false;
        }
    });
}

// 清除指数选择
function clearIndexSelection() {
    const checkboxes = document.querySelectorAll('#index-checkboxes input[type="checkbox"]');
    checkboxes.forEach(cb => {
        cb.checked = false;
        cb.disabled = false;
    });
    updateIndexSelectedCount();
}

// 获取选中的指数
function getSelectedIndices() {
    const checkboxes = document.querySelectorAll('#index-checkboxes input[type="checkbox"]:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

// 获取当前选中的时间周期
function getSelectedIndexPeriod() {
    const activeBtn = document.querySelector('.period-btn.active');
    return activeBtn ? activeBtn.getAttribute('data-period') : '365';
}

// 渲染指数图表
function renderIndexChart() {
    const indices = getSelectedIndices();
    const period = getSelectedIndexPeriod();

    if (indices.length === 0) {
        alert('请至少选择一个指数');
        return;
    }

    if (indices.length > 10) {
        alert('最多只能选择10个指数');
        return;
    }

    // 显示加载状态
    const chartContainer = document.getElementById('index-chart-container');
    chartContainer.innerHTML = '<div class="loading">正在加载图表数据...</div>';

    // 获取图表数据
    $.ajax({
        url: '/api/index/chart_data',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            symbols: indices,
            period: period + 'D', // 添加'D'后缀表示天数
            use_growth_rate: true // 默认使用增长率
        }),
        success: function(response) {
            if (response.success) {
                initIndexECharts(response.data, period);
            } else {
                chartContainer.innerHTML = `<div class="error">加载图表数据失败: ${response.message}</div>`;
                alert(response.message);
            }
        },
        error: function(xhr, status, error) {
            console.error('加载图表数据异常:', error);
            chartContainer.innerHTML = `<div class="error">加载图表数据异常: ${error}</div>`;
            alert('加载图表数据异常');
        }
    });
}

// 初始化ECharts图表
let indexChart = null;
let resizeHandler = null;

function initIndexECharts(chartData, period) {
    const chartContainer = document.getElementById('index-chart-container');

    // 检查容器是否仍然存在于DOM中
    if (!chartContainer) {
        console.warn('图表容器不存在，无法初始化图表');
        return;
    }

    // 销毁现有的图表实例
    if (indexChart) {
        try {
            if (typeof indexChart.isDisposed === 'function' && !indexChart.isDisposed()) {
                indexChart.dispose();
            } else if (typeof indexChart.isDisposed === 'undefined') {
                indexChart.dispose();
            }
        } catch (error) {
            console.warn('销毁图表实例时出错:', error);
        }
        indexChart = null;
    }

    // 移除之前的resize事件监听器
    if (resizeHandler) {
        window.removeEventListener('resize', resizeHandler);
        resizeHandler = null;
    }

    // 清空容器
    chartContainer.innerHTML = '';
    chartContainer.style.height = '600px';

    // 创建ECharts实例
    try {
        indexChart = echarts.init(chartContainer);
    } catch (error) {
        console.error('初始化ECharts实例失败:', error);
        return;
    }

    // 获取日期和系列数据
    const dates = chartData.dates || [];
    const seriesArray = chartData.series || []; // series现在是一个数组而不是对象

    // 构建ECharts配置
    const colors = [
        '#ff4d4f', '#1890ff', '#52c41a', '#faad14', '#722ed1',
        '#eb2f96', '#13c2c2', '#fa8c16', '#a0d911', '#2f54eb'
    ];

    // 将seriesArray转换为ECharts需要的格式
    const series = seriesArray.map((seriesInfo, index) => {
        // seriesInfo包含name和data字段
        const seriesName = seriesInfo.name;
        const seriesDataPoints = seriesInfo.data || [];
        return {
            name: seriesName,
            type: 'line',
            data: dates.map((date, i) => {
                if (seriesDataPoints[i] !== null && seriesDataPoints[i] !== undefined && seriesDataPoints[i] !== '-') {
                    return [new Date(date).getTime(), seriesDataPoints[i]];
                } else {
                    return [new Date(date).getTime(), null]; // 使用null表示空值，ECharts会自动跳过
                }
            }),
            smooth: true,
            connectNulls: false, // 不连接空值点
            showSymbol: false,
            lineStyle: {
                width: 2
            },
            emphasis: {
                focus: 'series'
            }
        };
    });

    const option = {
        title: {
            text: '指数走势对比',
            left: 'center'
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            },
            formatter: function(params) {
                // 处理时间戳格式的日期
                const date = new Date(params[0].axisValue);
                const formattedDate = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

                let result = `<div style="font-weight: bold; margin-bottom: 5px;">${formattedDate}</div>`;
                params.forEach(param => {
                    // 检查值是否为有效数字
                    if (param.value !== null && param.value !== undefined && param.value !== '-') {
                        const value = parseFloat(param.value);
                        if (!isNaN(value)) {
                            result += `<div style="display: flex; align-items: center; margin: 2px 0;">
                                <span style="display: inline-block; width: 10px; height: 10px; background: ${param.color}; margin-right: 5px; border-radius: 50%;"></span>
                                <span style="margin-right: 10px;">${param.seriesName}:</span>
                                <span style="font-weight: bold;">${value.toFixed(2)}%</span>
                            </div>`;
                        } else {
                            result += `<div style="display: flex; align-items: center; margin: 2px 0;">
                                <span style="display: inline-block; width: 10px; height: 10px; background: ${param.color}; margin-right: 5px; border-radius: 50%;"></span>
                                <span style="margin-right: 10px;">${param.seriesName}:</span>
                                <span style="font-weight: bold;">N/A</span>
                            </div>`;
                        }
                    } else {
                        result += `<div style="display: flex; align-items: center; margin: 2px 0;">
                            <span style="display: inline-block; width: 10px; height: 10px; background: ${param.color}; margin-right: 5px; border-radius: 50%;"></span>
                            <span style="margin-right: 10px;">${param.seriesName}:</span>
                            <span style="font-weight: bold;">N/A</span>
                        </div>`;
                    }
                });
                return result;
            }
        },
        legend: {
            type: 'scroll',
            orient: 'horizontal',
            bottom: 10,
            data: series.map(s => s.name)
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
            type: 'time',
            boundaryGap: false,
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
            name: '增长率(%)',
            axisLabel: {
                formatter: function(value) {
                    return value.toFixed(2) + '%';
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
    indexChart.setOption(option);

    // 创建resize事件处理器
    resizeHandler = function() {
        if (indexChart && typeof indexChart.resize === 'function' && !indexChart.isDisposed()) {
            indexChart.resize();
        }
    };

    // 响应窗口大小变化
    window.addEventListener('resize', resizeHandler);
}



console.log('index_view.js模块已加载，等待按需初始化');

// LPPL分析功能模块
let lpplAnalysisChart = null; // 全局图表变量

function initializeLpplAnalysis() {
    console.log("初始化LPPL分析功能");
    // 顶部的LPPL分析按钮已移除，改为每行添加按钮
    console.log("LPPL分析功能初始化完成（每行添加按钮模式）");
}

// 初始化单个指数的LPPL分析
function initializeSingleIndexLpplAnalysis() {
    console.log("单个指数LPPL分析功能已就绪");
}

function runSingleLpplAnalysis(symbol, indexName) {
    console.log("开始运行单个指数LPPL分析...", symbol, indexName);
    
    // 显示加载提示
    showLpplLoadingIndicator();
    
    // 调用后端API进行LPPL分析
    $.ajax({
        url: '/api/index/lppl_analysis_single',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            symbol: symbol,      // 单个指数代码
            name: indexName,     // 指数名称
            period: '3Y'         // 3年数据进行分析
        }),
        success: function(response) {
            hideLpplLoadingIndicator();
            
            if (response.success) {
                console.log("LPPL分析完成", response.data);
                
                // 将结果包装为与批量分析相同的格式，以便复用显示函数
                const wrappedResult = {};
                wrappedResult[symbol] = response.data;
                
                displayLpplResults(wrappedResult, indexName);  // 传递指数名称
            } else {
                alert(`LPPL分析失败: ${response.message}`);
            }
        },
        error: function(xhr, status, error) {
            hideLpplLoadingIndicator();
            console.error("LPPL分析请求失败:", error);
            alert(`LPPL分析请求失败: ${error}`);
        }
    });
}





function showLpplLoadingIndicator() {
    // 创建加载遮罩层
    const overlay = $(`
        <div id="lppl-loading-overlay" style="
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: 9999;
            display: flex;
            justify-content: center;
            align-items: center;
        ">
            <div style="
                background: white;
                padding: 30px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            ">
                <div style="font-size: 18px; margin-bottom: 15px;">正在进行LPPL泡沫分析...</div>
                <div class="spinner" style="
                    border: 4px solid #f3f3f3;
                    border-top: 4px solid #3498db;
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    animation: spin 1s linear infinite;
                    margin: 0 auto;
                "></div>
                <div style="margin-top: 15px; font-size: 14px; color: #666;">分析可能需要几分钟时间</div>
            </div>
        </div>
    `);
    
    $('body').append(overlay);
    
    // 添加旋转动画CSS
    if (!$('#lppl-spinner-style').length) {
        $('head').append(`
            <style id="lppl-spinner-style">
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        `);
    }
}

function hideLpplLoadingIndicator() {
    $('#lppl-loading-overlay').remove();
}

function displayLpplResults(results, indexName = null) {
    console.log("显示LPPL分析结果", results);
    
    // 获取实际的指数名称，如果indexName未传入则从结果中获取
    let displayName = indexName;
    if (!displayName) {
        // 从结果中获取第一个索引的名称
        const firstKey = Object.keys(results)[0];
        if (results[firstKey] && results[firstKey].index_name) {
            displayName = results[firstKey].index_name;
        } else {
            displayName = firstKey;
        }
    }
    
    // 创建结果展示模态框
    const modalHtml = `
        <div id="lppl-results-modal" class="modal-overlay" style="
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            z-index: 10000;
            display: flex;
            justify-content: center;
            align-items: center;
        ">
            <div class="modal-content" style="
                background: white;
                width: 90%;
                max-width: 1200px;
                max-height: 90vh;
                overflow-y: auto;
                border-radius: 8px;
                padding: 20px;
                position: relative;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <h2>LPPL泡沫分析结果 - ${displayName || '指数'}</h2>
                    <button id="close-lppl-modal" style="
                        background: #e74c3c;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 5px 10px;
                        cursor: pointer;
                    ">关闭</button>
                </div>
                
                <div id="lppl-results-container">
                    <!-- 结果将动态插入 -->
                </div>
                
                <div id="lppl-visualization-container" style="margin-top: 20px; height: 600px; border: 1px solid #ddd; border-radius: 4px;">
                    <!-- ECharts可视化将在此显示 -->
                </div>
            </div>
        </div>
    `;
    
    $('body').append(modalHtml);
    
    // 填充结果数据
    const resultsContainer = $('#lppl-results-container');
    let resultsHtml = '<div class="results-summary"><h3>分析摘要</h3>';
    
    for (const [symbol, result] of Object.entries(results)) {
        if (result.success) {
            const bubbleInfo = result.bubble_info || {};
            resultsHtml += `
                <div style="margin: 15px 0; padding: 15px; border: 1px solid #e0e0e0; border-radius: 6px; background-color: #f9f9f9;">
                    <div style="font-weight: bold; font-size: 16px; margin-bottom: 10px; color: #2c3e50;">
                        指数: ${symbol}
                    </div>
                    <div style="margin: 8px 0;">
                        <span style="font-weight: bold;">风险等级:</span>
                        <span style="color: ${
                            (result.bubble_info && result.bubble_info.risk_level) === '高风险' ? '#e74c3c' : 
                            (result.bubble_info && result.bubble_info.risk_level) === '中风险' ? '#f39c12' : 
                            (result.bubble_info && result.bubble_info.risk_level) === '低风险' ? '#27ae60' : '#7f8c8d'
                        }; font-weight: bold; font-size: 16px; margin-left: 10px;">${(result.bubble_info && result.bubble_info.risk_level) || result.risk_level || 'Unknown'}</span>
                    </div>
                    <div style="margin: 8px 0;">
                        <span style="font-weight: bold;">泡沫评分:</span>
                        <span style="color: #3498db; font-weight: bold; margin-left: 10px;">${((result.bubble_info && result.bubble_info.bubble_score) || result.bubble_score || 0).toFixed(3)}</span>
                    </div>
                    <div style="margin: 8px 0;">
                        <span style="font-weight: bold;">拟合误差(MSE):</span>
                        <span style="color: #9b59b6; font-weight: bold; margin-left: 10px;">${(result.fitting_error || 0).toExponential(3)}</span>
                    </div>
                </div>
            `;
            
            // 添加详细参数信息及解释
            if (result.model_params) {
                resultsHtml += `
                    <div style="margin: 15px 0; padding: 15px; border: 1px solid #3498db; border-radius: 6px; background-color: #ecf0f1;">
                        <div style="font-weight: bold; color: #2980b9; margin-bottom: 10px;">模型参数详情:</div>
                        <table style="width: 100%; border-collapse: collapse; margin-bottom: 10px;">
                            <thead>
                                <tr style="background-color: #d6eaf8;">
                                    <th style="border: 1px solid #bfe0f1; padding: 8px; text-align: left;">参数</th>
                                    <th style="border: 1px solid #bfe0f1; padding: 8px; text-align: left;">数值</th>
                                    <th style="border: 1px solid #bfe0f1; padding: 8px; text-align: left;">含义</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;"><strong>临界时间(tc)</strong></td>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;">${result.model_params.critical_time ? result.model_params.critical_time.toFixed(2) : 'N/A'}</td>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;">系统奇异性发生的时间点，可能对应市场转折点</td>
                                </tr>
                                <tr style="background-color: #f0f7fb;">
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;"><strong>加速参数(m)</strong></td>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;">${result.model_params.acceleration_param ? result.model_params.acceleration_param.toFixed(4) : 'N/A'}</td>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;">价格增长的加速程度，值越大表示加速越快</td>
                                </tr>
                                <tr>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;"><strong>振荡频率(w)</strong></td>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;">${result.model_params.frequency_param ? result.model_params.frequency_param.toFixed(4) : 'N/A'}</td>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;">价格振荡的频率，反映市场情绪的波动节奏</td>
                                </tr>
                                <tr style="background-color: #f0f7fb;">
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;"><strong>偏移参数(A)</strong></td>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;">${result.model_params.offset_param ? result.model_params.offset_param.toFixed(4) : 'N/A'}</td>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;">整体价格水平的基准值</td>
                                </tr>
                                <tr>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;"><strong>泡沫强度(B)</strong></td>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;">${result.model_params.bubble_strength ? result.model_params.bubble_strength.toFixed(4) : 'N/A'}</td>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;">泡沫形成的强度，正值表示泡沫，负值表示反泡沫</td>
                                </tr>
                                <tr style="background-color: #f0f7fb;">
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;"><strong>振荡强度(C)</strong></td>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;">${result.model_params.oscillation_strength ? result.model_params.oscillation_strength.toFixed(4) : 'N/A'}</td>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;">价格振荡的幅度，反映市场波动的剧烈程度</td>
                                </tr>
                                <tr>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;"><strong>相位参数(φ)</strong></td>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;">${result.model_params.phi_param ? result.model_params.phi_param.toFixed(4) : 'N/A'}</td>
                                    <td style="border: 1px solid #bfe0f1; padding: 8px;">振荡的起始相位，影响振荡的初始状态</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                `;
            }
            
            // 添加风险评估解释
            resultsHtml += `
                <div style="margin: 15px 0; padding: 15px; border: 1px solid #f39c12; border-radius: 6px; background-color: #fef9e7;">
                    <div style="font-weight: bold; color: #d35400; margin-bottom: 10px;">风险评估说明:</div>
                    <ul style="margin: 0; padding-left: 20px;">
                        <li>风险等级基于泡沫强度(B)、振荡强度(C)和加速参数(m)等综合计算</li>
                        <li>高风险表示可能存在显著的投机泡沫，市场转折风险较高</li>
                        <li>中风险表示存在一定的投机行为，需要密切关注市场变化</li>
                        <li>低风险表示市场相对稳定，泡沫特征不明显</li>
                        <li>泡沫评分越接近1.0，泡沫特征越明显；越接近0，越稳定</li>
                    </ul>
                </div>
            `;
        } else {
            resultsHtml += `
                <div style="margin: 15px 0; padding: 15px; border: 1px solid #e74c3c; border-radius: 6px; background-color: #fadbd8; color: #c0392b;">
                    <div style="font-weight: bold; font-size: 16px;">指数: ${symbol}</div>
                    <div>分析失败: ${result.error}</div>
                </div>
            `;
        }
    }
    
    resultsHtml += '</div>';
    
    resultsContainer.html(resultsHtml);
    
    // 绑定关闭事件
    $('#close-lppl-modal').on('click', function() {
        $('#lppl-results-modal').remove();
        if (lpplAnalysisChart) {
            lpplAnalysisChart.dispose();
            lpplAnalysisChart = null;
        }
    });
    
    // 创建ECharts可视化
    createSandDanceVisualization(results);
}

function createSandDanceVisualization(results) {
    console.log("开始创建ECharts可视化", results);
    
    // 准备ECharts数据 - 支持多个指数的数据
    let allChartData = [];
    
    // 从结果中提取所有有效的数据
    for (const [symbol, result] of Object.entries(results)) {
        if (result.success && result.residual_analysis) {
            const resAnalysis = result.residual_analysis;
            if (resAnalysis.dates && resAnalysis.residuals && resAnalysis.actual_values && resAnalysis.fitted_values) {
                // 不限制数据点数量，使用所有数据点
                const chartData = {
                    symbol: symbol,
                    dates: resAnalysis.dates,
                    residuals: resAnalysis.residuals,
                    actualPrices: resAnalysis.actual_values,
                    fittedPrices: resAnalysis.fitted_values
                };
                
                allChartData.push(chartData);
                console.log(`为指数 ${symbol} 准备了 ${resAnalysis.dates.length} 个数据点用于ECharts可视化`);
            } else {
                console.warn(`指数 ${symbol} 残差分析数据不完整`, resAnalysis);
            }
        } else {
            console.warn(`指数 ${symbol} 残差分析失败或数据为空`, result);
        }
    }
    
    if (allChartData.length > 0) {
        // 计算残差的标准差，用于确定±80% 阈值线
        let allResiduals = [];
        allChartData.forEach(chartData => {
            allResiduals = allResiduals.concat(chartData.residuals);
        });
        const residualStd = Math.sqrt(allResiduals.reduce((sum, r) => sum + r * r, 0) / allResiduals.length);
        const thresholdPlus = residualStd * 0.8;  // +80% 标准差
        const thresholdMinus = -residualStd * 0.8;  // -80% 标准差
        
        // 获取容器元素
        const chartContainer = document.getElementById('lppl-visualization-container');
        if (!chartContainer) {
            console.error("找不到可视化容器元素 #lppl-visualization-container");
            $('#lppl-visualization-container').html('<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #999;">找不到可视化容器</div>');
            return;
        }
        
        // 清空容器并创建两个图表容器
        chartContainer.innerHTML = `
            <div id="price-comparison-chart" style="height: 300px; margin-bottom: 20px; border: 1px solid #ddd; border-radius: 4px;"></div>
            <div id="residual-analysis-chart" style="height: 300px; border: 1px solid #ddd; border-radius: 4px;"></div>
        `;
        
        // 创建价格对比图表 - 支持多条线
        const priceChartDom = document.getElementById('price-comparison-chart');
        if (priceChartDom) {
            const priceChart = echarts.init(priceChartDom);
            
            // 构建多条线的数据
            let allDates = [];
            let priceSeries = [];
            let legendData = [];
            
            allChartData.forEach((chartData, index) => {
                // 使用第一个图表的数据作为日期轴（假设所有图表的日期是一致的）
                if (allDates.length === 0) {
                    allDates = chartData.dates;
                }
                
                // 实际价格线
                priceSeries.push({
                    name: `${chartData.symbol} 实际价格`,
                    type: 'line',
                    data: chartData.dates.map((dateStr, i) => {
                        const dateParts = dateStr.split('-');
                        const timestamp = new Date(Date.UTC(dateParts[0], dateParts[1] - 1, dateParts[2])).getTime();
                        return [timestamp, chartData.actualPrices[i]];
                    }),
                    smooth: true,
                    lineStyle: {
                        color: getColorByIndex(index * 2),
                        width: 2
                    },
                    showSymbol: false
                });
                
                // 拟合价格线
                priceSeries.push({
                    name: `${chartData.symbol} 拟合价格`,
                    type: 'line',
                    data: chartData.dates.map((dateStr, i) => {
                        const dateParts = dateStr.split('-');
                        const timestamp = new Date(Date.UTC(dateParts[0], dateParts[1] - 1, dateParts[2])).getTime();
                        return [timestamp, chartData.fittedPrices[i]];
                    }),
                    smooth: true,
                    lineStyle: {
                        color: getColorByIndex(index * 2 + 1),
                        width: 1,
                        type: 'dashed'
                    },
                    showSymbol: false
                });
                
                legendData.push(`${chartData.symbol} 实际价格`);
                legendData.push(`${chartData.symbol} 拟合价格`);
            });
            
            const priceOption = {
                title: {
                    text: '价格走势对比',
                    subtext: '实际价格 vs 拟合价格',
                    left: 'center'
                },
                tooltip: {
                    trigger: 'axis',
                    axisPointer: {
                        type: 'cross',
                        label: {
                            backgroundColor: '#6a7985'
                        }
                    },
                    formatter: function(params) {
                        const date = params[0].axisValue;
                        let result = `<div style="font-weight: bold; margin-bottom: 5px;">${date}</div>`;
                        params.forEach(param => {
                            if (param.value && param.value[1] !== null && param.value[1] !== undefined) {
                                result += `<div style="display: flex; align-items: center; margin: 2px 0;">
                                    <span style="display: inline-block; width: 10px; height: 10px; background: ${param.color}; margin-right: 5px; border-radius: 50%;"></span>
                                    <span style="margin-right: 10px;">${param.seriesName}:</span>
                                    <span style="font-weight: bold;">${param.value[1].toFixed(4)}</span>
                                </div>`;
                            }
                        });
                        return result;
                    }
                },
                legend: {
                    data: legendData,
                    top: '10%',
                    type: 'scroll', // 滚动类型，适应大量图例
                    orient: 'horizontal'
                },
                grid: {
                    left: '3%',
                    right: '4%',
                    bottom: '3%',
                    top: '20%',
                    containLabel: true
                },
                xAxis: {
                    type: 'time',
                    boundaryGap: false,
                    axisLabel: {
                        formatter: function(value) {
                            const date = new Date(value);
                            const year = date.getFullYear();
                            const month = date.getMonth() + 1;
                            const day = date.getDate();
                            return `${year}-${month.toString().padStart(2, '0')}-${day.toString().padStart(2, '0')}`;
                        }
                    }
                },
                yAxis: {
                    type: 'value',
                    name: '价格'
                },
                series: priceSeries,
                dataZoom: [
                    {
                        type: 'inside',
                        start: 0,
                        end: 100
                    },
                    {
                        start: 0,
                        end: 100
                    }
                ]
            };
            
            priceChart.setOption(priceOption);
            
            // 处理窗口大小变化
            const priceHandleResize = () => {
                if (priceChart && typeof priceChart.resize === 'function') {
                    priceChart.resize();
                }
            };
            window.addEventListener('resize', priceHandleResize);
        }
        
        // 创建残差分析图表 - 支持多条线
        const residualChartDom = document.getElementById('residual-analysis-chart');
        if (residualChartDom) {
            const residualChart = echarts.init(residualChartDom);
            
            // 构建残差数据
            let residualSeries = [];
            let residualLegendData = [];
            
            allChartData.forEach((chartData, index) => {
                // 残差线
                residualSeries.push({
                    name: `${chartData.symbol} 残差`,
                    type: 'line',
                    data: chartData.dates.map((dateStr, i) => {
                        const dateParts = dateStr.split('-');
                        const timestamp = new Date(Date.UTC(dateParts[0], dateParts[1] - 1, dateParts[2])).getTime();
                        return [timestamp, chartData.residuals[i]];
                    }),
                    smooth: true,
                    lineStyle: {
                        color: getColorByIndex(index),
                        width: 1
                    },
                    showSymbol: false
                });
                
                residualLegendData.push(`${chartData.symbol} 残差`);
            });
            
            // 添加零线
            if (allChartData.length > 0) {
                const firstChart = allChartData[0];
                residualSeries.push({
                    name: '零线',
                    type: 'line',
                    data: firstChart.dates.map((dateStr, i) => {
                        const dateParts = dateStr.split('-');
                        const timestamp = new Date(Date.UTC(dateParts[0], dateParts[1] - 1, dateParts[2])).getTime();
                        return [timestamp, 0];
                    }),
                    lineStyle: {
                        color: '#000',
                        type: 'dashed',
                        width: 1
                    },
                    showSymbol: false,
                    silent: true
                });
                residualLegendData.push('零线');
            }
            
            const residualOption = {
                title: {
                    text: '拟合残差分析',
                    subtext: '残差 vs 时间',
                    left: 'center'
                },
                tooltip: {
                    trigger: 'axis',
                    axisPointer: {
                        type: 'cross',
                        label: {
                            backgroundColor: '#6a7985'
                        }
                    },
                    formatter: function(params) {
                        const date = params[0].axisValue;
                        let result = `<div style="font-weight: bold; margin-bottom: 5px;">${date}</div>`;
                        params.forEach(param => {
                            if (param.value && param.value[1] !== null && param.value[1] !== undefined) {
                                result += `<div style="display: flex; align-items: center; margin: 2px 0;">
                                    <span style="display: inline-block; width: 10px; height: 10px; background: ${param.color}; margin-right: 5px; border-radius: 50%;"></span>
                                    <span style="margin-right: 10px;">${param.seriesName}:</span>
                                    <span style="font-weight: bold;">${param.value[1].toFixed(6)}</span>
                                </div>`;
                            }
                        });
                        return result;
                    }
                },
                legend: {
                    data: residualLegendData,
                    top: '10%',
                    type: 'scroll', // 滚动类型，适应大量图例
                    orient: 'horizontal'
                },
                grid: {
                    left: '3%',
                    right: '4%',
                    bottom: '3%',
                    top: '20%',
                    containLabel: true
                },
                xAxis: {
                    type: 'time',
                    boundaryGap: false,
                    axisLabel: {
                        formatter: function(value) {
                            const date = new Date(value);
                            const year = date.getFullYear();
                            const month = date.getMonth() + 1;
                            const day = date.getDate();
                            return `${year}-${month.toString().padStart(2, '0')}-${day.toString().padStart(2, '0')}`;
                        }
                    }
                },
                yAxis: {
                    type: 'value',
                    name: '残差',
                    markLine: {
                        data: [
                            { yAxis: thresholdPlus, name: '+80%', lineStyle: { color: '#ff0000', width: 2 } },
                            { yAxis: thresholdMinus, name: '-80%', lineStyle: { color: '#ff0000', width: 2 } }
                        ],
                        symbol: 'none'
                    }
                },
                series: residualSeries,
                dataZoom: [
                    {
                        type: 'inside',
                        start: 0,
                        end: 100
                    },
                    {
                        start: 0,
                        end: 100
                    }
                ]
            };
            
            residualChart.setOption(residualOption);
            
            // 处理窗口大小变化
            const residualHandleResize = () => {
                if (residualChart && typeof residualChart.resize === 'function') {
                    residualChart.resize();
                }
            };
            window.addEventListener('resize', residualHandleResize);
        }
        
        console.log("双ECharts可视化创建成功，包含", allChartData.length, "个指数的数据");
    } else {
        console.log("没有可用的残差数据进行可视化");
        $('#lppl-visualization-container').html('<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #999;">无可用的残差数据进行可视化</div>');
    }
}

// 辅助函数：根据索引获取不同颜色
function getColorByIndex(index) {
    const colors = [
        '#5470c6', '#fac858', '#ee6666', '#73c0de', '#3ba272',
        '#fc8452', '#9a60b4', '#ea7ccc', '#5933ab', '#3358ab',
        '#ab333a', '#ab8c33', '#33ab54', '#338aab', '#8a33ab'
    ];
    return colors[index % colors.length];
}

// 在页面加载完成后初始化LPPL分析功能
$(document).ready(function() {
    // 等待指数页面完全加载后初始化
    setTimeout(function() {
        initializeLpplAnalysis();
    }, 2000); // 延迟2秒确保页面完全加载
});

console.log('LPPL分析模块已加载');
