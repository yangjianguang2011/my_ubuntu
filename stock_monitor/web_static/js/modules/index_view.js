// 指数监控页面的JavaScript功能模块

// 初始化指数页面函数（供主页面调用）
function initializeIndexPage() {
    // 初始化页面
    loadIndexOverview();
    loadIndexRanking();
    initializeIndexChartPage(); // 初始化指数图表页面
}

// 加载指数概览
function loadIndexOverview() {
    $.get('/api/index_list', function(response) {
        if (response.success) {
            const indices = response.data;
            $('#total-indices').text(indices.length);
            
            // 计算上涨和下跌指数数量
            const rising = indices.filter(idx => idx.change_percent > 0).length;
            const falling = indices.filter(idx => idx.change_percent < 0).length;
            
            $('#rising-indices').text(rising);
            $('#falling-indices').text(falling);
        }
    }).fail(function() {
        console.error('加载指数概览失败');
    });
}

// 加载指数排名
function loadIndexRanking() {
    const topN = $('#top-n-index').val();
    const period = $('#index-period-select').val();
    const useSinaRanking = $('#use-sina-ranking').prop('checked');

    // 显示加载状态
    $('#index-ranking-container').html('<div class="loading">正在加载指数排名数据...</div>');

    $.get(`/api/index_ranking?top_n=${topN}&period=${period}&use_sina_ranking=${useSinaRanking}`, function(response) {
        if (response.success) {
            const data = response.data;
            let rankingData = [...data.top_gainers]; // 默认显示涨幅榜
            
            // 如果勾选了使用新浪排名，则使用实时数据
            if (useSinaRanking) {
                // 在这里我们暂时保持原样，因为后端需要修改才能支持这个功能
                // 实际上，我们需要将useSinaRanking参数传递给后端API
            }
            
            // 创建排名表格
            const containerId = 'index-ranking-container';
            const tableId = 'index-ranking-table';
            const fullTableId = '#' + tableId;
            
            // 确保容器中有表格元素
            $(`#${containerId}`).html(`<div id="${tableId}"></div>`);
            
            if (window.indexRankingTable) {
                try {
                    // 检查表格容器是否仍然存在于DOM中
                    const tableContainer = document.getElementById(tableId);
                    if (tableContainer && typeof window.indexRankingTable.destroy === 'function') {
                        window.indexRankingTable.destroy();
                    } else {
                        console.warn('表格容器不存在或表格实例已销毁，跳过销毁表格');
                    }
                } catch (error) {
                    console.warn('销毁排名表格时出现错误:', error);
                } finally {
                    window.indexRankingTable = null; // 确保清理引用
                }
            } else {
                console.log('没有存在的表格实例，无需销毁');
            }
            
            // 确保DOM元素存在后再初始化表格
            const tableElement = document.getElementById(tableId);
            if (!tableElement) {
                console.error(`找不到表格元素: ${tableId}`);
                return;
            }
            
            window.indexRankingTable = new Tabulator(`#${tableId}`, {
                data: rankingData,
                layout: "fitDataStretch",
                columns: [
                    {title: "排名", field: "rank", width: 60, hozAlign: "center"},
                    {title: "代码", field: "symbol", width: 100, hozAlign: "center"},
                    {title: "名称", field: "name", width: 150},
                    {title: "当前价格", field: "current_price", width: 120, hozAlign: "right",
                     formatter: "money", formatterParams: {precision: 2, symbol: "", thousand: ",", decimal: "."}},
                    {title: "涨跌额", field: "change_amount", width: 100, hozAlign: "right",
                     formatter: function(cell, formatterParams, onRendered) {
                         const value = cell.getValue();
                         const numValue = typeof value === 'number' ? value : parseFloat(value);
                         const displayValue = isNaN(numValue) ? value : numValue.toFixed(2);
                         if(!isNaN(numValue)) {
                             if(numValue >= 0) {
                                 cell.getElement().style.color = '#28a745'; // 绿色字体
                             } else {
                                 cell.getElement().style.color = '#dc3545'; // 红色字体
                             }
                         }
                         return displayValue;
                     }},
                    {title: "涨跌幅(%)", field: "change_percent", width: 120, hozAlign: "right",
                     formatter: function(cell, formatterParams, onRendered) {
                         const value = cell.getValue();
                         const numValue = typeof value === 'number' ? value : parseFloat(value);
                         const displayValue = isNaN(numValue) ? value : (numValue >= 0 ? '+' : '') + numValue.toFixed(2) + '%';
                         if(!isNaN(numValue)) {
                             if(numValue >= 0) {
                                 cell.getElement().style.color = '#28a745'; // 绿色字体
                             } else {
                                 cell.getElement().style.color = '#dc3545'; // 红色字体
                             }
                         }
                         return displayValue;
                     }}
                ],
                rowClick: function(e, row) {
                    // 点击行时可以添加更多功能
                },
                tableBuilt: function() {

                    // 表格构建完成后执行的操作
                }
            });
        } else {
            $('#index-ranking-container').html(`<div class="error">加载指数排名失败: ${response.message}</div>`);
        }
    }).fail(function(xhr, status, error) {
        console.error('加载指数排名失败:', error);
        console.log('错误详情:', xhr.responseText);
        $('#index-ranking-container').html(`<div class="error">加载指数排名失败: ${error}</div>`);
    });
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

    container.innerHTML = '<div class="loading">加载指数列表...</div>';

    // 从API获取主要指数列表，按涨跌幅降序排列
    $.get('/api/index_list?sort=change_desc', function(response) {
        if (response.success) {
            const indices = response.data;
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
        url: '/api/index_chart_data',
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

// 添加事件监听器到HTML元素
$(document).ready(function() {
    // 绑定刷新指数排名按钮事件
    $('#refresh-index-ranking').click(function() {
        loadIndexRanking();
    });

    // 绑定周期选择变化事件
    $('#index-period-select').change(function() {
        loadIndexRanking();
    });

    // 绑定显示前N个选择变化事件
    $('#top-n-index').change(function() {
        loadIndexRanking();
    });

    // 绑定跌幅指数复选框变化事件
    $('#show-loser-indices').change(function() {
        loadIndexRanking();
    });
});
