/**
 * PaperAiChat Web Dashboard - 实时交互逻辑
 */

// ========== Socket.IO 连接 ==========
const socket = io({
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionDelay: 2000,
    reconnectionAttempts: Infinity
});

// ========== 全局状态 ==========
let currentTab = 'overview';
let allLogs = [];
let logFilter = 'ALL';
let responseTimeChart = null;
let typingChart = null;
let apiLatencyChart = null;
let tokenChart = null;
const responseHistory = [];
const latencyHistory = [];
const tokenHistory = [];
const MAX_CHART_POINTS = 20;

// ========== Socket 事件 ==========
socket.on('connect', () => {
    updateConnectionStatus(true);
    showToast('已连接到仪表盘', 'success');
});

socket.on('disconnect', () => {
    updateConnectionStatus(false);
    showToast('连接已断开，正在重连...', 'error');
});

socket.on('stats_update', (data) => {
    updateDashboard(data);
});

socket.on('command_result', (data) => {
    if (data.success) {
        showToast(`指令执行成功: ${data.result || data.command}`, 'success');
    } else {
        showToast(`指令执行失败: ${data.error}`, 'error');
    }
});

// ========== 导航切换 ==========
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentTab = btn.dataset.tab;
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        document.getElementById(`panel-${currentTab}`).classList.add('active');
        // 切换时刷新图表
        if (currentTab === 'api') refreshApiCharts();
        socket.emit('request_stats');
    });
});

// ========== 仪表盘更新 ==========
function updateDashboard(data) {
    // 顶部状态
    document.getElementById('versionTag').textContent = `v${data.version || '--'}`;
    document.getElementById('sessionId').textContent = data.session_id || '--';
    document.getElementById('uptimeDisplay').textContent = data.uptime || '--';

    // 总览统计
    setStat('statUptime', data.uptime);
    setStat('statMessages', data.message_count);
    setStat('statActive', `${data.daily_active_count || 0} / ${(data.config && data.config.max_daily_active_messages) || 25}`);
    setStat('statErrors', data.error_count);
    setStat('statTyped', data.total_typed_chars);
    setStat('statAvgSpeed', `${data.avg_typing_speed || 0} <small>字/秒</small>`);
    setStat('statAvgResponse', `${data.avg_response_time || 0} <small>秒</small>`);
    setStat('statApiCalls', data.api_total_calls || 0);
    setStat('statTotalTokens', (data.api_total_tokens || 0).toLocaleString());

    // API 统计
    setStat('apiTotalCalls', data.api_total_calls || 0);
    setStat('apiTotalTokens', (data.api_total_tokens || 0).toLocaleString());
    setStat('apiAvgLatency', `${data.api_avg_latency_ms || 0} <small>ms</small>`);
    setStat('apiLastLatency', `${data.api_last_latency_ms || 0} <small>ms</small>`);
    setStat('apiLastTokens', data.api_last_tokens || 0);
    setStat('apiLastCall', data.api_last_call_ago || '--');

    // 按钮状态
    const btnPauseText = document.getElementById('btnPauseText');
    if (data.paused) {
        btnPauseText.textContent = '继续';
        document.getElementById('btnPause').classList.add('btn-success');
        document.getElementById('btnPause').classList.remove('btn-warning');
    } else {
        btnPauseText.textContent = '暂停';
        document.getElementById('btnPause').classList.add('btn-warning');
        document.getElementById('btnPause').classList.remove('btn-success');
    }

    // 更新日志
    if (data.recent_logs) {
        allLogs = data.recent_logs;
        renderLogs();
        renderMiniLogs(data.recent_logs);
    }

    // 更新消息
    if (data.recent_messages) {
        renderMessages(data.recent_messages);
    }

    // 更新响应时间图
    if (data.response_times && data.response_times.length > 0) {
        updateResponseTimeChart(data.response_times);
    }

    // 更新打字图
    updateTypingChart(data);

    // 更新 API 延迟历史
    if (data.api_last_latency_ms > 0) {
        latencyHistory.push(data.api_last_latency_ms);
        if (latencyHistory.length > MAX_CHART_POINTS) latencyHistory.shift();
    }
    if (data.api_last_tokens > 0) {
        tokenHistory.push(data.api_last_tokens);
        if (tokenHistory.length > MAX_CHART_POINTS) tokenHistory.shift();
    }
    if (currentTab === 'api') refreshApiCharts();
}

function setStat(id, value) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = String(value);
}

function updateConnectionStatus(connected) {
    const dot = document.getElementById('statusDot');
    const text = document.getElementById('statusText');
    if (connected) {
        dot.className = 'status-dot online';
        text.textContent = '已连接';
    } else {
        dot.className = 'status-dot offline';
        text.textContent = '已断开';
    }
}

