'use strict';

// ── Constants ─────────────────────────────────────────────────────────────────

const STAGE_DEFS = [
  { num: 1, name: '① Intent Parsing' },
  { num: 2, name: '② FlowRule Compile' },
  { num: 3, name: '③ Static Validation' },
  { num: 4, name: '④ Digital Twin' },
  { num: 5, name: '⑤ XAI Explanation' },
  { num: 6, name: '⑥ ONOS Deploy' },
];

// ── State ─────────────────────────────────────────────────────────────────────

const state = {
  intent: '',
  model: 'qwen3:8b',
  enableRag: true,
  skipTwin: false,
  skipDeploy: false,
  running: false,
  stages: STAGE_DEFS.map(s => ({
    ...s,
    status: 'idle',   // idle | running | done | error | skipped
    elapsed: null,
    result: null,
    expanded: false,
  })),
  decision: null,
  decisionReport: null,
  history: [],
  refreshIn: 1,
};

// ── Pipeline ──────────────────────────────────────────────────────────────────

async function runPipeline() {
  if (state.running || !state.intent.trim()) return;

  state.running = true;
  state.decision = null;
  state.decisionReport = null;
  state.stages.forEach(s => {
    s.status = 'idle'; s.elapsed = null; s.result = null; s.expanded = false;
  });
  renderAllStages();
  renderDecision();
  setRunBtn(true);

  try {
    const resp = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        intent: state.intent,
        model: state.model,
        rag_k: 3,
        no_rag: !state.enableRag,
        skip_twin: state.skipTwin,
        skip_deploy: state.skipDeploy,
      }),
    });

    if (!resp.ok) throw new Error(`Server error: ${resp.status}`);

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const chunks = buf.split('\n\n');
      buf = chunks.pop(); // keep incomplete chunk
      for (const chunk of chunks) {
        const line = chunk.trim();
        if (line.startsWith('data: ')) {
          try {
            handleSSEEvent(JSON.parse(line.slice(6)));
          } catch { /* skip malformed */ }
        }
      }
    }
  } catch (err) {
    console.error('Pipeline error:', err);
  } finally {
    state.running = false;
    setRunBtn(false);
    loadHistory();
  }
}

function handleSSEEvent(ev) {
  if (ev.type === 'stage') {
    const s = state.stages[ev.stage - 1];
    s.status = ev.status;
    if (ev.elapsed != null) s.elapsed = ev.elapsed;
    if (ev.result != null) s.result = ev.result;
    if (ev.error != null) s.result = { error: ev.error };
    renderStage(ev.stage - 1);
  } else if (ev.type === 'decision') {
    state.decision = ev.decision;
    state.decisionReport = ev.report;
    renderDecision();
  }
}

// ── API Calls ─────────────────────────────────────────────────────────────────

// Last successful topology snapshot (JSON string for cheap diffing)
let topoSnapshot = null;

async function fetchTopology() {
  try {
    const resp = await fetch('/api/topology');
    const data = await resp.json();

    if (data.error) {
      // ONOS 오프라인 — 이전 데이터 유지 (초기화하지 않음)
      if (!topoSnapshot) showTopoError(data.error);
      return;
    }

    // 변경 감지: nodes/links/flow_table/rule_count만 비교 (D3 좌표 제외)
    const key = JSON.stringify({
      nodes: data.nodes,
      links: data.links,
      flow_table: data.flow_table,
      rule_count: data.rule_count,
    });

    if (key === topoSnapshot) return; // 변경 없으면 렌더 스킵
    topoSnapshot = key;

    updateTopology(data);
    updateMetrics(data);
    updateFlowTable(data);
  } catch {
    // 네트워크 오류 — 이전 데이터 유지
  }
}

async function loadHistory() {
  try {
    const resp = await fetch('/api/logs');
    state.history = await resp.json();
    renderHistory();
  } catch { /* silent */ }
}

// ── Rendering ─────────────────────────────────────────────────────────────────

