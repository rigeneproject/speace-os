/* SPEACE AGI Team — Dashboard Application */

const API = '';
let agents = [];
let planData = {};
let ws = null;
let currentChatAgent = null;

// ── Initialization ──────────────────────────────────────────────────
async function init() {
  await loadStatus();
  await loadAgents();
  await loadPlan();
  await loadSpeaceContext();
  await loadOrchestrator();
  await loadHealthAlerts();
  await loadAutoAnalysis();
  setupTabs();
  setupModals();
  setupWebSocket();
  setupEventListeners();
  setupResearch();
}

// ── API Calls ───────────────────────────────────────────────────────
async function api(path, opts = {}) {
  try {
    const res = await fetch(`${API}${path}`, {
      headers: { 'Content-Type': 'application/json', ...opts.headers },
      ...opts,
    });
    return await res.json();
  } catch (e) {
    console.error('API error:', e);
    return null;
  }
}

async function loadStatus() {
  const data = await api('/api/status');
  if (data) {
    document.getElementById('agentCount').textContent = data.agents_count || '...';
    const pct = (data.plan_progress || 0) * 100;
    document.getElementById('planProgress').textContent = pct.toFixed(0) + '%';
    document.getElementById('modelName').textContent = data.model || '...';
  }
}

async function loadAgents() {
  agents = (await api('/api/agents'))?.agents || [];
  renderAgentCards(agents);
  renderChatAgentList(agents);
  updateAgentLists(agents);
}

async function loadPlan() {
  planData = await api('/api/plan');
  renderPlan();
}

async function loadSpeaceContext() {
  const ctx = await api('/api/speace/context');
  renderSpeaceContext(ctx);
}

// ── Orchestrator ────────────────────────────────────────────────────
async function loadOrchestrator() {
  const data = await api('/api/orchestrator/status');
  renderOrchestrator(data);
  const health = await api('/api/orchestrator/health');
  renderHealth(health);
  const load = await api('/api/orchestrator/load');
  renderLoad(load);
}

function renderOrchestrator(data) {
  const el = document.getElementById('orchestratorStatus');
  if (!data || data.running === false) {
    el.innerHTML = '<span class="health-status warn">Non avviato</span>';
    return;
  }
  const sched = data.scheduler || {};
  el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:6px;font-size:0.9em;">
      <div><strong>Stato:</strong> <span class="health-status ok">Attivo</span></div>
      <div>Findings totali: <strong>${sched.findings_count || 0}</strong></div>
      <div>Task eseguiti: <strong>${data.executions_count || 0}</strong></div>
      <div>Ultima chief-review: <strong>${Math.round(sched.seconds_since_chief || 0)}s</strong> fa (intervallo ${sched.chief_interval}s)</div>
      <div>Ultima supervisor-review: <strong>${Math.round(sched.seconds_since_supervisors || 0)}s</strong> fa (intervallo ${sched.supervisor_interval}s)</div>
    </div>
  `;
}

function renderHealth(health) {
  const el = document.getElementById('healthMonitor');
  if (!health) { el.innerHTML = 'Nessun dato'; return; }
  const status = health.ok ? 'ok' : 'alert';
  const statusLabel = health.ok ? 'OK' : 'ALLARME';
  el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:6px;font-size:0.9em;">
      <div><strong>Stato:</strong> <span class="health-status ${status}">${statusLabel}</span></div>
      <div>Coherence φ: <strong>${health.coherence_phi ?? 'N/A'}</strong></div>
      <div>Tick: <strong>${health.tick ?? 'N/A'}</strong></div>
      <div>CPU: <strong>${health.cpu !== null ? (health.cpu * 100).toFixed(1) + '%' : 'N/A'}</strong></div>
      <div>Memoria: <strong>${health.memory !== null ? (health.memory * 100).toFixed(1) + '%' : 'N/A'}</strong></div>
      ${(health.alerts || []).length > 0 ? `
        <div style="margin-top:8px;">
          <strong>Alert recenti:</strong>
          <ul style="margin-top:4px;padding-left:20px;">
            ${health.alerts.map(a => `<li style="color:var(--accent-red);font-size:0.85em;">${a}</li>`).join('')}
          </ul>
        </div>
      ` : ''}
      <div style="color:var(--text-dim);font-size:0.75em;margin-top:8px;">Check: ${(health.checks || []).join(', ')}</div>
    </div>
  `;
}

