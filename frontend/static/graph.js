/* Memory graph view — full Kuzu graph as an interactive 3D force-directed sphere
   (3d-force-graph + three.js, vendored locally). Read-only. Everything hangs off
   the Manufacturer hub, so it forms one connected ball. */

function getVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

const TYPE_COLOR = {
  Manufacturer: '#0E1512',
  Customer: getVar('--green'),
  Deal: '#2E7D9A',
  Call: '#C79A3A',
  Pattern: '#8B94A3',
};
const RED = getVar('--red');
const GREEN = getVar('--green');

const SIZE = { Manufacturer: 14, Customer: 5, Deal: 2.6, Call: 1.8, Pattern: 6 };

let Graph = null;

function colorFor(n) {
  if (n.type === 'Customer' && n.escalate) return RED;
  return TYPE_COLOR[n.type] || '#8B94A3';
}

async function load() {
  await setModeTag();
  const data = await fetch('/api/graph').then(r => r.json());
  render(data);
}

async function setModeTag() {
  try {
    const s = await fetch('/api/sessions').then(r => r.json());
    const tag = document.getElementById('mode-tag');
    if (s.model_mode === 'live') {
      tag.innerHTML = `<span class="mode-tag__dot"></span> LIVE · ${s.model}`;
    } else {
      tag.className = 'mode-tag mode-tag--mock';
      tag.innerHTML = `<span class="mode-tag__dot"></span> MOCK`;
    }
  } catch (e) { /* non-fatal */ }
}

function render(data) {
  const nodes = data.nodes.map(n => ({
    id: n.id, label: n.label, type: n.type, escalate: !!n.escalate,
    meta: n.meta || {}, color: colorFor(n), val: SIZE[n.type] || 4,
  }));
  const links = data.edges.map(e => ({
    source: e.source, target: e.target, type: e.type,
    similar: e.type === 'SIMILAR_TO',
  }));

  const el = document.getElementById('cy');
  el.innerHTML = '';

  Graph = ForceGraph3D()(el)
    .backgroundColor('#F6F8F5')
    .graphData({ nodes, links })
    .nodeVal('val')
    .nodeColor('color')
    .nodeOpacity(0.95)
    .nodeResolution(20)
    .nodeLabel(n => `<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;
        background:#0E1512;color:#fff;padding:4px 8px;border-radius:6px">
        ${n.type} · ${n.label}</div>`)
    .linkColor(l => l.similar ? GREEN : '#C2CAC3')
    .linkWidth(l => l.similar ? 1.4 : 0.25)
    .linkOpacity(0.28)
    .linkCurvature(l => l.similar ? 0.25 : 0)
    .linkDirectionalParticles(l => l.similar ? 2 : 0)
    .linkDirectionalParticleWidth(1.6)
    .linkDirectionalParticleColor(() => GREEN)
    .linkLabel(l => l.type)
    .cooldownTicks(120)
    .onNodeClick(node => showDetail(node))
    .onBackgroundClick(closeDetail);

  // Denser graph (~200 nodes): stronger repulsion + longer links spread it into
  // a full ball; pull the camera back so the whole sphere is in frame.
  Graph.d3Force('charge').strength(-90);
  Graph.d3Force('link').distance(l => l.similar ? 40 : 26);
  Graph.cameraPosition({ z: 620 });
  let fitted = false;
  Graph.onEngineStop(() => { if (!fitted) { fitted = true; Graph.zoomToFit(600, 60); } });

  window.addEventListener('resize', sizeGraph);
  sizeGraph();
}

function sizeGraph() {
  if (!Graph) return;
  const el = document.getElementById('cy');
  Graph.width(el.clientWidth).height(el.clientHeight);
}

// --- detail panel ------------------------------------------------------------
function showDetail(d) {
  const panel = document.getElementById('detail');
  document.getElementById('detail-type').textContent = d.type;
  document.getElementById('detail-title').textContent = d.label;
  document.getElementById('detail-body').innerHTML = renderMeta(d);
  panel.classList.add('open');
}
function closeDetail() { document.getElementById('detail').classList.remove('open'); }

function row(k, v) {
  return `<div class="memrow"><span class="memrow__k">${k}</span><span class="memrow__v">${v}</span></div>`;
}

function renderMeta(d) {
  const m = d.meta || {};
  let html = '';
  if (d.type === 'Manufacturer') {
    html += `<p style="font-size:13.5px;color:var(--ink-2);line-height:1.5;margin:0">${m.note || ''}</p>`;
  } else if (d.type === 'Customer') {
    const badge = { hard_haggler: 'badge--hard', responsive: 'badge--responsive', goes_silent: 'badge--silent' }[m.style] || 'badge';
    html += `<span class="badge ${badge} node-detail__badge">${m.style}</span>`;
    if (d.escalate) html += `<div class="escalation-banner" style="margin:0 0 12px"><span class="escalation-banner__icon">⚠</span> Needs human — declining outcomes</div>`;
    html += row('Region', m.region);
    html += row('Risk flags', (m.risk_flags && m.risk_flags.length) ? m.risk_flags.join(', ') : '—');
    html += row('Recent scores', (m.recent_scores || []).join(' → ') || '—');
  } else if (d.type === 'Deal') {
    html += row('Floor', `${m.floor_price} ${m.currency}`);
    html += row('Target', `${m.target_price} ${m.currency}`);
    html += row('Status', m.status);
  } else if (d.type === 'Call') {
    html += row('When', (m.ts || '').slice(0, 10));
    html += row('Sentiment', m.sentiment);
    const cls = m.outcome_score < 0.4 ? 'score-chip--lo' : 'score-chip--hi';
    html += row('Outcome score', `<span class="score-chip ${cls}">${m.outcome_score}</span>`);
    html += `<div class="callitem" style="margin-top:12px"><div class="callitem__summary">${m.summary || ''}</div></div>`;
  } else if (d.type === 'Pattern') {
    html += `<p style="font-size:13.5px;color:var(--ink-2);line-height:1.5;margin:0">${m.detail || ''}</p>`;
  }
  return html;
}

// --- controls ----------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('detail-close').addEventListener('click', closeDetail);
  document.getElementById('fit').addEventListener('click', () => Graph && Graph.zoomToFit(700, 40));
  document.getElementById('replay').addEventListener('click', async (e) => {
    e.target.disabled = true;
    await fetch('/api/refresh', { method: 'POST' });
    await load();
    e.target.disabled = false;
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDetail(); });
  load();
});