function buildStageCards() {
  const section = document.getElementById('stages-section');
  section.innerHTML = '';
  STAGE_DEFS.forEach((def, i) => {
    const card = document.createElement('div');
    card.className = 'stage-card';
    card.id = `stage-${def.num}`;
    card.style.animationDelay = `${i * 0.05}s`;
    card.innerHTML = `
      <div class="stage-header" data-idx="${i}">
        <div class="stage-badge" id="badge-${def.num}">${def.num}</div>
        <div class="stage-name">${def.name}</div>
        <div class="stage-time" id="time-${def.num}">—</div>
        <div class="stage-icon" id="icon-${def.num}">${iconDot()}</div>
      </div>
      <div class="stage-detail" id="detail-${def.num}"></div>
    `;
    card.querySelector('.stage-header').addEventListener('click', () => {
      state.stages[i].expanded = !state.stages[i].expanded;
      renderStage(i);
    });
    section.appendChild(card);
  });
}

function renderAllStages() {
  state.stages.forEach((_, i) => renderStage(i));
}

function renderStage(i) {
  const s = state.stages[i];
  const n = s.num;

  const card   = document.getElementById(`stage-${n}`);
  const badge  = document.getElementById(`badge-${n}`);
  const timeEl = document.getElementById(`time-${n}`);
  const iconEl = document.getElementById(`icon-${n}`);
  const detail = document.getElementById(`detail-${n}`);

  if (!card) return;

  // Card border
  card.className = `stage-card${s.status === 'running' ? ' border-running' : s.status === 'error' ? ' border-error' : ''}`;

  // Badge
  badge.className = s.status === 'idle' ? 'stage-badge' : `stage-badge badge-${s.status}`;
  badge.textContent = n;

  // Time
  timeEl.textContent = s.elapsed != null ? `${s.elapsed}s` : '—';

  // Icon
  iconEl.innerHTML = statusIcon(s.status);

  // Detail
  if (s.expanded && s.result) {
    detail.className = 'stage-detail open';
    detail.textContent = JSON.stringify(s.result, null, 2);
  } else {
    detail.className = 'stage-detail';
  }
}

function renderDecision() {
  const el = document.getElementById('decision-banner');
  if (!state.decision) { el.style.display = 'none'; return; }

  const approve = state.decision.includes('APPROVE');
  const color   = approve ? '#10b981' : '#ef4444';
  const bgColor = approve ? '#0f1c16' : '#1c0f0f';
  const icon    = approve
    ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0a0e1a" stroke-width="3"><path d="M5 13l4 4L19 7" stroke-linecap="round" stroke-linejoin="round"/></svg>`
    : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0a0e1a" stroke-width="3"><path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/></svg>`;

  const report = state.decisionReport || {};
  // XAIReport.to_dict() fields: decision_reason, ir_summary, static_summary, twin_summary
  const reason = report.decision_reason || report.ir_summary || '';

  el.style.display = 'flex';
  el.style.background = bgColor;
  el.style.borderColor = color;
  el.innerHTML = `
    <div class="decision-icon" style="background:${color}">${icon}</div>
    <div>
      <div class="decision-title" style="color:${color}">${state.decision}</div>
      <div class="decision-reason">${reason}</div>
    </div>
  `;
}

function renderHistory() {
  const el = document.getElementById('history-list');
  if (!el) return;
  if (state.history.length === 0) {
    el.innerHTML = '<div style="font-size:11px;color:#4b5563;font-family:\'JetBrains Mono\',monospace">No runs yet</div>';
    return;
  }
  el.innerHTML = state.history.map(h => {
    const badge = h.decision
      ? `<span style="font-size:10px;color:${h.decision.includes('APPROVE') ? '#10b981' : '#ef4444'}">${h.decision.includes('APPROVE') ? '✓' : '✗'}</span> `
      : '';
    return `<div class="history-item" title="${h.intent}" data-intent="${escHtml(h.intent)}">${badge}${escHtml(h.intent)}</div>`;
  }).join('');
  el.querySelectorAll('.history-item').forEach(item => {
    item.addEventListener('click', () => fillIntent(item.dataset.intent));
  });
}

