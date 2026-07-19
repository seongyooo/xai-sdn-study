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
    progress_log: [],
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
    s.status = 'idle'; s.elapsed = null; s.result = null; s.expanded = false; s.progress_log = [];
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
  if (ev.type === 'progress') {
    const s = state.stages[ev.stage - 1];
    s.progress_log.push(ev.msg);
    appendLogLine(ev.stage, ev.msg);
  } else if (ev.type === 'stage') {
    const s = state.stages[ev.stage - 1];
    s.status = ev.status;
    if (ev.elapsed != null) s.elapsed = ev.elapsed;
    if (ev.result != null) s.result = ev.result;
    if (ev.error != null) s.result = { error: ev.error };
    // 에러 단계는 자동으로 펼쳐서 즉시 확인 가능하게
    if (ev.status === 'error') s.expanded = true;
    renderStage(ev.stage - 1);
  } else if (ev.type === 'decision') {
    state.decision = ev.decision;
    state.decisionReport = ev.report;
    // REJECT 시 실패한 단계 모두 자동 펼치기
    if (ev.decision === 'REJECT') {
      state.stages.forEach(s => {
        if (s.status === 'error' || (s.status === 'done' && s.result && !s.result.passed)) {
          s.expanded = true;
          renderStage(s.num - 1);
        }
      });
    }
    renderDecision();
  }
}

// ── API Calls ─────────────────────────────────────────────────────────────────

// Last successful topology snapshot (JSON string for cheap diffing)
let topoSnapshot = null;

