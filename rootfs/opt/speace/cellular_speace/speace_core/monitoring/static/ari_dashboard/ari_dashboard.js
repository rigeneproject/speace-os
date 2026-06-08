/* ============================================================
   SPEACE ARI Dashboard — vanilla JS frontend
   Polls /api/snapshot every 5s and renders:
     - 3 hero cards (ARI%, AGI%, Δ)
     - 8 horizontal component bars
     - Radar chart (8 axes)
     - Time-series line chart (ARI% + AGI% legacy)
     - Cognitive status text block
   ============================================================ */

(function () {
    "use strict";

    const POLL_MS = 5000;
    const RADAR_AXES = [
        "arc_score",
        "generalization",
        "memory_integration",
        "self_improvement",
        "planning",
        "robustness",
        "kg_coherence",
        "autonomy",
    ];
    const RADAR_LABELS = [
        "ARC",
        "Generalization",
        "Memory",
        "Self-Improvement",
        "Planning",
        "Robustness",
        "KG Coherence",
        "Autonomy",
    ];

    // ------------------------------------------------------------
    // DOM helpers
    // ------------------------------------------------------------
    function $(id) { return document.getElementById(id); }

    function fmtPct(x) {
        if (typeof x !== "number" || isNaN(x)) return "–";
        return x.toFixed(2) + "%";
    }

    function fmtDelta(x) {
        if (typeof x !== "number" || isNaN(x)) return "–";
        const sign = x >= 0 ? "+" : "";
        return sign + x.toFixed(2) + "%";
    }

    function fmtTime(ts) {
        if (!ts) return "";
        try {
            const d = new Date(ts);
            if (isNaN(d.getTime())) return ts;
            return d.toISOString().replace("T", " ").replace("Z", "Z");
        } catch (_) {
            return ts;
        }
    }

    function setConn(ok, label) {
        const dot = $("conn-dot");
        const text = $("conn-text");
        if (dot) dot.className = "dot " + (ok ? "ok" : "err");
        if (text) text.textContent = label;
    }

    function setLastUpdate() {
        const el = $("last-update");
        if (el) {
            const d = new Date();
            el.textContent = "· last " + d.toLocaleTimeString();
        }
    }

    // ------------------------------------------------------------
    // Hero
    // ------------------------------------------------------------
    function renderHero(ari, agiLegacy, summary) {
        const ariPct = (ari && typeof ari.ari_percentage === "number") ? ari.ari_percentage : 0;
        $("ari-percentage").textContent = fmtPct(ariPct);
        $("ari-bar-fill").style.width = Math.max(0, Math.min(100, ariPct)) + "%";

        $("agi-percentage").textContent = fmtPct(agiLegacy || 0);

        const delta = summary && typeof summary.delta === "number" ? summary.delta : 0;
        $("ari-delta").textContent = fmtDelta(delta);
        const trendEl = $("ari-trend");
        if (trendEl && summary) {
            trendEl.textContent = `${summary.count} cycles · mean ${fmtPct(summary.mean)}`;
        }
    }

    // ------------------------------------------------------------
    // Component bars
    // ------------------------------------------------------------
    function renderComponents(components, weights) {
        const root = $("component-bars");
        root.innerHTML = "";

        if (!components) {
            root.innerHTML = '<div style="color:var(--fg-muted)">no data</div>';
            return;
        }

        RADAR_AXES.forEach((key) => {
            const v = (typeof components[key] === "number") ? components[key] : 0;
            const w = (weights && typeof weights[key] === "number") ? weights[key] : 0;

            const row = document.createElement("div");
            row.className = "bar-row";

            const name = document.createElement("div");
            name.className = "name";
            name.textContent = key.replace(/_/g, " ");

            const bar = document.createElement("div");
            bar.className = "bar";
            const fill = document.createElement("div");
            fill.className = "bar-fill";
            fill.style.width = Math.max(0, Math.min(100, v)) + "%";
            bar.appendChild(fill);

            const val = document.createElement("div");
            val.className = "value";
            const wspan = document.createElement("span");
            wspan.className = "weight";
            wspan.textContent = `(w=${w.toFixed(2)})`;
            val.appendChild(document.createTextNode(v.toFixed(2) + "% "));
            val.appendChild(wspan);

            row.appendChild(name);
            row.appendChild(bar);
            row.appendChild(val);
            root.appendChild(row);
        });
    }

    // ------------------------------------------------------------
    // Radar
    // ------------------------------------------------------------
    function drawRadar(canvas, components) {
        const ctx = canvas.getContext("2d");
        const w = canvas.width;
        const h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        const cx = w / 2;
        const cy = h / 2;
        const radius = Math.min(w, h) * 0.40;
        const n = RADAR_AXES.length;

        // Background rings (0.25, 0.5, 0.75, 1.0)
        ctx.strokeStyle = "#1e252e";
        ctx.lineWidth = 1;
        for (let r = 1; r <= 4; r++) {
            ctx.beginPath();
            for (let i = 0; i < n; i++) {
                const ang = -Math.PI / 2 + (i * 2 * Math.PI) / n;
                const x = cx + Math.cos(ang) * radius * (r / 4);
                const y = cy + Math.sin(ang) * radius * (r / 4);
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }
            ctx.closePath();
            ctx.stroke();
        }

        // Axis lines
        ctx.strokeStyle = "#1c232c";
        for (let i = 0; i < n; i++) {
            const ang = -Math.PI / 2 + (i * 2 * Math.PI) / n;
            ctx.beginPath();
            ctx.moveTo(cx, cy);
            ctx.lineTo(cx + Math.cos(ang) * radius, cy + Math.sin(ang) * radius);
            ctx.stroke();
        }

        // Filled polygon
        if (components) {
            ctx.fillStyle = "rgba(74, 222, 128, 0.20)";
            ctx.strokeStyle = "#4ade80";
            ctx.lineWidth = 2;
            ctx.beginPath();
            for (let i = 0; i < n; i++) {
                const key = RADAR_AXES[i];
                const v = Math.max(0, Math.min(1, (components[key] || 0) / 100));
                const ang = -Math.PI / 2 + (i * 2 * Math.PI) / n;
                const x = cx + Math.cos(ang) * radius * v;
                const y = cy + Math.sin(ang) * radius * v;
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }
            ctx.closePath();
            ctx.fill();
            ctx.stroke();

            // Vertex dots
            ctx.fillStyle = "#4ade80";
            for (let i = 0; i < n; i++) {
                const key = RADAR_AXES[i];
                const v = Math.max(0, Math.min(1, (components[key] || 0) / 100));
                const ang = -Math.PI / 2 + (i * 2 * Math.PI) / n;
                const x = cx + Math.cos(ang) * radius * v;
                const y = cy + Math.sin(ang) * radius * v;
                ctx.beginPath();
                ctx.arc(x, y, 3, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        // Labels
        ctx.fillStyle = "#e6edf3";
        ctx.font = "12px -apple-system, BlinkMacSystemFont, sans-serif";
        ctx.textBaseline = "middle";
        ctx.textAlign = "center";
        for (let i = 0; i < n; i++) {
            const ang = -Math.PI / 2 + (i * 2 * Math.PI) / n;
            const lx = cx + Math.cos(ang) * (radius + 22);
            const ly = cy + Math.sin(ang) * (radius + 22);
            ctx.fillText(RADAR_LABELS[i], lx, ly);
        }
    }

    // ------------------------------------------------------------
    // Line chart
    // ------------------------------------------------------------
    function drawLine(canvas, ariHistory, agiHistory) {
        const ctx = canvas.getContext("2d");
        const w = canvas.width;
        const h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        // Padding
        const padL = 50, padR = 14, padT = 18, padB = 28;
        const plotW = w - padL - padR;
        const plotH = h - padT - padB;

        // Grid
        ctx.strokeStyle = "#1e252e";
        ctx.fillStyle = "#555f6c";
        ctx.font = "10px ui-monospace, Consolas, monospace";
        ctx.textBaseline = "middle";
        ctx.textAlign = "right";
        for (let i = 0; i <= 4; i++) {
            const y = padT + (plotH * i) / 4;
            ctx.beginPath();
            ctx.moveTo(padL, y);
            ctx.lineTo(w - padR, y);
            ctx.stroke();
            const v = 100 - (100 * i) / 4;
            ctx.fillText(v.toFixed(0) + "%", padL - 6, y);
        }

        // Determine series length — use ARI history as primary
        const series = ariHistory || [];
        if (series.length === 0) {
            ctx.fillStyle = "#555f6c";
            ctx.font = "12px -apple-system, sans-serif";
            ctx.textAlign = "center";
            ctx.fillText("no history yet", w / 2, h / 2);
            return;
        }

        const n = series.length;
        const xStep = n > 1 ? plotW / (n - 1) : 0;

        // ARI line
        ctx.strokeStyle = "#4ade80";
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i < n; i++) {
            const v = Math.max(0, Math.min(100, series[i].ari_percentage || 0));
            const x = padL + xStep * i;
            const y = padT + plotH * (1 - v / 100);
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // AGI% legacy line (overlay if available)
        // AGI history may have different length — use the most recent min length
        const agiSeries = (agiHistory || []).map((h) => h.agi_percentage || 0);
        if (agiSeries.length > 0) {
            // Align by trimming AGI series to last `n` points
            const aligned = agiSeries.slice(-n);
            ctx.strokeStyle = "#8b95a3";
            ctx.lineWidth = 1.5;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            for (let i = 0; i < aligned.length; i++) {
                const v = Math.max(0, Math.min(100, aligned[i]));
                const x = padL + xStep * i;
                const y = padT + plotH * (1 - v / 100);
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.setLineDash([]);

            // Label last AGI point
            const lastV = aligned[aligned.length - 1];
            const lastX = padL + xStep * (aligned.length - 1);
            const lastY = padT + plotH * (1 - lastV / 100);
            ctx.fillStyle = "#8b95a3";
            ctx.beginPath();
            ctx.arc(lastX, lastY, 3, 0, Math.PI * 2);
            ctx.fill();
            ctx.textAlign = "left";
            ctx.fillText(fmtPct(lastV), lastX + 6, lastY);
        }

        // Label last ARI point
        const lastAri = series[n - 1].ari_percentage || 0;
        const lastX2 = padL + xStep * (n - 1);
        const lastY2 = padT + plotH * (1 - Math.max(0, Math.min(100, lastAri)) / 100);
        ctx.fillStyle = "#4ade80";
        ctx.beginPath();
        ctx.arc(lastX2, lastY2, 3.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.textAlign = "left";
        ctx.fillText(fmtPct(lastAri), lastX2 + 6, lastY2 - 2);

        // X-axis ticks (first / mid / last)
        ctx.fillStyle = "#555f6c";
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        const labels = [
            { i: 0, t: "−" + n },
            { i: Math.floor(n / 2), t: "−" + Math.ceil(n / 2) },
            { i: n - 1, t: "now" },
        ];
        labels.forEach((l) => {
            const x = padL + xStep * l.i;
            ctx.fillText(l.t, x, h - padB + 6);
        });
    }

    // ------------------------------------------------------------
    // Cognitive status text
    // ------------------------------------------------------------
    function renderCogStatus(cog) {
        const el = $("cog-status");
        if (!cog) {
            el.textContent = "(no data)";
            return;
        }
        const lines = [];
        lines.push("== ARI ==");
        if (cog.ari) {
            lines.push(`  ARI%            : ${fmtPct(cog.ari.ari_percentage)}`);
            lines.push(`  AGI% legacy     : ${fmtPct(cog.ari.agi_percentage_legacy)}`);
            if (cog.ari.components) {
                Object.keys(cog.ari.components).forEach((k) => {
                    lines.push(`  - ${k.padEnd(20)} ${(cog.ari.components[k] || 0).toFixed(2)}%`);
                });
            }
        }
        if (cog.memory) {
            lines.push("");
            lines.push("== Memory ==");
            lines.push(`  narrative_depth : ${cog.memory.narrative_depth}`);
        }
        if (cog.reasoning) {
            lines.push("");
            lines.push("== Reasoning ==");
            lines.push(`  workspace_ign   : ${(cog.reasoning.workspace_ignition || 0).toFixed(3)}`);
            lines.push(`  active_items    : ${cog.reasoning.active_items}`);
        }
        if (cog.planning) {
            lines.push("");
            lines.push("== Planning ==");
            lines.push(`  tasks_emitted   : ${cog.planning.tasks_emitted}`);
            if (cog.planning.by_priority) {
                const p = cog.planning.by_priority;
                lines.push(`  - high: ${p.high || 0}, medium: ${p.medium || 0}, low: ${p.low || 0}`);
            }
        }
        if (cog.learning) {
            lines.push("");
            lines.push("== Learning ==");
            lines.push(`  arc_accuracy    : ${(cog.learning.arc_subset_accuracy || 0).toFixed(3)}`);
            lines.push(`  self_imp_slope  : ${(cog.learning.self_improvement_slope || 0).toFixed(3)}`);
        }
        if (cog.autonomy && cog.autonomy.runtime_status) {
            const rs = cog.autonomy.runtime_status;
            lines.push("");
            lines.push("== Runtime ==");
            lines.push(`  state           : ${rs.state || "?"}`);
            lines.push(`  ticks           : ${rs.tick_count || 0}`);
        }
        el.textContent = lines.join("\n");
    }

    // ------------------------------------------------------------
    // Cognitive analysis — 7 dimensions
    // ------------------------------------------------------------
    function scoreClass(score) {
        if (score >= 90) return "excellent";
        if (score >= 75) return "strong";
        if (score >= 50) return "mid";
        return "weak";
    }

    function fmtMetric(v) {
        if (typeof v !== "number" || isNaN(v)) return "–";
        if (Math.abs(v) >= 100) return v.toFixed(0);
        if (Math.abs(v) >= 10)  return v.toFixed(2);
        return v.toFixed(3);
    }

    function renderMetricRow(key, val) {
        const row = document.createElement("div");
        row.className = "cog-metric";
        const k = document.createElement("span");
        k.className = "key";
        k.textContent = key;
        const v = document.createElement("span");
        v.className = "val";
        if (typeof val === "boolean") {
            v.textContent = val ? "✓" : "–";
        } else if (typeof val === "number") {
            v.textContent = fmtMetric(val);
        } else if (Array.isArray(val)) {
            v.textContent = JSON.stringify(val);
        } else if (val && typeof val === "object") {
            v.textContent = JSON.stringify(val);
        } else {
            v.textContent = String(val);
        }
        row.appendChild(k);
        row.appendChild(v);
        return row;
    }

    // Build the per-dimension metric list (skipping large blob fields)
    const SKIP_KEYS = new Set(["insights", "score", "verdict", "compartments", "capability_axes_detail"]);
    const RENAME_KEYS = {
        narrative_depth: "narrative_depth",
        active_items: "active_items",
        workspace_ignition: "workspace_ignition",
        identity_coherence: "identity_coherence",
        self_awareness: "self_awareness",
        capability_axes_total: "axes_total",
        capability_axes_active: "axes_active",
        tasks_emitted: "tasks_emitted",
        arc_accuracy: "arc_accuracy",
        arc_solved: "arc_solved",
        arc_total: "arc_total",
        tasks_total: "tasks_total",
        weighted_quality: "weighted_quality",
        executor_ok: "executor_ok",
        plan_present: "plan_present",
        arc_subset_accuracy: "arc_subset_acc",
        arc_runner_accuracy: "arc_runner_acc",
        agi_percentage: "agi_pct",
        self_improvement_slope: "self_imp_slope",
        refactor_proposals: "refactor_props",
        dna_proposals: "dna_props",
        agi_history_count: "history_n",
        agi_mean: "agi_mean",
        agi_stddev: "agi_stddev",
        agi_cv: "agi_cv",
        robustness: "robustness",
        runtime_status: "runtime_status",
        tick_count: "tick_count",
        total_uptime_seconds: "uptime_s",
        total_uptime_minutes: "uptime_min",
        session_count: "sessions",
        recent_errors: "recent_errs",
        cycles_in_window: "window_cycles",
        regulation_severity: "reg_severity",
        regulation_interventions: "reg_interv",
        cognition_status: "cog_status",
        cognition_ignition: "cog_ignition",
        alerts: "alerts",
        watch: "watch",
        regression_detected: "regression?",
        conflicts: "conflicts",
    };

    function buildMetrics(dim) {
        const wrap = document.createElement("div");
        wrap.className = "cog-metrics";
        Object.keys(dim).forEach((k) => {
            if (SKIP_KEYS.has(k)) return;
            const v = dim[k];
            // Skip objects (they have their own treatment)
            if (v && typeof v === "object" && !Array.isArray(v)) return;
            const label = RENAME_KEYS[k] || k;
            wrap.appendChild(renderMetricRow(label, v));
        });
        return wrap;
    }

    function buildInsights(dim) {
        const wrap = document.createElement("div");
        wrap.className = "cog-insights";
        const ul = document.createElement("ul");
        (dim.insights || []).forEach((line) => {
            const li = document.createElement("li");
            li.textContent = line;
            ul.appendChild(li);
        });
        wrap.appendChild(ul);
        return wrap;
    }

    function renderCognitiveAnalysis(report) {
        if (!report) return;

        // Overall
        $("cog-overall-score").textContent = (report.overall_score || 0).toFixed(1) + "%";
        $("cog-overall-verdict").textContent = report.overall_verdict || "–";
        $("cog-cycle-id").textContent = report.cycle_id || "–";
        $("cog-ari").textContent = (report.ari && report.ari.ari_percentage || 0).toFixed(2) + "%";
        $("cog-agi").textContent = (report.ari && report.ari.agi_percentage_legacy || 0).toFixed(2) + "%";
        $("cog-ts").textContent = fmtTime(report.timestamp);

        // Narrative
        const narrEl = $("cog-narrative");
        narrEl.innerHTML = "";
        (report.narrative || []).forEach((line) => {
            const p = document.createElement("p");
            p.textContent = line;
            narrEl.appendChild(p);
        });

        // Dimension cards
        const grid = $("cog-grid");
        grid.innerHTML = "";
        const dims = report.dimensions || {};
        const ordered = ["memory", "reasoning", "planning", "learning", "generalization", "autonomy", "adaptation"];
        ordered.forEach((key) => {
            const dim = dims[key];
            if (!dim) return;
            const card = document.createElement("div");
            card.className = "cog-card";

            const header = document.createElement("div");
            header.className = "cog-card-header";
            const title = document.createElement("div");
            title.className = "cog-card-title";
            title.textContent = key;
            const scoreWrap = document.createElement("div");
            const score = document.createElement("span");
            score.className = "cog-card-score " + scoreClass(dim.score);
            score.textContent = (dim.score || 0).toFixed(1) + "%";
            const verdict = document.createElement("span");
            verdict.className = "cog-card-verdict";
            verdict.textContent = dim.verdict || "–";
            scoreWrap.appendChild(score);
            scoreWrap.appendChild(verdict);
            header.appendChild(title);
            header.appendChild(scoreWrap);
            card.appendChild(header);

            card.appendChild(buildMetrics(dim));
            card.appendChild(buildInsights(dim));
            grid.appendChild(card);
        });
    }

    // ------------------------------------------------------------
    // Main render
    // ------------------------------------------------------------
    function render(snap) {
        if (!snap) return;
        const ari = snap.ari || {};
        const components = ari.components || {};
        const weights = snap.weights || ari.weights || {};
        const agiSeries = snap.agi_history || [];
        const ariSeries = snap.ari_history || [];

        // Compute AGI% legacy (last value, fallback to ari.agi_percentage_legacy)
        const lastAgi = agiSeries.length > 0
            ? (agiSeries[agiSeries.length - 1].agi_percentage || 0)
            : (ari.agi_percentage_legacy || 0);

        renderHero(ari, lastAgi, snap.ari_history_summary);

        renderComponents(components, weights);
        drawRadar($("radar-canvas"), components);
        drawLine($("line-canvas"), ariSeries, agiSeries);

        $("speace-version").textContent = "v" + (snap.speace_version || "?");
        $("server-uptime").textContent = "uptime " + (snap.server_uptime_s || 0) + "s";

        setLastUpdate();
    }

    // ------------------------------------------------------------
    // Fetch loop
    // ------------------------------------------------------------
    let _lastCogFetch = 0;
    const COG_POLL_MS = 10000;

    async function tick() {
        try {
            const r = await fetch("/api/snapshot", { cache: "no-store" });
            if (!r.ok) throw new Error("HTTP " + r.status);
            const snap = await r.json();
            render(snap);
            setConn(true, "online");
        } catch (err) {
            console.warn("snapshot error", err);
            setConn(false, "offline · retry");
        }
        // Cognitive analysis is cheap; refresh independently at 10s
        const now = Date.now();
        if (now - _lastCogFetch > COG_POLL_MS) {
            _lastCogFetch = now;
            try {
                const r = await fetch("/api/cognitive_analysis", { cache: "no-store" });
                if (r.ok) {
                    const report = await r.json();
                    renderCognitiveAnalysis(report);
                }
            } catch (e) {
                // ignore — keep last good render
            }
        }
    }

    async function bootstrap() {
        setConn(false, "loading…");
        // Fire one cognitive analysis call so the report is populated immediately
        try {
            const r = await fetch("/api/cognitive_analysis", { cache: "no-store" });
            if (r.ok) {
                const report = await r.json();
                renderCognitiveAnalysis(report);
            }
        } catch (e) {
            // ignore
        }
        // Fire one cognitive status call so the code block is populated
        try {
            const r = await fetch("/api/cognitive_status", { cache: "no-store" });
            if (r.ok) {
                const cog = await r.json();
                renderCogStatus(cog);
            }
        } catch (e) {
            $("cog-status").textContent = "(offline)";
        }
        await tick();
        setInterval(tick, POLL_MS);
    }

    document.addEventListener("DOMContentLoaded", bootstrap);
})();