function renderLoad(loadData) {
  const el = document.getElementById('loadDistribution');
  if (!loadData || !loadData.distribution) { el.innerHTML = 'Nessun dato'; return; }
  const entries = Object.entries(loadData.distribution).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) { el.innerHTML = 'Nessun agente'; return; }
  const max = Math.max(...entries.map(e => e[1]), 1);
  el.innerHTML = entries.map(([aid, score]) => `
    <div class="load-bar">
      <span class="load-bar-name">${aid}</span>
      <div class="load-bar-track">
        <div class="load-bar-fill" style="width:${Math.min(100, (score / max) * 100)}%"></div>
      </div>
      <span class="load-bar-value">${score.toFixed(1)}</span>
    </div>
  `).join('');
}

async function loadHealthAlerts() {
  const data = await api('/api/health/alerts?n=10');
  // (Rendered inside renderHealth if needed)
}

async function loadAutoAnalysis() {
  const data = await api('/api/auto-analysis/recent?n=15');
  const el = document.getElementById('autoAnalysisList');
  if (!data || !data.findings || data.findings.length === 0) {
    el.innerHTML = '<p style="color:var(--text-dim);">Nessuna auto-analisi ancora registrata. Aspetta il primo ciclo schedulato o premi "Forza Tick".</p>';
    return;
  }
  el.innerHTML = data.findings.reverse().map(f => `
    <div class="auto-analysis-item kind-${f.kind}">
      <div class="auto-analysis-meta">
        <strong>${f.kind}</strong> · ${f.agent_id} · ${new Date(f.ts * 1000).toLocaleString('it-IT')}
      </div>
      <div class="auto-analysis-content">${escapeHtml(f.content).slice(0, 600)}${f.content.length > 600 ? '...' : ''}</div>
    </div>
  `).join('');
}

// ── Rendering ───────────────────────────────────────────────────────
function renderAgentCards(agents) {
  const grid = document.getElementById('agentsGrid');
  grid.innerHTML = agents.map(a => `
    <div class="agent-card">
      <div class="agent-card-header">
        <span class="agent-card-name">${a.name || a.id}</span>
        <span class="agent-badge ${a.type === 'supervisor' ? 'badge-supervisor' : 'badge-technician'}">
          ${a.type || 'agent'}
        </span>
      </div>
      <div class="agent-card-role">${a.role || ''}</div>
      <div class="agent-card-desc">${a.description || ''}</div>
      <div style="display:flex;gap:6px;font-size:0.75em;color:var(--text-dim);margin-bottom:8px;">
        <span>Tasks: ${a.tasks_count || 0}</span>
        <span>Analisi: ${a.findings_count || 0}</span>
        <span>Stato: ${a.status || 'idle'}</span>
      </div>
      <div class="agent-card-actions">
        <button class="btn btn-primary btn-small" onclick="openChat('${a.id}')">Chat</button>
        <button class="btn btn-secondary btn-small" onclick="analyzeAgent('${a.id}')">Analizza</button>
      </div>
    </div>
  `).join('');
}

