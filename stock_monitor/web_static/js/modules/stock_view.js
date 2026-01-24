// 股票监控模块
// 包含所有与股票监控相关的JavaScript功能

/**
 * 页面加载完成后初始化
 */
document.addEventListener('DOMContentLoaded', function() {
    // 初始化页面导航
    initPageNavigation();
    
    // 默认显示股票监控页面
    showPage('stock-monitor');
    
    // 加载股票列表
    loadStocks();
    loadSettings();
    loadNotificationSettings(); // 加载消息发送设置
    
    // 添加股票表单提交
    const addStockForm = document.getElementById('add-stock-form');
    if (addStockForm) {
        addStockForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // 解析关键价位报警
            const keyPriceAlertsInput = document.getElementById('key-price-alerts').value;
            let keyPriceAlerts = [];
            if (keyPriceAlertsInput) {
                keyPriceAlerts = parseAlertsInput(keyPriceAlertsInput, 'price');
            }
            
            // 解析涨跌幅报警
            const changePctAlertsInput = document.getElementById('change-pct-alerts').value;
            let changePctAlerts = [];
            if (changePctAlertsInput) {
                changePctAlerts = parseAlertsInput(changePctAlertsInput, 'pct');
            }

            const stockData = {
                name: document.getElementById('stock-name').value,
                code: document.getElementById('stock-code').value,
                low_alert_price: parseFloat(document.getElementById('low-price').value) || null,
                high_alert_price: parseFloat(document.getElementById('high-price').value) || null,
                limit_alert: document.getElementById('limit-alert').checked,
                key_price_alerts: keyPriceAlerts,
                change_pct_alerts: changePctAlerts
            };
            
            fetch('/api/stocks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(stockData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage('股票添加成功', 'success');
                    document.getElementById('add-stock-form').reset();
                    loadStocks(); // 重新加载列表
                } else {
                    showMessage(data.message, 'error');
                }
            })
            .catch(error => {
                showMessage('添加股票失败: ' + error.message, 'error');
            });
        });
    }
    
    // 设置表单提交
    const settingsForm = document.getElementById('settings-form');
    if (settingsForm) {
        settingsForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const settingsData = {
                check_interval: parseInt(document.getElementById('check-interval').value),
                market_open_start: document.getElementById('market-open-start').value,
                market_open_end: document.getElementById('market-open-end').value
            };
            
            fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(settingsData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage('设置保存成功', 'success');
                } else {
                    showMessage(data.message, 'error');
                }
            })
            .catch(error => {
                showMessage('保存设置失败: ' + error.message, 'error');
            });
        });
    }
    
    // 立即查询按钮事件
    const refreshAllBtn = document.getElementById('refresh-all-btn');
    if (refreshAllBtn) {
        refreshAllBtn.addEventListener('click', function() {
            refreshAllStocksData();
        });
    }
    
    // 最近更新股票数据页面事件
    const refreshRecentlyUpdatedBtn = document.getElementById('refresh-recently-updated-btn');
    if (refreshRecentlyUpdatedBtn) {
        refreshRecentlyUpdatedBtn.addEventListener('click', function() {
            loadRecentlyUpdatedStocks();
        });
    }

    // 为最近更新控制区域添加样式
    const recentlyUpdatedControls = document.querySelector('.recently-updated-controls');
    if (recentlyUpdatedControls) {
        recentlyUpdatedControls.style.display = 'flex';
        recentlyUpdatedControls.style.alignItems = 'left';
        recentlyUpdatedControls.style.gap = '10px';
        recentlyUpdatedControls.style.marginTop = '10px';
    }
});

/**
 * 初始化页面导航
 */
function initPageNavigation() {
    // 页面导航功能
    const navButtons = document.querySelectorAll('.nav-btn');
    navButtons.forEach(button => {
        button.addEventListener('click', function() {
            const pageId = this.getAttribute('data-page');
            showPage(pageId);
            
            // 更新导航按钮状态
            navButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
        });
    });
}

/**
 * 显示指定页面
 * @param {string} pageId - 页面ID
 */
