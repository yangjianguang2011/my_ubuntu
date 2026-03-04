// 基金统计页面的JavaScript功能模块

// 缓存工具函数
const FundCache = {
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
                    console.log(`从缓存获取基金数据: ${key}`);
                    return parsed.data;
                } else {
                    // 缓存过期，删除它
                    localStorage.removeItem(key);
                    console.log(`基金缓存已过期并删除: ${key}`);
                }
            }
        } catch (e) {
            console.warn('读取基金缓存失败:', e);
            // 如果解析失败，删除损坏的缓存
            try {
                localStorage.removeItem(key);
            } catch (removeErr) {
                console.error('删除损坏的基金缓存失败:', removeErr);
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
            console.log(`基金数据已缓存: ${key}, 过期时间: ${ttlMinutes}分钟`);
        } catch (e) {
            console.warn('设置基金缓存失败，可能是存储空间不足:', e);
        }
    },

    // 清除特定缓存
    clear: function(key) {
        try {
            localStorage.removeItem(key);
            console.log(`基金缓存已清除: ${key}`);
        } catch (e) {
            console.error('清除基金缓存失败:', e);
        }
    },

    // 清除所有基金相关缓存
    clearAll: function() {
        try {
            Object.keys(localStorage).forEach(key => {
                if (key.startsWith('fund_')) {
                    localStorage.removeItem(key);
                }
            });
            console.log('所有基金缓存已清除');
        } catch (e) {
            console.error('清除所有基金缓存失败:', e);
        }
    }
};

// 加载基金排名
function loadFundRanking() {
    const topN = $('#top-n-fund').val();
    const period = $('#fund-period-select').val();

    // 处理"all"选项，将其转换为一个大数字
    const actualTopN = topN === 'all' ? 9999 : parseInt(topN);

    const cacheParams = {
        top_n: actualTopN,
        period: period
    };
    const cacheKey = FundCache.generateKey('fund_ranking', cacheParams);

    // 尝试从缓存获取数据
    const cachedData = FundCache.get(cacheKey);
    if (cachedData) {
        console.log('使用缓存的基金排名数据');
        renderFundRankingTable(cachedData);
        return;
    }

    // 显示加载状态
    $('#fund-ranking-container').html('<div class="loading">正在加载基金排名数据...</div>');

    $.get(`/api/fund/ranking?top_n=${actualTopN}&period=${period}`, function(response) {
        if (response.success) {
            const data = response.data;
            
            // 缓存数据
            FundCache.set(cacheKey, data, 5); // 5分钟缓存

            renderFundRankingTable(data);
        } else {
            $('#fund-ranking-container').html(`<div class="error">加载基金排名失败: ${response.message}</div>`);
        }
    }).fail(function(xhr, status, error) {
        console.error('加载基金排名失败:', error);
        console.log('错误详情:', xhr.responseText);
        $('#fund-ranking-container').html(`<div class="error">加载基金排名失败: ${error}</div>`);
    });
}

// 渲染基金排名表格
function renderFundRankingTable(data) {
    // 获取当前页面参数
    const topN = $('#top-n-fund').val();
    const period = $('#fund-period-select').val();

    // 处理显示文本，如果topN是9999，则显示"所有"
    const displayTopN = topN === 'all' ? '所有' : data.top_n;

    // 创建带统计信息的布局
    const containerHtml = `
        <div class="fund-full-width-panel active-page">
            <div class="fund-summary">
                <h3>基金排名统计摘要</h3>
                <p>基于动态选择的基金列表，按照周期 ${period}天的涨跌幅排行数据</p>
                <p>共${data.total_count}个基金， 显示前${displayTopN}个</p>
            </div>
            <div class="fund-data-panel">
                <div id="fund-ranking-table-container"></div>
            </div>
        </div>
    `;

    $('#fund-ranking-container').html(containerHtml);

    let rankingData = [...data.top_gainers];
    // 初始化Tabulator表格
    initFundRankingTable(rankingData);
}

