// 股票监控模块
// 包含所有与股票监控相关的JavaScript功能

// 常量定义
const CONSTANTS = {
    DEFAULT_REFRESH_INTERVAL: 60, // 改为60秒自动刷新
    NOTIFICATION_TIMEOUT: 3000,
    API_ENDPOINTS: {
        STOCKS: '/api/stocks',
        SETTINGS: '/api/settings',
        NOTIFICATIONS: '/api/notification_settings',
        GLOBAL_NOTIFICATION_ENABLED: '/api/global_notification_enabled'
    }
};

// 工具函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function handleError(operation, error) {
    console.error(`${operation} 失败:`, error);
    showMessage(`${operation} 失败: ${error.message}`, 'error');
}

async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(endpoint, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        return data;
    } catch (error) {
        throw error;
    }
}

// 本地存储相关函数
function saveSettingsToStorage(settings) {
    try {
        localStorage.setItem('stockMonitorSettings', JSON.stringify(settings));
    } catch (error) {
        console.warn('保存设置到本地存储失败:', error);
    }
}

function loadSettingsFromStorage() {
    try {
        const saved = localStorage.getItem('stockMonitorSettings');
        return saved ? JSON.parse(saved) : null;
    } catch (error) {
        console.warn('从本地存储加载设置失败:', error);
        return null;
    }
}

// 保存当前设置到本地存储
function saveCurrentSettings() {
    const settings = {
        checkInterval: document.getElementById('check-interval')?.value,
        marketOpenStart: document.getElementById('market-open-start')?.value,
        marketOpenEnd: document.getElementById('market-open-end')?.value
    };

    if (settings.checkInterval || settings.marketOpenStart || settings.marketOpenEnd) {
        saveSettingsToStorage(settings);
    }
}

// 输入验证函数
function validateStockData(stockData) {
    const errors = [];

    if (!stockData.name || stockData.name.trim() === '') {
        errors.push('股票名称不能为空');
    }

    if (!stockData.code || stockData.code.trim() === '') {
        errors.push('股票代码不能为空');
    }

    if (stockData.low_alert_price !== null && stockData.high_alert_price !== null &&
        typeof stockData.low_alert_price === 'number' && typeof stockData.high_alert_price === 'number' &&
        stockData.low_alert_price >= stockData.high_alert_price) {
        errors.push('低价报警价格必须小于高价报警价格');
    }

    return {
        isValid: errors.length === 0,
        errors
    };
}

// 创建股票项的辅助函数
function createStockItem(stock, isNotificationEnabled) {
    const stockItem = document.createElement('div');
    stockItem.className = 'stock-item';
    stockItem.innerHTML = `
        <div class="stock-content">
            <div class="stock-info" data-code="${stock.code}">
                <strong>${stock.name}</strong> (${stock.code})
                <span class="clock-direction" id="clock-${stock.code}" title="加载中...">⏳</span>
                <span class="current-data" id="current-data-${stock.code}"></span><br>
                低价报警: ${stock.low_alert_price || '无'} | 高价报警: ${stock.high_alert_price || '无'} | 涨跌停报警: ${stock.limit_alert ? '开启' : '关闭'}<br>
                关键价位报警: ${formatAlertsDisplay(stock.key_price_alerts, 'price')} | 涨跌幅报警: ${formatAlertsDisplay(stock.change_pct_alerts, 'pct')}
            </div>
            <div class="stock-actions">
                <button id="toggle-stock-${stock.code}" class="toggle-btn ${isNotificationEnabled ? 'toggle-on' : 'toggle-off'}">${isNotificationEnabled ? '关闭消息' : '开启消息'}</button>
                <button class="refresh-btn">刷新</button>
                <button class="kline-btn" id="kline-${stock.code}">K 线图</button>
                <button class="trend-analyze-btn" id="trend-analyze-${stock.code}">趋势分析</button>
                <button class="update-btn">编辑</button>
                <button class="delete-btn">删除</button>
            </div>
        </div>
    `;
    return stockItem;
}

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
        addStockForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            try {
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

                // 验证输入数据
                const validation = validateStockData(stockData);
                if (!validation.isValid) {
                    showMessage('输入验证失败: ' + validation.errors.join(', '), 'error');
                    return;
                }

                const result = await apiCall(CONSTANTS.API_ENDPOINTS.STOCKS, {
                    method: 'POST',
                    body: JSON.stringify(stockData)
                });

                if (result.success) {
                    showMessage('股票添加成功', 'success');
                    document.getElementById('add-stock-form').reset();
                    loadStocks(); // 重新加载列表
                } else {
                    showMessage(result.message, 'error');
                }
            } catch (error) {
                handleError('添加股票', error);
            }
        });
    }

    // 设置表单提交
    const settingsForm = document.getElementById('settings-form');
    if (settingsForm) {
        settingsForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            try {
                const settingsData = {
                    check_interval: parseInt(document.getElementById('check-interval').value),
                    market_open_start: document.getElementById('market-open-start').value,
                    market_open_end: document.getElementById('market-open-end').value
                };

                const result = await apiCall(CONSTANTS.API_ENDPOINTS.SETTINGS, {
                    method: 'POST',
                    body: JSON.stringify(settingsData)
                });

                if (result.success) {
                    showMessage('设置保存成功', 'success');
                    // 保存到本地存储
                    saveSettingsToStorage({
                        checkInterval: settingsData.check_interval,
                        marketOpenStart: settingsData.market_open_start,
                        marketOpenEnd: settingsData.market_open_end
                    });

                    // 重启自动刷新以应用新的时间设置
                    stopAutoRefresh();
                    startAutoRefresh();
                } else {
                    showMessage(result.message, 'error');
                }
            } catch (error) {
                handleError('保存设置', error);
            }
        });
    }

    // 移除"立即查询"按钮
    const refreshAllBtn = document.getElementById('refresh-all-btn');
    if (refreshAllBtn) {
        refreshAllBtn.remove();
    }

    // 启动自动刷新功能（仅在监控时间内）
    startAutoRefresh();

    // 为最近更新控制区域添加样式
    const recentlyUpdatedControls = document.querySelector('.recently-updated-controls');
    if (recentlyUpdatedControls) {
        recentlyUpdatedControls.style.display = 'flex';
        recentlyUpdatedControls.style.alignItems = 'left';
        recentlyUpdatedControls.style.gap = '10px';
        recentlyUpdatedControls.style.marginTop = '10px';
    }
});

// 趋势交易分析函数
async function analyzeTrendStock(code, name) {
    // 禁用分析按钮防止重复点击
    const analyzeBtn = document.getElementById(`trend-analyze-${code}`);

    try {
        // 显示加载状态
        showTrendLoadingState(code, name);

        if (analyzeBtn) {
            analyzeBtn.disabled = true;
            analyzeBtn.textContent = '趋势分析中...';
        }

        // 直接调用趋势分析API
        const response = await fetch(`/api/trend_analysis/${code}?name=${encodeURIComponent(name)}`);
        const data = await response.json();

        // 隐藏加载状态
        hideTrendLoadingState(code);
        if (analyzeBtn) {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = '趋势分析';
        }

        if (data.success) {
            showTrendAnalysisModal(code, name, data.report, data.timestamp, data.trading_signals);
        } else {
            showMessage(`趋势分析失败: ${data.message}`, 'error');
        }
    } catch (error) {
        hideTrendLoadingState(code);
        if (analyzeBtn) {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = '趋势分析';
        }
        handleError(`趋势分析股票 ${code}`, error);
    }
}