function showPage(pageId) {
    // 隐藏所有页面内容
    const pages = document.querySelectorAll('.page-content');
    pages.forEach(page => page.classList.remove('active-page'));
    
    // 显示选定页面
    const selectedPage = document.getElementById(`${pageId}-page`);
    if (selectedPage) {
        selectedPage.classList.add('active-page');
    }

    // 更新导航按钮状态
    const navButtons = document.querySelectorAll('.nav-btn');
    navButtons.forEach(btn => btn.classList.remove('active'));
    const activeButton = document.querySelector(`.nav-btn[data-page="${pageId}"]`);
    if (activeButton) {
        activeButton.classList.add('active');
    }

    // 根据页面ID执行特定的初始化函数
    switch(pageId) {
        case 'stock-monitor':
            // 股票监控页面已经通过DOMContentLoaded事件处理
            break;
        case 'analyst-view':
            // 分析师数据页面事件已经绑定
            break;
        case 'industry-index':
            // 行业板块页面事件已经绑定
            break;
        case 'index-monitor':
            // 初始化指数监控页面
            initializeIndexMonitorPage();
            break;
        default:
            break;
    }
}

/**
 * 初始化指数监控页面
 */
function initializeIndexMonitorPage() {
    // 确保只在页面第一次显示时初始化
    // 指数监控功能现在完全在index_view.js中实现
    console.log('指数监控页面初始化已委托给index_view.js模块');
}

/**
 * 绑定指数页面事件
 */
function bindIndexPageEvents() {
    // 此函数现在在index_view.js中实现
    console.log('指数页面事件绑定已委托给index_view.js模块');
}

/**
 * 加载通知设置
 */
function loadNotificationSettings() {
    fetch('/api/notification_settings')
    .then(response => response.json())
    .then(data => {
        // 更新全局消息发送开关按钮的显示状态
        updateGlobalNotificationButton(data.global_notification_enabled);
    })
    .catch(error => {
        console.error('加载消息发送设置失败:', error);
    });
}

/**
 * 更新全局通知按钮状态
 * @param {boolean} enabled - 是否启用
 */
function updateGlobalNotificationButton(enabled) {
    const button = document.getElementById('toggle-global-notification');
    if (button) {
        button.textContent = enabled ? '关闭全部消息' : '开启全部消息';
        button.className = enabled ? 'toggle-btn toggle-on' : 'toggle-btn toggle-off';
    }
}

/**
 * 切换全局通知状态
 */
function toggleGlobalNotification() {
    fetch('/api/notification_settings')
    .then(response => response.json())
    .then(data => {
        const newStatus = !data.global_notification_enabled;
        fetch('/api/global_notification_enabled', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                global_notification_enabled: newStatus
            })
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                updateGlobalNotificationButton(newStatus);
                showMessage(result.message, 'success');
            } else {
                showMessage(result.message, 'error');
            }
        })
        .catch(error => {
            showMessage('更新全局消息发送设置失败: ' + error.message, 'error');
        });
    })
    .catch(error => {
        showMessage('获取当前全局消息发送设置失败: ' + error.message, 'error');
    });
}

/**
 * 切换股票通知状态
 * @param {string} code - 股票代码
 */
function toggleStockNotification(code) {
    fetch(`/api/notification_settings`)
    .then(response => response.json())
    .then(settings => {
        const currentStatus = settings.stock_notification_enabled[code] !== undefined ? settings.stock_notification_enabled[code] : true;
        const newStatus = !currentStatus;
        fetch(`/api/stocks/${code}/notification_enabled`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                notification_enabled: newStatus
            })
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                // 更新按钮显示状态
                const button = document.getElementById(`toggle-stock-${code}`);
                if (button) {
                    button.textContent = newStatus ? '关闭消息' : '开启消息';
                    button.className = newStatus ? 'toggle-btn toggle-on' : 'toggle-btn toggle-off';
                }
                showMessage(result.message, 'success');
            } else {
                showMessage(result.message, 'error');
            }
        })
        .catch(error => {
            showMessage(`更新股票 ${code} 消息发送设置失败: ` + error.message, 'error');
        });
    })
    .catch(error => {
        showMessage(`获取股票 ${code} 消息发送设置失败: ` + error.message, 'error');
    });
}

/**
 * 加载股票列表
 */
