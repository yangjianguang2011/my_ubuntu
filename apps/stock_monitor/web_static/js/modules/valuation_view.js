// 个股估值报告页面 JavaScript 模块（独立、自包含）。
// 页面容器 #valuation-page、导航 .nav-btn[data-page=valuation]；页面 display 切换由
// stock_view.js 的统一 handler 完成，本模块负责首次进入时的初始化与数据交互/轮询。

(function () {
    'use strict';

    var inited = false;
    var pollTimer = null;
    var chart = null;
    var lastCode = '';
    var poolConstituents = [];

    function $(id) { return document.getElementById(id); }

    function api(method, url, body) {
        return fetch(url, {
            method: method,
            headers: body ? { 'Content-Type': 'application/json' } : undefined,
            body: body ? JSON.stringify(body) : undefined,
        }).then(function (r) {
            if (!r.ok) {
                return r.json().catch(function () { return {}; }).then(function (e) {
                    throw new Error(e.message || ('HTTP ' + r.status));
                });
            }
            return r.json();
        });
    }

    function esc(s) {
        return String((s === undefined || s === null) ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function setStatus(text) { $('vl-status').textContent = text; }
    function setBusy(busy) {
        $('vl-run').disabled = busy;
        $('vl-pool').disabled = busy;
    }

    // 从输入值中提取 6 位代码
    function extractCode(raw) {
        var m = String(raw || '').match(/\d{6}/);
        return m ? m[0] : '';
    }

    // 加载股票池成分，填充 datalist
    function loadConstituents(pool) {
        api('GET', '/api/valuation/pool/' + pool + '/constituents').then(function (d) {
            poolConstituents = (d.data || d).constituents || [];
            $('vl-stocks').innerHTML = poolConstituents.map(function (c) {
                return '<option value="' + esc(c.code + '  ' + c.name) + '"></option>';
            }).join('');
        }).catch(function (e) { setStatus('成分加载失败：' + e.message); });
    }

    // ---- 报告计算 + 轮询 ----
    function runReport() {
        var code = extractCode($('vl-code').value);
        if (!code) { setStatus('请输入或选择股票代码'); return; }
        lastCode = code;
        setBusy(true); setStatus('正在启动计算…');
        $('vl-result').style.display = 'none';
        api('POST', '/api/valuation/report/run', { code: code })
            .then(function () { startPoll(); })
            .catch(function (e) { setStatus('启动失败：' + e.message); setBusy(false); });
    }

    function startPoll() {
        if (pollTimer) return;
        pollTimer = setInterval(poll, 2000);
        poll();
    }
    function stopPoll() {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }

    function poll() {
        api('GET', '/api/valuation/report/status').then(function (resp) {
            var s = resp.data || resp;   // 统一响应：{success, data}
            setStatus((s.message || '') + (s.running ? '（计算中…）' : ''));
            if (s.running) { setBusy(true); return; }
            stopPoll(); setBusy(false);
            if (s.error) { setStatus('失败：' + s.error); return; }
            loadReport(lastCode);
        }).catch(function (e) {
            setStatus('进度获取失败：' + e.message);
            stopPoll(); setBusy(false);
        });
    }

    function loadReport(code) {
        api('GET', '/api/valuation/report/' + code + '/data').then(function (resp) {
            var r = resp.data || resp;   // 统一响应：{success, data}
            $('vl-result').style.display = 'block'; // 先显示容器，确保图表有正确宽度再初始化
            render(r);
            if (chart) chart.resize();
            setStatus('完成：' + (r.meta.name || code) + ' · 截止 ' + r.meta.as_of);
        }).catch(function (e) { setStatus('报告读取失败：' + e.message); });
    }

    // ---- 渲染 ----
    function render(r) {
        renderConclusion(r.conclusion, r.meta);
        renderPanel(r.panel_rows);
        renderChart(r.chart, r.meta);
        renderEvents(r.events, r.meta);
        renderStats(r.stats);
    }

    function renderConclusion(c, meta) {
        if (!c) return;
        var el = $('vl-conclusion');
        el.style.background = c.color + '14';
        el.style.borderLeft = '4px solid ' + c.color;
        var title = (meta.name || meta.code) + '（' + meta.code + '）· ' + c.state;
        var warn = c.warning
            ? '<div style="margin-top:8px;padding:8px 10px;background:#fff8e6;border:1px solid #f0d9a0;border-radius:4px;color:#8a6d3b;font-size:12px;">⚠ ' + esc(c.warning) + '</div>'
            : '';
        el.innerHTML = '<div style="font-weight:bold;font-size:16px;color:' + c.color + ';">' + esc(title) + '</div>'
            + '<div style="margin-top:6px;color:#333;">' + esc(c.main) + '</div>'
            + '<div style="margin-top:6px;color:#666;font-size:13px;">' + esc(c.extra) + '</div>'
            + warn
            + '<div style="margin-top:8px;color:#999;font-size:12px;">'
            + (meta.mkt_note ? esc(meta.mkt_note) + '<br>' : '')
            + '买卖信号口径：' + esc(meta.signal_name || meta.primary_name || '估值读数')
            + ' · ' + esc(meta.roe_note) + ' · ' + esc(meta.pc_note) + ' · 分红率：' + esc(meta.payout_note) + '</div>';
    }

    function renderPanel(rows) {
        var th = 'padding:6px 10px;border-bottom:1px solid #eef0f3;text-align:left;color:#888;font-weight:normal;';
        var td = 'padding:6px 10px;border-bottom:1px solid #f5f6f8;vertical-align:top;';
        $('vl-panel-table').innerHTML = '<thead><tr>'
            + '<th style="' + th + 'width:32%;">项目</th>'
            + '<th style="' + th + 'width:18%;">读数</th>'
            + '<th style="' + th + '">附注 / 历史位置</th>'
            + '</tr></thead><tbody>'
            + (rows || []).map(function (r) {
                return '<tr><td style="' + td + '">' + esc(r.label) + '</td>'
                    + '<td style="' + td + ';font-weight:600;">' + esc(r.value) + '</td>'
                    + '<td style="' + td + ';color:#777;">' + esc(r.note) + '</td></tr>';
            }).join('')
            + '</tbody>';
    }

    function renderEvents(events, meta) {
        var th = 'padding:6px 10px;border-bottom:1px solid #eef0f3;text-align:left;color:#888;font-weight:normal;';
        var td = 'padding:6px 10px;border-bottom:1px solid #f5f6f8;';
        var buyN = (events || []).filter(function (e) { return e.kind === '买'; }).length;
        var sellN = (events || []).filter(function (e) { return e.kind === '卖'; }).length;
        $('vl-events-table').innerHTML = '<thead><tr>'
            + '<th style="' + th + '">日期</th><th style="' + th + '">方向</th>'
            + '<th style="' + th + '">读数</th><th style="' + th + '">收盘</th>'
            + '<th style="' + th + '">触发后60日</th>'
            + '</tr></thead><tbody>'
            + (events || []).slice().reverse().map(function (e) {
                var isBuy = e.kind === '买';
                var color = isBuy ? '#1f7a33' : '#c0392b';
                var fwd = (e.fwd60 === null || e.fwd60 === undefined) ? '—' : (e.fwd60 >= 0 ? '+' : '') + (e.fwd60 * 100).toFixed(1) + '%';
                return '<tr><td style="' + td + '">' + esc(e.date) + '</td>'
                    + '<td style="' + td + ';color:' + color + ';font-weight:600;">' + esc(e.kind) + '</td>'
                    + '<td style="' + td + '">' + (e.read === null ? '—' : e.read.toFixed(3)) + '</td>'
                    + '<td style="' + td + '">' + esc(e.close) + '</td>'
                    + '<td style="' + td + '">' + fwd + '</td></tr>';
            }).join('')
            + '</tbody>';
        var sig = (meta && meta.signal_name) ? meta.signal_name : '估值读数';
        // 阈值一律以后端 meta 为准；缺失时显示 —，不再用 0.10/0.90 假数字兜底
        var bt = (meta && meta.buy_threshold !== undefined) ? meta.buy_threshold : null;
        var st = (meta && meta.sell_threshold !== undefined) ? meta.sell_threshold : null;
        var fmtThr = function (v) { return (v === null || v === undefined) ? '—' : v.toFixed(2); };
        var trg = (meta && meta.triggers) ? meta.triggers.length : 0;
        var gs = (meta && meta.gates) || [];
        var gtxt = gs.length
            ? ' · 买点门控：' + gs.map(function (g) { return g.name + ' ' + g.op + ' ' + g.threshold; }).join(' 且 ')
            : ' · 买点门控：未启用（单因子信号）';
        var note = '生效阈值：买 ≤ ' + fmtThr(bt) + ' / 卖 ≥ ' + fmtThr(st)
            + '（' + esc(sig) + '）· 二态机交易 ' + buyN + ' 笔买 / ' + sellN + ' 笔卖'
            + ' · 多次触发标记 ' + trg + ' 个（每次进入极端区，图上全画，不影响交易归并）'
            + gtxt;
        $('vl-events-note').textContent = note;
    }

    // 交易统计：持仓占比 / 总收益 / 最大回撤，与"一直持有"对比
    function renderStats(stats) {
        var el = $('vl-signal-stats');
        if (!el) return;
        if (!stats || !stats.total_days) { el.innerHTML = ''; return; }
        var pct = function (v, d) { return (v === null || v === undefined) ? '—' : (v * 100).toFixed(d === undefined ? 1 : d) + '%'; };
        var cell = 'padding:6px 12px;border-right:1px solid #eef0f3;';
        var lab = 'color:#888;font-size:12px;display:block;margin-bottom:2px;';
        var val = 'font-size:15px;font-weight:600;';
        var holdTxt = stats.holding_now ? '（当前持仓中）' : '（当前空仓）';
        el.innerHTML = '<div style="display:flex;flex-wrap:wrap;background:#f7f9fb;border:1px solid #e6e9ee;border-radius:6px;overflow:hidden;">'
            + '<div style="' + cell + '"><span style="' + lab + '">策略总收益</span><span style="' + val + ';color:' + (stats.strat_return >= 0 ? '#1f7a33' : '#c0392b') + ';">' + pct(stats.strat_return) + '</span></div>'
            + '<div style="' + cell + '"><span style="' + lab + '">一直持有</span><span style="' + val + ';color:' + (stats.bh_return >= 0 ? '#1f7a33' : '#c0392b') + ';">' + pct(stats.bh_return) + '</span></div>'
            + '<div style="' + cell + '"><span style="' + lab + '">超额</span><span style="' + val + ';color:' + (stats.strat_return - stats.bh_return >= 0 ? '#1f7a33' : '#c0392b') + ';">' + pct(stats.strat_return - stats.bh_return) + '</span></div>'
            + '<div style="' + cell + '"><span style="' + lab + '">策略最大回撤</span><span style="' + val + ';color:#c0392b;">' + pct(stats.strat_mdd) + '</span></div>'
            + '<div style="' + cell + '"><span style="' + lab + '">持有最大回撤</span><span style="' + val + ';color:#c0392b;">' + pct(stats.bh_mdd) + '</span></div>'
            + '<div style="' + cell + '"><span style="' + lab + '">持仓天数占比</span><span style="' + val + ';">' + pct(stats.pos_ratio, 0) + '</span></div>'
            + '<div style="' + cell + '"><span style="' + lab + '">持仓 / 总天数</span><span style="' + val + ';">' + stats.pos_days + ' / ' + stats.total_days + '</span></div>'
            + '<div style="' + cell + ';border-right:none;"><span style="' + lab + '">交易笔数</span><span style="' + val + ';">' + stats.trades + '</span></div>'
            + '</div>'
            + '<div style="color:#999;font-size:12px;margin-top:6px;">区间 ' + esc(stats.start) + ' ~ ' + esc(stats.end) + ' · ' + holdTxt
            + ' · 生效阈值 买≤' + (stats.buy_threshold !== undefined ? stats.buy_threshold.toFixed(2) : '—')
            + ' / 卖≥' + (stats.sell_threshold !== undefined ? stats.sell_threshold.toFixed(2) : '—')
            + (stats.gate_blocked ? ' · 门控挡下买点 ' + stats.gate_blocked + ' 天' : '') + '</div>';
    }

    // ---- ECharts 四层时序图（价格 / 估值读数 / 市赚率 / 门控）----
    function renderChart(d, meta) {
        var el = $('vl-chart');
        if (!window.echarts) { el.innerHTML = '<p style="color:#999;">ECharts 未加载</p>'; return; }
        // 四层需要更高画布；容器高度由模板给的 760px 抬到 900px（模板是私有文件，故在 JS 里设）
        if (el.style.height !== '900px') el.style.height = '900px';
        if (!chart) chart = window.echarts.init(el);
        chart.setOption(buildChartOption(d, meta), true);
        chart.resize();
    }

    function refLine() {
        return {
            silent: true, symbol: 'none',
            lineStyle: { type: 'dashed', color: '#bbb', width: 1 },
            label: { show: false },
            data: [{ yAxis: 0.10 }, { yAxis: 0.90 }],
        };
    }

    // 历史位置曲线；marks 非空时画门控阈值参考线
    function pctLine(name, data, color, gridIdx, withRef, yAxisIdx, marks) {
        var s = {
            name: name, type: 'line', data: data || [],
            xAxisIndex: gridIdx,
            yAxisIndex: (yAxisIdx === undefined || yAxisIdx === null) ? gridIdx : yAxisIdx,
            symbol: 'none', lineStyle: { width: 1.3, color: color },
            itemStyle: { color: color }, connectNulls: true,
        };
        if (withRef) s.markLine = refLine();
        if (marks && marks.length) {
            s.markLine = {
                silent: true, symbol: 'none',
                lineStyle: { type: 'dashed', color: '#b8860b', width: 1 },
                label: { show: true, position: 'insideEndTop', fontSize: 10, color: '#b8860b',
                         formatter: function (p) { return p.name; } },
                data: marks,
            };
        }
        return s;
    }

    function buildChartOption(d, meta) {
        var dates = d.dates || [];
        var grids = [], xAxes = [], yAxes = [], series = [];

        // 有季报 ROE 时才给第2层挂右轴：提前算，网格留出右侧刻度空间
        var hasRoe = (d.roe_step_b !== undefined && d.roe_step_b !== null);

        // 四层网格：0 价格 / 1 估值读数 / 2 市赚率(+ROE右轴) / 3 门控
        var N = 4;
        var gridTops = ['4%', '28%', '52%', '76%'];
        var legendTops = ['1%', '25%', '49%', '73%'];
        for (var i = 0; i < N; i++) {
            grids.push({
                left: 64,
                right: (i === 2 && hasRoe) ? 54 : 28,
                top: gridTops[i], height: '20%',
            });
            xAxes.push({
                type: 'category', gridIndex: i, data: dates,
                boundaryGap: false,
                axisLabel: { show: i === N - 1, fontSize: 10 },
                axisLine: { show: i === N - 1 },
                axisTick: { show: i === N - 1 },
            });
        }

        // 轴0：价格（自缩放）；轴1~3：0~1 历史位置；另加轴4：第2层右轴（ROE 原始值）
        yAxes.push({ gridIndex: 0, scale: true, splitNumber: 3, axisLabel: { fontSize: 10 } });
        for (var j = 1; j < N; j++) {
            yAxes.push({ gridIndex: j, min: 0, max: 1, interval: 0.5, axisLabel: { fontSize: 10 } });
        }
        var ROE_AXIS = yAxes.length;
        if (hasRoe) {
            yAxes.push({
                gridIndex: 2, position: 'right', scale: true, splitNumber: 3,
                splitLine: { show: false },
                axisLabel: {
                    fontSize: 10,
                    formatter: function (v) { return (v * 100).toFixed(0) + '%'; },
                },
            });
        }

        // ---- 第0层：价格 + 买卖标记 + 被门控挡下的标记 ----
        series.push({ name: '收盘价', type: 'line', data: d.close || [], xAxisIndex: 0, yAxisIndex: 0,
            symbol: 'none', lineStyle: { width: 1.4, color: '#2c3e50' }, itemStyle: { color: '#2c3e50' }, connectNulls: true });
        series.push({
            name: '买入机会', type: 'scatter', xAxisIndex: 0, yAxisIndex: 0, z: 5,
            data: (d.buy_markers || []).map(function (m) { return { value: [m.date, m.close] }; }),
            symbol: 'triangle', symbolSize: 11, itemStyle: { color: '#1f7a33' },
        });
        series.push({
            name: '卖出风险', type: 'scatter', xAxisIndex: 0, yAxisIndex: 0, z: 5,
            data: (d.sell_markers || []).map(function (m) { return { value: [m.date, m.close] }; }),
            symbol: 'triangle', symbolSize: 11, symbolRotate: 180, itemStyle: { color: '#c0392b' },
        });
        series.push({
            name: '信号被门控挡下', type: 'scatter', xAxisIndex: 0, yAxisIndex: 0, z: 4,
            data: (d.blocked_markers || []).map(function (m) { return { value: [m.date, m.close] }; }),
            symbol: 'triangle', symbolSize: 9,
            itemStyle: { color: '#ffffff', borderColor: '#b8860b', borderWidth: 1.6 },
        });

        // ---- 第0层：反转体系事件标记（月线反转 / 三线红 / 有效跌破20日线）----
        if (d.tbs_buy_markers) {
            series.push({
                name: '月线反转(买)', type: 'scatter', xAxisIndex: 0, yAxisIndex: 0, z: 6,
                data: (d.tbs_buy_markers || []).map(function (m) { return { value: [m.date, m.close] }; }),
                symbol: 'pin', symbolSize: 20,
                itemStyle: { color: '#e8a33d', borderColor: '#8a5a00', borderWidth: 1 },
                label: { show: false },
            });
        }
        if (d.tbs_red_markers) {
            series.push({
                name: '三线红(关注)', type: 'scatter', xAxisIndex: 0, yAxisIndex: 0, z: 5,
                data: (d.tbs_red_markers || []).map(function (m) { return { value: [m.date, m.close] }; }),
                symbol: 'circle', symbolSize: 8,
                itemStyle: { color: '#d94f4f', borderColor: '#8b1a1a', borderWidth: 1 },
            });
        }

        // ---- 各层曲线定义：[key, 名称, 颜色, 默认显示, 挂0.10/0.90参考线, yAxisIndex, 门控阈值线] ----
        var sigCol = (meta && meta.signal_col) || 'pb_adj_b_pct';
        var gates = (meta && meta.gates) || [];
        function gateThr(key) {
            for (var i = 0; i < gates.length; i++) { if (gates[i].key === key) return gates[i]; }
            return null;
        }
        var gPc = gateThr('price_position'), gRoe = gateThr('roe_quality');
        var marksPc = gPc ? [{ yAxis: gPc.threshold, name: gPc.name + ' ≤' + gPc.threshold }] : [];
        var marksRoe = gRoe ? [{ yAxis: gRoe.threshold, name: gRoe.name + ' ≥' + gRoe.threshold }] : [];

        var l1 = [];
        if (sigCol === 'fusion_pct') {
            l1.push(['fusion_pct', '多因子融合读数（信号源）', '#c0392b', true, true]);
        }
        l1.push(['pb_adj_b_pct', '盈利调节市净率·季报ROE' + (sigCol === 'pb_adj_b_pct' ? '（信号源）' : ''),
                 '#1f7a33', sigCol === 'pb_adj_b_pct', sigCol === 'pb_adj_b_pct']);
        l1.push(['fusion_pct', '多因子融合读数', '#c0392b', false, false]);
        l1.push(['ps_adj_pct', '盈利调节市销率', '#e67e22', false, false]);
        l1.push(['pb_adj_pct', '盈利调节市净率·日频ROE', '#8e44ad', false, false]);
        l1.push(['pb_pct', '市净率 PB', '#2980b9', false, false]);
        l1.push(['pe_ttm_pct', '市盈率 PE', '#16a085', false, false]);

        var l2 = [['pr_pct', '市赚率 PR', '#2980b9', true, true]];
        if (hasRoe) {
            l2.push(['roe_step_b', '季报年化ROE(%)·右轴', '#d35400', false, false, ROE_AXIS]);
        }

        var l3 = [
            ['price_cycle', '价格周期位置（门控）', '#7f8c8d', true, false, null, marksPc],
            ['roe_step_b_pct', '季报ROE位置（门控）', '#d35400', true, false, null, marksRoe],
            ['tbs_rps250', 'RPS250 相对强度', '#8a5a00', false, false],
            ['tbs_rps120', 'RPS120 相对强度', '#b8860b', false, false],
            ['tbs_rps50', 'RPS50 相对强度', '#e8a33d', false, false],
        ];

        var layerDefs = { 1: l1, 2: l2, 3: l3 };

        // 每层一个 legend（放在该层网格上方）；selected 控制默认显隐
        var legends = [{
            top: legendTops[0], left: 'center', type: 'scroll',
            itemWidth: 12, itemHeight: 9, textStyle: { fontSize: 11 },
            data: ['收盘价', '买入机会', '卖出风险', '信号被门控挡下',
                   '月线反转(买)', '三线红(关注)'],
        }];
        for (var li = 1; li < N; li++) {
            var names = [], sel = {};
            (layerDefs[li] || []).forEach(function (c) {
                if (d[c[0]] !== undefined && d[c[0]] !== null) {
                    series.push(pctLine(c[1], d[c[0]], c[2], li, c[4], c[5], c[6]));
                    names.push(c[1]);
                    sel[c[1]] = c[3];
                }
            });
            legends.push({
                top: legendTops[li], left: 'center', type: 'scroll',
                itemWidth: 12, itemHeight: 9, textStyle: { fontSize: 11 },
                data: names, selected: sel,
            });
        }

        return {
            animation: false,
            tooltip: { trigger: 'axis' },
            legend: legends,
            axisPointer: { link: [{ xAxisIndex: 'all' }] },
            grid: grids,
            xAxis: xAxes,
            yAxis: yAxes,
            dataZoom: [
                { type: 'inside', xAxisIndex: [0, 1, 2, 3], start: 0, end: 100 },
                { type: 'slider', xAxisIndex: [0, 1, 2, 3], bottom: 0, height: 18, start: 0, end: 100 },
            ],
            series: series,
        };
    }


    // ---- 初始化 ----
    function bind() {
        $('vl-run').addEventListener('click', runReport);
        $('vl-pool').addEventListener('change', function () { loadConstituents($('vl-pool').value); });
    }

    function initOnOpen() {
        if (inited) return;
        inited = true;
        bind();
        loadConstituents($('vl-pool').value);
        window.addEventListener('resize', function () { if (chart) chart.resize(); });
    }

    // 进入该 nav 时才做一次初始化（stock_view 负责 display 切换）
    function hookNav() {
        var btn = document.querySelector('.nav-btn[data-page="valuation"]');
        if (btn) btn.addEventListener('click', function () {
            setTimeout(initOnOpen, 0);
            setTimeout(function () { if (chart) chart.resize(); }, 60);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', hookNav);
    } else {
        hookNav();
    }
})();