// 初始化基金排名表格
function initFundRankingTable(data) {
    const container = document.getElementById('fund-ranking-table-container');

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
                return !isNaN(numValue) ? numValue.toFixed(4) : 'N/A';
            }
        },
        {title: "涨跌额", field: "change_amount", width: 100, headerSort: true,
            sorter: "number",
            formatter: function(cell, formatterParams, onRendered) {
                const value = cell.getValue();
                const numValue = typeof value === 'number' ? value : parseFloat(value);
                const displayValue = isNaN(numValue) ? value : (numValue >= 0 ? '+' : '') + numValue.toFixed(4);
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

// 初始化基金图表页面
function initializeFundChartPage() {
    // 绑定时间周期按钮事件
    const periodBtns = document.querySelectorAll('#fund-monitor-page .period-btn');
    periodBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // 移除其他按钮的active状态
            periodBtns.forEach(b => b.classList.remove('active'));
            // 添加当前按钮的active状态
            this.classList.add('active');
        });
    });

    // 绑定生成图表按钮事件
    const renderBtn = document.getElementById('render-fund-chart-btn');
    if (renderBtn) {
        renderBtn.addEventListener('click', renderFundChart);
    }

    // 绑定清除选择按钮事件
    const clearBtn = document.getElementById('clear-fund-selection-btn');
    if (clearBtn) {
        clearBtn.addEventListener('click', clearFundSelection);
    }

    // 加载基金列表
    loadFundNamesForChart();
}

// 初始化基金图表
function initializeFundChart() {
    // 这是一个空函数，用于兼容性
    console.log('initializeFundChart: 为兼容性定义的空函数');
}

// 加载基金名称列表（用于图表选择）
function loadFundNamesForChart() {
    const container = document.getElementById('fund-checkboxes');
    if (!container) return;

    // 尝试从缓存获取数据
    const cacheKey = FundCache.generateKey('fund_list_for_chart', {sort: 'change_desc'});
    const cachedData = FundCache.get(cacheKey);
    if (cachedData) {
        console.log('使用缓存的基金列表数据');
        displayFundCheckboxes(cachedData);
        return;
    }

    container.innerHTML = '<div class="loading">加载基金列表...</div>';

    // 从API获取动态基金列表，按涨跌幅降序排列
    $.get('/api/fund/dynamic_list?sort=change_desc&top_n=28&period=30D', function(response) {
        if (response.success) {
            const funds = response.data;
            FundCache.set(cacheKey, funds, 5);
            displayFundCheckboxes(funds);
        } else {
            console.warn('动态基金列表获取失败，尝试使用传统基金列表');
            // 如果动态基金列表API失败，回退到传统的基金列表
            $.get('/api/fund/list?sort=change_desc', function(fallbackResponse) {
                if (fallbackResponse.success) {
                    const funds = fallbackResponse.data;
                    FundCache.set(cacheKey, funds, 5); // 2分钟缓存
                    displayFundCheckboxes(funds);
                } else {
                    container.innerHTML = '<p class="error">加载基金列表失败</p>';
                }
            }).fail(function() {
                console.error('加载基金列表失败');
                container.innerHTML = '<p class="error">加载基金列表失败</p>';
            });
        }
    }).fail(function() {
        console.warn('动态基金列表API失败，尝试使用传统基金列表');
        // 如果动态基金列表API失败，回退到传统的基金列表
        $.get('/api/fund/list?sort=change_desc', function(fallbackResponse) {
            if (fallbackResponse.success) {
                const funds = fallbackResponse.data;
                FundCache.set(cacheKey, funds, 5); // 5分钟缓存
                displayFundCheckboxes(funds);
            } else {
                container.innerHTML = '<p class="error">加载基金列表失败</p>';
            }
        }).fail(function() {
            console.error('加载基金列表失败');
            container.innerHTML = '<p class="error">加载基金列表失败</p>';
        });
    });
}

// 显示基金复选框
function displayFundCheckboxes(funds) {
    const container = document.getElementById('fund-checkboxes');
    if (!container) return;

    if (!funds || funds.length === 0) {
        container.innerHTML = '<p>暂无基金数据</p>';
        return;
    }

    let html = '';
    funds.forEach((fund, index) => {
        // 检查基金对象的属性结构，适配不同的数据格式
        const fundCode = fund.symbol || fund['基金代码'] || fund.fund_code;
        const fundName = fund.name || fund['基金简称'] || fund.fund_name || fund.基金简称;

        html += `
            <label class="industry-checkbox-item">
                <input type="checkbox" value="${fundCode}" onchange="updateFundSelectedCount()">
                <span>${fundName} (${fundCode})</span>
            </label>
        `;
    });

    container.innerHTML = html;
    updateFundSelectedCount();
}

// 更新已选择的基金数量
function updateFundSelectedCount() {
    const checkboxes = document.querySelectorAll('#fund-checkboxes input[type="checkbox"]:checked');
    const count = checkboxes.length;
    const countSpan = document.getElementById('fund-selected-count');
    if (countSpan) {
        countSpan.textContent = `已选择: ${count} 个基金`;
        countSpan.style.color = count > 10 ? '#ff4d4f' : (count > 0 ? '#52c41a' : '#666');
    }

    // 如果超过10个，禁用更多选择
    const allCheckboxes = document.querySelectorAll('#fund-checkboxes input[type="checkbox"]');
    allCheckboxes.forEach(cb => {
        if (!cb.checked && count >= 10) {
            cb.disabled = true;
        } else {
            cb.disabled = false;
        }
    });
}