function loadStocks() {
    const stocksList = document.getElementById('stocks-list');
    stocksList.innerHTML = '<div class="loading">加载中...</div>';
    
    fetch('/api/stocks')
    .then(response => response.json())
    .then(data => {
        stocksList.innerHTML = '';
        
        if (data.stocks.length === 0) {
            stocksList.innerHTML = '<p>暂无监控股票</p>';
            return;
        }
        
        // 获取消息发送设置
        fetch('/api/notification_settings')
        .then(response => response.json())
        .then(notificationSettings => {
            // 将股票分为开启消息和关闭消息两组
            const enabledStocks = [];
            const disabledStocks = [];
            
            data.stocks.forEach(stock => {
                const isNotificationEnabled = notificationSettings.stock_notification_enabled[stock.code] !== undefined ? 
                    notificationSettings.stock_notification_enabled[stock.code] : true;
                
                if (isNotificationEnabled) {
                    enabledStocks.push({stock, isNotificationEnabled});
                } else {
                    disabledStocks.push({stock, isNotificationEnabled});
                }
            });
            
            // 先添加开启消息的股票
            if (enabledStocks.length > 0) {
                const enabledSection = document.createElement('div');
                enabledSection.className = 'stocks-section-enabled';
                enabledSection.innerHTML = '<h3 class="stocks-section-header">开启消息的股票</h3>';
                stocksList.appendChild(enabledSection);
                
                enabledStocks.forEach(item => {
                    const {stock, isNotificationEnabled} = item;
                    const stockItem = document.createElement('div');
                    stockItem.className = 'stock-item';
                    stockItem.innerHTML = `
                        <div class="stock-content">
                            <div class="stock-info">
                                <strong>${stock.name}</strong> (${stock.code}) <span class="current-data" id="current-data-${stock.code}"></span><br>
                                低价报警: ${stock.low_alert_price || '无'} | 高价报警: ${stock.high_alert_price || '无'} | 涨跌停报警: ${stock.limit_alert ? '开启' : '关闭'}<br>
                                关键价位报警: ${formatAlertsDisplay(stock.key_price_alerts, 'price')} | 涨跌幅报警: ${formatAlertsDisplay(stock.change_pct_alerts, 'pct')}
                            </div>
                            <div class="stock-actions">
                                <button id="toggle-stock-${stock.code}" class="toggle-btn ${isNotificationEnabled ? 'toggle-on' : 'toggle-off'}" onclick="toggleStockNotification('${stock.code}')">${isNotificationEnabled ? '关闭消息' : '开启消息'}</button>
                                <button class="refresh-btn" onclick="refreshStockData('${stock.code}')">刷新</button>
                                <button class="update-btn" onclick="editStock('${stock.code}')">编辑</button>
                                <button class="delete-btn" onclick="deleteStock('${stock.code}')">删除</button>
                            </div>
                        </div>
                    `;
                    enabledSection.appendChild(stockItem);
                });
            }
            
            // 再添加关闭消息的股票
            if (disabledStocks.length > 0) {
                const divider = document.createElement('div');
                divider.className = 'stocks-section-divider';
                divider.innerHTML = '<h3 class="stocks-section-header">关闭消息的股票</h3>';
                stocksList.appendChild(divider);
                
                disabledStocks.forEach(item => {
                    const {stock, isNotificationEnabled} = item;
                    const stockItem = document.createElement('div');
                    stockItem.className = 'stock-item';
                    stockItem.innerHTML = `
                        <div class="stock-content">
                            <div class="stock-info">
                                <strong>${stock.name}</strong> (${stock.code}) <span class="current-data" id="current-data-${stock.code}"></span><br>
                                低价报警: ${stock.low_alert_price || '无'} | 高价报警: ${stock.high_alert_price || '无'} | 涨跌停报警: ${stock.limit_alert ? '开启' : '关闭'}<br>
                                关键价位报警: ${formatAlertsDisplay(stock.key_price_alerts, 'price')} | 涨跌幅报警: ${formatAlertsDisplay(stock.change_pct_alerts, 'pct')}
                            </div>
                            <div class="stock-actions">
                                <button id="toggle-stock-${stock.code}" class="toggle-btn ${isNotificationEnabled ? 'toggle-on' : 'toggle-off'}" onclick="toggleStockNotification('${stock.code}')">${isNotificationEnabled ? '关闭消息' : '开启消息'}</button>
                                <button class="refresh-btn" onclick="refreshStockData('${stock.code}')">刷新</button>
                                <button class="update-btn" onclick="editStock('${stock.code}')">编辑</button>
                                <button class="delete-btn" onclick="deleteStock('${stock.code}')">删除</button>
                            </div>
                        </div>
                    `;
                    divider.appendChild(stockItem);
                });
            }
            
            // 如果没有股票，显示提示
            if (enabledStocks.length === 0 && disabledStocks.length === 0) {
                stocksList.innerHTML = '<p>暂无监控股票</p>';
            }

            // 加载完股票列表后，立即获取一次所有股票的实时数据
            setTimeout(() => {
                refreshAllStocksData();
            }, 1000); // 延迟1秒执行，确保DOM元素已渲染完成
        })
        .catch(error => {
            console.error('获取消息发送设置失败:', error);
            // 如果获取失败，按原有逻辑处理
            data.stocks.forEach(stock => {
                const stockItem = document.createElement('div');
                stockItem.className = 'stock-item';
                stockItem.innerHTML = `
                    <div class="stock-content">
                        <div class="stock-info">
                            <strong>${stock.name}</strong> (${stock.code}) <span class="current-data" id="current-data-${stock.code}"></span><br>
                            低价报警: ${stock.low_alert_price || '无'} | 高价报警: ${stock.high_alert_price || '无'} | 涨跌停报警: ${stock.limit_alert ? '开启' : '关闭'}<br>
                            关键价位报警: ${formatAlertsDisplay(stock.key_price_alerts, 'price')} | 涨跌幅报警: ${formatAlertsDisplay(stock.change_pct_alerts, 'pct')}
                        </div>
                        <div class="stock-actions">
                            <button id="toggle-stock-${stock.code}" class="toggle-btn toggle-on" onclick="toggleStockNotification('${stock.code}')">关闭消息</button>
                            <button class="refresh-btn" onclick="refreshStockData('${stock.code}')">刷新</button>
                            <button class="update-btn" onclick="editStock('${stock.code}')">编辑</button>
                            <button class="delete-btn" onclick="deleteStock('${stock.code}')">删除</button>
                        </div>
                    </div>
                `;
                stocksList.appendChild(stockItem);
            });

            // 加载完股票列表后，立即获取一次所有股票的实时数据
            setTimeout(() => {
                refreshAllStocksData();
            }, 1000); // 延迟1秒执行，确保DOM元素已渲染完成
        });
    })
    .catch(error => {
        stocksList.innerHTML = `<div class="error">加载股票列表失败: ${error.message}</div>`;
    });
}