function updateAgentLists(agents) {
  const supervisors = agents.filter(a => a.type === 'supervisor');
  const technicians = agents.filter(a => a.type === 'technician');

  document.getElementById('supervisorList').innerHTML = supervisors.map(a => `
    <div class="agent-item" onclick="openChat('${a.id}')">
      <span class="agent-status ${a.status || 'idle'}"></span>
      <div class="agent-info">
        <div class="agent-name">${a.name || a.id}</div>
        <div class="agent-role">${a.role || ''}</div>
      </div>
      <span class="agent-badge badge-supervisor">supervisor</span>
    </div>
  `).join('');

  document.getElementById('technicianList').innerHTML = technicians.map(a => `
    <div class="agent-item" onclick="openChat('${a.id}')">
      <span class="agent-status ${a.status || 'idle'}"></span>
      <div class="agent-info">
        <div class="agent-name">${a.name || a.id}</div>
        <div class="agent-role">${a.role || ''}</div>
      </div>
      <span class="agent-badge badge-technician">tecnico</span>
    </div>
  `).join('');
}

function renderChatAgentList(agents) {
  const list = document.getElementById('chatAgentList');
  list.innerHTML = agents.map(a => `
    <div class="chat-agent-item" data-id="${a.id}" onclick="openChat('${a.id}')">
      ${a.name || a.id}
    </div>
  `).join('');
}

function renderPlan() {
  const pct = ((planData?.overall_progress || 0) * 100).toFixed(1);
  document.getElementById('progressPercent').textContent = pct + '%';
  document.getElementById('progressArc').style.strokeDasharray = `${pct}, ${100 - pct}`;
  document.getElementById('planProgressBar').style.width = pct + '%';
  document.getElementById('planProgressLabel').textContent = pct + '%';

  const milestones = document.getElementById('milestonesContainer');
  milestones.innerHTML = (planData?.milestones || []).map((m, i) => `
    <div class="milestone-card">
      <div class="milestone-card-header">
        <span class="milestone-title">${m.id}: ${m.title}</span>
        <span class="milestone-status ${m.status}">${m.status}</span>
      </div>
      <div class="milestone-desc">${m.description || ''}</div>
      <div class="milestone-bar">
        <div class="milestone-bar-fill" style="width:${(m.progress || 0) * 100}%"></div>
      </div>
      <div style="font-size:0.75em;color:var(--text-dim);margin-top:4px;">
        ${((m.progress || 0) * 100).toFixed(0)}% · Agenti: ${(m.agents || []).join(', ')}
      </div>
    </div>
  `).join('');

  // Summary milestones in dashboard
  const msList = document.getElementById('milestoneList');
  msList.innerHTML = (planData?.milestones || []).map(m => `
    <div class="milestone-item">
      <span>${m.id}: ${m.title}</span>
      <span class="milestone-status ${m.status}">${((m.progress || 0) * 100).toFixed(0)}%</span>
    </div>
  `).join('');

  // Tasks
  const tasksContainer = document.getElementById('tasksContainer');
  if (planData && planData.total_tasks > 0) {
    const stats = `
      <h3 style="margin-bottom:8px;font-size:1em;">Task (${planData.total_tasks})</h3>
      <div style="display:flex;gap:16px;font-size:0.85em;margin-bottom:12px;">
        <span>✅ Completati: ${planData.completed_tasks || 0}</span>
        <span>⏳ In attesa: ${planData.pending_tasks || 0}</span>
        <span>❌ Falliti: ${planData.failed_tasks || 0}</span>
      </div>
    `;
    api('/api/plan/tasks').then(td => {
      const list = (td && td.tasks) || [];
      const items = list.map(t => `
        <div class="task-item" data-id="${t.id}">
          <div class="task-item-header">
            <strong>${t.id}</strong>: ${escapeHtml(t.title || '')}
            <span class="task-status task-${t.status}">${t.status}</span>
            <span class="task-priority task-priority-${t.priority}">${t.priority}</span>
          </div>
          <div class="task-item-desc">${escapeHtml(t.description || '').slice(0, 200)}</div>
          <div class="task-item-meta">
            <span>Agente: <strong>${t.agent_id}</strong></span>
            ${t.milestone_id ? `<span>Milestone: <strong>${t.milestone_id}</strong></span>` : ''}
            ${t.status === 'pending' ? `<button class="btn btn-primary btn-small" onclick="executeTask('${t.id}')">Esegui</button>` : ''}
          </div>
        </div>
      `).join('');
      tasksContainer.innerHTML = stats + (list.length > 0 ? `<div class="task-list">${items}</div>` : '<p style="color:var(--text-dim);">Nessun task in lista</p>');
    });
  } else {
    tasksContainer.innerHTML = '<p style="color:var(--text-dim);font-size:0.85em;">Nessun task ancora creato</p>';
  }
}

