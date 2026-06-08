const API_BASE = window.location.origin + '/api';

let apiKey = localStorage.getItem('speace_api_key') || '';
let connected = false;

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function setStatus(text, color) {
  const el = $('#conn-status');
  el.textContent = text;
  el.style.color = color || 'inherit';
}

async function req(path, opts = {}) {
  const url = API_BASE + path;
  const headers = { 'Content-Type': 'application/json', 'X-API-Key': apiKey };
  const res = await fetch(url, { ...opts, headers });
  if (res.status === 401 || res.status === 403) {
    setStatus('Autenticazione fallita', '#ef4444');
    connected = false;
  }
  if (!res.ok) return null;
  return res.json();
}

// ------------------------------------------------------------------ #
// Dashboard
// ------------------------------------------------------------------ #

async function loadDashboard() {
  if (!connected) return;
  const data = await req('/state');
  if (!data) return;
  const rt = data.runtime || {};
  const hl = data.health || {};
  $('#runtime-state').textContent = rt.state || '—';
  $('#tick-count').textContent = rt.tick_count ?? '—';
  $('#circadian-phase').textContent = rt.circadian_phase || '—';
  const score = (hl.health_score ?? 0);
  $('#health-value').textContent = (score * 100).toStringAsFixed(0) + '%';
  $('#health-bar').style.width = (score * 100).toStringAsFixed(0) + '%';
  $('#health-bar').style.background = score > 0.8 ? '#2dd4bf' : score > 0.5 ? '#f59e0b' : '#ef4444';

  const list = $('#alert-list');
  list.innerHTML = '';
  (data.alerts || []).forEach(a => {
    const li = document.createElement('li');
    li.className = a.severity || 'info';
    li.textContent = `[${a.severity?.toUpperCase() || 'INFO'}] ${a.message || ''}`;
    list.appendChild(li);
  });
}

// ------------------------------------------------------------------ #
// Dialogue
// ------------------------------------------------------------------ #

async function sendMessage() {
  const input = $('#chat-message');
  const text = input.value.trim();
  if (!text || !connected) return;
  input.value = '';
  appendChat('user', text);
  const res = await req('/dialogue/message', { method: 'POST', body: JSON.stringify({ message: text }) });
  if (res && res.response) {
    appendChat('speace', res.response);
  } else {
    appendChat('speace', 'Errore nella risposta del nodo.');
  }
}

function appendChat(role, text) {
  const box = $('#chat-history');
  const div = document.createElement('div');
  div.className = 'message ' + role;
  div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

// ------------------------------------------------------------------ #
// T122 — Runtime control proposals
// ------------------------------------------------------------------ #

let pendingAction = null;

function showModal(title, body, onConfirm) {
  $('#modal-title').textContent = title;
  $('#modal-body').textContent = body;
  $('#modal').classList.remove('hidden');
  pendingAction = onConfirm;
}

function hideModal() {
  $('#modal').classList.add('hidden');
  pendingAction = null;
}

$('#modal-cancel').addEventListener('click', hideModal);
$('#modal-confirm').addEventListener('click', () => {
  if (pendingAction) pendingAction();
  hideModal();
});

async function proposeRuntimeAction(action) {
  if (!connected) return;
  const res = await req('/runtime/propose', {
    method: 'POST',
    body: JSON.stringify({ action }),
  });
  if (res && res.proposal_id) {
    alert(`Proposta creata: ${res.proposal_id}\nAttendi approvazione.`);
    loadProposals();
  } else {
    alert('Errore nella creazione della proposta.');
  }
}

$$('.ctrl-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const action = btn.dataset.action;
    const labels = { pause: 'Pausa', resume: 'Riprendi', halt: 'Halt', checkpoint: 'Checkpoint' };
    showModal(
      `Conferma: ${labels[action]}`,
      `Stai per richiedere l'azione "${labels[action]}". Questa genererà una proposta di regolazione che dovrà essere approvata prima dell'esecuzione.`,
      () => proposeRuntimeAction(action)
    );
  });
});