/**
 * 加载设置
 */
function loadSettings() {
    fetch('/api/settings')
    .then(response => response.json())
    .then(settings => {
        document.getElementById('check-interval').value = settings.check_interval;
        document.getElementById('market-open-start').value = settings.market_open_start;
        document.getElementById('market-open-end').value = settings.market_open_end;
    })
    .catch(error => {
        console.error('加载设置失败:', error);
    });
}

/**
 * 删除股票
 * @param {string} code - 股票代码
 */
function deleteStock(code) {
    if (confirm(`确定要删除股票 ${code} 吗？`)) {
        fetch(`/api/stocks/${code}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage('股票删除成功', 'success');
                loadStocks(); // 重新加载列表
            } else {
                showMessage(data.message, 'error');
            }
        })
        .catch(error => {
            showMessage('删除股票失败: ' + error.message, 'error');
        });
    }
}

/**
 * 编辑股票
 * @param {string} code - 股票代码
 */
function editStock(code) {
    // 获取当前股票信息
    fetch(`/api/stocks`)
    .then(response => response.json())
    .then(data => {
        const stock = data.stocks.find(s => s.code === code);
        if (!stock) {
            showMessage(`未找到股票 ${code}`, 'error');
            return;
        }
        
        // 创建编辑弹窗
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <span class="close">&times;</span>
                <h3>编辑股票 - ${stock.name} (${stock.code})</h3>
                <form id="edit-stock-form-${code}">
                    <div class="form-row">
                        <input type="hidden" id="edit-stock-code-${code}" value="${stock.code}">
                        <input type="text" id="edit-stock-name-${code}" placeholder="股票名称" value="${stock.name}" required>
                    </div>
                    
                    <div class="form-row">
                        <input type="number" id="edit-low-price-${code}" placeholder="低价报警价格" step="0.01" value="${stock.low_alert_price || ''}">
                        <input type="number" id="edit-high-price-${code}" placeholder="高价报警价格" step="0.01" value="${stock.high_alert_price || ''}">
                    </div>
                    
                    <div class="form-row">
                        <label>
                            <input type="checkbox" id="edit-limit-alert-${code}" ${stock.limit_alert ? 'checked' : ''}> 涨跌停报警
                        </label>
                    </div>
                    
                    <div class="form-row">
                        <input type="text" id="edit-key-price-alerts-${code}" placeholder="关键价位报警 (格式: 价格:类型,如 64:支撑位,66:压力位)" value="${formatAlertsInput(stock.key_price_alerts, 'price')}">
                    </div>
                    
                    <div class="form-row">
                        <input type="text" id="edit-change-pct-alerts-${code}" placeholder="涨跌幅报警 (格式: 百分比:类型,如 3:警告,5:警报)" value="${formatAlertsInput(stock.change_pct_alerts, 'pct')}">
                    </div>
                    
                    <button type="submit">更新股票</button>
                </form>
            </div>
        `;
        document.body.appendChild(modal);
        
        // 关闭弹窗事件
        const span = modal.querySelector('.close');
        span.onclick = function() {
            modal.style.display = 'none';
            document.body.removeChild(modal);
        };
        
        // 点击弹窗外部关闭
        window.onclick = function(event) {
            if (event.target === modal) {
                modal.style.display = 'none';
                document.body.removeChild(modal);
            }
        };
        
        // 编辑股票表单提交事件
        document.getElementById(`edit-stock-form-${code}`).addEventListener('submit', function(e) {
            e.preventDefault();
            
            // 解析关键价位报警
            const keyPriceAlertsInput = document.getElementById(`edit-key-price-alerts-${code}`).value;
            let keyPriceAlerts = [];
            if (keyPriceAlertsInput) {
                keyPriceAlerts = parseAlertsInput(keyPriceAlertsInput, 'price');
            }
            
            // 解析涨跌幅报警
            const changePctAlertsInput = document.getElementById(`edit-change-pct-alerts-${code}`).value;
            let changePctAlerts = [];
            if (changePctAlertsInput) {
                changePctAlerts = parseAlertsInput(changePctAlertsInput, 'pct');
            }

            const updatedStock = {
                name: document.getElementById(`edit-stock-name-${code}`).value,
                code: document.getElementById(`edit-stock-code-${code}`).value,
                low_alert_price: parseFloat(document.getElementById(`edit-low-price-${code}`).value) || null,
                high_alert_price: parseFloat(document.getElementById(`edit-high-price-${code}`).value) || null,
                limit_alert: document.getElementById(`edit-limit-alert-${code}`).checked,
                key_price_alerts: keyPriceAlerts,
                change_pct_alerts: changePctAlerts
            };
            
            fetch(`/api/stocks/${code}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updatedStock)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage('股票更新成功', 'success');
                    modal.style.display = 'none';
                    document.body.removeChild(modal);
                    loadStocks(); // 重新加载列表
                } else {
                    showMessage(data.message, 'error');
                }
            })
            .catch(error => {
                showMessage('更新股票失败: ' + error.message, 'error');
            });
        });
    })
    .catch(error => {
        showMessage('获取股票信息失败: ' + error.message, 'error');
    });
}

/**
 * 解析报警输入
 * @param {string} inputStr - 输入字符串
 * @param {string} type - 类型 ('price' 或 'pct')
 * @returns {Array} 报警数组
 */
function parseAlertsInput(inputStr, type) {
    /*
     * 解析输入的报警信息
     * 输入格式: "价格:类型,价格:类型" 或 "百分比:类型,百分比:类型"
     * 例如: "64:支撑位,6:压力位" 或 "3:警告,5:警报"
     */
    if (!inputStr) return [];
    
    const alerts = [];
    const items = inputStr.split(',');
    
    for (let item of items) {
        item = item.trim();
        if (!item) continue;
        
        const parts = item.split(':');
        if (parts.length >= 2) {
            const value = parseFloat(parts[0].trim());
            const alertType = parts.slice(1).join(':').trim(); // 防止类型中包含冒号
            
            if (!isNaN(value)) {
                if (type === 'price') {
                    alerts.push({ price: value, type: alertType });
                } else if (type === 'pct') {
                    alerts.push({ pct: value, type: alertType });
                }
            }
        } else if (parts.length === 1) {
            // 如果没有冒号，只提供数值，使用默认类型
            const value = parseFloat(parts[0].trim());
            if (!isNaN(value)) {
                if (type === 'price') {
                    alerts.push({ price: value, type: '关键位' });
                } else if (type === 'pct') {
                    alerts.push({ pct: value, type: '警报' });
                }
            }
        }
    }
    
    return alerts;
}

/**
 * 格式化报警显示
 * @param {Array} alerts - 报警数组
 * @param {string} type - 类型 ('price' 或 'pct')
 * @returns {string} 格式化后的字符串
 */
function formatAlertsDisplay(alerts, type) {
    /*
     * 格式化报警信息用于显示
     * alerts: 报警数组
     * type: 'price' 或 'pct'
     */
    if (!alerts || alerts.length === 0) return '无';
    
    const displayItems = [];
    for (let alert of alerts) {
        if (type === 'price') {
            displayItems.push(`${alert.price}(${alert.type})`);
        } else if (type === 'pct') {
            displayItems.push(`${alert.pct}%(${alert.type})`);
        }
    }
    return displayItems.join(', ');
}

/**
 * 格式化报警输入
 * @param {Array} alerts - 报警数组
 * @param {string} type - 类型 ('price' 或 'pct')
 * @returns {string} 格式化后的字符串
 */
function formatAlertsInput(alerts, type) {
    /*
     * 格式化报警信息用于输入框显示
     * alerts: 报警数组
     * type: 'price' 或 'pct'
     */
    if (!alerts || alerts.length === 0) return '';
    
    const inputItems = [];
    for (let alert of alerts) {
        if (type === 'price') {
            inputItems.push(`${alert.price}:${alert.type}`);
        } else if (type === 'pct') {
            inputItems.push(`${alert.pct}:${alert.type}`);
        }
    }
    return inputItems.join(',');
}

/**
 * 刷新单个股票数据
 * @param {string} code - 股票代码
 */
function refreshStockData(code) {
    // 刷新单个股票的实时数据
    fetch(`/api/stocks/${code}/current_data`)
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const currentData = data.data;
            const currentDataElement = document.getElementById(`current-data-${code}`);
            if (currentDataElement) {
                const changeClass = currentData.change_pct >= 0 ? 'positive' : 'negative';
                currentDataElement.innerHTML = ` [当前: ${currentData.price.toFixed(2)} | 涨跌: ${currentData.change_pct >= 0 ? '+' : ''}${currentData.change_pct.toFixed(2)}% | 更新: ${currentData.update_time}]`;
                currentDataElement.className = `current-data ${changeClass}`;
            }
        } else {
            showMessage(`获取股票 ${code} 数据失败: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        showMessage(`获取股票 ${code} 数据失败: ${error.message}`, 'error');
    });
}

/**
 * 刷新所有股票数据
 */
function refreshAllStocksData() {
    // 刷新所有股票的实时数据
    fetch('/api/stocks/current_data')
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const allData = data.data;
            for (const code in allData) {
                const currentData = allData[code];
                const currentDataElement = document.getElementById(`current-data-${code}`);
                if (currentDataElement) {
                    const changeClass = currentData.change_pct >= 0 ? 'positive' : 'negative';
                    currentDataElement.innerHTML = ` [当前: ${currentData.price.toFixed(2)} | 涨跌: ${currentData.change_pct >= 0 ? '+' : ''}${currentData.change_pct.toFixed(2)}% | 更新: ${currentData.update_time}]`;
                    currentDataElement.className = `current-data ${changeClass}`;
                }
            }
            showMessage('所有股票数据刷新成功', 'success');
        } else {
            showMessage(`获取数据失败: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        showMessage(`获取数据失败: ${error.message}`, 'error');
    });
}

/**
 * 显示消息
 * @param {string} message - 消息内容
 * @param {string} type - 消息类型
 */
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

/**
 * 打开东方财富同行比较页面
 * @param {string} symbol - 股票代码
 */
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

/**
 * 显示股票历史分析师跟踪图表
 * @param {string} stockCode - 股票代码
 */
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

/**
 * 加载历史数据并渲染图表
 * @param {string} stockCode - 股票代码
 * @param {Object} modal - 模态框对象
 */
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

/**
 * 渲染历史分析师跟踪图表
 * @param {string} stockCode - 股票代码
 * @param {Object} chartData - 图表数据
 * @param {Object} modal - 模态框对象
 */
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

/**
 * 加载标签页数据
 * @param {string} symbol - 股票代码
 * @param {string} tabName - 标签页名称
 */
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

/**
 * 加载最近更新的股票数据
 */
function loadRecentlyUpdatedStocks() {
    // 实现最近更新股票数据加载逻辑
    console.log('加载最近更新的股票数据...');
    // 这个函数已经在analyst_view.js中实现
}