async function executeTask(taskId) {
  const data = await api(`/api/plan/task/${taskId}/execute`, { method: 'POST' });
  if (data && data.outcome) {
    alert(`Task ${taskId}: ${data.outcome.toUpperCase()}\nAgente: ${data.agent_id}\nSteps: ${data.steps.length}`);
    loadPlan();
  } else if (data && data.error) {
    alert(`Errore: ${data.error}`);
  }
}

// ── Web Research ───────────────────────────────────────────────────
function setupResearch() {
  // Populate agent selectors
  const populateSelect = (sel, includeNone = false) => {
    sel.innerHTML = (includeNone ? '<option value="">(ricerca diretta)</option>' : '') +
      agents.map(a => `<option value="${a.id}">${a.name || a.id}</option>`).join('');
  };
  populateSelect(document.getElementById('researchAgent'), true);
  populateSelect(document.getElementById('historyAgent'));

  document.getElementById('runResearchBtn').addEventListener('click', runResearch);
  document.getElementById('clearResearchBtn').addEventListener('click', () => {
    document.getElementById('researchQuery').value = '';
    document.getElementById('researchResults').innerHTML = 'Nessuna ricerca eseguita.';
    document.getElementById('researchStatus').textContent = '';
  });
  document.getElementById('loadHistoryBtn').addEventListener('click', loadResearchHistory);
  document.getElementById('chatWebSearchBtn').addEventListener('click', () => {
    if (!currentChatAgent) {
      alert('Seleziona prima un agente');
      return;
    }
    switchTab('research');
    const sel = document.getElementById('researchAgent');
    sel.value = currentChatAgent;
    document.getElementById('researchQuery').focus();
  });
}

async function runResearch() {
  const query = document.getElementById('researchQuery').value.trim();
  if (!query) { alert('Inserisci una query'); return; }
  const agentId = document.getElementById('researchAgent').value;
  const maxResults = parseInt(document.getElementById('researchMaxResults').value) || 5;
  const fetchTop = parseInt(document.getElementById('researchFetchTop').value) || 2;
  const synthesize = document.getElementById('researchSynthesize').checked;

  const statusEl = document.getElementById('researchStatus');
  const resultsEl = document.getElementById('researchResults');
  statusEl.textContent = agentId
    ? `Ricerca in corso come ${agentId}... (max ${maxResults} risultati, leggi top ${fetchTop})`
    : `Ricerca diretta in corso... (max ${maxResults} risultati)`;
  resultsEl.innerHTML = '<p style="color:var(--text-dim);">Ricerca in corso, attendere...</p>';

  let data;
  if (agentId) {
    data = await api(`/api/agents/${agentId}/research`, {
      method: 'POST',
      body: JSON.stringify({ query, max_results: maxResults, fetch_top: fetchTop, synthesis: synthesize }),
    });
  } else {
    data = await api('/api/web/research', {
      method: 'POST',
      body: JSON.stringify({ query, max_results: maxResults, fetch_top: fetchTop }),
    });
  }

  if (!data) {
    resultsEl.innerHTML = '<p style="color:var(--accent-red);">Errore nella ricerca</p>';
    statusEl.textContent = 'Fallita';
    return;
  }

  renderResearchResults(data);
  statusEl.textContent = `Ricerca completata: ${(data.results || []).length} risultati, ${(data.documents || []).length} documenti letti`;
}