// 显示趋势分析加载状态
function showTrendLoadingState(code, name) {
    const analysisResultDiv = document.getElementById(`trend-analysis-result-${code}`);
    if (analysisResultDiv) {
        analysisResultDiv.innerHTML = `
            <div class="trend-analysis-progress">
                <div class="spinner"></div>
                <div class="loading-content">
                    <h3>趋势交易AI正在分析中...</h3>
                    <p>正在分析 ${name}(${code})</p>
                    <div class="progress-status">
                        <span class="status-message">基于趋势交易理论进行深度分析...</span>
                    </div>
                    <div class="estimated-time">
                        <small>分析时间: 5-15秒</small>
                    </div>
                </div>
            </div>
        `;
    } else {
        // 如果没有专门的分析结果显示区域，创建一个临时的
        const stockItem = document.querySelector(`#trend-analyze-${code}`).closest('.stock-item');
        const stockActions = stockItem.querySelector('.stock-actions');
        const tempDiv = document.createElement('div');
        tempDiv.id = `trend-analysis-result-${code}`;
        tempDiv.className = 'trend-analysis-result';
        tempDiv.innerHTML = `
            <div class="trend-analysis-progress">
                <div class="spinner"></div>
                <div class="loading-content">
                    <h3>趋势交易AI正在分析中...</h3>
                    <p>正在分析 ${name}(${code})</p>
                    <div class="progress-status">
                        <span class="status-message">基于趋势交易理论进行深度分析...</span>
                    </div>
                    <div class="estimated-time">
                        <small>分析时间: 5-15秒</small>
                    </div>
                </div>
            </div>
        `;
        stockActions.parentNode.insertBefore(tempDiv, stockActions.nextSibling);
    }
}

// 隐藏趋势分析加载状态
function hideTrendLoadingState(code) {
    const analysisResultDiv = document.getElementById(`trend-analysis-result-${code}`);
    if (analysisResultDiv) {
        analysisResultDiv.remove();
    }
}

