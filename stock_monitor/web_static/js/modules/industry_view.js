// 行业板块页面的JavaScript功能模块

// 添加全局变量用于缓存行业排行数据
let cachedIndustryData = null;
let cachedIndustryPeriod = null;
let cachedIndustryTimestamp = null;
const INDUSTRY_CACHE_DURATION = 5 * 60 * 1000; // 5分钟缓存

// ==================== 行业图表功能 ====================

// 全局变量
let industryChart = null;
let allIndustryNames = [];

// 初始化行业图表页面
document.addEventListener('DOMContentLoaded', function() {
    // 初始化行业多选框
    initIndustryChartPage();
});

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
    
    fetch(`/api/industry_data?period=${selectedPeriod}&sector=all&top_n=${topN}`)
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
    fetch('/api/industry_chart_data', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            industries: industries,
            period: period
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

function loadIndustryData() {
    // 加载行业板块数据
    const industryContainer = document.getElementById('industry-data-container');
    const periodSelect = document.getElementById('industry-period-select');
    const sectorSelect = document.getElementById('industry-sector-select');

    const selectedPeriod = periodSelect ? periodSelect.value : '30';  // 默认为30天
    const selectedSector = sectorSelect ? sectorSelect.value : 'all';
    const topN = document.getElementById('top-n-input') ? document.getElementById('top-n-input').value || 20 : 20;

    // 检查是否有缓存的行业排行数据且未过期
    const now = new Date().getTime();
    if (cachedIndustryData && cachedIndustryPeriod === selectedPeriod && 
        cachedIndustryTimestamp && (now - cachedIndustryTimestamp) < INDUSTRY_CACHE_DURATION) {
        console.log('使用缓存的行业数据');
        displayIndustryData(cachedIndustryData, selectedPeriod);
        return;
    }

    industryContainer.innerHTML = '<div class="loading">正在加载行业数据... <span id="industry-progress">0%</span></div>';

    console.log(`请求行业数据，周期: ${selectedPeriod}, 板块: ${selectedSector}, 前N: ${topN}`);

    // 确保DOM元素渲染完成后再更新进度
    setTimeout(() => {
        const progressElement = document.getElementById('industry-progress');
        if (progressElement) {
            progressElement.textContent = '20%';
        } else {
            console.log('进度元素不存在，跳过更新进度');
        }

        // 调用后端API获取行业数据
        fetch(`/api/industry_data?period=${selectedPeriod}&sector=${selectedSector}&top_n=${topN}`)
        .then(response => {
            const progressElement = document.getElementById('industry-progress');
            if (progressElement) {
                progressElement.textContent = '60%';
            } else {
                console.log('进度元素不存在，跳过更新进度');
            }
            return response.json();
        })
        .then(data => {
            const progressElement = document.getElementById('industry-progress');
            if (progressElement) {
                progressElement.textContent = '100%';
            } else {
                console.log('进度元素不存在，跳过更新进度');
            }
            console.log('收到行业数据响应:', data);
            if (data.success) {
                // 缓存行业排行数据
                cachedIndustryData = data.data;
                cachedIndustryPeriod = selectedPeriod;
                cachedIndustryTimestamp = now;
                displayIndustryData(data.data, selectedPeriod);
            } else {
                industryContainer.innerHTML = `<div class="error">加载行业数据失败: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('加载行业数据时出错:', error);
            industryContainer.innerHTML = `<div class="error">加载行业数据失败: ${error.message}</div>`;
        });
    }, 0);
}

function displayIndustryData(data, period) {
    const industryContainer = document.getElementById('industry-data-container');

    let htmlContent = `
        <div class="industry-summary">
            <h3>行业板块统计 (最近${period}天)</h3>
            <p>遍历所有行业板块，按所选日期计算涨跌幅排名</p>
            <p>共统计 ${data.total_count} 个行业</p>
        </div>
    `;

    // 显示涨幅前N的行业
    if (data.top_gainers && data.top_gainers.length > 0) {
        htmlContent += `
            <h3>涨幅前${data.top_gainers.length}行业</h3>
            <table class="industry-table">
                <thead>
                    <tr>
                        <th>排名</th>
                        <th>行业名称</th>
                        <th>涨跌幅</th>
                        <th>起始价格</th>
                        <th>结束价格</th>
                        <th>起始日期</th>
                        <th>结束日期</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
        `;
        data.top_gainers.forEach((industry, index) => {
            const changeClass = industry.change_pct >= 0 ? 'positive' : 'negative';
            htmlContent += `
                <tr>
                    <td>${index + 1}</td>
                    <td>${industry.industry_name}</td>
                    <td class="industry-change ${changeClass}">${industry.change_pct >= 0 ? '+' : ''}${industry.change_pct}%</td>
                    <td>${industry.start_price.toFixed(2)}</td>
                    <td>${industry.end_price.toFixed(2)}</td>
                    <td>${industry.start_date}</td>
                    <td>${industry.end_date}</td>
                    <td><button onclick="showIndustryConstituents('${industry.industry_name}')">查看成份股</button></td>
                </tr>
            `;
        });
        htmlContent += `</tbody></table>`;
    }

    // 检查是否显示跌幅前N的行业
    const showLoserIndustriesCheckbox = document.getElementById('show-loser-industries');
    const shouldShowLosers = showLoserIndustriesCheckbox ? showLoserIndustriesCheckbox.checked : false;

    // 显示跌幅前N的行业（如果用户选择显示）
    if (shouldShowLosers && data.top_losers && data.top_losers.length > 0) {
        htmlContent += `
            <h3>跌幅前${data.top_losers.length}行业</h3>
            <table class="industry-table">
                <thead>
                    <tr>
                        <th>排名</th>
                        <th>行业名称</th>
                        <th>涨跌幅</th>
                        <th>起始价格</th>
                        <th>结束价格</th>
                        <th>起始日期</th>
                        <th>结束日期</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
        `;
        data.top_losers.forEach((industry, index) => {
            const changeClass = industry.change_pct >= 0 ? 'positive' : 'negative';
            htmlContent += `
                <tr>
                    <td>${index + 1}</td>
                    <td>${industry.industry_name}</td>
                    <td class="industry-change ${changeClass}">${industry.change_pct >= 0 ? '+' : ''}${industry.change_pct}%</td>
                    <td>${industry.start_price.toFixed(2)}</td>
                    <td>${industry.end_price.toFixed(2)}</td>
                    <td>${industry.start_date}</td>
                    <td>${industry.end_date}</td>
                    <td><button onclick="showIndustryConstituents('${industry.industry_name}')">查看成份股</button></td>
                </tr>
            `;
        });
        htmlContent += `</tbody></table>`;
    }

    industryContainer.innerHTML = htmlContent;
}

function showIndustryConstituents(industryName) {
    // 显示行业成份股
    const industryContainer = document.getElementById('industry-data-container');
    industryContainer.innerHTML = '<div class="loading">加载行业成份股数据中...</div>';
    console.log(`请求行业成份股数据，行业名称: ${industryName}`);

    fetch(`/api/industry_constituents?industry_name=${encodeURIComponent(industryName)}`)
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
                loadIndustryData(); // 返回到行业排行页面
            }, 300);
        }
    })
    .catch(error => {
        industryContainer.innerHTML = `<div class="error">加载行业成份股数据异常: ${error.message}</div>`;
        // 提供返回按钮
        setTimeout(() => {
            loadIndustryData(); // 返回到行业排行页面
        }, 3000);
    });
}

function displayIndustryConstituents(constituents, industryName) {
    const industryContainer = document.getElementById('industry-data-container');

    let htmlContent = `
        <div class="industry-summary">
            <h3>${industryName} - 成份股列表</h3>
            <button onclick="showCachedIndustryData()" style="margin-bottom: 15px;">返回行业排行</button>
        </div>
    `;

    if (constituents && constituents.length > 0) {
        htmlContent += `
            <p>共 ${constituents.length} 个成份股</p>
            <table class="industry-table">
                <thead>
                    <tr>
                        <th>序号</th>
                        <th>股票代码</th>
                        <th>股票名称</th>
                        <th>涨跌幅</th>
                        <th>价格</th>
                        <th>成交量</th>
                        <th>流通市值</th>
                    </tr>
                </thead>
                <tbody>
        `;
        constituents.forEach((stock, index) => {
            // 处理涨跌幅数据，防止NaN值
            const changeValue = stock['涨跌幅'];
            const changeFloat = changeValue != null && changeValue !== 'NaN' && changeValue !== '' ? parseFloat(changeValue) : NaN;
            const changeClass = !isNaN(changeFloat) && changeFloat >= 0 ? 'positive' : 'negative';
            const changeDisplay = !isNaN(changeFloat) ? changeFloat.toFixed(2) + '%' : 'N/A';
            
            // 处理最新价数据，防止NaN值
            const priceValue = stock['最新价'];
            const priceFloat = priceValue != null && priceValue !== 'NaN' && priceValue !== '' ? parseFloat(priceValue) : NaN;
            const priceDisplay = !isNaN(priceFloat) ? priceFloat.toFixed(2) : 'N/A';
            
            htmlContent += `
                <tr>
                    <td>${index + 1}</td>
                    <td>${stock['代码'] || 'N/A'}</td>
                    <td>${stock['名称'] || 'N/A'}</td>
                    <td class="industry-change ${changeClass}">${changeDisplay}</td>
                    <td>${priceDisplay}</td>
                    <td>${stock['成交量'] || 'N/A'}</td>
                    <td>${stock['流通市值'] || 'N/A'}</td>
                </tr>
            `;
        });
        htmlContent += `</tbody></table>`;
    } else {
        htmlContent += `<p>暂无成份股数据</p>`;
    }

    htmlContent += `<button onclick="showCachedIndustryData()" style="margin-top: 15px;">返回行业排行</button>`;
    industryContainer.innerHTML = htmlContent;
}

function showCachedIndustryData() {
    // 使用缓存的数据来显示行业排行，避免重新请求API
    const industryContainer = document.getElementById('industry-data-container');

    // 检查是否有缓存的行业排行数据且未过期
    const now = new Date().getTime();
    if (cachedIndustryData && cachedIndustryPeriod && cachedIndustryTimestamp && 
        (now - cachedIndustryTimestamp) < INDUSTRY_CACHE_DURATION) {
        console.log('使用缓存的行业数据返回行业排行页面');
        displayIndustryData(cachedIndustryData, cachedIndustryPeriod);
    } else {
        // 如果缓存已过期或不存在，则重新加载数据
        console.log('缓存已过期或不存在，重新加载行业数据');
        loadIndustryData();
    }
}

// 行业板块页面的初始化函数
function initializeIndustryPage() {
    console.log('行业板块页面初始化完成');
}
