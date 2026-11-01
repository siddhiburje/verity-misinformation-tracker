/*
 * Verity — chronological narrative evolution tree.
 *
 * This graph deliberately does NOT invent contradiction relationships.
 * Similarity is used only to choose a likely parent/lineage connection;
 * verification status is the only source of the red/green/yellow/neutral
 * claim state.
 */
function createVerityGraph(container, { nodes = [], edges = [], onSelect, centerId }) {
  container.innerHTML = '';
  const width = container.clientWidth || 760;
  const height = container.clientHeight || 420;
  const svgNS = 'http://www.w3.org/2000/svg';

  const wrap = document.createElement('div');
  wrap.style.cssText = 'position:absolute;inset:0;overflow:hidden;';
  container.appendChild(wrap);

  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('width', '100%');
  svg.setAttribute('height', '100%');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.style.cursor = 'grab';
  wrap.appendChild(svg);

  const world = document.createElementNS(svgNS, 'g');
  svg.appendChild(world);

  const truncate = (text, max) => {
    const value = String(text || '').replace(/\s+/g, ' ').trim();
    return value.length > max ? `${value.slice(0, max - 1)}…` : value;
  };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (c) => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c]));
  const addText = (parent, x, y, text, size, fill, weight = '400') => {
    const el = document.createElementNS(svgNS, 'text');
    el.setAttribute('x', x); el.setAttribute('y', y);
    el.setAttribute('font-size', size);
    el.setAttribute('font-family', 'Inter, Arial, sans-serif');
    el.setAttribute('font-weight', weight);
    el.setAttribute('fill', fill);
    el.textContent = text;
    parent.appendChild(el);
    return el;
  };

  // De-duplicate exact/near-identical node text before laying anything out.
  // Server-side claim reuse handles persistent duplicates; this protects the
  // visual graph from legacy duplicate rows already present in the database.
  const normalize = (text) => String(text || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  const tokenSimilarity = (a, b) => {
    const A = new Set(normalize(a).split(/\s+/).filter(Boolean));
    const B = new Set(normalize(b).split(/\s+/).filter(Boolean));
    if (!A.size || !B.size) return 0;
    let common = 0;
    A.forEach(t => { if (B.has(t)) common++; });
    return common / Math.max(A.size, B.size);
  };
  const uniqueNodes = [];
  const duplicateIds = new Set();
  nodes.slice().sort((a, b) => {
    if (String(a.id) === String(centerId)) return -1;
    if (String(b.id) === String(centerId)) return 1;
    return Number(a.id) - Number(b.id);
  }).forEach((n) => {
    const duplicate = uniqueNodes.find((u) =>
      String(u.origin) === String(n.origin) &&
      (normalize(u.text) === normalize(n.text) || tokenSimilarity(u.text, n.text) >= 0.95)
    );
    if (duplicate) duplicateIds.add(n.id);
    else uniqueNodes.push({ ...n });
  });

  if (!uniqueNodes.length) {
    const emptyText = document.createElementNS(svgNS, 'text');
    emptyText.setAttribute('x', width / 2); emptyText.setAttribute('y', height / 2);
    emptyText.setAttribute('text-anchor', 'middle'); emptyText.setAttribute('fill', '#96a0b8');
    emptyText.setAttribute('font-family', 'JetBrains Mono, monospace');
    emptyText.textContent = 'No related claims yet.';
    svg.appendChild(emptyText);
    return { destroy() { container.innerHTML = ''; }, highlight() {} };
  }

  const idToNode = {};
  uniqueNodes.forEach(n => { idToNode[n.id] = n; });
  const validEdges = edges.filter(e => idToNode[e.source] && idToNode[e.target]);

  const timeValue = (n) => {
    const raw = n.published_at || n.created_at;
    const t = raw ? Date.parse(raw) : NaN;
    return Number.isFinite(t) ? t : 0;
  };
  uniqueNodes.sort((a, b) => timeValue(a) - timeValue(b) || Number(a.id) - Number(b.id));

  // Build a chronological parent for each node. We only use existing
  // similarity edges; when a same-cluster claim has no direct edge, the
  // nearest earlier same-cluster claim provides a visual lineage connection.
  const parents = {};
  uniqueNodes.forEach((node) => {
    const prior = uniqueNodes.filter(other => timeValue(other) < timeValue(node) ||
      (timeValue(other) === timeValue(node) && Number(other.id) < Number(node.id)));
    if (!prior.length) return;

    const candidates = [];
    validEdges.forEach((e) => {
      let otherId = null;
      if (String(e.source) === String(node.id)) otherId = e.target;
      if (String(e.target) === String(node.id)) otherId = e.source;
      if (otherId == null) return;
      const other = idToNode[otherId];
      if (!other || !prior.some(p => String(p.id) === String(other.id))) return;
      candidates.push({ node: other, similarity: Number(e.similarity) || 0 });
    });

    candidates.sort((a, b) => b.similarity - a.similarity || timeValue(b.node) - timeValue(a.node));
    if (candidates.length) {
      parents[node.id] = { id: candidates[0].node.id, similarity: candidates[0].similarity, kind: 'similar' };
      return;
    }

    const sameCluster = prior.filter(p => node.cluster_id && p.cluster_id && p.cluster_id === node.cluster_id);
    if (sameCluster.length) {
      const parent = sameCluster[sameCluster.length - 1];
      parents[node.id] = { id: parent.id, similarity: 0, kind: 'cluster' };
    }
  });

  // Hierarchical columns are assigned recursively. A child normally stays
  // below its parent; multiple branches get their own horizontal lanes.
  const children = {};
  uniqueNodes.forEach(n => { children[n.id] = []; });
  Object.entries(parents).forEach(([childId, parent]) => {
    if (children[parent.id]) children[parent.id].push(idToNode[childId]);
  });

  const roots = uniqueNodes.filter(n => !parents[n.id]);
  const CARD_W = Math.min(230, Math.max(190, width * 0.25));
  const CARD_H = 92;
  const X_GAP = 28;
  const colStep = CARD_W + X_GAP;
  const maxDepth = Math.max(0, ...uniqueNodes.map(n => {
    let d = 0, cur = n;
    const seen = new Set();
    while (parents[cur.id] && !seen.has(cur.id)) {
      seen.add(cur.id); cur = idToNode[parents[cur.id].id]; d++;
    }
    return d;
  }));
  const rowStep = maxDepth > 0
    ? Math.max(CARD_H + 22, Math.min(CARD_H + 58, (height - 80) / Math.min(maxDepth, 6)))
    : CARD_H + 58;

  // First pass: assign each node a tree depth. If the graph is wider than
  // the viewport, the user can pan/zoom horizontally.
  const depth = {};
  const setDepth = (n, d) => {
    if (depth[n.id] == null || d < depth[n.id]) depth[n.id] = d;
    (children[n.id] || []).forEach(c => setDepth(c, d + 1));
  };
  roots.forEach(r => setDepth(r, 0));
  uniqueNodes.forEach(n => { if (depth[n.id] == null) depth[n.id] = 0; });

  const byDepth = {};
  uniqueNodes.forEach(n => (byDepth[depth[n.id]] ||= []).push(n));
  Object.values(byDepth).forEach(arr => arr.sort((a,b) => timeValue(a) - timeValue(b) || Number(a.id) - Number(b.id)));

  const positions = {};
  Object.entries(byDepth).forEach(([d, arr]) => {
    const y = 60 + Number(d) * rowStep;
    const totalW = arr.length * CARD_W + Math.max(0, arr.length - 1) * X_GAP;
    const startX = Math.max(CARD_W / 2 + 12, (width - totalW) / 2 + CARD_W / 2);
    arr.forEach((n, i) => {
      positions[n.id] = { x: startX + i * colStep, y };
    });
  });

  // Extend the world vertically if the tree needs more room.
  const worldHeight = Math.max(height, 110 + maxDepth * rowStep + CARD_H);
  svg.setAttribute('viewBox', `0 0 ${Math.max(width, Math.max(...Object.values(positions).map(p => p.x + CARD_W / 2), width))} ${worldHeight}`);

  const verificationMeta = (status) => {
    const key = String(status || '').toLowerCase();
    if (key === 'supported') return { color: '#3b8c5a', bg: '#dff1e5', label: 'SUPPORTED' };
    if (key === 'contradicted') return { color: '#c0392b', bg: '#f7ddd8', label: 'CONTRADICTED' };
    if (key === 'mixed') return { color: '#b27b16', bg: '#f5e8bd', label: 'MIXED' };
    return { color: '#7d8190', bg: '#e5e5e3', label: 'UNVERIFIED' };
  };
  const originLabel = ({ user_text:'YOUR TEXT', user_image:'YOUR IMAGE', news:'NEWS', reference:'REFERENCE' }[uniqueNodes[0].origin] || 'CLAIM');

  // Cluster bands are subtle context only; they do not represent truth or
  // contradiction relationships.
  const clusterGroup = {};
  uniqueNodes.forEach(n => {
    const key = n.cluster_id || `single-${n.id}`;
    (clusterGroup[key] ||= []).push(n);
  });
  const clusterBg = document.createElementNS(svgNS, 'g');
  world.appendChild(clusterBg);
  Object.values(clusterGroup).forEach(group => {
    if (group.length < 2) return;
    const xs = group.map(n => positions[n.id].x), ys = group.map(n => positions[n.id].y);
    const minX = Math.min(...xs) - CARD_W / 2 - 18;
    const maxX = Math.max(...xs) + CARD_W / 2 + 18;
    const minY = Math.min(...ys) - CARD_H / 2 - 28;
    const maxY = Math.max(...ys) + CARD_H / 2 + 18;
    const rect = document.createElementNS(svgNS, 'rect');
    rect.setAttribute('x', minX); rect.setAttribute('y', minY);
    rect.setAttribute('width', Math.max(220, maxX - minX));
    rect.setAttribute('height', Math.max(120, maxY - minY));
    rect.setAttribute('rx', 18); rect.setAttribute('fill', '#171b25');
    rect.setAttribute('stroke', '#343b4e'); rect.setAttribute('stroke-dasharray', '5 5');
    rect.setAttribute('opacity', '0.82');
    clusterBg.appendChild(rect);
    addText(clusterBg, minX + 14, minY + 18, truncate(group[0].narrative_label || 'Narrative cluster', 42), 10, '#aeb6c9', '600');
  });

  const edgeGroup = document.createElementNS(svgNS, 'g');
  world.appendChild(edgeGroup);
  Object.entries(parents).forEach(([childId, parent]) => {
    const a = positions[parent.id], b = positions[childId];
    if (!a || !b) return;
    const path = document.createElementNS(svgNS, 'path');
    const midY = (a.y + b.y) / 2;
    path.setAttribute('d', `M ${a.x} ${a.y + CARD_H/2} C ${a.x} ${midY}, ${b.x} ${midY}, ${b.x} ${b.y - CARD_H/2}`);
    path.setAttribute('fill', 'none'); path.setAttribute('stroke', '#687188'); path.setAttribute('stroke-width', '1.8');
    path.setAttribute('opacity', '0.72');
    edgeGroup.appendChild(path);

    if (parent.similarity > 0) {
      const label = document.createElementNS(svgNS, 'text');
      label.setAttribute('x', (a.x + b.x) / 2);
      label.setAttribute('y', midY - 4);
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('font-size', '8');
      label.setAttribute('font-family', 'Inter, Arial, sans-serif');
      label.setAttribute('fill', '#aeb6c9');
      label.textContent = `related · ${Math.round(parent.similarity * 100)}%`;
      edgeGroup.appendChild(label);
    }
  });

  const nodeGroup = document.createElementNS(svgNS, 'g');
  world.appendChild(nodeGroup);
  const nodeEls = {};

  function showDetails(n) {
    const v = verificationMeta(n.verification && n.verification.status);
    const keywords = (n.keywords || []).map(k => `<span style="display:inline-block;padding:3px 7px;border-radius:999px;background:#e8e2d6;margin:2px;font-size:10px;">${escapeHtml(k.term || k)}</span>`).join('') || '<span style="font-size:11px;color:#6e6a61;">None detected</span>';
    const entities = (n.entities || []).map(e => `<div style="display:flex;justify-content:space-between;gap:8px;margin:4px 0;font-size:11px;"><span>${escapeHtml(e.text)}</span><span style="color:#6e6a61;">${escapeHtml(e.label)}</span></div>`).join('') || '<span style="font-size:11px;color:#6e6a61;">None detected</span>';
    const sources = (n.verification && n.verification.sources || []).map(s => s.url
      ? `<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;padding:7px 0;border-top:1px solid #d8d0c3;"><span style="font-size:11px;">${escapeHtml(s.publisher || s.title || 'Fact-check source')}</span><a href="${escapeHtml(s.url)}" target="_blank" rel="noopener" style="font-size:10px;font-weight:700;color:#8c3323;">Open</a></div>`
      : '').join('');
    const sourceFallback = n.source_url ? `<div style="padding-top:8px;"><a href="${escapeHtml(n.source_url)}" target="_blank" rel="noopener" style="font-size:11px;font-weight:700;color:#8c3323;">Open source</a></div>` : '';

    details.innerHTML = `
      <button type="button" style="float:right;border:0;background:transparent;font-size:18px;cursor:pointer;color:#333;">×</button>
      <div style="font-size:10px;font-weight:700;letter-spacing:.08em;color:${v.color};">${escapeHtml(v.label)}</div>
      <div style="font-size:14px;font-weight:700;line-height:1.4;margin:7px 0 8px;">${escapeHtml(n.text || '')}</div>
      <div style="font-size:11px;color:#6e6a61;line-height:1.5;">
        <strong>Narrative:</strong> ${escapeHtml(n.narrative_label || 'Unclustered')}<br>
        <strong>Source:</strong> ${escapeHtml(n.source_name || 'Unknown source')}<br>
        <strong>Date:</strong> ${escapeHtml(n.published_at || n.created_at || 'Unknown')}
      </div>
      <div style="margin-top:12px;"><strong style="font-size:11px;">Keywords</strong><div style="margin-top:4px;">${keywords}</div></div>
      <div style="margin-top:12px;"><strong style="font-size:11px;">Named entities</strong><div style="margin-top:4px;">${entities}</div></div>
      <div style="margin-top:12px;padding-top:10px;border-top:1px solid #d8d0c3;"><strong style="font-size:11px;">Verification</strong><div style="font-size:11px;margin-top:5px;">${escapeHtml(n.verification && n.verification.explanation || 'This claim has not been independently fact-checked.')}</div>${sources}${sourceFallback}</div>
    `;
    details.style.display = 'block';
    details.querySelector('button').addEventListener('click', e => { e.stopPropagation(); details.style.display = 'none'; });
  }

  const details = document.createElement('div');
  details.style.cssText = 'position:absolute;right:12px;bottom:12px;width:min(380px,calc(100% - 24px));max-height:calc(100% - 24px);overflow:auto;display:none;z-index:5;background:#f2ece0;color:#20242d;border:1px solid #8a8574;border-radius:12px;box-shadow:0 12px 30px rgba(0,0,0,.45);padding:14px;font-family:Inter,Arial,sans-serif;';
  container.appendChild(details);

  uniqueNodes.forEach(n => {
    const p = positions[n.id];
    const g = document.createElementNS(svgNS, 'g');
    g.style.cursor = 'pointer'; g.setAttribute('data-node-id', n.id);
    const v = verificationMeta(n.verification && n.verification.status);
    const isCenter = String(n.id) === String(centerId);

    const shadow = document.createElementNS(svgNS, 'rect');
    shadow.setAttribute('x', p.x-CARD_W/2+3); shadow.setAttribute('y', p.y-CARD_H/2+4);
    shadow.setAttribute('width', CARD_W); shadow.setAttribute('height', CARD_H); shadow.setAttribute('rx', 12);
    shadow.setAttribute('fill', '#07090e'); shadow.setAttribute('opacity', '.65'); g.appendChild(shadow);

    const card = document.createElementNS(svgNS, 'rect');
    card.setAttribute('x', p.x-CARD_W/2); card.setAttribute('y', p.y-CARD_H/2);
    card.setAttribute('width', CARD_W); card.setAttribute('height', CARD_H); card.setAttribute('rx', 12);
    card.setAttribute('fill', '#f2ece0'); card.setAttribute('stroke', v.color); card.setAttribute('stroke-width', isCenter ? 3 : 1.8); g.appendChild(card);

    addText(g, p.x-CARD_W/2+12, p.y-CARD_H/2+16, v.label, 8, v.color, '700');
    const origin = ({ user_text:'YOUR TEXT', user_image:'YOUR IMAGE', news:'NEWS', reference:'REFERENCE' }[n.origin] || 'CLAIM');
    addText(g, p.x+CARD_W/2-12, p.y-CARD_H/2+16, origin, 7.5, '#777166', '700').setAttribute('text-anchor','end');

    const words = truncate(n.text, 76).split(' '); let line1='', line2='';
    words.forEach(word => { if ((line1+' '+word).trim().length <= 35) line1=(line1+' '+word).trim(); else if ((line2+' '+word).trim().length <= 35) line2=(line2+' '+word).trim(); });
    if (!line2 && String(n.text||'').length > line1.length) line2 = String(n.text||'').slice(line1.length).trim();
    addText(g, p.x-CARD_W/2+12, p.y-12, line1, 10.5, '#20242d', '600');
    if (line2) addText(g, p.x-CARD_W/2+12, p.y+3, truncate(line2, 37), 10.5, '#20242d', '600');

    const date = n.published_at || n.created_at;
    addText(g, p.x-CARD_W/2+12, p.y+28, date ? new Date(date).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'}) : 'No date', 8.2, '#6e6a61');
    addText(g, p.x+CARD_W/2-12, p.y+28, truncate(n.narrative_label || 'Unclustered', 27), 8.2, '#6e6a61').setAttribute('text-anchor','end');

    if (isCenter) {
      const badge = document.createElementNS(svgNS,'rect'); badge.setAttribute('x',p.x-CARD_W/2); badge.setAttribute('y',p.y-CARD_H/2-14); badge.setAttribute('width',56); badge.setAttribute('height',18); badge.setAttribute('rx',9); badge.setAttribute('fill','#b8412c'); g.appendChild(badge);
      const bt = addText(g,p.x-CARD_W/2+28,p.y-CARD_H/2-1,'CURRENT',7.5,'#fff8ef','700'); bt.setAttribute('text-anchor','middle');
    }

    g.addEventListener('click', e => { e.stopPropagation(); if (onSelect) onSelect(n.id); showDetails(n); highlight(n.id); });
    nodeGroup.appendChild(g); nodeEls[n.id] = { g, card };
  });

  function highlight(nodeId) {
    Object.entries(nodeEls).forEach(([id, el]) => {
      const active = String(id) === String(nodeId);
      el.card.setAttribute('stroke-width', active ? 3.8 : (String(id) === String(centerId) ? 3 : 1.8));
    });
  }

  // Pan + zoom.
  let scale = 1, panX = 0, panY = 0, dragging = false, lastX = 0, lastY = 0;
  function applyTransform() { world.setAttribute('transform', `translate(${panX} ${panY}) scale(${scale})`); }
  svg.addEventListener('mousedown', e => { if (e.target.closest && e.target.closest('g[data-node-id]')) return; dragging=true; lastX=e.clientX; lastY=e.clientY; svg.style.cursor='grabbing'; });
  window.addEventListener('mouseup', () => { dragging=false; svg.style.cursor='grab'; });
  window.addEventListener('mousemove', e => { if(!dragging)return; panX+=e.clientX-lastX; panY+=e.clientY-lastY; lastX=e.clientX; lastY=e.clientY; applyTransform(); });
  svg.addEventListener('wheel', e => { e.preventDefault(); scale=Math.min(2.2,Math.max(.45,scale+(e.deltaY>0?-.08:.08))); applyTransform(); }, {passive:false});
  svg.addEventListener('click', () => { details.style.display='none'; });

  return {
    highlight,
    zoomIn(){scale=Math.min(2.2,scale+.2);applyTransform();},
    zoomOut(){scale=Math.max(.45,scale-.2);applyTransform();},
    reset(){scale=1;panX=0;panY=0;applyTransform();details.style.display='none';},
    destroy(){container.innerHTML='';}
  };
}
