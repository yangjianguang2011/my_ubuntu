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