function renderResearchResults(data) {
  const el = document.getElementById('researchResults');
  const parts = [];
  parts.push(`<h3 style="margin-bottom:8px;">Risultati per: "${escapeHtml(data.query || '')}"</h3>`);

  if (data.synthesis) {
    parts.push(`
      <div class="research-result-block synthesis">
        <div class="research-result-title">Sintesi dell'agente</div>
        <div class="research-result-text">${escapeHtml(data.synthesis)}</div>
      </div>
    `);
  }

  if (data.results && data.results.length > 0) {
    parts.push(`<h4 style="margin:12px 0 6px;font-size:0.95em;">Risultati web (${data.results.length})</h4>`);
    data.results.forEach((r, i) => {
      parts.push(`
        <div class="research-result-block">
          <div class="research-result-title">[${i+1}] ${escapeHtml(r.title || '')}</div>
          <div class="research-result-url"><a href="${escapeHtml(r.url || '')}" target="_blank" rel="noopener">${escapeHtml(r.url || '')}</a></div>
          ${r.snippet ? `<div class="research-result-snippet">${escapeHtml(r.snippet)}</div>` : ''}
        </div>
      `);
    });
  }

  if (data.documents && data.documents.length > 0) {
    parts.push(`<h4 style="margin:12px 0 6px;font-size:0.95em;">Documenti letti (${data.documents.length})</h4>`);
    data.documents.forEach((d, i) => {
      parts.push(`
        <div class="research-result-block doc">
          <div class="research-result-title">[Doc ${i+1}] ${escapeHtml(d.title || d.url || '')}</div>
          <div class="research-result-url"><a href="${escapeHtml(d.url || '')}" target="_blank" rel="noopener">${escapeHtml(d.url || '')}</a> — ${d.length || 0} caratteri</div>
          ${d.error ? `<div class="research-result-text" style="color:var(--accent-red);">Errore: ${escapeHtml(d.error)}</div>` : ''}
          ${d.text ? `<details><summary>Contenuto estratto</summary><div class="research-result-text">${escapeHtml(d.text)}</div></details>` : ''}
        </div>
      `);
    });
  }

  if ((!data.results || data.results.length === 0) && (!data.documents || data.documents.length === 0)) {
    parts.push('<p style="color:var(--text-dim);">Nessun risultato trovato.</p>');
  }

  el.innerHTML = parts.join('');
}

async function loadResearchHistory() {
  const agentId = document.getElementById('historyAgent').value;
  if (!agentId) return;
  const data = await api(`/api/agents/${agentId}/research-history?n=20`);
  const el = document.getElementById('researchHistory');
  if (!data || !data.history || data.history.length === 0) {
    el.innerHTML = '<p style="color:var(--text-dim);">Nessuna ricerca registrata per questo agente.</p>';
    return;
  }
  el.innerHTML = data.history.map(h => {
    const ts = new Date(h.ts * 1000).toLocaleString('it-IT');
    const label = h.type === 'search' ? `Query: ${escapeHtml(h.query || '')}` :
                  h.type === 'fetch' ? `URL: ${escapeHtml((h.url || '').slice(0, 60))}` :
                  `Research: ${escapeHtml(h.query || '')} (${h.results_count || 0} risultati)`;
    return `
      <div class="research-history-item">
        <span class="research-history-type ${h.type}">${h.type}</span>
        <span style="flex:1;">${label}</span>
        <span style="color:var(--text-dim);font-size:0.85em;">${ts}</span>
      </div>
    `;
  }).join('');
}