// 显示趋势分析结果模态框
function showTrendAnalysisModal(code, name, analysis, timestamp, tradingSignals) {
    // 创建分析结果弹窗
    const modal = document.createElement('div');
    modal.className = 'modal';

    // Handle case when analysis is undefined or null
    const analysisContent = analysis ? analysis.replace(/\n/g, '<br>') : '暂无分析结果';

    // 生成买入信号详细信息 HTML
    let buySignalsHtml = '';
    if (tradingSignals && tradingSignals.buy_signals && tradingSignals.buy_signals.length > 0) {
        buySignalsHtml = tradingSignals.buy_signals.map((signal) => {
            const strengthColor = signal.strength === 'STRONG' ? '#c0392b' : signal.strength === 'MEDIUM' ? '#f39c12' : '#27ae60';
            const strengthText = signal.strength === 'STRONG' ? '强' : signal.strength === 'MEDIUM' ? '中' : '弱';
            const conditionsList = signal.conditions_met && signal.conditions_met.length > 0
                ? signal.conditions_met.map(c => '<li>✅ ' + c + '</li>').join('')
                : '<li>无条件满足</li>';
            const stopLossText = signal.stop_loss ? signal.stop_loss.toFixed(2) + ' 元' : '未设置';
            const targetPriceText = signal.target_price && signal.target_price[0]
                ? signal.target_price[0].toFixed(2) + ' ~ ' + (signal.target_price[1] ? signal.target_price[1].toFixed(2) : '∞') + ' 元'
                : '未设置';

            return `
                <div class="buy-signal-card" style="background: linear-gradient(135deg, #e8f5e9 0%, #f1f8e9 100%); border: 1px solid #a5d6a7; border-radius: 8px; padding: 15px; margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <h4 style="margin: 0; color: #2e7d32; font-size: 16px;">
                            <span style="color: #26A69A; font-weight: bold;">✅</span> ${signal.signal}
                        </h4>
                        <span style="background-color: ${strengthColor}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;">
                            ${strengthText}信号
                        </span>
                    </div>
                    <p style="margin: 8px 0; color: #555; font-size: 14px; line-height: 1.5;">
                        <strong>📝 信号描述:</strong> ${signal.description}
                    </p>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; margin-top: 10px;">
                        ${signal.price ? '<p style="margin: 0; color: #666; font-size: 13px;"><strong>💰 当前价:</strong> ' + signal.price.toFixed(2) + ' 元</p>' : ''}
                        ${signal.stop_loss ? '<p style="margin: 0; color: #666; font-size: 13px;"><strong>🛑 止损价:</strong> ' + stopLossText + '</p>' : ''}
                        ${signal.target_price && signal.target_price[0] ? '<p style="margin: 0; color: #666; font-size: 13px;"><strong>🎯 目标价:</strong> ' + targetPriceText + '</p>' : ''}
                    </div>
                    <div style="display: flex; gap: 15px; margin-top: 8px; flex-wrap: wrap;">
                        ${signal.trend_direction ? '<p style="margin: 0; color: #666; font-size: 13px;"><strong>📈 趋势:</strong> ' + signal.trend_direction + '</p>' : ''}
                        ${signal.health_score !== undefined ? '<p style="margin: 0; color: #666; font-size: 13px;"><strong>💪 健康度:</strong> <span style="color: ' + (signal.health_score >= 60 ? '#27ae60' : signal.health_score >= 40 ? '#f39c12' : '#c0392b') + ';">' + signal.health_score + '/100</span></p>' : ''}
                    </div>

                    <div style="margin-top: 12px; padding-top: 10px; border-top: 1px dashed #a5d6a7;">
                        <strong style="color: #2e7d32; font-size: 14px;">✅ 满足条件:</strong>
                        <ul style="margin: 8px 0; padding-left: 20px; color: #555; font-size: 13px; line-height: 1.8;">
                            ${conditionsList}
                        </ul>
                    </div>
                </div>
            `;
        }).join('');
    } else {
        buySignalsHtml = '<div style="padding: 30px; text-align: center; color: #999; background: #f8f9fa; border-radius: 8px; border: 1px dashed #dee2e6;">📭 暂无买入信号</div>';
    }

    modal.innerHTML = `
        <div class="modal-content" style="max-width: 1000px; max-height: 80vh; overflow-y: auto;">
            <span class="close">&times;</span>
            <h3>趋势交易AI分析 - ${name} (${code})</h3>

            <div class="analysis-result">
                <p><strong>分析时间:</strong> ${timestamp}</p>
                <div class="analysis-content" style="white-space: pre-line; line-height: 1.6; margin-top: 15px; font-family: monospace;">
                    ${analysisContent}
                </div>

            </div>

            <!-- 买入信号详细区域 -->
            <div style="margin: 20px 0;">
                <h4 style="color: #2e7d32; margin-bottom: 15px; font-size: 18px; border-bottom: 2px solid #a5d6a7; padding-bottom: 8px;">📈 买入信号详情</h4>
                <div class="buy-signals-container">
                    ${buySignalsHtml}
                </div>
            </div>

            <div style="margin-top: 20px; padding: 10px; background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px;">
                <strong>风险提示:</strong> 趋势交易分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。
            </div>

            <!-- 指标解释区域 -->
            <div class="indicator-explanation" style="margin-top: 20px;">
                <details style="background: #f8f9fa; padding: 15px; border-radius: 5px; border: 1px solid #dee2e6;">
                    <summary style="cursor: pointer; font-weight: bold; color: #2c3e50; padding: 5px 0;">📊 点击查看指标解释</summary>
                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #dee2e6;">
                        <div style="margin-bottom: 20px;">
                            <strong style="color: #2980b9;">📈 趋势斜率</strong>
                            <p style="margin: 8px 0 5px 0; color: #555; font-size: 14px;">使用对数价格计算的日均变化率，表示价格平均每天的变化百分比。</p>
                            <ul style="margin: 5px 0; padding-left: 25px; color: #666; font-size: 14px;">
                                <li><span style="color: #27ae60;">正值</span>：上涨趋势（如 0.5%/日 表示日均上涨 0.5%）</li>
                                <li><span style="color: #c0392b;">负值</span>：下跌趋势（如 -0.5%/日 表示日均下跌 0.5%）</li>
                                <li><span style="color: #8e44ad;">绝对值越大</span>：趋势越陡峭</li>
                            </ul>
                        </div>
                        <div style="margin-bottom: 20px;">
                            <strong style="color: #2980b9;">📊 波动率</strong>
                            <p style="margin: 8px 0 5px 0; color: #555; font-size: 14px;">最近 60 天内最高价与最低价之间的价格波动范围。</p>
                            <ul style="margin: 5px 0; padding-left: 25px; color: #666; font-size: 14px;">
                                <li><span style="color: #27ae60;">&lt; 15%</span>：低波动（适合密集成交区判断）</li>
                                <li><span style="color: #f39c12;">15%-25%</span>：中等波动</li>
                                <li><span style="color: #c0392b;">&gt; 25%</span>：高波动（趋势性行情）</li>
                            </ul>
                        </div>
                        <div style="margin-bottom: 20px;">
                            <strong style="color: #2980b9;">📉 均线集中度</strong>
                            <p style="margin: 8px 0 5px 0; color: #555; font-size: 14px;">衡量短、中、长期均线（MA5/20/60）之间的离散程度。</p>
                            <ul style="margin: 5px 0; padding-left: 25px; color: #666; font-size: 14px;">
                                <li><span style="color: #27ae60;">&lt; 2%</span>：均线高度密集（密集成交区特征）</li>
                                <li><span style="color: #f39c12;">2%-5%</span>：均线适度发散（正常趋势状态）</li>
                                <li><span style="color: #c0392b;">&gt; 5%</span>：均线高度发散（强势趋势）</li>
                            </ul>
                        </div>
                        <div style="margin-bottom: 20px;">
                            <strong style="color: #2980b9;">📊 均线排列状态</strong>
                            <p style="margin: 8px 0 5px 0; color: #555; font-size: 14px;">使用 MA20/MA60/MA120 三条均线判断趋势方向，MA5 作为短期价格参考不参与排列判断。</p>
                            <ul style="margin: 5px 0; padding-left: 25px; color: #666; font-size: 14px;">
                                <li><span style="color: #27ae60;">多头排列</span>：MA20 > MA60 > MA120，且 MA20 比 MA120 高至少 5%</li>
                                <li><span style="color: #c0392b;">空头排列</span>：MA20 < MA60 < MA120，且 MA20 比 MA120 低至少 5%</li>
                                <li><span style="color: #666;">均线缠绕</span>：不满足上述条件，均线交错无明显趋势</li>
                            </ul>
                        </div>
                        <div style="margin-bottom: 20px;">
                            <strong style="color: #2980b9;">🎯 密集成交区</strong>
                            <p style="margin: 8px 0 5px 0; color: #555; font-size: 14px;">60个窗口期内当波动率 &lt; 20% 且 均线集中度 &lt; 5% 时判定为密集成交区（放宽条件）。</p>
                            <ul style="margin: 5px 0; padding-left: 25px; color: #666; font-size: 14px;">
                                <li><span style="color: #27ae60;">边界值</span>：始终返回 60 日窗口内的最高价 (upper_bound) 和最低价 (lower_bound)</li>
                                <li><span style="color: #27ae60;">密集成交区</span>（波动率&lt;20% 且 集中度&lt;5%）：边界值有强参考意义，可能即将突破</li>
                                <li><span style="color: #666;">非密集成交区</span>：边界值表示近期价格运行区间，处于趋势性行情中</li>
                            </ul>
                        </div>
                        <div style="margin-bottom: 20px;">
                            <strong style="color: #2980b9;">🕐 时钟方向（5 类趋势）</strong>
                            <p style="margin: 8px 0 5px 0; color: #555; font-size: 14px;">使用时钟方向形象化表示趋势状态，综合考虑均线排列、趋势斜率和持续时间：</p>
                            <ul style="margin: 5px 0; padding-left: 25px; color: #666; font-size: 14px;">
                                <li><span style="color: #27ae60;">一点钟方向</span>：加速上涨（MA5>MA20>MA60>MA120 + MA20 斜率>0.3%/日 + 持续≥10 天）</li>
                                <li><span style="color: #27ae60;">两点钟方向</span>：稳定上涨（MA20>MA60>MA120 + MA20 斜率>0.1%/日 + 持续≥5 天 + 健康度≥60）</li>
                                <li><span style="color: #f39c12;">三点钟方向</span>：横盘整理（波动率&lt;15% 且 均线集中度&lt;2%）</li>
                                <li><span style="color: #c0392b;">四点钟方向</span>：稳定下跌（MA20<MA60<MA120 + MA20 斜率<-0.1%/日 + 持续≥10 天）</li>
                                <li><span style="color: #c0392b;">五点钟方向</span>：加速下跌（MA5<MA20<MA60 + MA5 斜率<-0.3%/日 + 持续≥10 天）</li>
                            </ul>
                        </div>

                        <!-- 顶底构造 -->
                        <div style="margin-bottom: 20px;">
                            <strong style="color: #2980b9;">🏔️ 顶底构造</strong>
                            <p style="margin: 8px 0 5px 0; color: #555; font-size: 14px;">识别趋势顶部和底部的重要 K 线组合形态：</p>
                            <ul style="margin: 5px 0; padding-left: 25px; color: #666; font-size: 14px;">
                                <li><strong>顶部构造</strong>：lower high（不再创新高）+ lower low（创出新低），是趋势可能见顶的信号</li>
                                <li><strong>底部构造</strong>：higher low（不再创新低）+ higher high（创出新高），是趋势可能见底的信号</li>
                            </ul>
                        </div>

                        <!-- 趋势交易建议 -->
                        <div style="margin-bottom: 20px;">
                            <strong style="color: #2980b9;">📊 趋势健康度评分</strong>
                            <p style="margin: 8px 0 5px 0; color: #555; font-size: 14px;">综合评估趋势质量（0-100 分），基础分 50 分 + 加分项：</p>
                            <ul style="margin: 5px 0; padding-left: 25px; color: #666; font-size: 14px;">
                                <li>有明确趋势（多头/空头排列）：+20 分</li>
                                <li>趋势持续时间 > 10 天：+15 分</li>
                                <li>均线间距适中（1%-10%）：+10 分</li>
                                <li>趋势稳定（MA5 波动率 < 2%）：+5 分</li>
                            </ul>
                        </div>
                    </div>
                </details>
            </div>
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
}

// ==================== K 线图相关函数 ====================

/**
 * 显示 K 线图
 * @param {string} code - 股票代码
 * @param {string} name - 股票名称
 */
async function showKlineChart(code, name) {
    const klineBtn = document.getElementById(`kline-${code}`);

    try {
        // 显示加载状态
        showKlineLoadingState(code, name);

        if (klineBtn) {
            klineBtn.disabled = true;
            klineBtn.textContent = '加载中...';
        }

        // 调用 K 线数据 API（默认 365 天）
        const response = await fetch(`/api/stocks/${code}/kline?period=365`);
        const data = await response.json();

        // 隐藏加载状态
        hideKlineLoadingState(code);

        if (klineBtn) {
            klineBtn.disabled = false;
            klineBtn.textContent = 'K 线图';
        }

        if (data.success) {
            showKlineChartModal(code, name, data.data);
        } else {
            showMessage(`K 线图加载失败：${data.message}`, 'error');
        }
    } catch (error) {
        hideKlineLoadingState(code);
        if (klineBtn) {
            klineBtn.disabled = false;
            klineBtn.textContent = 'K 线图';
        }
        handleError(`加载 K 线图 ${code}`, error);
    }
}

/**
 * 显示 K 线图加载状态
 */
function showKlineLoadingState(code, name) {
    const loadingDiv = document.getElementById(`kline-loading-${code}`);
    if (loadingDiv) {
        loadingDiv.remove();
    }

    const stockItem = document.querySelector(`#kline-${code}`).closest('.stock-item');
    const stockActions = stockItem.querySelector('.stock-actions');
    const tempDiv = document.createElement('div');
    tempDiv.id = `kline-loading-${code}`;
    tempDiv.className = 'kline-loading';
    tempDiv.innerHTML = `
        <div class="trend-analysis-progress">
            <div class="spinner"></div>
            <div class="loading-content">
                <h3>正在加载 K 线图...</h3>
                <p>正在获取 ${name}(${code}) 的 K 线数据</p>
            </div>
        </div>
    `;
    stockActions.parentNode.insertBefore(tempDiv, stockActions.nextSibling);
}