async function fetchTopology() {
  if (editor.active) return; // don't overwrite editor canvas
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
      <div class="stage-progress" id="progress-${def.num}">
        <div class="stage-progress-bar" id="progress-bar-${def.num}"></div>
      </div>
      <div class="live-log" id="live-${def.num}"></div>
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

  const card    = document.getElementById(`stage-${n}`);
  const badge   = document.getElementById(`badge-${n}`);
  const timeEl  = document.getElementById(`time-${n}`);
  const iconEl  = document.getElementById(`icon-${n}`);
  const liveEl  = document.getElementById(`live-${n}`);
  const detail  = document.getElementById(`detail-${n}`);
  const progBar = document.getElementById(`progress-bar-${n}`);

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

  // Progress bar
  if (progBar) {
    progBar.className = 'stage-progress-bar';
    if (s.status === 'running')  progBar.classList.add('bar-running');
    else if (s.status === 'done')    progBar.classList.add('bar-done');
    else if (s.status === 'error')   progBar.classList.add('bar-error');
    else if (s.status === 'skipped') progBar.classList.add('bar-skipped');
    // idle: no extra class → invisible
  }

  // Live log: running 중에만 표시, 완료 시 "current" 강조 해제
  if (liveEl) {
    if (s.status === 'running') {
      liveEl.style.display = 'block';
    } else {
      liveEl.style.display = 'none';
      // 완료 후 current 라인 일반화 (다음 실행 대비)
      liveEl.querySelectorAll('.log-line.current').forEach(el => {
        el.classList.remove('current');
        el.classList.add('done');
      });
    }
  }

  // Detail (클릭 확장)
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

// ── Topology Editor State ─────────────────────────────────────────────────────

const editor = {
  active: false,
  tool: 'select',   // 'select' | 'switch' | 'host' | 'link' | 'delete'
  linking: null,    // null | { sourceId }  — while drawing a link
  nodes: [],        // { id, label, type, dpid?, ip?, mac?, x, y }
  links: [],        // { id, source, target, bw? }
  selected: null,   // selected node id
  _cnt: { s: 1, h: 1, l: 1 },
};

const TOOL_HINTS = {
  select: '[Esc] Select · Drag to move · Shift+drag to lasso-delete',
  switch: '[S] Click canvas to add switch · Del=delete selected',
  host:   '[H] Click canvas to add host · Del=delete selected',
  link:   '[L] Click source node → click target node',
  delete: '[D] Click node/link · Shift+drag to delete area · Ctrl+Z undo',
};

function editorNewId(type) {
  if (type === 'switch') return `s${editor._cnt.s++}`;
  if (type === 'host')   return `h${editor._cnt.h++}`;
  return `l${editor._cnt.l++}`;
}

// ── Editor: mode transitions ──────────────────────────────────────────────────

async function enterEditMode() {
  editor.active = true;
  console.log('[Editor] entering edit mode');

  const ids = ['topo-title', 'live-mode-controls', 'topo-editor-bar',
                'metrics-grid', 'flow-table-section', 'topo-props-panel'];
  for (const id of ids) {
    if (!document.getElementById(id)) {
      console.error(`[Editor] missing element: #${id}`);
    }
  }

  document.getElementById('topo-title').textContent = 'Topology Editor';
  document.getElementById('live-mode-controls').style.display = 'none';
  document.getElementById('topo-editor-bar').style.display = 'flex';
  document.getElementById('metrics-grid').style.display = 'none';
  document.getElementById('flow-table-section').style.display = 'none';
  document.getElementById('topo-props-panel').style.display = 'block';

  clearTopologyGraph();
  await loadEditorData();
  setEditorTool('select');
  renderEditorGraph();
  console.log('[Editor] ready — nodes:', editor.nodes.length, 'links:', editor.links.length);
}

function exitEditMode() {
  editor.active = false;
  editor.linking = null;
  editor.selected = null;

  document.getElementById('topo-title').textContent = 'Live Network Topology';
  document.getElementById('live-mode-controls').style.display = 'flex';
  document.getElementById('topo-editor-bar').style.display = 'none';
  document.getElementById('metrics-grid').style.display = 'grid';
  document.getElementById('flow-table-section').style.display = 'block';
  document.getElementById('topo-props-panel').style.display = 'none';

  clearTopologyGraph();
  topoSnapshot = null;

  // Render immediately from editor state so the user sees their topology
  // right away without waiting for the ONOS connection attempt to time out.
  // _renderEditorSnapshot() sets topoSnapshot — we deliberately keep it
  // so fetchTopology() doesn't call showTopoError() on ONOS-offline errors.
  _renderEditorSnapshot();
  fetchTopology();
}

// Render the current editor.nodes / editor.links as a static live graph.
// Positions are preserved from the editor (x/y), so the layout matches.
function _renderEditorSnapshot() {
  if (!editor.nodes.length) return;

  const nodes = editor.nodes.map(n => ({
    id: n.id, label: n.label, type: n.type, state: 'idle',
    ip: n.ip || '', x: n.x, y: n.y,
  }));
  const links = editor.links.map(l => ({ source: l.source, target: l.target }));
  const data = { nodes, links, flow_table: [], rule_count: nodes.length };

  // Store snapshot so the next fetchTopology() only re-renders if data changed
  topoSnapshot = JSON.stringify({
    nodes: data.nodes, links: data.links,
    flow_table: [], rule_count: data.rule_count,
  });

  updateTopology(data);
  updateMetrics(data);
  updateFlowTable(data);
}

function clearTopologyGraph() {
  if (!topoSvg) return;
  if (simulation) { simulation.stop(); simulation = null; }
  topoSvg.select('.links').selectAll('*').remove();
  topoSvg.select('.nodes').selectAll('*').remove();
  topoSvg.selectAll('#ghost-link').remove();
  topoSvg.selectAll('#lasso-rect').remove();
  topoSvg.on('click', null).on('mousemove', null)
         .on('mousedown.lasso', null).on('mouseup.lasso', null);
  lasso.active = false;
}

// ── Editor: data loading ──────────────────────────────────────────────────────

async function loadEditorData() {
  try {
    const resp = await fetch('/api/topology/custom');
    if (!resp.ok) throw new Error('no custom topology');
    const data = await resp.json();
    if ((data.switches || []).length > 0 || (data.hosts || []).length > 0) {
      importCustomData(data);
      return;
    }
  } catch { /* fall through */ }
  loadDefaultDiamond();
}

function importCustomData(data) {
  const allSw = (data.switches || []);
  const allH  = (data.hosts   || []);
  editor._cnt.s = allSw.length + 1;
  editor._cnt.h = allH.length  + 1;
  editor._cnt.l = (data.links || []).length + 1;

  editor.nodes = [
    ...allSw.map(sw => ({
      id: sw.id, label: sw.label || sw.id, type: 'switch',
      dpid: sw.dpid, x: sw.x ?? 150, y: sw.y ?? 140,
    })),
    ...allH.map(h => ({
      id: h.id, label: h.label || h.id, type: 'host',
      ip: h.ip, mac: h.mac, x: h.x ?? 80, y: h.y ?? 80,
    })),
  ];
  editor.links = (data.links || []).map(l => ({
    id: l.id || editorNewId('link'),
    source: l.source, target: l.target, bw: l.bw,
  }));
}

function loadDefaultDiamond() {
  editor._cnt = { s: 5, h: 5, l: 9 };
  const cx = 171, cy = 140;
  editor.nodes = [
    { id: 's1', label: 'S1', type: 'switch', dpid: '0000000000000001', x: cx - 55, y: cy - 45 },
    { id: 's2', label: 'S2', type: 'switch', dpid: '0000000000000002', x: cx - 75, y: cy + 40 },
    { id: 's3', label: 'S3', type: 'switch', dpid: '0000000000000003', x: cx + 75, y: cy + 40 },
    { id: 's4', label: 'S4', type: 'switch', dpid: '0000000000000004', x: cx + 55, y: cy - 45 },
    { id: 'h1', label: 'H1', type: 'host', ip: '10.0.0.1', mac: '00:00:00:00:00:01', x: cx - 130, y: cy - 70 },
    { id: 'h2', label: 'H2', type: 'host', ip: '10.0.0.2', mac: '00:00:00:00:00:02', x: cx - 135, y: cy + 15 },
    { id: 'h3', label: 'H3', type: 'host', ip: '10.0.0.3', mac: '00:00:00:00:00:03', x: cx + 135, y: cy + 15 },
    { id: 'h4', label: 'H4', type: 'host', ip: '10.0.0.4', mac: '00:00:00:00:00:04', x: cx + 130, y: cy - 70 },
  ];
  editor.links = [
    { id: 'l1', source: 'h1', target: 's1', bw: 100 },
    { id: 'l2', source: 'h2', target: 's1', bw: 100 },
    { id: 'l3', source: 'h3', target: 's4', bw: 100 },
    { id: 'l4', source: 'h4', target: 's4', bw: 100 },
    { id: 'l5', source: 's1', target: 's2', bw: 1   },
    { id: 'l6', source: 's2', target: 's4', bw: 1   },
    { id: 'l7', source: 's1', target: 's3', bw: 10  },
    { id: 'l8', source: 's3', target: 's4', bw: 10  },
  ];
}

// ── Editor: tool selection ────────────────────────────────────────────────────

function setEditorTool(tool) {
  editor.tool = tool;
  editor.linking = null;
  if (topoSvg) {
    topoSvg.select('#ghost-link').attr('opacity', 0);
    const cur = { select: 'default', switch: 'crosshair', host: 'crosshair', link: 'crosshair', delete: 'not-allowed' };
    topoSvg.style('cursor', cur[tool] || 'default');
  }
  document.querySelectorAll('.tool-btn').forEach(b => b.classList.toggle('active', b.dataset.tool === tool));
  const hint = document.getElementById('tool-hint');
  if (hint) hint.textContent = TOOL_HINTS[tool] || '';
}

// ── Editor: D3 rendering ──────────────────────────────────────────────────────

function renderEditorGraph() {
  if (!editor.active) return;
  if (!topoSvg) initTopology();

  const container = document.getElementById('topology-graph');
  const W = container.clientWidth  || 342;
  const H = container.clientHeight || 280;

  const ph = document.getElementById('topology-placeholder');
  if (ph) ph.style.display = 'none';

  // Ghost link (drawn above everything)
  if (topoSvg.select('#ghost-link').empty()) {
    topoSvg.append('line')
      .attr('id', 'ghost-link')
      .attr('stroke', '#3b82f6')
      .attr('stroke-width', 1.5)
      .attr('stroke-dasharray', '6,4')
      .attr('opacity', 0)
      .attr('pointer-events', 'none');
  }

  // Lasso rect (Shift+drag delete)
  if (topoSvg.select('#lasso-rect').empty()) {
    topoSvg.insert('rect', ':first-child')
      .attr('id', 'lasso-rect')
      .attr('opacity', 0);
  }

  // SVG background interactions
  topoSvg.on('click', function(ev) {
    if (!editor.active) return;
    // Ignore if click landed on a child element (node/link)
    if (ev.target !== this) return;
    const [x, y] = d3.pointer(ev);
    if (editor.tool === 'switch') {
      editorAddNode('switch', x, y);
    } else if (editor.tool === 'host') {
      editorAddNode('host', x, y);
    } else if (editor.tool === 'link' && editor.linking) {
      editor.linking = null;
      topoSvg.select('#ghost-link').attr('opacity', 0);
      renderEditorGraph();
    } else {
      editor.selected = null;
      renderPropsPanel();
      renderEditorGraph();
    }
  });

  topoSvg.on('mousemove', function(ev) {
    const [mx, my] = d3.pointer(ev);
    if (lasso.active) {
      lasso.x1 = mx; lasso.y1 = my;
      updateLassoRect();
    }
    if (!editor.active || editor.tool !== 'link' || !editor.linking) return;
    const src = editor.nodes.find(n => n.id === editor.linking.sourceId);
    if (!src) return;
    topoSvg.select('#ghost-link')
      .attr('x1', src.x).attr('y1', src.y)
      .attr('x2', mx).attr('y2', my)
      .attr('opacity', 1);
  });

  topoSvg.on('mousedown.lasso', function(ev) {
    if (!editor.active || !ev.shiftKey) return;
    if (!isEditorBg(ev)) return;
    ev.preventDefault();
    const [x, y] = d3.pointer(ev);
    lasso.active = true;
    lasso.x0 = lasso.x1 = x;
    lasso.y0 = lasso.y1 = y;
    updateLassoRect();
  });

  topoSvg.on('mouseup.lasso', function() {
    if (!lasso.active) return;
    lasso.active = false;
    topoSvg.select('#lasso-rect').attr('opacity', 0);
    commitLasso();
  });

  // ── Links ──
  const linkGs = topoSvg.select('.links')
    .selectAll('g.ed-link')
    .data(editor.links, d => d.id)
    .join(enter => {
      const g = enter.append('g').attr('class', 'ed-link').style('cursor', 'pointer');
      g.append('line').attr('class', 'lhit').attr('stroke', 'transparent').attr('stroke-width', 8);
      g.append('line').attr('class', 'lvis').attr('stroke-width', 1.5);
      g.append('text').attr('class', 'lbw')
        .attr('text-anchor', 'middle').attr('font-size', 9)
        .attr('font-family', 'JetBrains Mono, monospace').attr('fill', '#6b7280');
      return g;
    });

  linkGs.each(function(d) {
    const src = editor.nodes.find(n => n.id === d.source);
    const tgt = editor.nodes.find(n => n.id === d.target);
    if (!src || !tgt) return;
    const mx = (src.x + tgt.x) / 2, my = (src.y + tgt.y) / 2;
    const isDel = editor.tool === 'delete';
    const g = d3.select(this);
    g.select('.lhit').attr('x1', src.x).attr('y1', src.y).attr('x2', tgt.x).attr('y2', tgt.y);
    g.select('.lvis')
      .attr('x1', src.x).attr('y1', src.y).attr('x2', tgt.x).attr('y2', tgt.y)
      .attr('stroke', isDel ? '#ef444488' : '#374151');
    g.select('.lbw').attr('x', mx).attr('y', my - 5).text(d.bw != null ? `${d.bw}M` : '');
  });

  linkGs.on('click', (ev, d) => {
    ev.stopPropagation();
    if (editor.tool === 'delete') {
      editorPushHistory();
      editor.links = editor.links.filter(l => l.id !== d.id);
      renderEditorGraph();
    }
  });

  // ── Nodes ──
  const drag = d3.drag()
    .filter(ev => !ev.shiftKey)  // Shift+drag → lasso, not node drag
    .on('start', (ev, d) => { if (editor.tool !== 'select') ev.sourceEvent.stopPropagation(); })
    .on('drag',  (ev, d) => {
      if (editor.tool !== 'select') return;
      d.x = Math.max(18, Math.min(W - 18, ev.x));
      d.y = Math.max(18, Math.min(H - 18, ev.y));
      renderEditorGraph();
    });

  const nodeGs = topoSvg.select('.nodes')
    .selectAll('g.ed-node')
    .data(editor.nodes, d => d.id)
    .join(enter => enter.append('g').attr('class', 'ed-node'))
    .call(drag);

  nodeGs.selectAll('*').remove();

  nodeGs.each(function(d) {
    const g = d3.select(this);
    const sel  = editor.selected === d.id;
    const lsrc = editor.linking?.sourceId === d.id;
    const fill = lsrc ? '#1e3a5f' : nodeColor(d);
    const strokeColor = sel ? '#60a5fa' : lsrc ? '#3b82f6' : (d.type === 'switch' ? '#0a0e1a' : '#3b82f6');
    const strokeW = sel ? 2.5 : 1.5;

    if (d.type === 'switch') {
      g.append('polygon')
        .attr('points', '0,-15 13,-7.5 13,7.5 0,15 -13,7.5 -13,-7.5')
        .attr('fill', fill)
        .attr('stroke', strokeColor)
        .attr('stroke-width', strokeW);
    } else {
      g.append('circle')
        .attr('r', 10)
        .attr('fill', '#111827')
        .attr('stroke', strokeColor)
        .attr('stroke-width', strokeW);
    }

    g.append('text')
      .attr('text-anchor', 'middle').attr('dy', '0.35em')
      .attr('font-size', 9).attr('font-weight', '700')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('fill', d.type === 'switch' ? (lsrc ? '#60a5fa' : '#0a0e1a') : '#f9fafb')
      .attr('pointer-events', 'none')
      .text(d.label);

    g.attr('transform', `translate(${d.x},${d.y})`)
      .style('cursor', editor.tool === 'delete' ? 'not-allowed' : editor.tool === 'select' ? 'grab' : 'pointer');
  });

  nodeGs.on('click', (ev, d) => {
    ev.stopPropagation();
    handleEditorNodeClick(d);
  });

  // Keep ghost link on top
  topoSvg.select('#ghost-link').raise();
}

function handleEditorNodeClick(d) {
  if (editor.tool === 'delete') {
    editorPushHistory();
    editor.nodes = editor.nodes.filter(n => n.id !== d.id);
    editor.links = editor.links.filter(l => l.source !== d.id && l.target !== d.id);
    if (editor.selected === d.id) editor.selected = null;
    renderEditorGraph();
    renderPropsPanel();
    return;
  }

  if (editor.tool === 'link') {
    if (!editor.linking) {
      editor.linking = { sourceId: d.id };
      renderEditorGraph();
    } else if (editor.linking.sourceId === d.id) {
      // Cancel link on same node
      editor.linking = null;
      topoSvg.select('#ghost-link').attr('opacity', 0);
      renderEditorGraph();
    } else {
      // Complete link — prevent duplicates
      const a = editor.linking.sourceId, b = d.id;
      const dup = editor.links.some(l =>
        (l.source === a && l.target === b) || (l.source === b && l.target === a)
      );
      if (!dup) {
        editorPushHistory();
        const bw = (editor.nodes.find(n=>n.id===a)?.type === 'switch' &&
                    editor.nodes.find(n=>n.id===b)?.type === 'switch') ? 10 : 100;
        editor.links.push({ id: editorNewId('link'), source: a, target: b, bw });
      }
      editor.linking = null;
      topoSvg.select('#ghost-link').attr('opacity', 0);
      renderEditorGraph();
    }
    return;
  }

  // Select tool
  editor.selected = d.id;
  renderPropsPanel();
  renderEditorGraph();
}

function editorAddNode(type, x, y) {
  editorPushHistory();
  const id  = editorNewId(type);
  const num = type === 'switch' ? editor._cnt.s - 1 : editor._cnt.h - 1;
  const node = { id, label: type === 'switch' ? `S${num}` : `H${num}`, type, x, y };
  if (type === 'switch') {
    node.dpid = `0000000000000000${num}`.slice(-16);
  } else {
    node.ip  = `10.0.0.${num}`;
    node.mac = `00:00:00:00:00:${`0${num}`.slice(-2)}`;
  }
  editor.nodes.push(node);
  editor.selected = id;
  renderEditorGraph();
  renderPropsPanel();
}

// ── Editor: properties panel ──────────────────────────────────────────────────

function renderPropsPanel() {
  const panel = document.getElementById('props-content');
  if (!panel) return;

  const node = editor.nodes.find(n => n.id === editor.selected);
  if (!node) {
    panel.innerHTML = `<div class="props-hint">Click a node to edit its properties</div>`;
    return;
  }

  const swFields  = [{ k:'label', l:'Label' }, { k:'dpid', l:'DPID (16 hex digits)' }];
  const hostFields = [{ k:'label', l:'Label' }, { k:'ip', l:'IP Address' }, { k:'mac', l:'MAC Address' }];
  const fields = node.type === 'switch' ? swFields : hostFields;

  // Connected links for this node
  const connLinks = editor.links.filter(l => l.source === node.id || l.target === node.id);
  const linkRows = connLinks.length > 0
    ? connLinks.map(l => {
        const peerId = l.source === node.id ? l.target : l.source;
        const peer = editor.nodes.find(n => n.id === peerId);
        return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">
          <span style="font-size:11px;color:#9ca3af;flex:1">${peer?.label ?? peerId}</span>
          <input class="props-input link-bw-input" data-lid="${l.id}" value="${l.bw ?? ''}"
            style="width:60px;text-align:right" placeholder="Mbps" />
          <span style="font-size:10px;color:#4b5563">M</span>
          <button class="props-delete-btn" data-lid="${l.id}"
            style="width:auto;margin:0;padding:3px 6px;font-size:10px">✕</button>
        </div>`;
      }).join('')
    : `<div class="props-hint">No connected links</div>`;

  panel.innerHTML = `
    ${fields.map(f => `
      <div class="props-field">
        <div class="props-field-label">${f.l}</div>
        <input class="props-input" data-key="${f.k}" value="${escHtml(node[f.k] || '')}" />
      </div>`).join('')}
    <div class="props-section-title">Links</div>
    ${linkRows}
    <button id="props-delete-node-btn" class="props-delete-btn">Delete ${node.type === 'switch' ? 'Switch' : 'Host'}</button>
  `;

  // Node field changes
  panel.querySelectorAll('.props-input[data-key]').forEach(inp => {
    inp.addEventListener('input', ev => {
      const n = editor.nodes.find(x => x.id === editor.selected);
      if (n) { n[ev.target.dataset.key] = ev.target.value; renderEditorGraph(); }
    });
  });

  // Link bw changes
  panel.querySelectorAll('.link-bw-input').forEach(inp => {
    inp.addEventListener('input', ev => {
      const lnk = editor.links.find(l => l.id === ev.target.dataset.lid);
      if (lnk) { lnk.bw = Number(ev.target.value) || null; renderEditorGraph(); }
    });
  });

  // Link delete buttons
  panel.querySelectorAll('button[data-lid]').forEach(btn => {
    btn.addEventListener('click', () => {
      editorPushHistory();
      editor.links = editor.links.filter(l => l.id !== btn.dataset.lid);
      renderEditorGraph();
      renderPropsPanel();
    });
  });

  // Node delete
  document.getElementById('props-delete-node-btn')?.addEventListener('click', () => {
    editorPushHistory();
    editor.nodes = editor.nodes.filter(n => n.id !== editor.selected);
    editor.links = editor.links.filter(l => l.source !== editor.selected && l.target !== editor.selected);
    editor.selected = null;
    renderEditorGraph();
    renderPropsPanel();
  });
}

// ── Editor: apply / save ──────────────────────────────────────────────────────

async function applyTopology() {
  const payload = {
    switches: editor.nodes
      .filter(n => n.type === 'switch')
      .map(n => ({ id: n.id, label: n.label, dpid: n.dpid, x: Math.round(n.x), y: Math.round(n.y) })),
    hosts: editor.nodes
      .filter(n => n.type === 'host')
      .map(n => ({ id: n.id, label: n.label, ip: n.ip, mac: n.mac, x: Math.round(n.x), y: Math.round(n.y) })),
    links: editor.links.map(l => ({ id: l.id, source: l.source, target: l.target, bw: l.bw })),
  };

  // Show "Applying..." in the apply button
  const applyBtn = document.getElementById('topo-apply-btn');
  const origText = applyBtn.textContent;
  applyBtn.textContent = 'Applying…';
  applyBtn.disabled = true;

  try {
    // 1. Save topology file
    await fetch('/api/topology/custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    // 2. Push to ONOS netcfg (best-effort — ONOS may be offline)
    let onosMsg = '';
    try {
      const applyRes = await fetch('/api/topology/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const applyData = await applyRes.json();
      if (applyData.ok) {
        const d = applyData.pushed || {};
        onosMsg = `ONOS synced (${d.devices ?? 0} devices, ${d.hosts ?? 0} hosts)`;
      } else {
        onosMsg = `ONOS offline — topology saved locally (${applyData.error || ''})`;
      }
    } catch (_) {
      onosMsg = 'ONOS offline — topology saved locally';
    }

    updateExampleChips(payload);
    exitEditMode();

    // Show brief status in topology title
    const titleEl = document.getElementById('topo-title');
    if (titleEl) {
      const prev = titleEl.textContent;
      titleEl.textContent = onosMsg;
      setTimeout(() => { titleEl.textContent = prev; }, 4000);
    }
  } catch (err) {
    console.error('Failed to apply topology:', err);
    applyBtn.textContent = 'Error';
    setTimeout(() => {
      applyBtn.textContent = origText;
      applyBtn.disabled = false;
    }, 2000);
    return;
  }

  applyBtn.textContent = origText;
  applyBtn.disabled = false;
}

function updateExampleChips(topo) {
  const hosts = topo.hosts || [];
  const switches = topo.switches || [];
  if (hosts.length < 2 || switches.length < 1) return;

  const h1 = hosts[0];
  const h2 = hosts[hosts.length - 1];
  const s1 = switches[0];
  const swLabel = s1.label?.toLowerCase() ?? s1.id;
  const swPhrase = `switch ${swLabel.replace(/\D/g, '') || 1}`;

  const chips = [
    { t: `Block ${h1.ip}→${h2.ip}`,    i: `Block all traffic from ${h1.ip} to ${h2.ip} on ${swPhrase}` },
    { t: `Block SSH to ${h1.ip}`,       i: `Block TCP traffic on port 22 destined for ${h1.ip} on ${swPhrase}` },
    { t: `Forward ICMP→${h1.ip}`,       i: `Forward ICMP traffic destined for ${h1.ip} through port 3 on ${swPhrase}` },
    { t: `Forward HTTP→${h2.ip}`,       i: `Forward TCP traffic on port 80 destined for ${h2.ip} via port 2 on ${swPhrase}` },
  ];
  if (hosts.length >= 4) {
    const h3 = hosts[2], h4 = hosts[3];
    chips.push({ t: `QoS ${h1.ip}→${h4.ip}`, i: `Apply QoS for video streaming from ${h1.ip} to ${h4.ip} on ${swPhrase}` });
    chips.push({ t: `Block ${h3.ip}→${h4.ip}`, i: `Block all traffic from ${h3.ip} to ${h4.ip} on switch ${switches[switches.length-1].label?.replace(/\D/g,'') || switches.length}` });
  }

  const container = document.getElementById('example-chips');
  container.innerHTML = chips.map(c =>
    `<div class="example-chip" data-intent="${escHtml(c.i)}">${escHtml(c.t)}</div>`
  ).join('');
  container.querySelectorAll('.example-chip').forEach(chip =>
    chip.addEventListener('click', () => fillIntent(chip.dataset.intent))
  );
}

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

  // Seed positions: prefer stored positions, then backend-provided x/y
  nodes.forEach(n => {
    const prev = nodePositions.get(n.id);
    if (prev) { n.x = prev.x; n.y = prev.y; }
    else if (n.x != null && n.y != null) {
      nodePositions.set(n.id, { x: n.x, y: n.y }); // cache backend coords
    }
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
    .selectAll('g.live-node')
    .data(nodes, d => d.id)
    .join(enter => enter.append('g').attr('class', 'live-node'))
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

function appendLogLine(stageNum, msg) {
  const el = document.getElementById(`live-${stageNum}`);
  if (!el) return;

  // 이전 current 라인 → done으로 강등
  const prev = el.querySelector('.log-line.current');
  if (prev) {
    prev.classList.remove('current');
    prev.classList.add('done');
  }

  // 새 라인 → current로 추가
  const line = document.createElement('div');
  line.className = 'log-line current';
  if (msg.startsWith('✓')) line.classList.add('log-ok');
  else if (msg.startsWith('✗')) line.classList.add('log-fail');
  else if (msg.startsWith('⚠')) line.classList.add('log-warn');
  line.textContent = msg;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
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

  // Topology editor controls
  document.getElementById('topo-fullscreen-btn').addEventListener('click', toggleTopoFullscreen);

  document.getElementById('topo-edit-btn').addEventListener('click', () => {
    if (editor.active) {
      exitEditMode();
    } else {
      enterEditMode().catch(err => console.error('[Editor] enterEditMode failed:', err));
    }
  });
  document.querySelectorAll('.tool-btn').forEach(btn => {
    btn.addEventListener('click', () => setEditorTool(btn.dataset.tool));
  });
  document.getElementById('topo-apply-btn').addEventListener('click', applyTopology);
  document.getElementById('topo-cancel-btn').addEventListener('click', exitEditMode);

  document.getElementById('clear-history-btn').addEventListener('click', async () => {
    if (!confirm('히스토리를 모두 삭제할까요?')) return;
    await fetch('/api/logs', { method: 'DELETE' });
    state.history = [];
    renderHistory();
  });

  // Load history + start topology refresh
  loadHistory();
  startRefreshLoop();
}

// ── Fullscreen ─────────────────────────────────────────────────────────────────

let topoFullscreen = false;

function toggleTopoFullscreen() {
  topoFullscreen = !topoFullscreen;
  document.getElementById('topology-panel').classList.toggle('fullscreen', topoFullscreen);
  const btn = document.getElementById('topo-fullscreen-btn');
  if (btn) btn.textContent = topoFullscreen ? '⊡' : '⛶';
  // Re-render after CSS transition (50ms) so SVG picks up new dimensions
  setTimeout(() => {
    if (editor.active) renderEditorGraph();
  }, 60);
}

// ── Editor: undo stack ─────────────────────────────────────────────────────────

const editorHistory = [];

function editorPushHistory() {
  editorHistory.push({
    nodes: JSON.parse(JSON.stringify(editor.nodes)),
    links: JSON.parse(JSON.stringify(editor.links)),
  });
  if (editorHistory.length > 30) editorHistory.shift();
}

function editorUndo() {
  if (!editorHistory.length) return;
  const snap = editorHistory.pop();
  editor.nodes = snap.nodes;
  editor.links = snap.links;
  editor.selected = null;
  renderEditorGraph();
  renderPropsPanel();
}

// ── Editor: lasso (Shift+drag) ─────────────────────────────────────────────────

const lasso = { active: false, x0: 0, y0: 0, x1: 0, y1: 0 };

function updateLassoRect() {
  if (!topoSvg) return;
  const x = Math.min(lasso.x0, lasso.x1);
  const y = Math.min(lasso.y0, lasso.y1);
  const w = Math.abs(lasso.x1 - lasso.x0);
  const h = Math.abs(lasso.y1 - lasso.y0);
  topoSvg.select('#lasso-rect')
    .attr('x', x).attr('y', y).attr('width', w).attr('height', h)
    .attr('opacity', 1);
}

function commitLasso() {
  const x0 = Math.min(lasso.x0, lasso.x1);
  const x1 = Math.max(lasso.x0, lasso.x1);
  const y0 = Math.min(lasso.y0, lasso.y1);
  const y1 = Math.max(lasso.y0, lasso.y1);
  if (x1 - x0 < 5 && y1 - y0 < 5) return; // too small — treat as click, ignore
  const inside = editor.nodes.filter(n => n.x >= x0 && n.x <= x1 && n.y >= y0 && n.y <= y1);
  if (inside.length === 0) return;
  editorPushHistory();
  const ids = new Set(inside.map(n => n.id));
  editor.nodes = editor.nodes.filter(n => !ids.has(n.id));
  editor.links = editor.links.filter(l => !ids.has(l.source) && !ids.has(l.target));
  if (ids.has(editor.selected)) editor.selected = null;
  renderEditorGraph();
  renderPropsPanel();
}

function isEditorBg(ev) {
  // True if the click target is SVG background (not an ed-node or ed-link group)
  let el = ev.target;
  while (el && el !== topoSvg?.node()) {
    if (el.classList?.contains('ed-node') || el.classList?.contains('ed-link')) return false;
    el = el.parentElement;
  }
  return true;
}

// ── Keyboard shortcuts ──────────────────────────────────────────────────────────

document.addEventListener('keydown', ev => {
  const inInput = ev.target.tagName === 'INPUT' || ev.target.tagName === 'TEXTAREA';

  // F — fullscreen toggle (always available unless typing)
  if (ev.key === 'f' && !ev.ctrlKey && !ev.metaKey && !inInput) {
    toggleTopoFullscreen();
    return;
  }
  // Escape exits fullscreen first
  if (ev.key === 'Escape' && topoFullscreen) {
    toggleTopoFullscreen();
    return;
  }

  if (!editor.active || inInput) return;

  switch (ev.key) {
    case 's': setEditorTool('switch'); break;
    case 'h': setEditorTool('host');   break;
    case 'l': setEditorTool('link');   break;
    case 'd': setEditorTool('delete'); break;
    case 'Escape':
      if (editor.linking) {
        editor.linking = null;
        topoSvg?.select('#ghost-link').attr('opacity', 0);
        renderEditorGraph();
      } else {
        setEditorTool('select');
      }
      break;
    case 'Backspace':
    case 'Delete':
      if (editor.selected) {
        editorPushHistory();
        editor.nodes = editor.nodes.filter(n => n.id !== editor.selected);
        editor.links = editor.links.filter(l =>
          l.source !== editor.selected && l.target !== editor.selected
        );
        editor.selected = null;
        renderEditorGraph();
        renderPropsPanel();
        ev.preventDefault();
      }
      break;
    case 'z':
      if (ev.ctrlKey || ev.metaKey) { editorUndo(); ev.preventDefault(); }
      break;
  }
});

document.addEventListener('DOMContentLoaded', init);
