/** Vanilla JS dashboard updater — polls /api/state every 1000 ms. */
(function () {
  'use strict';

  const POLL_INTERVAL = 1000;

  const els = {
    headerMeta: document.getElementById('header-meta'),
    connStatus: document.getElementById('conn-status'),
    connText: document.getElementById('conn-text'),
    errorBanner: document.getElementById('error-banner'),
    logStream: document.getElementById('log-stream'),
    driveList: document.getElementById('drive-list'),
    smNarrative: document.getElementById('sm-narrative'),
    distNodes: document.getElementById('dist-nodes'),
  };

  let _health = null;

  function fmtNum(n, digits) {
    if (n === null || n === undefined || Number.isNaN(n)) return '—';
    return Number(n).toFixed(digits);
  }

  function fmtBytes(b) {
    if (!b || Number.isNaN(b)) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let idx = 0;
    while (b >= 1024 && idx < units.length - 1) { b /= 1024; idx++; }
    return b.toFixed(1) + ' ' + units[idx];
  }

  function setConn(ok, text) {
    els.connStatus.style.background = ok ? 'var(--accent-green)' : 'var(--accent-red)';
    els.connText.textContent = text;
    els.errorBanner.style.display = ok ? 'none' : 'block';
    if (!ok) els.errorBanner.textContent = text;
  }

  async function fetchHealth() {
    try {
      const r = await fetch('/api/health');
      if (!r.ok) throw new Error('HTTP ' + r.status);
      _health = await r.json();
      setConn(true, 'connected');
      if (_health) {
        els.headerMeta.textContent = `${_health.speace_version || '0.0.0'} | uptime: ${_health.uptime_seconds || 0}s`;
      }
    } catch (e) {
      setConn(false, 'disconnected');
    }
  }

  async function fetchLogs() {
    try {
      const r = await fetch('/api/logs');
      if (!r.ok) return;
      const logs = await r.json();
      renderLogs(logs);
    } catch (e) {
      // silently fail — logs are non-critical
    }
  }

  function renderLogs(logs) {
    if (!Array.isArray(logs) || logs.length === 0) {
      els.logStream.innerHTML = '<div class="log-entry">No events</div>';
      return;
    }
    els.logStream.innerHTML = logs.slice().reverse().map(ev => {
      const ts = new Date((ev.timestamp || Date.now()) * 1000).toISOString().split('T')[1].replace('Z', '');
      const type = ev.event_type || 'unknown';
      const src = ev.source_id || ev.region_id || 'system';
      return `<div class="log-entry"><span class="log-time">${ts}</span> [${type}] ${src}</div>`;
    }).join('');
  }

  function renderDrives(drives) {
    if (!Array.isArray(drives) || drives.length === 0) {
      els.driveList.innerHTML = '<div class="drive-item"><span class="drive-name">No drives</span></div>';
      return;
    }
    els.driveList.innerHTML = drives.map(d => {
      const level = Math.max(0, Math.min(1, d.level || 0));
      const pct = (level * 100).toFixed(0);
      const color = level > 0.7 ? 'var(--accent-red)' : level > 0.4 ? 'var(--accent-yellow)' : 'var(--accent-green)';
      return (
        `<div class="drive-item">` +
        `<span class="drive-name">${d.name || 'unknown'}</span>` +
        `<div class="drive-bar"><div class="drive-bar-inner" style="width:${pct}%; background:${color}"></div></div>` +
        `<span class="drive-value">${pct}%</span>` +
        `</div>`
      );
    }).join('');
  }

  function renderNarrative(items, container) {
    if (!Array.isArray(items) || items.length === 0) {
      container.innerHTML = '<li>—</li>';
      return;
    }
    container.innerHTML = items.slice().reverse().map(it => {
      let txt = '';
      if (typeof it === 'string') txt = it;
      else if (it.title) txt = it.title;
      else if (it.event) txt = it.event;
      else txt = JSON.stringify(it).slice(0, 80);
      return `<li>${txt}</li>`;
    }).join('');
  }

  function renderNodes(nodes, container) {
    if (!Array.isArray(nodes) || nodes.length === 0) {
      container.innerHTML = '<li>—</li>';
      return;
    }
    container.innerHTML = nodes.map(n => {
      const id = n.node_id || '?';
      const trust = (n.trust_score !== undefined) ? fmtNum(n.trust_score, 2) : '?';
      return `<li>${id} (trust ${trust})</li>`;
    }).join('');
  }

  function updateBar(id, val, max) {
    const inner = document.getElementById(id);
    if (!inner) return;
    const pct = Math.max(0, Math.min(100, (val / max) * 100));
    inner.style.width = pct + '%';
    inner.className = 'gauge-bar-inner ' + (pct > 80 ? 'red' : pct > 50 ? 'yellow' : 'green');
  }

  async function fetchState() {
    try {
      const r = await fetch('/api/state');
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      setConn(true, 'connected');
      applyState(data);
    } catch (e) {
      setConn(false, e.message || 'disconnected');
    }
  }

  function applyState(s) {
    const sum = s.organismic_summary || {};
    document.getElementById('ov-coherence').textContent = fmtNum(sum.coherence_phi, 3);
    document.getElementById('ov-energy').textContent = fmtNum(sum.mean_energy, 3);
    document.getElementById('ov-neurons').textContent = sum.active_neurons || 0;
    document.getElementById('ov-ticks').textContent = sum.ticks || 0;

    const sens = s.sensors || {};
    const cpu = sens.cpu || 0;
    const mem = sens.memory ? sens.memory / (1024 * 1024 * 1024) : 0; // rough GB if raw bytes
    const memPct = sens.memory ? Math.min(100, (sens.memory / (16 * 1024 * 1024 * 1024)) * 100) : 0; // assume 16GB for bar
    const temp = sens.temperature || 0;
    const net = sens.network || 0;

    document.getElementById('s-cpu').textContent = cpu.toFixed(1) + '%';
    updateBar('b-cpu', cpu, 100);
    document.getElementById('s-mem').textContent = mem.toFixed(2) + ' GB';
    updateBar('b-mem', memPct, 100);
    document.getElementById('s-temp').textContent = temp.toFixed(1) + ' C';
    updateBar('b-temp', temp, 100);
    document.getElementById('s-net').textContent = fmtBytes(net);
    updateBar('b-net', net, 1e9); // assume 1GB max for bar scaling

    renderDrives(s.drives);

    const ws = s.workspace || {};
    document.getElementById('ws-state').textContent = ws.global_state || '—';
    document.getElementById('ws-focus').textContent = ws.attention_focus || '—';
    document.getElementById('ws-awareness').textContent = fmtNum(ws.awareness_level, 3);

    const sm = s.self_model || {};
    const sig = sm.identity_signature || [];
    document.getElementById('sm-sig').textContent = sig.length ? `vec[${sig.length}]` : '—';
    document.getElementById('sm-stage').textContent = sm.developmental_stage || '—';
    document.getElementById('sm-coherence').textContent = fmtNum(sm.coherence, 3);
    renderNarrative(sm.narrative, els.smNarrative);

    const emb = s.embodiment || {};
    document.getElementById('emb-depth').textContent = fmtNum(emb.depth, 3);
    document.getElementById('emb-latency').textContent = fmtNum(emb.loop_latency_ms, 1) + ' ms';
    document.getElementById('emb-pred').textContent = fmtNum(emb.prediction_accuracy, 3);
    document.getElementById('emb-action').textContent = fmtNum(emb.action_success_rate, 3);

    const dist = s.distributed || {};
    document.getElementById('dist-count').textContent = dist.node_count || 0;
    document.getElementById('dist-hash').textContent = (dist.consensus_identity_hash || '').slice(0, 16) || '—';
    renderNodes(dist.nodes, els.distNodes);

    const soc = s.social || {};
    document.getElementById('soc-count').textContent = soc.agent_count || 0;
    document.getElementById('soc-trust').textContent = fmtNum(soc.average_trust, 3);
    document.getElementById('soc-coop').textContent = fmtNum(soc.cooperation_rate, 3);

    const stab = s.stabilizer || {};
    const li = stab.last_intervention || {};
    const liText = li.tick !== undefined ? `tick ${li.tick}: ${li.pattern || '—'} → ${li.modulation || '—'}` : '—';
    document.getElementById('stab-intervention').textContent = liText;
    document.getElementById('stab-attractors').textContent = stab.attractor_count || 0;
    document.getElementById('stab-score').textContent = fmtNum(stab.stability_score, 3);

    // narrative from life_story if available
    if (s.narrative && s.narrative.length) {
      renderNarrative(s.narrative, els.smNarrative);
    }
  }

  // ------------------------------------------------------------------ //
  // Boot
  // ------------------------------------------------------------------ //

  fetchHealth();
  fetchState();
  fetchLogs();

  setInterval(() => {
    fetchHealth();
    fetchState();
    fetchLogs();
  }, POLL_INTERVAL);
})();