/**
 * 隐藏 K 线图加载状态
 */
function hideKlineLoadingState(code) {
    const loadingDiv = document.getElementById(`kline-loading-${code}`);
    if (loadingDiv) {
        loadingDiv.remove();
    }
}

/**
 * 显示 K 线图弹窗
 */
function showKlineChartModal(code, name, chartData) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'block';

    // 生成唯一容器 ID
    const chartContainerId = `kline-chart-${code}-${Date.now()}`;

    modal.innerHTML = `
        <div class="modal-content" style="max-width: 1200px; max-height: 90vh; overflow-y: auto;">
            <span class="close">&times;</span>
            <h3>K 线图 - ${name} (${code})</h3>

            <!-- 图例说明移到顶部 -->
            <div style="margin: 10px 0 15px 0; padding: 12px; background-color: #f8f9fa; border-radius: 4px; font-size: 13px; display: flex; flex-wrap: wrap; gap: 15px; align-items: center;">
                <strong style="color: #555;">📊 图例：</strong>
                <span>📈 K 线（红涨绿跌）</span>
                <span>🟠 MA5</span>
                <span>🔵 MA20</span>
                <span>🟣 MA60</span>
                <span>⚫ MA120</span>
                <span style="color: #26A69A; font-weight: bold;">● 买入</span>
                <span style="color: #EF5350; font-weight: bold;">● 卖出</span>
                <span>🟡 密集成交区</span>
            </div>

            <!-- 当前价格和趋势信息 -->
            <div style="margin-bottom: 15px; padding: 10px; background: linear-gradient(135deg, #f5f7fa 0%, #e8ecef 100%); border-radius: 6px; display: flex; gap: 20px; align-items: center; flex-wrap: wrap;">
                <span style="font-size: 14px;">
                    当前价：<strong style="color: ${chartData.current_price ? '#ef5350' : '#666'}; font-size: 16px;">${chartData.current_price || 'N/A'}</strong>
                </span>
                ${chartData.trend_direction ? `<span style="font-size: 14px;">| 趋势：<strong style="color: #1976d2;">${chartData.trend_direction}</strong></span>` : ''}
                ${chartData.health_score ? `<span style="font-size: 14px;">| 健康度：<strong style="color: ${chartData.health_score >= 60 ? '#27ae60' : chartData.health_score >= 40 ? '#f39c12' : '#c0392b'}; font-size: 16px;">${chartData.health_score}/100</strong></span>` : ''}
            </div>

            <div id="${chartContainerId}" style="width: 100%; height: 600px; border: 1px solid #ddd; border-radius: 4px;"></div>
        </div>
    `;

    document.body.appendChild(modal);

    // 关闭弹窗事件 - 使用 echarts.getInstanceByDom 获取图表实例
    const span = modal.querySelector('.close');
    span.onclick = function() {
        modal.style.display = 'none';
        document.body.removeChild(modal);
        const chartDom = document.getElementById(chartContainerId);
        if (chartDom) {
            const existingChart = echarts.getInstanceByDom(chartDom);
            if (existingChart) {
                existingChart.dispose();
            }
        }
    };

    window.onclick = function(event) {
        if (event.target === modal) {
            modal.style.display = 'none';
            document.body.removeChild(modal);
            const chartDom = document.getElementById(chartContainerId);
            if (chartDom) {
                const existingChart = echarts.getInstanceByDom(chartDom);
                if (existingChart) {
                    existingChart.dispose();
                }
            }
        }
    };

    // 渲染 K 线图（默认 365 天）
    renderKlineChart(chartContainerId, chartData, code, name);
}

/**
 * 渲染 K 线图（使用 ECharts）
 */
