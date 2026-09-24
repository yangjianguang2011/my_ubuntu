// 市场温度 JavaScript 模块（自包含）。
// 展示三大指数（上证综指/深证成指/创业板指）的指数温度；
// 容器在「股票监控」页底部（#market-section / #mt-result）。
// 温度计算在后台执行（首次约需 1~3 分钟），故需轮询进度。

(function () {
    'use strict';

    var inited = false;
    var pollTimer = null;
    var running = false;

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

    function setStatus(text) { $('mt-status').textContent = text; }
    function setBusy(busy) {
        $('mt-refresh').disabled = busy;
        running = busy;
    }

    function startPoll() {
        if (pollTimer) return;
        pollTimer = setInterval(poll, 3000);
        poll();
    }
    function stopPoll() {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }

    function poll() {
        api('GET', '/api/valuation/market/status').then(function (resp) {
            var s = resp.data || resp;   // 统一响应：{success, data}
            setStatus((s.message || '') + (s.running ? '（计算中…）' : ''));
            if (s.running) { setBusy(true); return; }
            stopPoll(); setBusy(false);
            if (s.error) { setStatus('失败：' + s.error); return; }
            api('GET', '/api/valuation/market/data').then(function (d) {
                renderMarket(d.data || d);
                setStatus('完成（' + ((d.data && d.data.indices) ? d.data.indices.length : 0) + ' 个指数）');
            }).catch(function (e) { setStatus('读取失败：' + e.message); });
        }).catch(function (e) {
            setStatus('进度获取失败：' + e.message);
            stopPoll(); setBusy(false);
        });
    }

    function startRun() {
        setBusy(true); setStatus('正在计算…（首次约需 1~3 分钟）');
        api('POST', '/api/valuation/market/run', { force: true })
            .then(function () { startPoll(); })
            .catch(function (e) { setStatus('启动失败：' + e.message); setBusy(false); });
    }

    function loadMarket() {
        // 只读已有结果；**未计算时不自动触发**——温度属低频数据，由「刷新温度」手动触发。
        api('GET', '/api/valuation/market/data').then(function (d) {
            renderMarket(d.data || d);
            setStatus('已加载（' + ((d.data && d.data.indices) ? d.data.indices.length : 0) + ' 个指数）');
        }).catch(function () {
            setStatus('尚未计算，点击「刷新温度」开始（首次约需 1~3 分钟）');
        });
    }

    // ---- 渲染 ----
    function fmtVal(v) {
        return (v === null || v === undefined || v !== v) ? '—' : Number(v).toFixed(2);
    }
    function fmtPos(p) {
        return (p === null || p === undefined || p !== p) ? '—' : (p * 100).toFixed(0) + '%';
    }

    function renderIndex(idx) {
        var temp = (idx.temperature === null || idx.temperature === undefined) ? '—' : (idx.temperature * 100).toFixed(1) + '℃';
        var broad = (idx.broad === null || idx.broad === undefined) ? '—' : (idx.broad * 100).toFixed(0) + '%';
        var err = idx.error ? '<div style="margin-top:6px;color:#c0392b;font-size:12px;">计算失败：' + esc(idx.error) + '</div>' : '';
        var warn = idx.degraded
            ? '<div style="margin-top:6px;padding:5px 9px;background:#fff8e6;border:1px solid #f0d9a0;border-radius:4px;color:#8a6d3b;font-size:12px;">'
              + '⚠ ' + esc(idx.degraded_reason || '部分数据来自缓存')
              + '（成份股为低频数据，几天内不影响判断）</div>'
            : '';
        var cards = (idx.cards || []).map(function (c) {
            var isMain = c.group === 'main';
            return '<div style="flex:1;min-width:112px;background:' + (isMain ? '#f4f9f4' : '#fafbfc')
                + ';border:1px solid ' + (isMain ? '#d6e8d6' : '#eef0f3') + ';border-radius:5px;padding:6px 9px;">'
                + '<div style="font-size:11px;color:#888;">' + esc(c.item) + '</div>'
                + '<div style="font-size:14px;font-weight:600;margin-top:2px;">' + fmtVal(c.value) + '</div>'
                + '<div style="font-size:11px;color:#999;">历史位置 ' + fmtPos(c.pos) + '</div>'
                + '</div>';
        }).join('');

        return '<div style="background:#fff;border:1px solid #e6e9ee;border-radius:6px;padding:10px 12px;margin-bottom:10px;">'
            + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:6px;">'
            + '<h3 style="margin:0;font-size:15px;">' + esc(idx.label) + ' <span style="font-size:11px;color:#aaa;font-weight:normal;">' + esc(idx.symbol) + ' · 数据截至 ' + esc(idx.date || '—') + '</span></h3>'
            + '<span style="font-size:13px;font-weight:bold;color:' + esc(idx.color || '#8a6d3b') + ';">' + esc(idx.state || '—') + ' · 温度 ' + temp + ' · 水位 ' + broad + '</span>'
            + '</div>'
            + '<div style="display:flex;flex-wrap:wrap;gap:6px;">' + cards + '</div>'
            + err
            + warn
            + '</div>';
    }

    function renderMarket(d) {
        // 兼容传入「已解包 payload」或「完整响应」两种形态
        var indices = (d && (d.indices || (d.data && d.data.indices))) || [];
        $('mt-result').innerHTML = indices.length
            ? indices.map(renderIndex).join('')
            : '<div style="color:#999;padding:18px;text-align:center;">暂无数据</div>';
    }

    // ---- 初始化 ----
    function bind() {
        $('mt-refresh').addEventListener('click', function () { startRun(); });
    }

    function initOnOpen() {
        if (inited) return;
        inited = true;
        if (!$('mt-result')) return;   // 该模块已并入股票页，容器不在则直接跳过
        bind();
        api('GET', '/api/valuation/market/status').then(function (resp) {
            var s = resp.data || resp;   // 统一响应：{success, data}
            if (s.running) { setBusy(true); startPoll(); }
            else { loadMarket(); }
        }).catch(function () { loadMarket(); });
    }

    // 市场温度已并入「股票监控」页底部（原独立页面与 nav 按钮已移除），
    // 故直接在页面加载后初始化，不再挂在 nav 按钮上。
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initOnOpen);
    } else {
        initOnOpen();
    }
})();
