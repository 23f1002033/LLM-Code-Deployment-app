"""
Embedded HTML dashboard served directly by FastAPI.

Available at /dashboard — no separate Streamlit process needed.
Works on HF Spaces since it shares the same port as the API.
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM Deployment Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }

        .nav {
            background: rgba(15, 23, 42, 0.8);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid #1e293b;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .nav-title {
            font-size: 1.25rem;
            font-weight: 700;
            background: linear-gradient(135deg, #818cf8, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .nav-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.85rem;
            color: #94a3b8;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #ef4444;
            transition: background 0.3s;
        }

        .status-dot.online { background: #34d399; box-shadow: 0 0 8px #34d399; }

        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2rem;
        }

        .metric-card {
            background: linear-gradient(145deg, #1e293b, #0f172a);
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 1.5rem;
            transition: transform 0.2s, border-color 0.2s;
        }

        .metric-card:hover {
            transform: translateY(-2px);
            border-color: #818cf8;
        }

        .metric-label {
            font-size: 0.75rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.5rem;
        }

        .metric-value {
            font-size: 2rem;
            font-weight: 700;
        }

        .metric-value.green { color: #34d399; }
        .metric-value.amber { color: #fbbf24; }
        .metric-value.blue { color: #818cf8; }
        .metric-value.gray { color: #94a3b8; font-size: 0.9rem; }

        .tabs {
            display: flex;
            gap: 0;
            border-bottom: 1px solid #334155;
            margin-bottom: 1.5rem;
        }

        .tab {
            padding: 0.75rem 1.5rem;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 500;
            color: #64748b;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
            user-select: none;
        }

        .tab:hover { color: #e2e8f0; }
        .tab.active { color: #818cf8; border-color: #818cf8; }

        .tab-content { display: none; }
        .tab-content.active { display: block; }

        .task-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            font-size: 0.85rem;
        }

        .task-table thead th {
            background: #1e293b;
            color: #94a3b8;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-size: 0.7rem;
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid #334155;
            position: sticky;
            top: 60px;
        }

        .task-table tbody tr {
            transition: background 0.15s;
        }

        .task-table tbody tr:hover { background: #1e293b; }

        .task-table td {
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #1e293b;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .badge {
            display: inline-block;
            padding: 0.2rem 0.65rem;
            border-radius: 9999px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
        }

        .badge-done { background: #064e3b; color: #34d399; }
        .badge-processing { background: #78350f; color: #fbbf24; }
        .badge-failed { background: #7f1d1d; color: #f87171; }
        .badge-queued { background: #1e293b; color: #94a3b8; }

        .log-viewer {
            background: #020617;
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 1rem;
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 0.75rem;
            line-height: 1.6;
            max-height: 500px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-all;
            color: #94a3b8;
        }

        .log-controls {
            display: flex;
            gap: 1rem;
            align-items: center;
            margin-bottom: 1rem;
        }

        .btn {
            padding: 0.5rem 1.25rem;
            border: 1px solid #334155;
            border-radius: 8px;
            background: #1e293b;
            color: #e2e8f0;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s;
            font-family: inherit;
        }

        .btn:hover { background: #334155; border-color: #818cf8; }
        .btn.primary { background: #4f46e5; border-color: #4f46e5; }
        .btn.primary:hover { background: #4338ca; }

        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }

        .form-group { display: flex; flex-direction: column; gap: 0.4rem; }
        .form-group.full { grid-column: 1 / -1; }

        .form-group label {
            font-size: 0.75rem;
            font-weight: 500;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .form-group input,
        .form-group textarea {
            background: #020617;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 0.65rem 0.85rem;
            color: #e2e8f0;
            font-family: inherit;
            font-size: 0.85rem;
            transition: border-color 0.2s;
        }

        .form-group input:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: #818cf8;
        }

        .form-group textarea { resize: vertical; min-height: 80px; }

        .toast {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            padding: 1rem 1.5rem;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 500;
            opacity: 0;
            transform: translateY(20px);
            transition: all 0.3s;
            z-index: 200;
        }

        .toast.show { opacity: 1; transform: translateY(0); }
        .toast.success { background: #064e3b; color: #34d399; border: 1px solid #34d399; }
        .toast.error { background: #7f1d1d; color: #f87171; border: 1px solid #f87171; }

        .empty-state {
            text-align: center;
            padding: 3rem;
            color: #475569;
        }

        .empty-state .icon { font-size: 3rem; margin-bottom: 1rem; }

        a { color: #818cf8; text-decoration: none; }
        a:hover { text-decoration: underline; }

        @media (max-width: 768px) {
            .form-grid { grid-template-columns: 1fr; }
            .metrics-grid { grid-template-columns: 1fr 1fr; }
            .container { padding: 1rem; }
        }
    </style>
</head>
<body>

<nav class="nav">
    <div class="nav-title">🚀 LLM Code Deployment</div>
    <div class="nav-status">
        <div class="status-dot" id="statusDot"></div>
        <span id="statusText">Connecting...</span>
    </div>
</nav>

<div class="container">
    <div class="metrics-grid" id="metricsGrid">
        <div class="metric-card">
            <div class="metric-label">Service Status</div>
            <div class="metric-value green" id="metricStatus">—</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Active Tasks</div>
            <div class="metric-value amber" id="metricActive">0</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Total Tasks</div>
            <div class="metric-value blue" id="metricTotal">0</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Version</div>
            <div class="metric-value gray" id="metricVersion">—</div>
        </div>
    </div>

    <div class="tabs">
        <div class="tab active" data-tab="tasks">📋 Task History</div>
        <div class="tab" data-tab="logs">📜 Logs</div>
        <div class="tab" data-tab="submit">📤 Submit Task</div>
    </div>

    <div class="tab-content active" id="tab-tasks">
        <div id="taskTableContainer">
            <div class="empty-state">
                <div class="icon">📭</div>
                <p>No tasks recorded yet</p>
            </div>
        </div>
    </div>

    <div class="tab-content" id="tab-logs">
        <div class="log-controls">
            <button class="btn" onclick="fetchLogs()">🔄 Refresh</button>
            <select id="logLines" class="btn" onchange="fetchLogs()">
                <option value="100">100 lines</option>
                <option value="300" selected>300 lines</option>
                <option value="500">500 lines</option>
                <option value="1000">1000 lines</option>
            </select>
            <label style="font-size:0.8rem;color:#64748b">
                <input type="checkbox" id="autoRefreshLogs" style="margin-right:4px"> Auto-refresh (10s)
            </label>
        </div>
        <div class="log-viewer" id="logViewer">Loading logs...</div>
    </div>

    <div class="tab-content" id="tab-submit">
        <p style="color:#fbbf24;font-size:0.85rem;margin-bottom:1.5rem">
            ⚡ Manual submission for testing. Requires a valid secret.
        </p>
        <div class="form-grid">
            <div class="form-group">
                <label>Task ID</label>
                <input type="text" id="fTask" placeholder="e.g. my-test-app">
            </div>
            <div class="form-group">
                <label>Email</label>
                <input type="email" id="fEmail" placeholder="you@example.com">
            </div>
            <div class="form-group">
                <label>Round</label>
                <input type="number" id="fRound" value="1" min="1" max="10">
            </div>
            <div class="form-group">
                <label>Nonce</label>
                <input type="text" id="fNonce" placeholder="random-nonce">
            </div>
            <div class="form-group full">
                <label>Brief</label>
                <textarea id="fBrief" placeholder="Describe the web app to generate..."></textarea>
            </div>
            <div class="form-group">
                <label>Evaluation URL</label>
                <input type="url" id="fEvalUrl" placeholder="https://eval.example.com/submit">
            </div>
            <div class="form-group">
                <label>Secret</label>
                <input type="password" id="fSecret" placeholder="••••••••">
            </div>
            <div class="form-group full" style="margin-top:0.5rem">
                <button class="btn primary" onclick="submitTask()" style="width:fit-content">
                    🚀 Submit Task
                </button>
            </div>
        </div>
    </div>
</div>

<div class="toast" id="toast"></div>

<script>
    const BASE = window.location.origin;
    let logInterval = null;

    // --- tabs ---
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
            if (tab.dataset.tab === 'logs') fetchLogs();
        });
    });

    // --- toast ---
    function showToast(msg, type = 'success') {
        const t = document.getElementById('toast');
        t.textContent = msg;
        t.className = 'toast ' + type + ' show';
        setTimeout(() => t.classList.remove('show'), 4000);
    }

    // --- fetch helpers ---
    async function api(path) {
        const r = await fetch(BASE + path);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r;
    }

    // --- health poll ---
    async function pollHealth() {
        try {
            const data = await (await api('/health')).json();
            document.getElementById('statusDot').className = 'status-dot online';
            document.getElementById('statusText').textContent = 'Online';
            document.getElementById('metricStatus').textContent = '● Healthy';
            document.getElementById('metricVersion').textContent = 'v' + (data.version || '?');
            document.getElementById('metricActive').textContent = data.active_tasks || 0;
        } catch {
            document.getElementById('statusDot').className = 'status-dot';
            document.getElementById('statusText').textContent = 'Offline';
            document.getElementById('metricStatus').textContent = '● Offline';
            document.getElementById('metricStatus').style.color = '#f87171';
        }
    }

    // --- task history ---
    async function pollStatus() {
        try {
            const data = await (await api('/status')).json();
            document.getElementById('metricTotal').textContent = data.total_tasks || 0;
            document.getElementById('metricActive').textContent = data.active_tasks || 0;

            const tasks = data.recent || [];
            if (tasks.length === 0) {
                document.getElementById('taskTableContainer').innerHTML =
                    '<div class="empty-state"><div class="icon">📭</div><p>No tasks recorded yet</p></div>';
                return;
            }

            let html = '<table class="task-table"><thead><tr>' +
                '<th>Task ID</th><th>Round</th><th>Status</th><th>Received</th><th>Pages URL</th>' +
                '</tr></thead><tbody>';

            tasks.forEach(t => {
                const badge = 'badge-' + (t.status || 'queued');
                const url = t.pages_url
                    ? '<a href="' + t.pages_url + '" target="_blank">View ↗</a>'
                    : '—';
                html += '<tr>' +
                    '<td>' + (t.task_id || '') + '</td>' +
                    '<td>' + (t.round || '') + '</td>' +
                    '<td><span class="badge ' + badge + '">' + (t.status || 'queued') + '</span></td>' +
                    '<td>' + (t.received_at || '') + '</td>' +
                    '<td>' + url + '</td>' +
                    '</tr>';
            });

            html += '</tbody></table>';
            document.getElementById('taskTableContainer').innerHTML = html;
        } catch {}
    }

    // --- logs ---
    async function fetchLogs() {
        try {
            const lines = document.getElementById('logLines').value;
            const text = await (await api('/logs?lines=' + lines)).text();
            const viewer = document.getElementById('logViewer');
            viewer.textContent = text || '(empty)';
            viewer.scrollTop = viewer.scrollHeight;
        } catch (e) {
            document.getElementById('logViewer').textContent = 'Error fetching logs: ' + e.message;
        }
    }

    // --- auto refresh logs ---
    document.getElementById('autoRefreshLogs').addEventListener('change', function() {
        if (this.checked) {
            fetchLogs();
            logInterval = setInterval(fetchLogs, 10000);
        } else {
            clearInterval(logInterval);
            logInterval = null;
        }
    });

    // --- submit task ---
    async function submitTask() {
        const payload = {
            task: document.getElementById('fTask').value,
            email: document.getElementById('fEmail').value,
            round: parseInt(document.getElementById('fRound').value) || 1,
            brief: document.getElementById('fBrief').value,
            evaluation_url: document.getElementById('fEvalUrl').value,
            nonce: document.getElementById('fNonce').value,
            secret: document.getElementById('fSecret').value,
            attachments: []
        };

        if (!payload.task || !payload.email || !payload.brief || !payload.secret) {
            showToast('Please fill all required fields', 'error');
            return;
        }

        try {
            const r = await fetch(BASE + '/ready', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await r.json();
            if (r.ok) {
                showToast('Task submitted: ' + (data.task || payload.task));
                setTimeout(pollStatus, 2000);
            } else {
                showToast('Error: ' + (data.detail || r.status), 'error');
            }
        } catch (e) {
            showToast('Connection error: ' + e.message, 'error');
        }
    }

    // --- init ---
    pollHealth();
    pollStatus();
    fetchLogs();
    setInterval(pollHealth, 15000);
    setInterval(pollStatus, 10000);
</script>
</body>
</html>
"""