function renderKlineChart(containerId, data, code, name) {
    const chartDom = document.getElementById(containerId);
    if (!chartDom) return;

    // 如果已有图表，先销毁
    let chart = echarts.getInstanceByDom(chartDom);
    if (chart) {
        chart.dispose();
    }
    chart = echarts.init(chartDom);

    // 准备数据
    const dates = data.dates;
    const klineData = data.kline;
    const volumes = data.volumes;
    const ma5 = data.ma5;
    const ma20 = data.ma20;
    const ma60 = data.ma60;
    const ma120 = data.ma120;

    // 计算价格范围用于绘制密集成交区
    let priceMin = Infinity, priceMax = -Infinity;
    klineData.forEach(k => {
        if (k[3] > priceMax) priceMax = k[3];
        if (k[2] < priceMin) priceMin = k[2];
    });

    const option = {
        backgroundColor: '#fff',
        animation: false,
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            },
            borderWidth: 1,
            borderColor: '#ccc',
            padding: 10,
            textStyle: {
                color: '#000'
            },
            position: function (pos, params, el, elRect, size) {
                const obj = {
                    top: 10,
                    left: 10,
                    right: size.contentSize[0] < size.viewSize[0] ? 'auto' : 10
                };
                obj[['right', 'left'][+(pos[0] < size.viewSize[0] / 2)]] = 30;
                return obj;
            }
        },
        axisPointer: {
            link: [{ xAxisIndex: 'all' }],
            label: {
                backgroundColor: '#777'
            }
        },
        grid: [
            {
                left: '10%',
                right: '8%',
                height: '50%'
            },
            {
                left: '10%',
                right: '8%',
                top: '65%',
                height: '15%'
            }
        ],
        xAxis: [
            {
                type: 'category',
                data: dates,
                scale: true,
                boundaryGap: false,
                axisLine: { onZero: false },
                splitLine: { show: false },
                splitNumber: 20,
                axisLabel: {
                    formatter: function (value) {
                        return value.substring(5); // 只显示月 - 日
                    }
                },
                gridIndex: 0
            },
            {
                type: 'category',
                gridIndex: 1,
                data: dates,
                axisLabel: { show: false }
            }
        ],
        yAxis: [
            {
                scale: true,
                splitArea: {
                    show: true,
                    areaStyle: {
                        color: ['rgba(250,250,250,0.3)', 'rgba(200,200,200,0.1)']
                    }
                },
                gridIndex: 0
            },
            {
                scale: true,
                gridIndex: 1,
                splitNumber: 2,
                axisLabel: { show: false },
                axisLine: { show: false },
                splitLine: { show: false }
            }
        ],
        dataZoom: [
            {
                type: 'inside',
                xAxisIndex: [0, 1],
                start: 50,
                end: 100
            },
            {
                show: true,
                xAxisIndex: [0, 1],
                type: 'slider',
                bottom: 10,
                start: 50,
                end: 100
            }
        ],
        series: [
            {
                name: 'K 线',
                type: 'candlestick',
                data: klineData,
                itemStyle: {
                    color: '#EF5350',
                    color0: '#26A69A',
                    borderColor: '#EF5350',
                    borderColor0: '#26A69A',
                    lineWidth: 1.5
                },
                markPoint: {
                    symbol: 'pin',
                    symbolSize: 22,
                    label: {
                        show: true,
                        formatter: function (param) {
                            return param.name;
                        },
                        fontSize: 14,
                        fontWeight: 'bold',
                        color: '#fff'
                    },
                    data: [
                        // 买入信号 - 显示在 K 线下方
                        ...data.buy_signals.map(s => ({
                            name: s.signal,
                            coord: [s.date, s.price],
                            value: '买',
                            symbol: 'pin',
                            symbolSize: 22,
                            label: {
                                formatter: '买',
                                fontSize: 14,
                                fontWeight: 'bold',
                                color: '#fff',
                                offset: [0, -2]
                            },
                            itemStyle: {
                                color: '#26A69A',
                                shadowBlur: 8,
                                shadowColor: 'rgba(38, 166, 154, 0.6)'
                            }
                        })),
                        // 卖出信号 - 显示在 K 线上方
                        ...data.sell_signals.map(s => ({
                            name: s.signal,
                            coord: [s.date, s.price],
                            value: '卖',
                            symbol: 'pin',
                            symbolSize: 22,
                            label: {
                                formatter: '卖',
                                fontSize: 14,
                                fontWeight: 'bold',
                                color: '#fff',
                                offset: [0, 2]
                            },
                            itemStyle: {
                                color: '#EF5350',
                                shadowBlur: 8,
                                shadowColor: 'rgba(239, 83, 80, 0.6)'
                            }
                        }))
                    ],
                    tooltip: {
                        formatter: function (param) {
                            return param.name + ': ' + param.value;
                        }
                    }
                }
            },
            {
                name: 'MA5',
                type: 'line',
                data: ma5,
                smooth: true,
                lineStyle: {
                    color: '#FF9800',
                    width: 1
                },
                tooltip: {
                    show: false
                }
            },
            {
                name: 'MA20',
                type: 'line',
                data: ma20,
                smooth: true,
                lineStyle: {
                    color: '#2196F3',
                    width: 2
                },
                tooltip: {
                    show: false
                }
            },
            {
                name: 'MA60',
                type: 'line',
                data: ma60,
                smooth: true,
                lineStyle: {
                    color: '#9C27B0',
                    width: 2
                },
                tooltip: {
                    show: false
                }
            },
            {
                name: 'MA120',
                type: 'line',
                data: ma120,
                smooth: true,
                lineStyle: {
                    color: '#607D8B',
                    width: 2
                },
                tooltip: {
                    show: false
                }
            },
            {
                name: '成交量',
                type: 'bar',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: volumes.map((v, i) => ({
                    value: v[1],
                    itemStyle: {
                        color: v[2] === 1 ? '#EF5350' : '#26A69A'
                    }
                }))
            }
        ]
    };

    // 添加密集成交区标记（如果有）
    if (data.consolidation_zone && data.consolidation_zone.upper_bound) {
        option.series[0].markArea = {
            itemStyle: {
                color: 'rgba(255, 235, 59, 0.3)'
            },
            data: [[{
                name: data.consolidation_zone.status || '密集成交区',
                xAxis: dates[0],
                yAxis: data.consolidation_zone.lower_bound
            }, {
                xAxis: dates[dates.length - 1],
                yAxis: data.consolidation_zone.upper_bound
            }]]
        };
    }

    console.log(`[K 线图] 渲染图表：${code}, 数据点数：${dates.length}, K 线数据：${klineData.length}`);
    chart.setOption(option);
    console.log(`[K 线图] 图表已设置`);

    // 响应窗口大小变化
    window.addEventListener('resize', function() {
        chart.resize();
    });
}

// 添加事件委托来处理动态生成的元素事件
document.addEventListener('click', function(e) {
    // 处理刷新按钮点击
    if (e.target.classList.contains('refresh-btn')) {
        const stockCode = e.target.closest('.stock-item').querySelector('.stock-info').dataset.code;
        refreshStockData(stockCode);
    }

    // 处理趋势分析按钮点击
    if (e.target.classList.contains('trend-analyze-btn')) {
        const stockCode = e.target.id.replace('trend-analyze-', '');
        const stockName = e.target.closest('.stock-item').querySelector('.stock-info strong').textContent;
        analyzeTrendStock(stockCode, stockName);
    }

    // 处理 K 线图按钮点击
    if (e.target.classList.contains('kline-btn')) {
        const stockCode = e.target.id.replace('kline-', '');
        const stockName = e.target.closest('.stock-item').querySelector('.stock-info strong').textContent;
        showKlineChart(stockCode, stockName);
    }

    // 处理编辑按钮点击
    if (e.target.classList.contains('update-btn')) {
        const stockCode = e.target.closest('.stock-item').querySelector('.stock-info').dataset.code;
        editStock(stockCode);
    }

    // 处理删除按钮点击
    if (e.target.classList.contains('delete-btn')) {
        const stockCode = e.target.closest('.stock-item').querySelector('.stock-info').dataset.code;
        deleteStock(stockCode);
    }

    // 处理切换通知按钮点击
    if (e.target.classList.contains('toggle-btn') && !e.target.id.startsWith('toggle-global-notification')) {
        const stockCode = e.target.id.replace('toggle-stock-', '');
        toggleStockNotification(stockCode);
    }
});

// 页面卸载时清理定时器
window.addEventListener('beforeunload', function() {
    stopAutoRefresh();
});


// 添加股票分组功能
function addStockGroup(groupName) {
    // 创建股票分组
    const groups = JSON.parse(localStorage.getItem('stockGroups') || '{}');
    if (!groups[groupName]) {
        groups[groupName] = [];
        localStorage.setItem('stockGroups', JSON.stringify(groups));
        return true;
    }
    return false;
}

// 获取所有股票分组
function getAllStockGroups() {
    return JSON.parse(localStorage.getItem('stockGroups') || '{}');
}

// 将股票添加到分组
function addStockToGroup(stockCode, groupName) {
    const groups = getAllStockGroups();
    if (!groups[groupName]) {
        groups[groupName] = [];
    }
    if (!groups[groupName].includes(stockCode)) {
        groups[groupName].push(stockCode);
        localStorage.setItem('stockGroups', JSON.stringify(groups));
        return true;
    }
    return false;
}

// 从分组中移除股票
function removeStockFromGroup(stockCode, groupName) {
    const groups = getAllStockGroups();
    if (groups[groupName]) {
        const index = groups[groupName].indexOf(stockCode);
        if (index > -1) {
            groups[groupName].splice(index, 1);
            localStorage.setItem('stockGroups', JSON.stringify(groups));
            return true;
        }
    }
    return false;
}

// 获取分组中的股票
function getStocksInGroup(groupName) {
    const groups = getAllStockGroups();
    return groups[groupName] || [];
}

// 自定义列功能
function getVisibleColumns() {
    // 获取用户设置的可见列，如果没有设置则使用默认值
    const saved = localStorage.getItem('stockVisibleColumns');
    if (saved) {
        return JSON.parse(saved);
    }
    // 默认显示所有列
    return {
        'name': true,
        'code': true,
        'price': true,
        'change_pct': true,
        'low_alert': true,
        'high_alert': true,
        'limit_alert': true,
        'actions': true
    };
}

// 保存可见列设置
function saveVisibleColumns(columns) {
    localStorage.setItem('stockVisibleColumns', JSON.stringify(columns));
}