function renderSpeaceContext(ctx) {
  if (!ctx || ctx.status === 'no_data') {
    document.getElementById('speaceMetrics').innerHTML =
      '<p style="color:var(--text-dim);">Dati SPEACE non disponibili. Avvia il runtime SPEACE prima.</p>';
    return;
  }

  const metrics = [
    { label: 'Coerenza Phi', value: ctx.coherence_phi ?? 'N/A', fmt: v => typeof v === 'number' ? v.toFixed(4) : v },
    { label: 'Energia Media', value: ctx.mean_energy ?? 'N/A', fmt: v => typeof v === 'number' ? (v * 100).toFixed(1) + '%' : v },
    { label: 'Neuroni Attivi', value: ctx.active_neurons ?? 'N/A', fmt: v => v },
    { label: 'Tick', value: ctx.tick ?? 'N/A', fmt: v => v },
    { label: 'CPU', value: ctx.cpu ?? 'N/A', fmt: v => typeof v === 'number' ? (v * 100).toFixed(1) + '%' : v },
    { label: 'Memoria', value: ctx.memory ?? 'N/A', fmt: v => typeof v === 'number' ? (v * 100).toFixed(1) + '%' : v },
    { label: 'Disk', value: ctx.disk ?? 'N/A', fmt: v => typeof v === 'number' ? (v * 100).toFixed(1) + '%' : v },
  ];

  document.getElementById('speaceMetrics').innerHTML = metrics.map(m => `
    <div class="metric-card">
      <div class="metric-value">${m.fmt(m.value)}</div>
      <div class="metric-label">${m.label}</div>
    </div>
  `).join('');

  document.getElementById('speaceRawData').textContent = JSON.stringify(ctx, null, 2);
}

// ── Chat ────────────────────────────────────────────────────────────
async function openChat(agentId) {
  currentChatAgent = agentId;
  document.getElementById('chatAgentName').textContent =
    agents.find(a => a.id === agentId)?.name || agentId;
  document.getElementById('chatMessages').innerHTML =
    '<div style="text-align:center;color:var(--text-dim);font-size:0.85em;">Caricamento conversazione...</div>';

  // Highlight in sidebar
  document.querySelectorAll('.chat-agent-item').forEach(el => el.classList.remove('active'));
  const item = document.querySelector(`.chat-agent-item[data-id="${agentId}"]`);
  if (item) item.classList.add('active');

  // Load conversation
  const data = await api(`/api/agents/${agentId}/conversation`);
  const messages = document.getElementById('chatMessages');
  const conv = data?.conversation || [];
  if (conv.length === 0) {
    messages.innerHTML = '<div class="chat-placeholder">Inizia una conversazione con questo agente</div>';
  } else {
    messages.innerHTML = conv.map(m => `
      <div class="chat-msg ${m.role === 'user' ? 'user' : 'agent'}">
        <div class="chat-msg-label">${m.role === 'user' ? 'Tu' : agents.find(a => a.id === agentId)?.name}</div>
        ${m.content}
      </div>
    `).join('');
    messages.scrollTop = messages.scrollHeight;
  }

  // Switch to chat tab
  switchTab('chat');
}

async function sendChat() {
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if (!msg || !currentChatAgent) return;

  input.value = '';
  const messages = document.getElementById('chatMessages');

  // Add user message
  const userDiv = document.createElement('div');
  userDiv.className = 'chat-msg user';
  userDiv.innerHTML = `<div class="chat-msg-label">Tu</div>${escapeHtml(msg)}`;
  messages.appendChild(userDiv);
  messages.scrollTop = messages.scrollHeight;

  // Add loading indicator
  const loadingDiv = document.createElement('div');
  loadingDiv.className = 'chat-msg agent';
  loadingDiv.innerHTML = '<div class="chat-msg-label">Elaborazione...</div><em>Sto pensando...</em>';
  loadingDiv.id = 'chatLoading';
  messages.appendChild(loadingDiv);
  messages.scrollTop = messages.scrollHeight;

  // Send to API
  const data = await api(`/api/agents/${currentChatAgent}/chat`, {
    method: 'POST',
    body: JSON.stringify({ message: msg }),
  });

  // Remove loading
  const loading = document.getElementById('chatLoading');
  if (loading) loading.remove();

  if (data) {
    const agentDiv = document.createElement('div');
    agentDiv.className = 'chat-msg agent';
    const agentName = agents.find(a => a.id === currentChatAgent)?.name || currentChatAgent;
    agentDiv.innerHTML = `<div class="chat-msg-label">${agentName}</div>${escapeHtml(data.response || 'Nessuna risposta')}`;
    messages.appendChild(agentDiv);
    messages.scrollTop = messages.scrollHeight;
  }
}

