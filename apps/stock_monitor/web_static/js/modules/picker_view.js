// 策略选股页面 JavaScript 模块（独立、自包含）。
// 页面容器 #picker-page、导航 .nav-btn[data-page=picker]；页面 display 切换由
// stock_view.js 的统一 handler 完成，本模块负责首次进入时的初始化与数据交互/轮询。

(function () {
    'use strict';

    var inited = false;
    var pollTimer = null;
    var state = { matched: [], partial: [], running: false, message: '' };
    var activeTab = 'hit';

    function $(id) { return document.getElementById(id); }

    // 请求统一走 stock_view.js 的全局 apiCall（含 15s 超时）
    function post(url, body) {
        return apiCall(url, body === undefined
            ? { method: 'POST' }
            : { method: 'POST', body: JSON.stringify(body) });
    }

    function numVal(id, def) {
        var v = parseFloat($(id).value);
        return isNaN(v) ? def : v;
    }

    function collectParams() {
        var lookback = numVal('pk-cross-lookback', 120);
        return {
            ma_fast: numVal('pk-ma-fast', 20),
            ma_mid: numVal('pk-ma-mid', 60),
            ma_slow: numVal('pk-ma-slow', 200),
            cross_lookback_bars: lookback,
            cross_max_bars_since: lookback,
            pullback_max_dist_pct: numVal('pk-pullhigh', 5.0),
            pullback_low_touch_above_pct: numVal('pk-touch-above', 3.0),
            pullback_low_touch_below_pct: numVal('pk-touch-below', 1.5),
            use_volume_shrink: !!$('pk-volume').checked,
        };
    }

    function setBanner(text) { $('pk-status').textContent = text; }
    function setBar(pct) { $('pk-bar').style.width = (Math.max(0, Math.min(100, pct))) + '%'; }
    function setBusy(busy) {
        $('pk-run').disabled = busy;
        $('pk-stop').disabled = !busy;
        $('pk-pool').disabled = busy;
    }

    function runScan() {
        setBusy(true); setBar(1); setBanner('正在启动扫描…');
        post('/api/picker/run', {
            pool: $('pk-pool').value,
            params: collectParams(),
            force: !!$('pk-force').checked,
        }).then(function () { startPoll(); })
          .catch(function (e) { setBanner('启动失败：' + e.message); setBusy(false); });
    }

    function stopScan() {
        post('/api/picker/stop').then(function () { setBanner('已请求停止'); });
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
        apiCall('/api/picker/status').then(function (resp) {
            var s = resp.data || resp;
            state.running = s.running;
            state.matched = s.matched || [];
            state.partial = s.partial || [];
            state.message = s.message || '';
            setBar(s.progress_pct || (s.running ? 2 : 0));
            setBanner((state.message || '') + (state.running ? '（扫描中…）' : ''));
            if (s.running) {
                setBusy(true);
            } else {
                stopPoll(); setBusy(false);
                if (s.matched && s.matched.length) setBanner(state.message + '，完整命中 ' + s.matched.length + ' 只');
                render();
                loadHistTab(); // 保存了本次快照
            }
        }).catch(function (e) {
            setBanner('进度获取失败：' + e.message);
            stopPoll(); setBusy(false);
        });
    }

    function render() {
        if (activeTab === 'hit') renderHit();
        else if (activeTab === 'part') renderPart();
        else renderHist();
    }

    // ---- 渲染 ----
    function esc(s) {
        return String((s === undefined || s === null) ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function metric(reasons, key) {
        for (var i = 0; i < (reasons || []).length; i++) {
            var m = reasons[i].metrics;
            if (m && m[key] !== undefined && m[key] !== null) return m[key];
        }
        return null;
    }

    function setHeads(cols) {
        $('pk-thead').innerHTML = '<tr>' + cols.map(function (c) { return '<th>' + c[1] + '</th>'; }).join('') + '</tr>';
    }

    function fillTable(rows, cols, cellRenderer) {
        var has = rows.length > 0;
        $('pk-empty').style.display = has ? 'none' : 'block';
        if (!has) { $('pk-thead').innerHTML = ''; $('pk-tbody').innerHTML = ''; return; }
        setHeads(cols);
        $('pk-tbody').innerHTML = rows.map(function (r) {
            return '<tr>' + cols.map(function (c) {
                var raw = cellRenderer ? cellRenderer(c[0], r) : r[c[0]];
                return '<td style="padding:6px 10px;border-bottom:1px solid #f0f1f3;">' + raw + '</td>';
            }).join('') + '</tr>';
        }).join('');
    }

    var msgByRule = { structure: '多头结构', golden_cross: '金叉确认', pullback: '回踩确认', volume: '缩量' };

    function reasonHtml(reasons) {
        return reasons.map(function (r) {
            var mark = r.passed ? '<span style="color:#389e0d;">✓</span>' : '<span style="color:#cf1322;">✗</span>';
            var tag = r.rule_id + '/';
            return mark + ' <b>' + esc((msgByRule[r.rule_id] || r.rule_id)) + '</b> — <span style="color:#555;">' + esc(r.note) + '</span>';
        }).join('<br>');
    }

    function renderHit() {
        var rows = state.matched.map(function (it) {
            var dist = metric(it.reasons, 'dist_to_ma_fast_pct');
            var pct = it.change_pct;
            var c = esc(pct === undefined || pct === null ? '—' : (pct >= 0 ? '+' + Number(pct).toFixed(2) : Number(pct).toFixed(2)) + '%');
            if (pct >= 0 && pct !== undefined && pct !== null) c = '<span style="color:#cf1322;">' + c + '</span>';
            else if (pct !== undefined && pct !== null) c = '<span style="color:#389e0d;">' + c + '</span>';
            return { cell: {
                code: it.code,
                name: '<b>' + esc(it.name) + '</b>',
                price: esc(it.price),
                chg: c,
                ma_slow: esc(metric(it.reasons, 'ma_slow')),
                dist: esc(dist === null || dist === undefined ? '—' : Number(dist).toFixed(2) + '%'),
                detail: reasonHtml(it.reasons),
            } };
        }).map(function (o) { return o.cell; });
        fillTable(rows, COLS_HIT); setEmptyMsg('暂无完整命中。可调整参数或切换股票池后再扫描。');
    }

    function renderPart() {
        // 观察(部分命中)：保留至少命中 多头结构 或 金叉确认 之一的；仅单独命中回踩确认/缩量易造成干扰，予以剔除
        var kept = (state.partial || []).filter(function (it) {
            var r = it.hit_rules || [];
            return r.indexOf('structure') >= 0 || r.indexOf('golden_cross') >= 0;
        });
        var rows = kept.map(function (it) {
            return {
                code: it.code,
                name: '<b>' + esc(it.name) + '</b>',
                price: esc(it.price),
                rules: esc((it.hit_rules || []).map(function (r) { return msgByRule[r] || r; }).join('、') || '—'),
            };
        });
        fillTable(rows, COLS_PART); setEmptyMsg('暂无观察列表。');
    }

    var COLS_HIT = [
        ['code', '代码'], ['name', '名称'], ['price', '现价'], ['chg', '当日'],
        ['ma_slow', '慢线'], ['dist', '距快线'], ['detail', '命中明细'],
    ];
    var COLS_PART = [['code', '代码'], ['name', '名称'], ['price', '现价'], ['rules', '已命中规则']];
    var COLS_HIST = [['run_label', '运行'], ['pool', '股票池'], ['matched_count', '命中'], ['scanned', '扫描'], ['created_at', '完成时间']];

    function fmtRunId(id) {
        var m = /^picker_run_(\d{8})T(\d{6})$/.exec(String(id || ''));
        if (!m) return String(id || '');
        var d = m[1], t = m[2];
        return d.slice(0, 4) + '-' + d.slice(4, 6) + '-' + d.slice(6, 8) + ' '
             + t.slice(0, 2) + ':' + t.slice(2, 4) + ':' + t.slice(4, 6);
    }

    function setEmptyMsg(text) { $('pk-empty').textContent = text; }

    var snapLoadedLast = null;
    function loadHistTab() {
        apiCall('/api/picker/snapshots?limit=20').then(function (resp) {
            var d = resp.data || resp;
            snapLoadedLast = d.snapshots || d;
            if (activeTab === 'hist') renderHist();
        }).catch(function () { });
    }

    var histDetailCache = {};   // run_id -> {matched:[...]} 
    var COLS_HIST_DETAIL = [['code', '代码'], ['name', '名称'], ['price', '现价'],
                            ['chg', '当日'], ['dist', '距快线'], ['r', '命中明细']];
    function renderHistRowDetail(s, matched) {
        var rowsHtml = matched.map(function (m) {
            var dist = metric(m.reasons, 'dist_to_ma_fast_pct');
            var chg = m.change_pct;
            var chgHtml = (chg === null || chg === undefined) ? '—' : esc(chg >= 0 ? '+' + Number(chg).toFixed(2) + '%' : Number(chg).toFixed(2) + '%');
            var cells = [
                esc(m.code), '<b>' + esc(m.name) + '</b>',
                esc(m.price === undefined || m.price === null ? '—' : m.price),
                chgHtml,
                esc(dist === null || dist === undefined ? '—' : Number(dist).toFixed(2) + '%'),
                reasonHtml(m.reasons || []),
            ];
            return '<tr>' + cells.map(function (c) { return '<td style="padding:5px 10px;border-bottom:1px solid #f0f1f3;vertical-align:top;">' + c + '</td>'; }).join('') + '</tr>';
        }).join('');
        return '<tr class="pk-exprow" data-run-id="' + esc(s.run_id) + '">'
            + '<td colspan="' + COLS_HIST.length + '" style="background:#fafcff;padding:6px 10px;">'
            + (matched.length
                ? '<div style="margin-bottom:4px;color:#666;font-size:12px;">完整命中 ' + matched.length + ' 只：</div>'
                  + '<table class="pk-table" style="width:100%;border-collapse:collapse;">'
                  + '<thead><tr>' + COLS_HIST_DETAIL.map(function (c) { return '<th style="padding:5px 10px;">' + c[1] + '</th>'; }).join('') + '</tr></thead>'
                  + '<tbody>' + rowsHtml + '</tbody></table>'
                : '<span style="color:#bbb;">该次命中为空：无记录</span>')
            + '</td></tr>';
    }

    function handleHistRowClick(ev) {
        var tr = ev.target.closest ? ev.target.closest('tr[data-run-id]') : null;
        if (!tr) return;
        if (String(tr.className || '').indexOf('pk-exprow') >= 0) return; // 点展开行不动作
        var root = tr.parentNode;
        if (root !== $('pk-tbody')) return;
        var runId = tr.getAttribute('data-run-id');
        // 查找同运行行是否已有一条展开行
        var existing = null;
        for (var i = tr.rowIndex + 1; i < root.rows.length; i++) {
            var r = root.rows[i];
            if (String(r.className || '').indexOf('pk-exprow') >= 0 && r.getAttribute('data-run-id') === runId) {
                existing = r; break;
            }
        }
        if (existing) { setHistArrow(tr, false); root.deleteRow(existing.rowIndex); return; }
        var s = null;
        (snapLoadedLast || []).forEach(function (x) { if (x.run_id === runId) s = x; });
        setHistArrow(tr, true);
        if (!histDetailCache[runId]) {
            apiCall('/api/picker/snapshots/' + encodeURIComponent(runId)).then(function (resp) {
                var detail = resp.data || resp;
                histDetailCache[runId] = (detail && detail.matched) || [];
                appendHistDetail(s, histDetailCache[runId]);
            }).catch(function () { appendHistDetail(s, []); });
        } else {
            appendHistDetail(s, histDetailCache[runId]);
        }
    }
    function appendHistDetail(s, matched) {
        if (!s) return;
        $('pk-tbody').insertAdjacentHTML('beforeend', renderHistRowDetail(s, matched));
    }

    function renderHist() {
        var rows = (snapLoadedLast || []).map(function (s) {
            return {
                run_id: s.run_id,
                run_label: fmtRunId(s.run_id),
                pool: s.pool === 'zz500' ? '中证500' : (s.pool === 'hs300' ? '沪深300' : s.pool),
                matched_count: s.matched_count,
                scanned: s.scanned,
                created_at: (s.created_at || '').replace('T', ' '),
            };
        });
        fillTable(rows, COLS_HIST);
        setEmptyMsg('暂无历史快照。');
        // 给运行行加 data-run-id + 可展开指示(▸) 样式
        var tbody = $('pk-tbody');
        for (var i = 0; i < tbody.rows.length; i++) {
            var tr = tbody.rows[i];
            tr.setAttribute('data-run-id',
                (rows[i] && rows[i].run_id !== undefined) ? rows[i].run_id : tr.cells[0].textContent.trim());
            tr.classList.add('pk-hist-row');
            if (tr.cells.length) {
                tr.cells[0].insertAdjacentHTML('afterbegin', '<span class="pk-harrow">▸</span> ');
            }
        }
    }

    // 展开/收起该运行行的箭头指示
    function setHistArrow(tr, opening) {
        if (!tr || !tr.cells || !tr.cells.length) return;
        var a = tr.cells[0].querySelector('.pk-harrow');
        if (a) a.textContent = opening ? '▾' : '▸';
    }

    // ---- Tab 切换 ----
    function switchTab(tab) {
        activeTab = tab;
        var map = { hit: 'pk-tab-hit', part: 'pk-tab-part', hist: 'pk-tab-hist' };
        Object.keys(map).forEach(function (k) { $(map[k]).classList.toggle('active', k === tab); });
        render();
    }

    function bind() {
        $('pk-run').addEventListener('click', runScan);
        $('pk-stop').addEventListener('click', stopScan);
        $('pk-tab-hit').addEventListener('click', function () { switchTab('hit'); });
        $('pk-tab-part').addEventListener('click', function () { switchTab('part'); });
        $('pk-tab-hist').addEventListener('click', function () { switchTab('hist'); loadHistTab(); });
        // 历史 Tab 行展开/收起（事件委托）
        $('pk-tbody').addEventListener('click', handleHistRowClick);
    }

    function initOnOpen() {
        if (inited) return;
        inited = true;
        bind();
        switchTab('hit');
        apiCall('/api/picker/status').then(function (resp) {
            var s = resp.data || resp;
            state.running = s.running;

            if (s.running) { startPoll(); }
            else {
                state.matched = s.matched || []; state.partial = s.partial || [];
                setBar(s.progress_pct || 0);
                setBanner(s.message || '空闲');
                loadHistTab();
            }
        }).catch(function () { });
    }

    // 进入该 nav 时才做一次初始化（stock_view 负责 display 切换）
    function hookNav() {
        var btn = document.querySelector('.nav-btn[data-page="picker"]');
        if (btn) btn.addEventListener('click', function () { setTimeout(initOnOpen, 0); });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', hookNav);
    } else {
        hookNav();
    }
})();