// 更新股票列表显示的列
function updateColumnVisibility() {
    const visibleColumns = getVisibleColumns();
    const stockItems = document.querySelectorAll('.stock-item');

    stockItems.forEach(item => {
        // 根据可见列设置显示/隐藏相应元素
        // 这里需要根据实际的DOM结构调整
        const stockInfo = item.querySelector('.stock-info');
        if (stockInfo) {
            // 更新显示内容以匹配用户选择的列
            // 这是一个简化版本，实际实现需要更详细的DOM操作
        }
    });
}

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

// 模块初始化状态管理
const moduleInitializationStatus = {
    'analyst-view': false,
    'industry-index': false,
    'index-monitor': false,
    'fund-monitor': false
};

/**
 * 显示指定页面
 * @param {string} pageId - 页面ID
 */
function showPage(pageId) {
    console.log(`切换到页面: ${pageId}`);

    // 强制隐藏所有页面内容 - 修复关键点1
    const pages = document.querySelectorAll('.page-content');
    pages.forEach(page => {
        page.classList.remove('active-page');
        // 确保页面完全隐藏
        page.style.display = 'none';
    });

    // 显示选定页面
    const selectedPage = document.getElementById(`${pageId}-page`);
    if (selectedPage) {
        selectedPage.classList.add('active-page');
        // 确保页面显示
        selectedPage.style.display = 'block';
    }

    // 更新导航按钮状态
    const navButtons = document.querySelectorAll('.nav-btn');
    navButtons.forEach(btn => btn.classList.remove('active'));
    const activeButton = document.querySelector(`.nav-btn[data-page="${pageId}"]`);
    if (activeButton) {
        activeButton.classList.add('active');
    }

    // 验证页面切换结果 - 修复关键点2
    setTimeout(() => {
        const activePages = document.querySelectorAll('.page-content.active-page');
        if (activePages.length > 1) {
            console.error(`页面切换后出现多个激活页面: ${activePages.length}个`);
            // 强制只保留目标页面
            const targetPage = document.getElementById(`${pageId}-page`);
            if (targetPage) {
                activePages.forEach(page => {
                    if (page !== targetPage) {
                        page.classList.remove('active-page');
                        page.style.display = 'none';
                        page.style.visibility = 'hidden';
                    }
                });
            }
        }

        // 二次验证：确保目标页面确实可见
        const targetPage = document.getElementById(`${pageId}-page`);
        if (targetPage) {
            if (!targetPage.classList.contains('active-page')) {
                console.error('目标页面未正确激活，强制激活');
                targetPage.classList.add('active-page');
            }
            if (targetPage.style.display === 'none') {
                console.error('目标页面仍被隐藏，强制显示');
                targetPage.style.display = 'block';
            }
        }
    }, 50);

    // 根据页面ID执行特定的初始化函数
    switch(pageId) {
        case 'stock-monitor':
            // 股票监控页面已经通过DOMContentLoaded事件处理
            // 确保自动刷新在股票监控页面激活时运行
            if (!isAutoRefreshEnabled) {
                startAutoRefresh();
            }
            break;
        case 'analyst-view':
            // 停止自动刷新，节省资源
            stopAutoRefresh();
            // 按需初始化分析师页面
            initializeAnalystPage();
            break;
        case 'industry-index':
            // 停止自动刷新，节省资源
            stopAutoRefresh();
            // 按需初始化行业页面
            initializeIndustryPage();
            break;
        case 'index-monitor':
            // 停止自动刷新，节省资源
            stopAutoRefresh();
            // 按需初始化指数页面
            initializeIndexPage();
            break;
        case 'fund-monitor':
            // 基金数据统计页面
            // 停止自动刷新，节省资源
            stopAutoRefresh();
            // 按需初始化基金页面
            initializeFundPage();
            break;
        default:
            break;
    }
}

/**
 * 按需初始化基金页面
 */
function initializeFundPage() {
    if (moduleInitializationStatus['fund-monitor']) {
        console.log('基金页面已初始化，跳过重复初始化');
        return;
    }

    console.log('开始初始化基金页面');

    // 检查基金页面相关函数是否存在
    if (typeof initializeFundChartPage === 'function') {
        initializeFundChartPage();
    }

    // 绑定基金页面事件
    const refreshFundRankingBtn = document.getElementById('refresh-fund-ranking');
    if (refreshFundRankingBtn && !refreshFundRankingBtn.hasAttribute('data-initialized')) {
        refreshFundRankingBtn.addEventListener('click', function() {
            if (typeof loadFundRanking === 'function') {
                loadFundRanking();
            }
        });
        refreshFundRankingBtn.setAttribute('data-initialized', 'true');
    }

    // 绑定周期选择变化事件
    const fundPeriodSelect = document.getElementById('fund-period-select');
    if (fundPeriodSelect && !fundPeriodSelect.hasAttribute('data-initialized')) {
        fundPeriodSelect.addEventListener('change', function() {
            if (typeof loadFundRanking === 'function') {
                loadFundRanking();
            }
        });
        fundPeriodSelect.setAttribute('data-initialized', 'true');
    }

    // 绑定显示前N个选择变化事件
    const topNFund = document.getElementById('top-n-fund');
    if (topNFund && !topNFund.hasAttribute('data-initialized')) {
        topNFund.addEventListener('change', function() {
            if (typeof loadFundRanking === 'function') {
                loadFundRanking();
            }
        });
        topNFund.setAttribute('data-initialized', 'true');
    }

    moduleInitializationStatus['fund-monitor'] = true;
    console.log('基金页面初始化完成');
}

/**
 * 按需初始化分析师页面
 */
function initializeAnalystPage() {
    if (moduleInitializationStatus['analyst-view']) {
        console.log('分析师页面已初始化，跳过重复初始化');
        return;
    }

    console.log('开始初始化分析师页面');

    // 绑定分析师页面事件
    const refreshAnalystBtn = document.getElementById('refresh-analyst-btn');
    if (refreshAnalystBtn && !refreshAnalystBtn.hasAttribute('data-initialized')) {
        refreshAnalystBtn.addEventListener('click', function() {
            if (typeof loadAnalystFocusStocks === 'function') {
                loadAnalystFocusStocks();
            }
        });
        refreshAnalystBtn.setAttribute('data-initialized', 'true');
    }

    const refreshRecentlyUpdatedBtn = document.getElementById('refresh-recently-updated-btn');
    if (refreshRecentlyUpdatedBtn && !refreshRecentlyUpdatedBtn.hasAttribute('data-initialized')) {
        refreshRecentlyUpdatedBtn.addEventListener('click', function() {
            if (typeof loadAnalystUpdatedStocks === 'function') {
                loadAnalystUpdatedStocks();
            }
        });
        refreshRecentlyUpdatedBtn.setAttribute('data-initialized', 'true');
    }

    moduleInitializationStatus['analyst-view'] = true;
    console.log('分析师页面初始化完成');
}

/**
 * 按需初始化行业页面
 */
function initializeIndustryPage() {
    if (moduleInitializationStatus['industry-index']) {
        console.log('行业页面已初始化，跳过重复初始化');
        return;
    }

    console.log('开始初始化行业页面');

    // 调用industry_view.js的初始化函数
    if (typeof initIndustryChartPage === 'function') {
        initIndustryChartPage();
    }

    // 绑定行业页面事件
    const refreshIndustryBtn = document.getElementById('refresh-industry-btn');
    if (refreshIndustryBtn && !refreshIndustryBtn.hasAttribute('data-initialized')) {
        refreshIndustryBtn.addEventListener('click', function() {
            if (typeof loadIndustryData === 'function') {
                loadIndustryData();
            }
        });
        refreshIndustryBtn.setAttribute('data-initialized', 'true');
    }

    moduleInitializationStatus['industry-index'] = true;
    console.log('行业页面初始化完成');
}