function updateMetrics(data) {
  const nodes = data.nodes || [];
  const links = data.links || [];
  const switches = nodes.filter(n => n.type === 'switch').length;
  const hosts    = nodes.filter(n => n.type === 'host').length;
  const swLinks  = links.filter(l => {
    const s = typeof l.source === 'object' ? l.source.id : l.source;
    const t = typeof l.target === 'object' ? l.target.id : l.target;
    return s && t && s.startsWith('of:') && t.startsWith('of:');
  }).length;

  document.getElementById('metric-switches').textContent = switches || '—';
  document.getElementById('metric-hosts').textContent    = hosts    || '—';
  document.getElementById('metric-links').textContent    = swLinks  || '—';
  document.getElementById('metric-rules').textContent    = data.rule_count ?? '—';
}

function updateFlowTable(data) {
  const body = document.getElementById('flow-table-body');
  const rows = data.flow_table || [];
  if (rows.length === 0) {
    body.innerHTML = `<div style="padding:12px 10px;font-size:11px;color:#4b5563;font-family:'JetBrains Mono',monospace">No flow rules</div>`;
    return;
  }
  body.innerHTML = rows.map(r => {
    const actionColor = r.action === 'FORWARD' ? '#10b981' : r.action === 'DROP' ? '#f59e0b' : '#9ca3af';
    return `
      <div class="flow-table-row">
        <div class="flow-cell-device">${escHtml(String(r.device))}</div>
        <div class="flow-cell-pri">${r.priority}</div>
        <div class="flow-cell-match">${escHtml(String(r.match))}</div>
        <div class="flow-cell-action" style="color:${actionColor}">
          <span class="flow-action-dot" style="background:${actionColor}"></span>
          ${escHtml(String(r.action))}
        </div>
      </div>`;
  }).join('');
}

function showTopoError(msg) {
  const el = document.getElementById('topology-placeholder');
  if (el) {
    el.style.display = 'flex';
    el.textContent = `ONOS offline — ${msg}`;
  }
}

// ── D3 Topology ───────────────────────────────────────────────────────────────

let topoSvg = null;
let simulation = null;
const nodePositions = new Map(); // persist positions across refreshes

function initTopology() {
  const container = document.getElementById('topology-graph');
  const w = container.clientWidth  || 342;
  const h = container.clientHeight || 280;

  topoSvg = d3.select('#topology-graph')
    .append('svg')
    .attr('width',   '100%')
    .attr('height',  '100%')
    .attr('viewBox', `0 0 ${w} ${h}`);

  topoSvg.append('g').attr('class', 'links');
  topoSvg.append('g').attr('class', 'nodes');
}

function updateTopology(data) {
  if (!topoSvg) initTopology();

  const placeholder = document.getElementById('topology-placeholder');
  if (placeholder) placeholder.style.display = 'none';

  const { nodes, links } = data;
  if (!nodes || nodes.length === 0) {
    showTopoError('No devices found');
    return;
  }

  const container = document.getElementById('topology-graph');
  const w = container.clientWidth  || 342;
  const h = container.clientHeight || 280;

  // Seed positions from previous run
  nodes.forEach(n => {
    const prev = nodePositions.get(n.id);
    if (prev) { n.x = prev.x; n.y = prev.y; }
  });

  if (simulation) simulation.stop();

  simulation = d3.forceSimulation(nodes)
    .force('link',      d3.forceLink(links).id(d => d.id).distance(70))
    .force('charge',    d3.forceManyBody().strength(-180))
    .force('center',    d3.forceCenter(w / 2, h / 2))
    .force('collision', d3.forceCollide(24));

  // Links
  const link = topoSvg.select('.links')
    .selectAll('line')
    .data(links, d => `${d.source?.id ?? d.source}-${d.target?.id ?? d.target}`)
    .join('line')
    .attr('stroke', '#374151')
    .attr('stroke-width', 1.5);

  // Nodes
  const drag = d3.drag()
    .on('start', (ev, d) => {
      if (!ev.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x; d.fy = d.y;
    })
    .on('drag', (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
    .on('end',  (ev, d) => {
      if (!ev.active) simulation.alphaTarget(0);
      d.fx = null; d.fy = null;
    });

  const nodeG = topoSvg.select('.nodes')
    .selectAll('g')
    .data(nodes, d => d.id)
    .join('g')
    .call(drag);

  nodeG.selectAll('*').remove();

  nodeG.each(function(d) {
    const g = d3.select(this);
    const fill = nodeColor(d);

    if (d.type === 'switch') {
      g.append('polygon')
        .attr('points', '0,-15 13,-7.5 13,7.5 0,15 -13,7.5 -13,-7.5')
        .attr('fill', fill)
        .attr('stroke', '#0a0e1a')
        .attr('stroke-width', 1.5);
    } else {
      g.append('circle')
        .attr('r', 10)
        .attr('fill', '#111827')
        .attr('stroke', '#3b82f6')
        .attr('stroke-width', 2);
    }

    g.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('font-size', 9)
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('fill', d.type === 'switch' ? '#0a0e1a' : '#f9fafb')
      .attr('font-weight', '700')
      .attr('pointer-events', 'none')
      .text(d.label);
  });

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);
    nodeG.attr('transform', d => {
      // clamp to svg bounds
      const x = Math.max(20, Math.min(w - 20, d.x));
      const y = Math.max(20, Math.min(h - 20, d.y));
      return `translate(${x},${y})`;
    });
  });

  simulation.on('end', () => {
    nodes.forEach(n => nodePositions.set(n.id, { x: n.x, y: n.y }));
  });
}