// ── Agent Actions ───────────────────────────────────────────────────
async function analyzeAgent(agentId) {
  const btn = event?.target;
  if (btn) { btn.textContent = 'Analizzando...'; btn.disabled = true; }
  const data = await api(`/api/agents/${agentId}/analyze`, { method: 'POST' });
  if (btn) { btn.textContent = 'Analizza'; btn.disabled = false; }
  if (data) {
    openChat(agentId);
    setTimeout(() => sendMessageToChat('Analizza lo stato corrente di SPEACE e fornisci un report dettagliato'), 500);
  }
}

async function broadcastAll() {
  document.getElementById('broadcastModal').classList.add('active');
}

async function sendBroadcast() {
  const input = document.getElementById('broadcastInput');
  const msg = input.value.trim();
  if (!msg) return;

  const resultsDiv = document.getElementById('broadcastResults');
  resultsDiv.innerHTML = '<div style="color:var(--text-dim);">Invio in corso...</div>';

  const data = await api('/api/broadcast', {
    method: 'POST',
    body: JSON.stringify({ message: msg }),
  });

  if (data) {
    const responses = data.responses || {};
    resultsDiv.innerHTML = Object.entries(responses).map(([aid, resp]) => `
      <div class="broadcast-result-item">
        <strong>${agents.find(a => a.id === aid)?.name || aid}:</strong>
        <span>${resp.slice(0, 200)}${resp.length > 200 ? '...' : ''}</span>
      </div>
    `).join('');
  }
}

function sendMessageToChat(msg) {
  document.getElementById('chatInput').value = msg;
  sendChat();
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ── Tab System ──────────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      switchTab(target);
    });
  });
}

function switchTab(tabName) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelector(`.tab[data-tab="${tabName}"]`)?.classList.add('active');
  document.getElementById(`tab-${tabName}`)?.classList.add('active');
}

// ── Modals ──────────────────────────────────────────────────────────
function setupModals() {
  document.querySelectorAll('.modal-close').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
    });
  });

  // Close modal on backdrop click
  document.querySelectorAll('.modal').forEach(m => {
    m.addEventListener('click', (e) => {
      if (e.target === m) m.classList.remove('active');
    });
  });
}