/**
 * 按需初始化指数页面
 */
function initializeIndexPage() {
    if (moduleInitializationStatus['index-monitor']) {
        console.log('指数页面已初始化，跳过重复初始化');
        return;
    }

    console.log('开始初始化指数页面');

    // 调用index_view.js的初始化函数
    if (typeof initializeIndexChartPage === 'function') {
        initializeIndexChartPage();
    }

    // 绑定指数排名刷新按钮事件
    const refreshIndexRankingBtn = document.getElementById('refresh-index-ranking');
    if (refreshIndexRankingBtn && !refreshIndexRankingBtn.hasAttribute('data-initialized')) {
        refreshIndexRankingBtn.addEventListener('click', function() {
            if (typeof loadIndexRanking === 'function') {
                loadIndexRanking();
            }
        });
        refreshIndexRankingBtn.setAttribute('data-initialized', 'true');
        console.log('指数排名刷新按钮事件已绑定');
    } else {
        console.warn('refresh-index-ranking 按钮未找到');
    }

    // 绑定周期选择变化事件
    const indexPeriodSelect = document.getElementById('index-period-select');
    if (indexPeriodSelect && !indexPeriodSelect.hasAttribute('data-initialized')) {
        indexPeriodSelect.addEventListener('change', function() {
            if (typeof loadIndexRanking === 'function') {
                loadIndexRanking();
            }
        });
        indexPeriodSelect.setAttribute('data-initialized', 'true');
    }

    // 绑定显示前 N 个选择变化事件
    const topNIndex = document.getElementById('top-n-index');
    if (topNIndex && !topNIndex.hasAttribute('data-initialized')) {
        topNIndex.addEventListener('change', function() {
            if (typeof loadIndexRanking === 'function') {
                loadIndexRanking();
            }
        });
        topNIndex.setAttribute('data-initialized', 'true');
    }

    moduleInitializationStatus['index-monitor'] = true;
    console.log('指数页面初始化完成');
}

/**
 * 加载通知设置
 */
function loadNotificationSettings() {
    fetch(CONSTANTS.API_ENDPOINTS.NOTIFICATIONS)
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
    fetch(CONSTANTS.API_ENDPOINTS.NOTIFICATIONS)
    .then(response => response.json())
    .then(async data => {
        const newStatus = !data.global_notification_enabled;

        const result = await apiCall(CONSTANTS.API_ENDPOINTS.GLOBAL_NOTIFICATION_ENABLED, {
            method: 'PUT',
            body: JSON.stringify({
                global_notification_enabled: newStatus
            })
        });

        if (result.success) {
            updateGlobalNotificationButton(newStatus);
            showMessage(result.message, 'success');
        } else {
            showMessage(result.message, 'error');
        }
    })
    .catch(error => {
        handleError('获取当前全局消息发送设置', error);
    });
}

/**
 * 切换股票通知状态
 * @param {string} code - 股票代码
 */
function toggleStockNotification(code) {
    fetch(CONSTANTS.API_ENDPOINTS.NOTIFICATIONS)
    .then(response => response.json())
    .then(async settings => {
        const currentStatus = settings.stock_notification_enabled[code] !== undefined ? settings.stock_notification_enabled[code] : true;
        const newStatus = !currentStatus;

        const result = await apiCall(`${CONSTANTS.API_ENDPOINTS.STOCKS}/${code}/notification_enabled`, {
            method: 'PUT',
            body: JSON.stringify({
                notification_enabled: newStatus
            })
        });

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
        handleError(`获取股票 ${code} 消息发送设置`, error);
    });
}

/**
 * 加载股票列表
 */
function loadStocks() {
    const stocksList = document.getElementById('stocks-list');
    stocksList.innerHTML = '<div class="loading">加载中...</div>';

    fetch(CONSTANTS.API_ENDPOINTS.STOCKS)
    .then(response => response.json())
    .then(async data => {
        stocksList.innerHTML = '';

        if (data.stocks.length === 0) {
            stocksList.innerHTML = '<p>暂无监控股票</p>';
            return;
        }

        try {
            // 获取消息发送设置
            const notificationSettings = await fetch(CONSTANTS.API_ENDPOINTS.NOTIFICATIONS).then(res => res.json());

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
                    const stockItem = createStockItem(stock, isNotificationEnabled);
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
                    const stockItem = createStockItem(stock, isNotificationEnabled);
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
                loadStockClockDirections();  // 加载时钟方向
            }, 1000); // 延迟1秒执行，确保DOM元素已渲染完成
        } catch (error) {
            console.error('获取消息发送设置失败:', error);
            // 如果获取失败，按原有逻辑处理，使用默认开启状态
            data.stocks.forEach(stock => {
                const stockItem = createStockItem(stock, true);
                stocksList.appendChild(stockItem);
            });
        }
    })
    .catch(error => {
        stocksList.innerHTML = `<div class="error">加载股票列表失败: ${error.message}</div>`;
    });
}

/**
 * 加载设置
 */