// ========== 图表 ==========
function updateResponseTimeChart(times) {
    const ctx = document.getElementById('chartResponseTime');
    if (!ctx) return;
    if (responseTimeChart) {
        responseTimeChart.data.labels = times.map((_, i) => `#${i + 1}`);
        responseTimeChart.data.datasets[0].data = times;
        responseTimeChart.update('none');
    } else {
        responseTimeChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: times.map((_, i) => `#${i + 1}`),
                datasets: [{
                    label: '响应时间 (秒)',
                    data: times,
                    borderColor: '#6c5ce7',
                    backgroundColor: 'rgba(108, 92, 231, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                    pointBackgroundColor: '#6c5ce7',
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#5a5e78' }, grid: { color: 'rgba(255,255,255,0.04)' } },
                    y: { ticks: { color: '#5a5e78' }, grid: { color: 'rgba(255,255,255,0.04)' }, beginAtZero: true }
                }
            }
        });
    }
}

function updateTypingChart(data) {
    const ctx = document.getElementById('chartTyping');
    if (!ctx) return;
    if (typingChart) {
        typingChart.data.datasets[0].data = [data.total_typed_chars || 0, data.total_typing_time || 0, data.message_count || 0, data.active_message_count || 0, data.error_count || 0];
        typingChart.update('none');
    } else {
        typingChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['输入字符', '打字时间(秒)', '消息数', '主动消息', '错误数'],
                datasets: [{
                    data: [data.total_typed_chars || 0, data.total_typing_time || 0, data.message_count || 0, data.active_message_count || 0, data.error_count || 0],
                    backgroundColor: ['#6c5ce7', '#0095ff', '#00d68f', '#ffaa00', '#ff3d71'],
                    borderRadius: 6,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#5a5e78' }, grid: { display: false } },
                    y: { ticks: { color: '#5a5e78' }, grid: { color: 'rgba(255,255,255,0.04)' }, beginAtZero: true }
                }
            }
        });
    }
}

function refreshApiCharts() {
    // API 延迟分布
    const ctx1 = document.getElementById('chartApiLatency');
    if (ctx1 && latencyHistory.length > 0) {
        if (apiLatencyChart) {
            apiLatencyChart.data.labels = latencyHistory.map((_, i) => `#${i + 1}`);
            apiLatencyChart.data.datasets[0].data = latencyHistory;
            apiLatencyChart.update('none');
        } else {
            apiLatencyChart = new Chart(ctx1, {
                type: 'bar',
                data: {
                    labels: latencyHistory.map((_, i) => `#${i + 1}`),
                    datasets: [{
                        label: '延迟 (ms)',
                        data: latencyHistory,
                        backgroundColor: latencyHistory.map(v => v > 2000 ? '#ff3d71' : v > 1000 ? '#ffaa00' : '#00d68f'),
                        borderRadius: 4,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { color: '#5a5e78' }, grid: { display: false } },
                        y: { ticks: { color: '#5a5e78' }, grid: { color: 'rgba(255,255,255,0.04)' }, beginAtZero: true }
                    }
                }
            });
        }
    }

    // Token 消耗
    const ctx2 = document.getElementById('chartTokens');
    if (ctx2 && tokenHistory.length > 0) {
        if (tokenChart) {
            tokenChart.data.labels = tokenHistory.map((_, i) => `#${i + 1}`);
            tokenChart.data.datasets[0].data = tokenHistory;
            tokenChart.update('none');
        } else {
            tokenChart = new Chart(ctx2, {
                type: 'line',
                data: {
                    labels: tokenHistory.map((_, i) => `#${i + 1}`),
                    datasets: [{
                        label: 'Tokens',
                        data: tokenHistory,
                        borderColor: '#00d68f',
                        backgroundColor: 'rgba(0, 214, 143, 0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                        pointBackgroundColor: '#00d68f',
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { color: '#5a5e78' }, grid: { color: 'rgba(255,255,255,0.04)' } },
                        y: { ticks: { color: '#5a5e78' }, grid: { color: 'rgba(255,255,255,0.04)' }, beginAtZero: true }
                    }
                }
            });
        }
    }
}

// ========== 日志 ==========
function renderLogs() {
    const container = document.getElementById('logContainer');
    const count = document.getElementById('logCount');
    if (!container) return;

    const filtered = logFilter === 'ALL' ? allLogs : allLogs.filter(l => l.level === logFilter);
    count.textContent = `${filtered.length} 条`;

    if (filtered.length === 0) {
        container.innerHTML = '<div class="log-empty">暂无日志</div>';
        return;
    }

    container.innerHTML = filtered.map(l => `
        <div class="log-entry">
            <span class="log-ts">${l.ts}</span>
            <span class="log-level ${l.level}">${l.level}</span>
            <span class="log-cat">[${l.cat}]</span>
            <span class="log-msg">${escapeHtml(l.msg)}</span>
        </div>
    `).join('');
    container.scrollTop = container.scrollHeight;
}