// ── WebSocket ───────────────────────────────────────────────────────
function setupWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${location.host}/ws`;

  try {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => console.log('WebSocket connected');
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleWSMessage(msg);
      } catch (e) { /* ignore */ }
    };
    ws.onclose = () => {
      setTimeout(setupWebSocket, 3000);
    };
  } catch (e) {
    console.warn('WebSocket not available');
  }
}

function handleWSMessage(msg) {
  if (msg.type === 'agent_chat' && currentChatAgent === msg.agent_id) {
    // Already handled by the REST response
  } else if (msg.type === 'plan_milestone_updated') {
    loadPlan();
  } else if (msg.type === 'plan_task_added' || msg.type === 'plan_task_completed') {
    loadPlan();
  } else if (msg.type === 'agent_analysis') {
    loadAgents();
  } else if (msg.type === 'task_executed') {
    loadPlan();
  } else if (msg.type === 'health_alerts') {
    if (document.getElementById('tab-orchestrator').classList.contains('active')) {
      loadOrchestrator();
    }
  } else if (msg.type === 'bulk_analysis_progress') {
    // Could update a progress bar
  }
}

// ── Event Listeners ─────────────────────────────────────────────────
function setupEventListeners() {
  // Chat
  document.getElementById('chatSendBtn').addEventListener('click', sendChat);
  document.getElementById('chatInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });
  document.getElementById('chatClearBtn').addEventListener('click', async () => {
    if (currentChatAgent) {
      await api(`/api/agents/${currentChatAgent}/clear`, { method: 'POST' });
      document.getElementById('chatMessages').innerHTML =
        '<div class="chat-placeholder">Conversazione pulita</div>';
    }
  });

  // Filter buttons
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const filter = btn.dataset.filter;
      const filtered = filter === 'all' ? agents : agents.filter(a => (a.type || '').toLowerCase() === filter);
      renderAgentCards(filtered);
    });
  });

  // Broadcast
  document.getElementById('broadcastBtn').addEventListener('click', broadcastAll);
  document.getElementById('broadcastChatBtn').addEventListener('click', broadcastAll);
  document.getElementById('broadcastSendBtn').addEventListener('click', sendBroadcast);

  // Analyze all
  document.getElementById('analyzeBtn').addEventListener('click', async () => {
    document.getElementById('analyzeBtn').textContent = 'Analisi in corso...';
    document.getElementById('analyzeBtn').disabled = true;
    for (const a of agents) {
      await api(`/api/agents/${a.id}/analyze`, { method: 'POST' });
    }
    document.getElementById('analyzeBtn').textContent = 'Analizza SPEACE';
    document.getElementById('analyzeBtn').disabled = false;
    loadAgents();
  });

  // Plan
  document.getElementById('addTaskBtn').addEventListener('click', () => {
    const agentSelect = document.getElementById('taskAgent');
    agentSelect.innerHTML = agents.map(a =>
      `<option value="${a.id}">${a.name || a.id}</option>`
    ).join('');

    const msSelect = document.getElementById('taskMilestone');
    msSelect.innerHTML = (planData?.milestones || []).map(m =>
      `<option value="${m.id}">${m.id}: ${m.title}</option>`
    ).join('');

    document.getElementById('taskModal').classList.add('active');
  });

  document.getElementById('taskSaveBtn').addEventListener('click', async () => {
    const task = {
      title: document.getElementById('taskTitle').value,
      description: document.getElementById('taskDesc').value,
      agent_id: document.getElementById('taskAgent').value,
      priority: document.getElementById('taskPriority').value,
      milestone_id: document.getElementById('taskMilestone').value,
    };
    if (!task.title) return;
    await api('/api/plan/task', { method: 'POST', body: JSON.stringify(task) });
    document.getElementById('taskModal').classList.remove('active');
    document.getElementById('taskTitle').value = '';
    document.getElementById('taskDesc').value = '';
    loadPlan();
  });

  document.getElementById('refreshPlanBtn').addEventListener('click', loadPlan);

  // Refresh SPEACE context
  setInterval(loadSpeaceContext, 10000);
  setInterval(loadStatus, 15000);
  // Refresh orchestrator every 30s
  setInterval(() => {
    if (document.getElementById('tab-orchestrator').classList.contains('active')) {
      loadOrchestrator();
      loadAutoAnalysis();
    }
  }, 30000);

  // Orchestrator buttons
  const triggerTickBtn = document.getElementById('triggerTickBtn');
  if (triggerTickBtn) {
    triggerTickBtn.addEventListener('click', async () => {
      triggerTickBtn.textContent = 'In corso...';
      triggerTickBtn.disabled = true;
      await api('/api/orchestrator/tick', { method: 'POST' });
      await loadOrchestrator();
      await loadAutoAnalysis();
      triggerTickBtn.textContent = 'Forza Tick';
      triggerTickBtn.disabled = false;
    });
  }
  const triggerAnalyzeAllBtn = document.getElementById('triggerAnalyzeAllBtn');
  if (triggerAnalyzeAllBtn) {
    triggerAnalyzeAllBtn.addEventListener('click', async () => {
      triggerAnalyzeAllBtn.textContent = 'Analisi in corso...';
      triggerAnalyzeAllBtn.disabled = true;
      await api('/api/agents/analyze-all', { method: 'POST', body: '{}' });
      await loadAgents();
      await loadAutoAnalysis();
      triggerAnalyzeAllBtn.textContent = 'Analizza Tutti';
      triggerAnalyzeAllBtn.disabled = false;
    });
  }
}

// ── Start ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