// 清除基金选择
function clearFundSelection() {
    const checkboxes = document.querySelectorAll('#fund-checkboxes input[type="checkbox"]');
    checkboxes.forEach(cb => {
        cb.checked = false;
        cb.disabled = false;
    });
    updateFundSelectedCount();
}

// 获取选中的基金
function getSelectedFunds() {
    const checkboxes = document.querySelectorAll('#fund-checkboxes input[type="checkbox"]:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

// 获取当前选中的时间周期
function getSelectedFundPeriod() {
    const activeBtn = document.querySelector('#fund-monitor-page .period-btn.active');
    return activeBtn ? activeBtn.getAttribute('data-period') : '365';
}

// 渲染基金图表
function renderFundChart() {
    const funds = getSelectedFunds();
    const period = getSelectedFundPeriod();

    if (funds.length === 0) {
        alert('请至少选择一个基金');
        return;
    }

    if (funds.length > 10) {
        alert('最多只能选择10个基金');
        return;
    }

    // 显示加载状态
    const chartContainer = document.getElementById('fund-chart-container');
    chartContainer.innerHTML = '<div class="loading">正在加载图表数据...</div>';

    // 获取图表数据
    $.ajax({
        url: '/api/fund/chart_data',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            symbols: funds,
            period: period + 'D', // 添加'D'后缀表示天数
            use_growth_rate: true // 默认使用增长率
        }),
        success: function(response) {
            if (response.success) {
                initFundECharts(response.data, period);
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
let fundChart = null;
let fundResizeHandler = null;

function initFundECharts(chartData, period) {
    const chartContainer = document.getElementById('fund-chart-container');

    // 检查容器是否仍然存在于DOM中
    if (!chartContainer) {
        console.warn('图表容器不存在，无法初始化图表');
        return;
    }

    // 移除之前的resize事件监听器
    if (fundResizeHandler) {
        window.removeEventListener('resize', fundResizeHandler);
        fundResizeHandler = null;
    }

    // 销毁现有的图表实例
    if (fundChart) {
        try {
            // 检查图表实例是否仍然关联到DOM元素
            if (typeof fundChart.getDom === 'function') {
                const chartDom = fundChart.getDom();
                // 只有当DOM元素仍然存在于文档中时才销毁
                if (chartDom && document.contains(chartDom)) {
                    fundChart.dispose();
                }
            } else {
                // 如果无法检查DOM状态，直接尝试销毁
                fundChart.dispose();
            }
        } catch (error) {
            console.warn('销毁图表实例时出错:', error);
        }
        fundChart = null;
    }

    // 清空容器
    chartContainer.innerHTML = '';
    chartContainer.style.height = '600px';

    // 创建ECharts实例
    try {
        fundChart = echarts.init(chartContainer);
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

        // 确保数据格式正确，过滤掉无效数据点
        const validDataPoints = seriesDataPoints.filter(point => {
            // 检查是否为有效的 [timestamp, value] 格式
            return Array.isArray(point) &&
                   point.length === 2 &&
                   typeof point[0] === 'number' &&
                   (typeof point[1] === 'number' || point[1] === null);
        });

        return {
            name: seriesName,
            type: 'line',
            data: validDataPoints, // 使用过滤后的有效数据
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
            text: '基金走势对比',
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
                    if (param.value !== null && param.value !== undefined && param.value !== '-' && param.value[1] !== null) {
                        // 对于时间序列数据，param.value 是 [timestamp, value] 格式
                        const value = Array.isArray(param.value) ? param.value[1] : param.value;
                        if (value !== null && value !== undefined && !isNaN(parseFloat(value))) {
                            result += `<div style="display: flex; align-items: center; margin: 2px 0;">
                                <span style="display: inline-block; width: 10px; height: 10px; background: ${param.color}; margin-right: 5px; border-radius: 50%;"></span>
                                <span style="margin-right: 10px;">${param.seriesName}:</span>
                                <span style="font-weight: bold;">${parseFloat(value).toFixed(2)}%</span>
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
                    // 确保增长率以百分比形式显示
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
    fundChart.setOption(option);

    // 创建resize事件处理器
    fundResizeHandler = function() {
        if (fundChart && typeof fundChart.resize === 'function' && !fundChart.isDisposed()) {
            fundChart.resize();
        }
    };

    // 响应窗口大小变化
    window.addEventListener('resize', fundResizeHandler);
}

console.log('fund_view.js模块已加载，等待按需初始化');