function filterLogs() {
    logFilter = document.getElementById('logFilter').value;
    renderLogs();
}

function clearLogs() {
    allLogs = [];
    renderLogs();
}

function renderMiniLogs(logs) {
    const container = document.getElementById('logMini');
    if (!container) return;
    const recent = logs.slice(-15);
    if (recent.length === 0) {
        container.innerHTML = '<div class="log-empty">暂无日志</div>';
        return;
    }
    container.innerHTML = recent.map(l => `
        <div class="log-entry">
            <span class="log-ts">${l.ts}</span>
            <span class="log-level ${l.level}">${l.level}</span>
            <span class="log-cat">[${l.cat}]</span>
            <span class="log-msg">${escapeHtml(l.msg)}</span>
        </div>
    `).join('');
    container.scrollTop = container.scrollHeight;
}

// ========== 消息 ==========
function renderMessages(messages) {
    const container = document.getElementById('messageContainer');
    if (!container) return;
    if (!messages || messages.length === 0) {
        container.innerHTML = '<div class="log-empty">暂无消息</div>';
        return;
    }
    container.innerHTML = messages.slice().reverse().map(m => `
        <div class="msg-entry ${m.role}">
            <div class="msg-header">
                <span class="msg-role">${m.role === 'user' ? '[用户]' : '[AI]'}</span>
                <span class="msg-ts">${m.ts}</span>
            </div>
            <div class="msg-content">${escapeHtml(m.content)}</div>
        </div>
    `).join('');
        container.scrollTop = 0;
}

// ========== 指令 ==========
function sendCommand(cmd, args = {}) {
    socket.emit('bot_command', { command: cmd, args });
    showToast(`发送指令: ${cmd}`, 'info');
}

// ========== 配置 ==========
document.getElementById('configForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {
        api_key: document.getElementById('cfgApiKey').value || undefined,
        api_url: document.getElementById('cfgApiUrl').value,
        model_name: document.getElementById('cfgModel').value,
        human_pace: document.getElementById('cfgPace').value,
        max_history: parseInt(document.getElementById('cfgMaxHistory').value),
        check_interval: parseFloat(document.getElementById('cfgInterval').value),
        typing_speed_min: parseInt(document.getElementById('cfgSpeedMin').value),
        typing_speed_max: parseInt(document.getElementById('cfgSpeedMax').value),
        active_message_frequency: parseFloat(document.getElementById('cfgActiveFreq').value),
        max_daily_active_messages: parseInt(document.getElementById('cfgMaxDaily').value),
        active_message_cooldown: parseInt(document.getElementById('cfgCooldown').value),
    };
    try {
        const resp = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await resp.json();
        if (result.success) {
            showToast(result.message, 'success');
        } else {
            showToast('保存失败: ' + (result.error || '未知错误'), 'error');
        }
    } catch (err) {
        showToast('网络错误: ' + err.message, 'error');
    }
});

function toggleApiKey() {
    const input = document.getElementById('cfgApiKey');
    input.type = input.type === 'password' ? 'text' : 'password';
}

// ========== Toast ==========
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(40px)';
        toast.style.transition = '0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ========== 工具函数 ==========
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ========== 初始化 ==========
async function loadInitialConfig() {
    try {
        const resp = await fetch('/api/config');
        const cfg = await resp.json();
        if (!cfg.error) {
            document.getElementById('cfgApiUrl').value = cfg.api_url || 'https://api.deepseek.com';
            document.getElementById('cfgModel').value = cfg.model_name || 'deepseek-chat';
            document.getElementById('cfgPace').value = cfg.human_pace || '平衡';
            document.getElementById('cfgMaxHistory').value = cfg.max_history || 30;
            document.getElementById('cfgInterval').value = cfg.check_interval || 1.0;
            document.getElementById('cfgSpeedMin').value = cfg.typing_speed_min || 3;
            document.getElementById('cfgSpeedMax').value = cfg.typing_speed_max || 8;
            document.getElementById('cfgActiveFreq').value = cfg.active_message_frequency || 1.0;
            document.getElementById('cfgMaxDaily').value = cfg.max_daily_active_messages || 25;
            document.getElementById('cfgCooldown').value = cfg.active_message_cooldown || 300;
            if (cfg.api_key) {
                document.getElementById('cfgApiKey').value = cfg.api_key;
            }
        }
    } catch (e) {
        console.error('加载配置失败:', e);
    }
}

loadInitialConfig();
