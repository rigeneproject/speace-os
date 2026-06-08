/** SPEACE T101 — Local Organism Monitor Frontend */
(function () {
  'use strict';

  const WS_URL = 'ws://127.0.0.1:8787/ws/state';
  const API_URL = 'http://127.0.0.1:8787/api/state';
  const POLL_INTERVAL = 2000;

  const els = {
    headerMeta: document.getElementById('header-meta'),
    connStatus: document.getElementById('conn-status'),
    connText: document.getElementById('conn-text'),
    errorBanner: document.getElementById('error-banner'),
  };

  let ws = null;
  let pollTimer = null;
  let _health = null;

  function fmtNum(n, d) {
    if (n === null || n === undefined || Number.isNaN(n)) return '—';
    return Number(n).toFixed(d);
  }

  function fmtBytes(b) {
    if (!b || Number.isNaN(b)) return '0 B';
    const u = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
    return b.toFixed(1) + ' ' + u[i];
  }

  function setConn(ok, text) {
    els.connStatus.style.background = ok ? 'var(--accent-green)' : 'var(--accent-red)';
    els.connText.textContent = text;
    if (ok) {
      els.errorBanner.style.display = 'none';
    } else {
      els.errorBanner.style.display = 'block';
      els.errorBanner.textContent = text;
    }
  }

  function setBar(id, val, max) {
    const el = document.getElementById(id);
    if (!el) return;
    const pct = Math.max(0, Math.min(100, (val / max) * 100));
    el.style.width = pct + '%';
    el.className = 'gauge-bar-inner ' + (pct > 80 ? 'red' : pct > 50 ? 'yellow' : 'green');
  }

  function setBadge(id, level) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = level;
    el.className = 'badge ' + level;
  }

  function setPanelStatus(panelId, status) {
    const panel = document.getElementById(panelId);
    if (!panel) return;
    panel.classList.remove('critical', 'warning', 'info');
    if (status === 'critical') panel.classList.add('critical');
    else if (status === 'high' || status === 'warning') panel.classList.add('warning');
    else if (status === 'info') panel.classList.add('info');
  }

  // ------------------------------------------------------------------ //
  // Render helpers
  // ------------------------------------------------------------------ //

  function renderList(containerId, items, mapper) {
    const c = document.getElementById(containerId);
    if (!c) return;
    if (!Array.isArray(items) || items.length === 0) {
      c.innerHTML = '<li>—</li>';
      return;
    }
    c.innerHTML = items.slice().reverse().map(mapper).join('');
  }

  function renderDrives(drives) {
    const c = document.getElementById('dr-list');
    if (!c) return;
    if (!Array.isArray(drives) || drives.length === 0) {
      c.innerHTML = '<div class="drive-item"><span class="drive-name">No drives</span></div>';
      return;
    }
    c.innerHTML = drives.map(d => {
      const lvl = Math.max(0, Math.min(1, d.level || 0));
      const pct = (lvl * 100).toFixed(0);
      const color = lvl > 0.7 ? 'var(--accent-red)' : lvl > 0.4 ? 'var(--accent-yellow)' : 'var(--accent-green)';
      return `<div class="drive-item">` +
        `<span class="drive-name">${d.name || 'unknown'}</span>` +
        `<div class="drive-bar"><div class="drive-bar-inner" style="width:${pct}%; background:${color}"></div></div>` +
        `<span class="drive-value">${pct}%</span>` +
        `</div>`;
    }).join('');
  }

  function renderAnomalies(anomalies) {
    const c = document.getElementById('a-list');
    if (!c) return;
    if (!Array.isArray(anomalies) || anomalies.length === 0) {
      c.innerHTML = '<li><span class="anomaly-type">No anomalies detected</span></li>';
      return;
    }
    c.innerHTML = anomalies.map(a => {
      const sev = a.severity || 'warning';
      return `<li>` +
        `<span class="anomaly-type">${a.type || 'unknown'}</span>` +
        `<span class="anomaly-severity ${sev}">${sev.toUpperCase()}</span>` +
        `</li>`;
    }).join('');
  }

  // ------------------------------------------------------------------ //
  // Apply state
  // ------------------------------------------------------------------ //

  function applyState(s) {
    // Body
    const b = s.body || {};
    document.getElementById('b-cpu').textContent = fmtNum(b.cpu, 1) + '%';
    setBar('bb-cpu', b.cpu, 100);
    const memGB = (b.memory_bytes || 0) / (1024 * 1024 * 1024);
    document.getElementById('b-ram').textContent = fmtNum(memGB, 2) + ' GB';
    setBar('bb-ram', memGB, 16);
    const diskGB = (b.disk_bytes || 0) / (1024 * 1024 * 1024);
    document.getElementById('b-disk').textContent = fmtNum(diskGB, 2) + ' GB';
    setBar('bb-disk', diskGB, 500);
    document.getElementById('b-net').textContent = fmtBytes(b.network_bytes);
    setBar('bb-net', b.network_bytes || 0, 1e9);
    document.getElementById('b-temp').textContent = fmtNum(b.temperature, 1) + ' C';
    setBar('bb-temp', b.temperature, 100);
    document.getElementById('b-batt').textContent = fmtNum(b.battery, 1) + '%';
    setBar('bb-batt', b.battery, 100);

    // Cognition
    const c = s.cognition || {};
    const gw = c.global_workspace || {};
    document.getElementById('c-gw').textContent = gw.global_state || gw.state || '—';
    document.getElementById('c-focus').textContent = c.attention_focus || '—';
    document.getElementById('c-awareness').textContent = fmtNum(gw.awareness_level || gw.awareness || 0, 3);
    const sm = c.self_model || {};
    document.getElementById('c-stage').textContent = sm.developmental_stage || '—';
    document.getElementById('c-phi').textContent = fmtNum(sm.coherence_phi || 0, 3);
    const goals = Array.isArray(c.active_goals) ? c.active_goals.join(', ') : '—';
    document.getElementById('c-goals').textContent = goals;
    renderList('c-narrative', c.narrative_trace || [], it => {
      let txt = it.title || it.event || (typeof it === 'string' ? it : JSON.stringify(it).slice(0, 80));
      return `<li>${txt}</li>`;
    });

    // Dynamics
    const d = s.dynamics || {};
    document.getElementById('d-chaos').textContent = fmtNum(d.chaos_score, 3);
    document.getElementById('d-rigidity').textContent = fmtNum(d.rigidity_score, 3);
    document.getElementById('d-drift').textContent = fmtNum(d.drift, 4);
    document.getElementById('d-attractors').textContent = d.attractor_count || 0;
    const crit = d.criticality || {};
    document.getElementById('d-branching').textContent = fmtNum(crit.branching_ratio, 3);
    document.getElementById('d-critical').textContent = crit.near_critical ? 'true' : 'false';
    const li = d.stabilizer && d.stabilizer.last_intervention ? d.stabilizer.last_intervention : {};
    const liTxt = li.tick !== undefined ? `tick ${li.tick}: ${li.pattern || '—'} → ${li.modulation || '—'}` : '—';
    document.getElementById('d-intervention').textContent = liTxt;
    setPanelStatus('panel-dynamics', d.chaos_score > 0.7 ? 'critical' : d.chaos_score > 0.4 ? 'warning' : 'normal');

    // Prediction Error
    const e = s.embodiment || {};
    document.getElementById('p-acc').textContent = fmtNum(e.prediction_accuracy, 3);
    document.getElementById('p-err').textContent = fmtNum(e.prediction_error, 3);

    // Embodiment
    document.getElementById('e-depth').textContent = fmtNum(e.depth, 3);
    document.getElementById('e-latency').textContent = fmtNum(e.loop_latency_ms, 1) + ' ms';
    document.getElementById('e-success').textContent = fmtNum(e.action_success_rate, 3);
    document.getElementById('e-sensor').textContent = e.sensor_status || 'unknown';
    document.getElementById('e-actuator').textContent = e.actuator_status || 'unknown';

    // Identity
    const i = s.identity || {};
    document.getElementById('i-count').textContent = i.node_count || 0;
    document.getElementById('i-hash').textContent = (i.consensus_identity_hash || '').slice(0, 16) || '—';
    document.getElementById('i-divergence').textContent = i.divergence_detected ? 'true' : 'false';
    renderList('i-nodes', i.distributed_nodes || [], n => `<li>${n.node_id || '?'} (trust ${fmtNum(n.trust_score, 2)})</li>`);
    renderList('i-narrative', i.narrative_sync || [], it => `<li>${it.title || it.event || JSON.stringify(it).slice(0, 60)}</li>`);

    // T106 — Personality Drift
    const pd = s.personality_drift || {};
    document.getElementById('pd-drive').textContent = fmtNum(pd.drive_divergence, 3);
    document.getElementById('pd-self').textContent = fmtNum(pd.self_model_divergence, 3);
    document.getElementById('pd-narrative').textContent = fmtNum(pd.narrative_divergence, 3);
    document.getElementById('pd-decisional').textContent = fmtNum(pd.decisional_divergence, 3);
    document.getElementById('pd-overall').textContent = fmtNum(pd.overall_drift, 3);
    setPanelStatus('panel-personality', (pd.overall_drift || 0) > 0.5 ? 'critical' : (pd.overall_drift || 0) > 0.2 ? 'warning' : 'normal');

    // Drives
    const dr = s.drives || {};
    document.getElementById('dr-tendency').textContent = dr.action_tendency || 'idle';
    document.getElementById('dr-dominant').textContent = dr.dominant_drive || '—';
    renderDrives(dr.drives);

    // Safety
    const safe = s.safety || {};
    const risk = safe.risk_level || 'low';
    setBadge('s-badge', risk);
    document.getElementById('s-mode').textContent = safe.governance_mode || 'observation_only';
    document.getElementById('s-revert').textContent = safe.revert_available ? 'true' : 'false';
    document.getElementById('s-patches').textContent = safe.pending_patches || 0;
    const blockedCount = Array.isArray(safe.blocked_actions) ? safe.blocked_actions.length : 0;
    document.getElementById('s-blocked').textContent = blockedCount;
    const flags = Array.isArray(safe.anomaly_flags) ? safe.anomaly_flags : (Array.isArray(safe.flags) ? safe.flags : []);
    renderList('s-flags', flags, f => `<li>${f.type || 'unknown'}${f.tick !== undefined ? ' @ tick ' + f.tick : ''}</li>`);
    setPanelStatus('panel-safety', risk);

    // Anomaly Panel
    const ap = s.anomaly_panel || {};
    const overall = ap.overall_status || 'normal';
    setBadge('a-badge', overall);
    document.getElementById('a-status').textContent = overall;
    document.getElementById('a-count').textContent = ap.anomaly_count || 0;
    renderAnomalies(ap.anomalies || []);
    setPanelStatus('panel-anomaly', overall);

    // T102 — Alert Telemetry
    const al = s.alert_engine || {};
    const alAlerts = Array.isArray(al.alerts) ? al.alerts : [];
    const alRecent = Array.isArray(al.recent_alerts) ? al.recent_alerts : alAlerts;
    document.getElementById('al-health').textContent = fmtNum(al.health_score, 3);
    document.getElementById('al-count').textContent = alAlerts.length;
    const alCrit = alAlerts.filter(a => a.severity === 'critical').length;
    const alWarn = alAlerts.filter(a => a.severity === 'warning').length;
    const alInfo = alAlerts.filter(a => a.severity === 'info').length;
    document.getElementById('al-critical').textContent = alCrit;
    document.getElementById('al-warning').textContent = alWarn;
    const alMaxSev = alCrit > 0 ? 'critical' : alWarn > 0 ? 'warning' : alInfo > 0 ? 'info' : 'normal';
    setBadge('al-badge', alMaxSev);
    renderList('al-timeline', alRecent, a => {
      const t = a.timestamp ? new Date(a.timestamp * 1000).toISOString().split('T')[1].replace('Z', '').slice(0, 8) : '—';
      return `<li><span class="anomaly-type">${a.alert_type || 'unknown'}</span><span class="anomaly-severity ${a.severity || 'warning'}">${(a.severity || 'warning').toUpperCase()}</span><span class="meta">${t}</span></li>`;
    });
    setPanelStatus('panel-alerts', alMaxSev);

    // T104 — Regulation Proposals
    const rp = s.regulation_proposals || {};
    const rpPending = rp.pending_count || 0;
    document.getElementById('rp-pending').textContent = rpPending;
    setBadge('rp-badge', rpPending > 0 ? 'warning' : 'info');
    const rpLatest = Array.isArray(rp.latest) ? rp.latest : [];
    const rpConf = rpLatest.length > 0 && rpLatest[0].confidence ? rpLatest[0].confidence.confidence : null;
    document.getElementById('rp-confidence').textContent = rpConf !== null ? rpConf.toFixed(2) : '—';
    renderList('rp-list', rpLatest, p => {
      const conf = p.confidence ? p.confidence.confidence : 0.5;
      const sev = p.alert && p.alert.severity ? p.alert.severity : 'warning';
      return `<li><span class="anomaly-type">${p.proposed_action || 'unknown'} (conf ${conf.toFixed(2)})</span><span class="anomaly-severity ${sev}">${sev.toUpperCase()}</span></li>`;
    });
    setPanelStatus('panel-regulation', rpPending > 0 ? 'warning' : 'normal');

    // T106 — Personality Drift
    const pd = s.personality_drift || {};
    document.getElementById('pd-drive').textContent = fmtNum(pd.drive_divergence, 3);
    document.getElementById('pd-self').textContent = fmtNum(pd.self_model_divergence, 3);
    document.getElementById('pd-narrative').textContent = fmtNum(pd.narrative_divergence, 3);
    document.getElementById('pd-decisional').textContent = fmtNum(pd.decisional_divergence, 3);
    document.getElementById('pd-overall').textContent = fmtNum(pd.overall_drift, 3);
    setPanelStatus('panel-personality', (pd.overall_drift || 0) > 0.5 ? 'critical' : (pd.overall_drift || 0) > 0.2 ? 'warning' : 'normal');

    // T108 — Experiential Continuity (filled via separate fetch below)

    // Header meta from health (if loaded separately)
    if (s.timestamp) {
      const ts = new Date(s.timestamp * 1000).toISOString().split('T')[1].replace('Z', '');
      // optionally update something
    }
  }

  // ------------------------------------------------------------------ //
  // T105 — Longitudinal Memory sparkline
  // ------------------------------------------------------------------ //

  function renderSparkline(values) {
    const c = document.getElementById('lm-sparkline');
    if (!c || values.length === 0) {
      if (c) c.innerHTML = '<div class="sparkline-empty">no data</div>';
      return;
    }
    const max = Math.max(...values, 0.01);
    const min = Math.min(...values, 0);
    const range = max - min || 1;
    const bars = values.map(v => {
      const h = ((v - min) / range) * 100;
      const col = v > max * 0.8 ? 'red' : v > max * 0.5 ? 'yellow' : 'green';
      return `<div class="sparkline-bar" style="height:${h.toFixed(1)}%; background:var(--accent-${col})"></div>`;
    }).join('');
    c.innerHTML = `<div class="sparkline">${bars}</div>`;
  }

  async function loadHistory() {
    const metric = document.getElementById('lm-metric').value;
    const hours = document.getElementById('lm-hours').value;
    try {
      const r = await fetch(`${API_URL.replace('/api/state', `/api/history/${metric}?hours=${hours}&limit=100`)}`);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      const points = data.data || [];
      const values = points.map(p => p.value);
      renderSparkline(values);
      document.getElementById('lm-points').textContent = points.length;

      // trend
      const tr = await fetch(`${API_URL.replace('/api/state', `/api/history/trend/${metric}?hours=${hours}`)}`);
      if (tr.ok) {
        const td = await tr.json();
        const dir = td.direction || 'stable';
        const delta = td.delta !== undefined ? (td.delta > 0 ? '+' : '') + td.delta.toFixed(4) : '—';
        document.getElementById('lm-trend').textContent = `${dir} (${delta})`;
      }
    } catch (e) {
      document.getElementById('lm-sparkline').innerHTML = '';
      document.getElementById('lm-points').textContent = '0';
      document.getElementById('lm-trend').textContent = '—';
    }
  }

  document.getElementById('lm-metric').addEventListener('change', loadHistory);
  document.getElementById('lm-hours').addEventListener('change', loadHistory);

  // ------------------------------------------------------------------ //
  // T108 — Experiential Continuity
  // ------------------------------------------------------------------ //

  async function loadExperience() {
    try {
      const r = await fetch(`${API_URL.replace('/api/state', '/api/experience/state')}`);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      const humans = Array.isArray(data.relational_humans) ? data.relational_humans : [];
      document.getElementById('ex-humans').textContent = data.relational_human_count || humans.length;
      const lastHuman = humans.length > 0 ? humans[0].name || humans[0].human_id : '—';
      document.getElementById('ex-last-human').textContent = lastHuman;
      const cont = data.session_continuity || {};
      document.getElementById('ex-last-topic').textContent = cont.last_topic || '—';
      const staleDays = cont._stale_days;
      if (staleDays !== undefined) {
        document.getElementById('ex-stale').textContent = staleDays < 1 ? 'fresh' : `${Math.floor(staleDays)} days`;
      } else {
        document.getElementById('ex-stale').textContent = '—';
      }
      document.getElementById('ex-resume').textContent = data.resume_narrative || '—';
    } catch (e) {
      /* ignore */
    }
    try {
      const t = await fetch(`${API_URL.replace('/api/state', '/api/experience/timeline?hours=168&limit=20')}`);
      if (!t.ok) throw new Error('HTTP ' + t.status);
      const td = await t.json();
      renderList('ex-timeline', td.events || [], ev => {
        const ts = ev.timestamp ? new Date(ev.timestamp * 1000).toISOString().split('T')[1].replace('Z', '').slice(0, 8) : '—';
        return `<li><span class="anomaly-type">${ev.event_type || 'event'}</span><span class="meta">${ts}</span> ${escapeHtml(ev.description || '').slice(0, 60)}</li>`;
      });
    } catch (e) {
      /* ignore */
    }
  }

  // ------------------------------------------------------------------ //
  // T107 — Dialogue chat
  // ------------------------------------------------------------------ //

  function appendMessage(speaker, text) {
    const c = document.getElementById('dl-messages');
    if (!c) return;
    const div = document.createElement('div');
    div.style.marginBottom = '0.35rem';
    const color = speaker === 'user' ? 'var(--accent-cyan)' : 'var(--accent-green)';
    const align = speaker === 'user' ? 'right' : 'left';
    div.style.textAlign = align;
    div.innerHTML = `<span style="color:${color}; font-weight:bold;">${speaker === 'user' ? 'YOU' : 'SPEACE'}:</span> ${escapeHtml(text)}`;
    c.appendChild(div);
    c.scrollTop = c.scrollHeight;
  }

  function escapeHtml(t) {
    return t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  async function sendDialogue() {
    const input = document.getElementById('dl-input');
    if (!input) return;
    const msg = input.value.trim();
    if (!msg) return;
    appendMessage('user', msg);
    input.value = '';
    try {
      const r = await fetch(`${API_URL.replace('/api/state', '/api/dialogue/message')}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: msg}),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      if (data.message) appendMessage('speace', data.message);
    } catch (e) {
      appendMessage('speace', 'Error: ' + e.message);
    }
  }

  const dlSend = document.getElementById('dl-send');
  const dlInput = document.getElementById('dl-input');
  if (dlSend) dlSend.addEventListener('click', sendDialogue);
  if (dlInput) dlInput.addEventListener('keydown', ev => { if (ev.key === 'Enter') sendDialogue(); });

  // ------------------------------------------------------------------ //
  // Transport
  // ------------------------------------------------------------------ //

  function connectWS() {
    try {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => { setConn(true, 'live'); };
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          applyState(data);
        } catch (e) { /* ignore malformed */ }
      };
      ws.onerror = () => { setConn(false, 'ws error'); fallbackPoll(); };
      ws.onclose = () => { setConn(false, 'ws closed'); fallbackPoll(); };
    } catch (e) {
      fallbackPoll();
    }
  }

  async function fetchState() {
    try {
      const r = await fetch(API_URL);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      setConn(true, 'polling');
      applyState(data);
    } catch (e) {
      setConn(false, e.message || 'disconnected');
    }
  }

  function fallbackPoll() {
    if (pollTimer) return;
    fetchState();
    pollTimer = setInterval(() => {
      fetchState();
    }, POLL_INTERVAL);
  }

  function stopPoll() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  // ------------------------------------------------------------------ //
  // T109 — Organism Runtime
  // ------------------------------------------------------------------ //

  async function loadRuntime() {
    try {
      const r = await fetch(`${API_URL.replace('/api/state', '/api/runtime/state')}`);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      const status = data.status || 'ok';
      const state = data.state || 'not running';
      document.getElementById('rt-state').textContent = state;
      setBadge('rt-badge', state === 'running' ? 'info' : state === 'sleeping' ? 'warning' : state === 'halted' ? 'critical' : 'normal');

      const circ = data.circadian || {};
      document.getElementById('rt-phase').textContent = circ.phase || '—';

      document.getElementById('rt-tick').textContent = data.tick_count || 0;
      const up = data.uptime_seconds || 0;
      document.getElementById('rt-uptime').textContent = up < 60 ? `${Math.floor(up)}s` : `${Math.floor(up / 60)}m ${Math.floor(up % 60)}s`;

      const life = data.lifecycle || {};
      document.getElementById('rt-lifecycle').textContent = life.current_state || '—';
      document.getElementById('rt-brainstem').textContent = data.brainstem || '—';

      const halt = data.halt || {};
      document.getElementById('rt-halt').textContent = halt.is_halted ? (halt.halt_reason || 'yes') : 'no';
    } catch (e) {
      document.getElementById('rt-state').textContent = 'not running';
      setBadge('rt-badge', 'normal');
    }
    try {
      const h = await fetch(`${API_URL.replace('/api/state', '/api/runtime/health')}`);
      if (!h.ok) throw new Error('HTTP ' + h.status);
      const hd = await h.json();
      if (hd.status === 'not_running') {
        document.getElementById('rt-health').textContent = '—';
        document.getElementById('rt-jitter').textContent = '—';
        document.getElementById('rt-latency').textContent = '—';
      } else {
        document.getElementById('rt-health').textContent = (hd.health_score !== undefined ? hd.health_score.toFixed(2) : '—');
        document.getElementById('rt-jitter').textContent = (hd.tick_jitter_ms !== undefined ? hd.tick_jitter_ms.toFixed(0) + ' ms' : '—');
        document.getElementById('rt-latency').textContent = (hd.tick_latency_ms !== undefined ? hd.tick_latency_ms.toFixed(0) + ' ms' : '—');
      }
    } catch (e) {
      document.getElementById('rt-health').textContent = '—';
    }
    try {
      const cp = await fetch(`${API_URL.replace('/api/state', '/api/runtime/checkpoints?limit=5')}`);
      if (!cp.ok) throw new Error('HTTP ' + cp.status);
      const cpd = await cp.json();
      renderList('rt-checkpoints', cpd.checkpoints || [], c => {
        const ts = c.timestamp ? new Date(c.timestamp * 1000).toISOString().split('T')[1].replace('Z', '').slice(0, 8) : '—';
        return `<li><span class="anomaly-type">checkpoint</span><span class="meta">${ts}</span> tick ${c.orchestrator?.current_tick || '?'}</li>`;
      });
    } catch (e) {
      /* ignore */
    }
  }

  async function sendRuntimeControl(action) {
    try {
      const r = await fetch(`${API_URL.replace('/api/state', '/api/runtime/control')}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action}),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      await loadRuntime();
    } catch (e) {
      /* ignore */
    }
  }

  document.getElementById('rt-btn-pause').addEventListener('click', () => sendRuntimeControl('pause'));
  document.getElementById('rt-btn-resume').addEventListener('click', () => sendRuntimeControl('resume'));
  document.getElementById('rt-btn-halt').addEventListener('click', () => sendRuntimeControl('halt'));
  document.getElementById('rt-btn-cp').addEventListener('click', () => sendRuntimeControl('checkpoint'));

  // ------------------------------------------------------------------ //
  // Boot
  // ------------------------------------------------------------------ //

  fetchState().then(() => {
    connectWS();
    loadExperience();
    setInterval(loadExperience, POLL_INTERVAL * 5); // slower poll for experience
    loadRuntime();
    setInterval(loadRuntime, POLL_INTERVAL * 2); // moderate poll for runtime
  });
})();