function nodeColor(d) {
  if (d.type === 'host') return '#3b82f6';
  return { forward: '#10b981', drop: '#f59e0b', offline: '#ef4444', idle: '#6b7280' }[d.state] || '#6b7280';
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function statusIcon(status) {
  if (status === 'done')
    return `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3"><path d="M5 13l4 4L19 7" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  if (status === 'running')
    return `<svg width="16" height="16" viewBox="0 0 24 24" style="animation:spin 1s linear infinite"><circle cx="12" cy="12" r="9" fill="none" stroke="#1f2937" stroke-width="3"/><path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="#3b82f6" stroke-width="3" stroke-linecap="round"/></svg>`;
  if (status === 'error')
    return `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="3"><path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/></svg>`;
  if (status === 'skipped')
    return `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>`;
  return iconDot();
}

function iconDot() {
  return `<div style="width:8px;height:8px;border-radius:50%;background:#374151;margin:auto"></div>`;
}

function fillIntent(text) {
  state.intent = text;
  document.getElementById('intent-input').value = text;
}

function setRunBtn(running) {
  const btn = document.getElementById('run-btn');
  btn.disabled = running;
  btn.innerHTML = running
    ? `<svg width="14" height="14" viewBox="0 0 24 24" style="animation:spin 1s linear infinite"><circle cx="12" cy="12" r="9" fill="none" stroke="rgba(255,255,255,0.3)" stroke-width="3"/><path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="white" stroke-width="3" stroke-linecap="round"/></svg> Running...`
    : `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg> Run Pipeline`;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Topology Refresh Countdown ────────────────────────────────────────────────

let topoFetching = false;

function startRefreshLoop() {
  async function tick() {
    if (!topoFetching) {
      topoFetching = true;
      await fetchTopology();
      topoFetching = false;
    }
    const el = document.getElementById('refresh-countdown');
    if (el) el.textContent = '↻ 1s';
    setTimeout(tick, 1000);
  }
  tick();
}

// ── Init ──────────────────────────────────────────────────────────────────────

function init() {
  // Build stage cards
  buildStageCards();

  // Intent textarea
  const intentInput = document.getElementById('intent-input');
  intentInput.addEventListener('input', e => { state.intent = e.target.value; });

  // Run button
  document.getElementById('run-btn').addEventListener('click', runPipeline);

  // Example chips
  document.querySelectorAll('.example-chip').forEach(chip => {
    chip.addEventListener('click', () => fillIntent(chip.dataset.intent));
  });

  // Settings
  document.getElementById('model-select').addEventListener('change', e => { state.model = e.target.value; });
  document.getElementById('toggle-rag').addEventListener('change',  e => { state.enableRag = e.target.checked; });
  document.getElementById('toggle-twin').addEventListener('change', e => { state.skipTwin  = e.target.checked; });
  document.getElementById('toggle-deploy').addEventListener('change', e => { state.skipDeploy = e.target.checked; });

  // Load history + start topology refresh
  loadHistory();
  startRefreshLoop();
}

document.addEventListener('DOMContentLoaded', init);