function loadSettings() {
    // 首先尝试从本地存储加载设置
    const localSettings = loadSettingsFromStorage();
    if (localSettings) {
        if (localSettings.checkInterval) document.getElementById('check-interval').value = localSettings.checkInterval;
        if (localSettings.marketOpenStart) document.getElementById('market-open-start').value = localSettings.marketOpenStart;
        if (localSettings.marketOpenEnd) document.getElementById('market-open-end').value = localSettings.marketOpenEnd;

        // 重启自动刷新以应用新的时间设置
        stopAutoRefresh();
        startAutoRefresh();
    }

    // 然后从服务器加载设置并覆盖本地值
    fetch(CONSTANTS.API_ENDPOINTS.SETTINGS)
    .then(response => response.json())
    .then(settings => {
        document.getElementById('check-interval').value = settings.check_interval;
        document.getElementById('market-open-start').value = settings.market_open_start;
        document.getElementById('market-open-end').value = settings.market_open_end;

        // 同时保存到本地存储
        saveSettingsToStorage({
            checkInterval: settings.check_interval,
            marketOpenStart: settings.market_open_start,
            marketOpenEnd: settings.market_open_end
        });

        // 重启自动刷新以应用新的时间设置
        stopAutoRefresh();
        startAutoRefresh();
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
        apiCall(`${CONSTANTS.API_ENDPOINTS.STOCKS}/${code}`, {
            method: 'DELETE'
        })
        .then(data => {
            if (data.success) {
                showMessage('股票删除成功', 'success');
                loadStocks(); // 重新加载列表
            } else {
                showMessage(data.message, 'error');
            }
        })
        .catch(error => {
            handleError(`删除股票 ${code}`, error);
        });
    }
}

/**
 * 编辑股票
 * @param {string} code - 股票代码
 */
function editStock(code) {
    // 获取当前股票信息
    fetch(CONSTANTS.API_ENDPOINTS.STOCKS)
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
                    </div>

                    <div class="form-row">
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
        document.getElementById(`edit-stock-form-${code}`).addEventListener('submit', async function(e) {
            e.preventDefault();

            try {
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

                // 验证输入数据
                const validation = validateStockData(updatedStock);
                if (!validation.isValid) {
                    showMessage('输入验证失败: ' + validation.errors.join(', '), 'error');
                    return;
                }

                const result = await apiCall(`${CONSTANTS.API_ENDPOINTS.STOCKS}/${code}`, {
                    method: 'PUT',
                    body: JSON.stringify(updatedStock)
                });

                if (result.success) {
                    showMessage('股票更新成功', 'success');
                    modal.style.display = 'none';
                    document.body.removeChild(modal);
                    loadStocks(); // 重新加载列表
                } else {
                    showMessage(result.message, 'error');
                }
            } catch (error) {
                handleError('更新股票', error);
            }
        });
    })
    .catch(error => {
        handleError('获取股票信息', error);
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
 * 解析时钟方向
 * @param {string} trendDirection - 趋势方向字符串
 * @returns {{icon: string, class: string, text: string}} 时钟方向信息
 */
function parseClockDirection(trendDirection) {
    if (!trendDirection) return { icon: '➡️', class: '', text: '未知' };

    if (trendDirection.includes('一点钟')) {
        return { icon: '🕐', class: 'clock-1', text: '加速上涨' };
    } else if (trendDirection.includes('两点钟') || trendDirection.includes('两点半')) {
        return { icon: '🕑', class: 'clock-2', text: '稳定上涨' };
    } else if (trendDirection.includes('三点钟')) {
        return { icon: '🕒', class: 'clock-3', text: '横盘整理' };
    } else if (trendDirection.includes('四点钟')) {
        return { icon: '🕓', class: 'clock-4', text: '稳定下跌' };
    } else if (trendDirection.includes('五点钟')) {
        return { icon: '🕔', class: 'clock-5', text: '加速下跌' };
    }
    return { icon: '➡️', class: '', text: '横盘' };
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
    fetch(`${CONSTANTS.API_ENDPOINTS.STOCKS}/${code}/current_data`)
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const currentData = data.data;
            const currentDataElement = document.getElementById(`current-data-${code}`);
            if (currentDataElement) {
                const price = currentData.price !== null && currentData.price !== undefined ? currentData.price : 0;
                const changePct = currentData.change_pct !== null && currentData.change_pct !== undefined ? currentData.change_pct : 0;
                const changeClass = changePct >= 0 ? 'positive' : 'negative';
                currentDataElement.innerHTML = ` [当前: ${price.toFixed(2)} | 涨跌: ${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}% | 更新: ${currentData.update_time}]`;
                currentDataElement.className = `current-data ${changeClass}`;
            }
        } else {
            showMessage(`获取股票 ${code} 数据失败: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        handleError(`获取股票 ${code} 数据`, error);
    });
}

/**
 * 刷新所有股票数据
 */
function refreshAllStocksData() {
    // 刷新所有股票的实时数据
    fetch(`${CONSTANTS.API_ENDPOINTS.STOCKS}/current_data`)
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const allData = data.data;

            // 批量更新DOM以提高性能
            const updates = [];
            for (const code in allData) {
                const currentData = allData[code];
                const currentDataElement = document.getElementById(`current-data-${code}`);
                if (currentDataElement) {
                    const price = currentData.price !== null && currentData.price !== undefined ? currentData.price : 0;
                    const changePct = currentData.change_pct !== null && currentData.change_pct !== undefined ? currentData.change_pct : 0;
                    const changeClass = changePct >= 0 ? 'positive' : 'negative';
                    const newInnerHTML = ` [当前: ${price.toFixed(2)} | 涨跌: ${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}% | 更新: ${currentData.update_time}]`;

                    updates.push({
                        element: currentDataElement,
                        innerHTML: newInnerHTML,
                        className: `current-data ${changeClass}`
                    });
                }
            }

            // 应用所有更新
            updates.forEach(update => {
                update.element.innerHTML = update.innerHTML;
                update.element.className = update.className;
            });

            showMessage('所有股票数据刷新成功', 'success');
        } else {
            showMessage(`获取数据失败: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        handleError('获取数据', error);
    });
}

// 对刷新函数应用防抖
const debouncedRefreshAllStocksData = debounce(refreshAllStocksData, 300);

/**
 * 加载所有股票的时钟方向
 */
async function loadStockClockDirections() {
    const stockItems = document.querySelectorAll('.stock-item');
    for (const item of stockItems) {
        const code = item.querySelector('.stock-info').dataset.code;
        await fetchClockDirection(code);
        // 添加小延迟以避免请求过快
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
}

/**
 * 获取单个股票的时钟方向
 * @param {string} code - 股票代码
 */
async function fetchClockDirection(code) {
    try {
        const response = await fetch(`/api/trend_analysis/${code}?name=`);
        const data = await response.json();

        if (data.success && data.trend_analysis && data.trend_analysis.direction) {
            const trendAnalysis = data.trend_analysis;
            const trendDirection = trendAnalysis.direction;
            const clockInfo = parseClockDirection(trendDirection);

            const clockElement = document.getElementById(`clock-${code}`);
            if (clockElement) {
                clockElement.className = `clock-direction ${clockInfo.class}`;
                clockElement.textContent = clockInfo.icon;
                
                // 构建详细的 title 提示：几点钟方向（均线排列状态，健康度得分，密集成交区状态）
                const maAlignment = trendAnalysis.status || '未知';
                const healthScore = trendAnalysis.health_score || 0;
                const consolidationStatus = trendAnalysis.consolidation?.status || '非密集成交区';
                const isConsolidationZone = trendAnalysis.consolidation?.is_zone ? '是' : '非';
                
                // 格式：三点钟方向（均线多头排列，95 分，非密集成交区）
                clockElement.title = `${trendDirection}（${maAlignment}，${healthScore}分，${isConsolidationZone === '是' ? '密集成交区' : '非密集成交区'}）`;
            }
        }
    } catch (error) {
        // 静默失败，不影响其他功能
        console.debug(`获取股票 ${code} 趋势方向失败：`, error.message);
    }
}

// 自动刷新相关变量
let autoRefreshIntervalId = null;
let isAutoRefreshEnabled = false;

// 检查是否在监控时间内
function isMarketTime() {
    const now = new Date();
    const dayOfWeek = now.getDay();

    // 周六、周日不监控
    if (dayOfWeek === 0 || dayOfWeek === 6) {
        return false;
    }

    const hours = now.getHours();
    const minutes = now.getMinutes();
    const time = hours * 60 + minutes;

    // 从页面设置中获取监控开始和结束时间
    const startTimeStr = document.getElementById('market-open-start')?.value || '09:30';
    const endTimeStr = document.getElementById('market-open-end')?.value || '15:00';

    // 解析时间字符串为分钟数
    const [startHour, startMinute] = startTimeStr.split(':').map(Number);
    const [endHour, endMinute] = endTimeStr.split(':').map(Number);

    const startTime = startHour * 60 + startMinute;
    const endTime = endHour * 60 + endMinute;

    // 如果结束时间小于开始时间，说明跨过了午夜（不太可能在股票交易场景中）
    if (endTime >= startTime) {
        return time >= startTime && time < endTime;
    } else {
        // 跨越午夜的情况（例如晚上到早上）
        return time >= startTime || time < endTime;
    }
}

// 开始自动刷新
function startAutoRefresh() {
    if (isAutoRefreshEnabled) {
        return; // 已经启动了
    }

    // 设置定时器，每分钟检查一次
    autoRefreshIntervalId = setInterval(() => {
        if (isMarketTime()) {
            debouncedRefreshAllStocksData();
        }
    }, CONSTANTS.DEFAULT_REFRESH_INTERVAL * 1000); // 转换为毫秒

    isAutoRefreshEnabled = true;
    console.log('自动刷新已启动');

    // 如果当前在监控时间内，立即执行一次
    if (isMarketTime()) {
        debouncedRefreshAllStocksData();
    }
}

// 停止自动刷新
function stopAutoRefresh() {
    if (autoRefreshIntervalId) {
        clearInterval(autoRefreshIntervalId);
        autoRefreshIntervalId = null;
    }
    isAutoRefreshEnabled = false;
    console.log('自动刷新已停止');
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

    // 使用常量定义的时间后自动移除
    setTimeout(() => {
        messageDiv.remove();
    }, CONSTANTS.NOTIFICATION_TIMEOUT);
}
