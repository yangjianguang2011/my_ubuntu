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

    // ---- 条件目录（后端 /api/picker/conditions 下发；前端不写死任何条件）----
    var catalog = null;   // {global_params, groups:[{group, conditions:[...]}]}

    function escAttr(s) {
        return String(s === undefined || s === null ? '' : s)
            .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
            .replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function paramInput(condId, name, spec) {
        var id = 'pkp-' + condId + '-' + name;
        if (spec.type === 'bool') {
            return '<label style="display:flex;align-items:center;gap:3px;">'
                + '<input type="checkbox" id="' + id + '" data-param="' + escAttr(name) + '"'
                + (spec.default ? ' checked' : '') + '> ' + escAttr(spec.label) + '</label>';
        }
        if (spec.type === 'select') {
            var opts = (spec.options || []).map(function (o) {
                return '<option value="' + escAttr(o) + '"'
                    + (o === spec.default ? ' selected' : '') + '>' + escAttr(o) + '</option>';
            }).join('');
            return '<label style="display:flex;flex-direction:column;font-size:12px;color:#666;">'
                + escAttr(spec.label) + '<select id="' + id + '" data-param="' + escAttr(name)
                + '" style="margin-top:2px;padding:3px;">' + opts + '</select></label>';
        }
        var step = spec.type === 'int' ? '1' : 'any';
        return '<label style="display:flex;flex-direction:column;font-size:12px;color:#666;">'
            + escAttr(spec.label) + '<input type="number" id="' + id + '" data-param="'
            + escAttr(name) + '" value="' + escAttr(spec.default) + '" step="' + step
            + '" style="margin-top:2px;width:86px;padding:3px;"></label>';
    }

    function renderCatalog() {
        // 全局参数（均线体系）
        var gp = catalog.global_params || {};
        $('pk-global-params').innerHTML = Object.keys(gp).map(function (k) {
            var s = gp[k];
            return '<label style="display:flex;flex-direction:column;font-size:13px;color:#666;">'
                + escAttr(s.label) + '<input type="number" id="pkg-' + escAttr(k)
                + '" data-gparam="' + escAttr(k) + '" value="' + escAttr(s.default)
                + '" style="margin-top:4px;width:80px;padding:6px;"></label>';
        }).join('');

        // 条件：按分组渲染到**各自容器**（组标题已在 HTML 中，便于分区更明显）
        (catalog.groups || []).forEach(function (g) {
            var isVal = String(g.group).indexOf('估值') >= 0;
            var target = isVal ? $('pk-conditions-val') : $('pk-conditions-tech');
            if (!target) return;
            var color = isVal ? '#8e44ad' : '#1f7a33';
            target.innerHTML = (g.conditions || []).map(function (c) {
                COND_LABELS[c.id] = c.label;
                var ps = Object.keys(c.params || {}).map(function (pn) {
                    return paramInput(c.id, pn, c.params[pn]);
                }).join('');
                return '<div data-condbox="' + escAttr(c.id) + '" style="border:1px solid '
                    + (isVal ? '#e8ddf0' : '#dbe8db')
                    + ';border-radius:5px;padding:7px 10px;background:#fff;min-width:240px;">'
                    + '<label style="display:flex;align-items:center;gap:5px;font-size:13px;">'
                    + '<input type="checkbox" data-cond="' + escAttr(c.id) + '"'
                    + (c.default_on ? ' checked' : '') + '>'
                    + '<b style="color:' + color + ';">' + escAttr(c.label) + '</b></label>'
                    + (c.note ? '<div style="font-size:11px;color:#999;margin:2px 0 4px;">'
                                + escAttr(c.note) + '</div>' : '')
                    + '<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:flex-end;">'
                    + ps + '</div></div>';
            }).join('');
        });
    }

    function loadCatalog() {
        return apiCall('/api/picker/conditions').then(function (resp) {
            catalog = (resp && resp.data) || null;
            if (catalog) renderCatalog();
        }).catch(function (e) { setBanner('条件清单加载失败：' + e.message); });
    }

    function readParams(box, attr) {
        var out = {};
        (box.querySelectorAll('[' + attr + ']') || []).forEach(function (el) {
            var name = el.getAttribute(attr);
            if (el.type === 'checkbox') out[name] = !!el.checked;
            else if (el.type === 'number') {
                var v = parseFloat(el.value);
                if (!isNaN(v)) out[name] = v;
            } else out[name] = el.value;
        });
        return out;
    }

    function collectPayload() {
        var globalParams = {};
        $('pk-global-params').querySelectorAll('[data-gparam]').forEach(function (el) {
            var v = parseFloat(el.value);
            if (!isNaN(v)) globalParams[el.getAttribute('data-gparam')] = v;
        });

        var conditions = {};
        var boxes = document.querySelectorAll('#pk-conditions-tech [data-cond], #pk-conditions-val [data-cond]');
        Array.prototype.forEach.call(boxes, function (cb) {
            var cid = cb.getAttribute('data-cond');
            var box = cb.closest('[data-condbox]');
            conditions[cid] = {
                enabled: !!cb.checked,
                params: box ? readParams(box, 'data-param') : {},
            };
        });
        return { pool: $('pk-pool').value, global_params: globalParams, conditions: conditions };
    }

    function setBanner(text) { $('pk-status').textContent = text; }
    function setBar(pct) { $('pk-bar').style.width = (Math.max(0, Math.min(100, pct))) + '%'; }
    // 阶段统计：技术 N → 估值 M → 命中 K
    function setSummary(s) {
        var el = $('pk-summary');
        if (!el) return;
        s = s || {};
        if (!s.tech_passed && !s.val_scanned) { el.textContent = ''; return; }
        var parts = [];
        if (s.tech_passed) parts.push('技术 ' + s.tech_passed);
        if (s.val_scanned) parts.push('估值 ' + s.val_scanned);
        parts.push('命中 ' + ((s.matched || []).length));
        el.textContent = parts.join('  →  ');
    }
    function setBusy(busy) {
        $('pk-run').disabled = busy;
        $('pk-stop').disabled = !busy;
        $('pk-pool').disabled = busy;
    }

    function runScan() {
        setBusy(true); setBar(1); setBanner('正在启动扫描…');
        finished = false; polling = false;   // 新一轮扫描：解除"已完成"锁定
        var payload = collectPayload();
        payload.force = !!$('pk-force').checked;
        post('/api/picker/run', payload).then(function () { startPoll(); })
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

    // 轮询防重入 + 完成锁定：
    //  * `polling`  —— 上一次请求未返回前不发新请求（避免慢响应乱序）
    //  * `finished` —— 一旦收到 running=false 就置位；此后**丢弃迟到的响应**，
    //                  否则旧响应会把「已完成」覆盖回「扫描中」→ 按钮永久 busy。
    var polling = false;
    var finished = false;

    function poll() {
        if (polling || finished) return;
        polling = true;
        apiCall('/api/picker/status').then(function (resp) {
            if (finished) return;               // 已完成：丢弃迟到响应
            var s = resp.data || resp;
            state.running = s.running;
            state.matched = s.matched || [];
            state.partial = s.partial || [];
            state.message = s.message || '';
            // 进度条用**当前阶段**的百分比（后端 progress_pct 已按 stage_total 计算）
            setBar(s.running ? (s.progress_pct || 2) : 100);
            var prefix = (s.stage && s.stage !== '完成') ? '[' + s.stage + '] ' : '';
            setBanner(prefix + (state.message || '') + (s.running ? '（扫描中…）' : ''));
            setSummary(s);
            if (s.running) {
                setBusy(true);
            } else {
                finished = true;
                stopPoll(); setBusy(false);
                if (s.matched && s.matched.length) setBanner(state.message + '，完整命中 ' + s.matched.length + ' 只');
                render();
                loadHistTab(); // 保存了本次快照
            }
        }).catch(function (e) {
            if (finished) return;
            setBanner('进度获取失败：' + e.message);
            stopPoll(); setBusy(false);
        }).then(function () { polling = false; });
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

    // 把快照里存的策略参数拼成一行可读文本（旧快照可能没有 params，做了兜底）
    var COND_LABELS = {};   // cid -> 条件显示名（由 catalog 填充）

    function fmtParams(p) {
        p = p || {};
        var parts = [];
        if (p.ma_fast != null) parts.push('快线 MA' + p.ma_fast);
        if (p.ma_mid != null) parts.push('中线 MA' + p.ma_mid);
        if (p.ma_slow != null) parts.push('慢线 MA' + p.ma_slow);
        if (p.cross_lookback_bars != null) parts.push('金叉回溯 ' + p.cross_lookback_bars + ' 根');
        if (p.pullback_min_dist_pct != null && p.pullback_max_dist_pct != null) {
            parts.push('回调带 ' + p.pullback_min_dist_pct + '% ~ +' + p.pullback_max_dist_pct + '%');
        }
        if (p.pullback_low_touch_below_pct != null && p.pullback_low_touch_above_pct != null) {
            parts.push('回踩带 -' + p.pullback_low_touch_below_pct + '% ~ +' + p.pullback_low_touch_above_pct + '%');
        }
        if (p.pullback_confirm_window != null) parts.push('回踩窗口 ' + p.pullback_confirm_window + ' 根');
        parts.push('缩量软条件 ' + (p.use_volume_shrink ? '开' : '关'));
        return parts.join(' · ');
    }

    // 新格式快照：全局参数 + 各条件及其参数
    function fmtConditions(s) {
        var gp = s.global_params || {};
        var parts = [];
        if (gp.ma_fast != null) parts.push('快线 MA' + gp.ma_fast);
        if (gp.ma_mid != null) parts.push('中线 MA' + gp.ma_mid);
        if (gp.ma_slow != null) parts.push('慢线 MA' + gp.ma_slow);
        var cs = s.conditions || {};
        Object.keys(cs).forEach(function (cid) {
            var label = COND_LABELS[cid] || cid;
            var p = (cs[cid] || {}).params || {};
            var kv = Object.keys(p).map(function (k) { return k + '=' + p[k]; }).join(', ');
            parts.push(label + (kv ? '（' + kv + '）' : ''));
        });
        return parts.join(' · ');
    }

    function fmtSnapshotPlan(s) {
        // 新格式优先；旧快照（只有 params）走 fmtParams
        if (s && s.conditions && Object.keys(s.conditions).length) return fmtConditions(s);
        return fmtParams((s || {}).params);
    }

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
            + '<div style="margin-bottom:6px;color:#555;font-size:12px;background:#fff;'
            + 'border:1px solid #eef0f3;border-radius:4px;padding:5px 8px;">'
            + '<b style="color:#1890ff;">当时条件</b>：' + esc(fmtSnapshotPlan(s))
            + (s.failed ? ' <span style="color:#c0392b;">· 取数失败 ' + s.failed + ' 只</span>' : '')
            + '</div>'
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

        // ⚠️ 必须用**段内索引**（tbody.rows 的下标）定位与删除：
        // `rowIndex` 是**表级**索引（含 thead），与 `rows[i]` / `deleteRow(i)` 的段级语义不一致，
        // 混用会「扫描错位 + 删错行」（表现为再次点击时记录少一条）。
        var selfIdx = Array.prototype.indexOf.call(root.rows, tr);
        var existingIdx = -1;
        for (var i = selfIdx + 1; i < root.rows.length; i++) {
            var r = root.rows[i];
            if (String(r.className || '').indexOf('pk-exprow') >= 0
                && r.getAttribute('data-run-id') === runId) {
                existingIdx = i; break;
            }
        }
        if (existingIdx >= 0) {
            setHistArrow(tr, false);
            root.deleteRow(existingIdx);
            return;
        }
        setHistArrow(tr, true);
        if (!histDetailCache[runId]) {
            apiCall('/api/picker/snapshots/' + encodeURIComponent(runId)).then(function (resp) {
                var detail = resp.data || resp;
                histDetailCache[runId] = (detail && detail.matched) || [];
                appendHistDetail(runId, histDetailCache[runId]);
            }).catch(function () { appendHistDetail(runId, []); });
        } else {
            appendHistDetail(runId, histDetailCache[runId]);
        }
    }

    // 按 run_id 找回“运行行”（排除展开行本身）
    function findHistRow(runId) {
        var tbody = $('pk-tbody');
        for (var i = 0; i < tbody.rows.length; i++) {
            var r = tbody.rows[i];
            if (r.getAttribute('data-run-id') === runId
                && String(r.className || '').indexOf('pk-exprow') < 0) {
                return r;
            }
        }
        return null;
    }

    // 展开行插在**该运行行的正下方**（原实现 append 到表尾，会跑到列表最底部）
    function appendHistDetail(runId, matched) {
        var tr = findHistRow(runId);
        if (!tr) return;
        var s = null;
        (snapLoadedLast || []).forEach(function (x) { if (x.run_id === runId) s = x; });
        if (!s) return;
        tr.insertAdjacentHTML('afterend', renderHistRowDetail(s, matched));
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
        loadCatalog();          // 条件清单（动态表单）
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