async function loadProposals() {
  if (!connected) return;
  const data = await req('/runtime/proposals?status=pending');
  const list = $('#proposal-list');
  list.innerHTML = '';
  if (!data || !data.proposals || data.proposals.length === 0) {
    list.innerHTML = '<li>Nessuna proposta pending</li>';
    return;
  }
  data.proposals.forEach((p, idx) => {
    const li = document.createElement('li');
    const info = document.createElement('div');
    info.innerHTML = `<strong>${p.proposed_action}</strong><br/><small>${p.alert?.message || ''} — Risk: ${(p.risk_score * 100).toFixed(0)}%</small>`;
    const actions = document.createElement('div');
    actions.className = 'proposal-actions';

    const btnApprove = document.createElement('button');
    btnApprove.textContent = '✅ Approva';
    btnApprove.addEventListener('click', () => approveProposal(p.proposal_id));

    const btnReject = document.createElement('button');
    btnReject.textContent = '❌ Rifiuta';
    btnReject.style.background = '#ef4444';
    btnReject.addEventListener('click', () => rejectProposal(p.proposal_id));

    actions.appendChild(btnApprove);
    actions.appendChild(btnReject);
    li.appendChild(info);
    li.appendChild(actions);
    list.appendChild(li);
  });
}

async function approveProposal(proposalId) {
  const res = await req(`/runtime/approve/${proposalId}`, {
    method: 'POST',
    body: JSON.stringify({ reviewer: 'web_user' }),
  });
  if (res && res.status === 'executed') {
    alert('Proposta approvata ed eseguita.');
    loadProposals();
    loadDashboard();
  } else {
    alert('Errore: ' + (res?.error || 'unknown'));
  }
}

async function rejectProposal(proposalId) {
  const res = await req(`/runtime/reject/${proposalId}`, {
    method: 'POST',
    body: JSON.stringify({ reviewer: 'web_user' }),
  });
  if (res && res.status === 'rejected') {
    alert('Proposta rifiutata.');
    loadProposals();
  } else {
    alert('Errore: ' + (res?.error || 'unknown'));
  }
}

$('#btn-refresh-proposals').addEventListener('click', loadProposals);

// ------------------------------------------------------------------ #
// T123 — Nodes
// ------------------------------------------------------------------ #

async function loadNodes() {
  if (!connected) return;
  const data = await req('/nodes');
  const tbody = $('#nodes-table tbody');
  tbody.innerHTML = '';
  if (!data || !data.nodes) {
    tbody.innerHTML = '<tr><td colspan="4">Nessun nodo</td></tr>';
    return;
  }
  const nodes = data.nodes;
  if (Object.keys(nodes).length === 0) {
    tbody.innerHTML = '<tr><td colspan="4">Nessun nodo registrato</td></tr>';
    return;
  }
  Object.entries(nodes).forEach(([id, node]) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${id}</td>
      <td>${node.trust_score ?? '—'}</td>
      <td>${node.last_seen ? new Date(node.last_seen * 1000).toLocaleString() : '—'}</td>
      <td>${node.online ? '🟢 Online' : '🔴 Offline'}</td>
    `;
    tbody.appendChild(tr);
  });
}

$('#btn-refresh-nodes').addEventListener('click', loadNodes);

// ------------------------------------------------------------------ #
// Tabs
// ------------------------------------------------------------------ #

$$('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    $$('.tab-btn').forEach(b => b.classList.remove('active'));
    $$('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    $(`#${btn.dataset.tab}`).classList.add('active');
  });
});

// ------------------------------------------------------------------ #
// Connect / init
// ------------------------------------------------------------------ #

$('#btn-connect').addEventListener('click', async () => {
  apiKey = $('#api-key').value.trim();
  if (!apiKey) { setStatus('Inserisci API key', '#f59e0b'); return; }
  const data = await req('/health');
  if (data && data.status === 'ok') {
    connected = true;
    localStorage.setItem('speace_api_key', apiKey);
    setStatus('Connesso', '#2dd4bf');
    loadDashboard();
    loadProposals();
    loadNodes();
  } else {
    setStatus('Connessione fallita', '#ef4444');
  }
});

$('#btn-send').addEventListener('click', sendMessage);
$('#chat-message').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') sendMessage();
});

if (apiKey) {
  $('#api-key').value = apiKey;
  $('#btn-connect').click();
}

setInterval(() => {
  loadDashboard();
  loadProposals();
}, 5000);
