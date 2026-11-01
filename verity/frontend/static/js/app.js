/*
 * Verity — dashboard application logic.
 * Wires every page (Overview, Analyze, Import, News tracker, History)
 * to the real backend endpoints defined in api.js.
 */
(function () {
  if (!Verity.requireAuth()) return;

  const V = Verity;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // ---------------------------------------------------------------
  // Navigation
  // ---------------------------------------------------------------
  function goToPage(pageId) {
    $$('.page').forEach((p) => p.classList.toggle('active', p.id === `page-${pageId}`));
    $$('.sb-item[data-page]').forEach((b) => b.classList.toggle('active', b.dataset.page === pageId));
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (pageId === 'overview') loadOverview();
    if (pageId === 'history') loadHistory();
  }
  $$('.sb-item[data-page]').forEach((btn) => btn.addEventListener('click', () => goToPage(btn.dataset.page)));
  $$('[data-nav]').forEach((el) => el.addEventListener('click', (e) => { e.preventDefault(); goToPage(el.dataset.nav); }));

  $('#logoutBtn').addEventListener('click', async () => {
    try { await V.api('/api/auth/logout', { method: 'POST' }); } catch (e) { /* ignore */ }
    V.logout();
  });

  // ---------------------------------------------------------------
  // Sidebar user info
  // ---------------------------------------------------------------
  function initUser() {
    const cached = V.getUser();
    if (cached) applyUser(cached);
    V.api('/api/auth/me').then((d) => { V.setUser(d.user); applyUser(d.user); }).catch(() => {});
  }
  function applyUser(user) {
    $('#userName').textContent = user.name;
    $('#userEmail').textContent = user.email;
    $('#userAvatar').textContent = (user.name || '?').trim().charAt(0).toUpperCase();
    $('#overviewGreeting').textContent = `Welcome back, ${user.name.split(' ')[0]}`;
  }

  // ---------------------------------------------------------------
  // Overview
  // ---------------------------------------------------------------
  async function loadOverview() {
    try {
      const [historyData, statsData] = await Promise.all([
        V.api('/api/history'),
        V.api('/api/stats'),
      ]);
      $('#statSearches').textContent = historyData.history.length;
      $('#statClaims').textContent = statsData.total_claims;

      const active = statsData.most_active_cluster;
      if (active) {
        $('#activeClusterName').textContent = active.label || 'Unclustered narrative';
        $('#activeClusterMeta').textContent = `${active.count} claim${active.count === 1 ? '' : 's'} tracked in the last 7 days`;
      } else {
        $('#activeClusterName').textContent = 'No active cluster yet';
        $('#activeClusterMeta').textContent = 'Analyze a claim to start a narrative trail.';
      }
    } catch (err) {
      console.error(err);
    }
  }

  // ---------------------------------------------------------------
  // Shared: render a claim analysis result (used by Analyze + History)
  // ---------------------------------------------------------------
  function renderResult(targetEl, payload, options = {}) {
    const tpl = document.getElementById('resultTemplate');
    const node = tpl.content.cloneNode(true);
    const claim = payload.claim;

    node.querySelector('.claim-text').textContent = options.headerOverride || claim.text;
    const originLabel = { reference: 'Reference dataset', user_text: 'You · text', user_image: 'You · image', news: claim.source_name }[claim.origin] || claim.source_name;
    node.querySelector('.claim-meta').textContent = `${originLabel} · ${V.formatDate(claim.published_at || claim.created_at)}`;
    node.querySelector('.narrative-badge').textContent = claim.narrative_label || 'Unclustered';

    // keywords
    const kwList = node.querySelector('.kw-list');
    if (claim.keywords && claim.keywords.length) {
      claim.keywords.forEach((k) => {
        const tag = document.createElement('span');
        tag.className = 'tag tag-neutral';
        tag.textContent = k.term;
        kwList.appendChild(tag);
      });
    } else {
      kwList.innerHTML = '<span class="result-meta on-paper">No distinctive keywords found.</span>';
    }

    // entities
    const entList = node.querySelector('.entity-list');
    if (claim.entities && claim.entities.length) {
      claim.entities.forEach((e) => {
        const row = document.createElement('div');
        row.className = 'entity-row on-paper';
        row.innerHTML = `<span>${V.escapeHtml(e.text)}</span><span class="tag tag-blue" style="padding:2px 8px;">${V.escapeHtml(e.label)}</span>`;
        entList.appendChild(row);
      });
    } else {
      entList.innerHTML = '<span class="result-meta on-paper">No named entities detected.</span>';
    }

    // sentiment
    if (claim.sentiment) {
      const pol = claim.sentiment.polarity;
      const subj = claim.sentiment.subjectivity;
      node.querySelector('.polarity-val').textContent = pol.toFixed(2);
      node.querySelector('.subjectivity-val').textContent = subj.toFixed(2);
      const polarityLabel = pol > 0.15 ? 'Positive' : (pol < -0.15 ? 'Negative' : 'Neutral');
      const polarityEl = node.querySelector('.polarity-label');
      polarityEl.textContent = polarityLabel;
      polarityEl.className = `polarity-label tag ${pol > 0.15 ? 'tag-green' : (pol < -0.15 ? 'tag-red' : 'tag-neutral')}`;
      node.querySelector('.polarity-bar').style.left = `${((pol + 1) / 2) * 100}%`;
      node.querySelector('.subjectivity-bar').style.left = `${subj * 100}%`;
    }

    // best match (narrative similarity — NOT a truth verdict)
    const bmEl = node.querySelector('.best-match-text');
    if (payload.best_match) {
      bmEl.textContent = `${payload.best_match.similarity}% similar to "${payload.best_match.narrative_label || 'a related claim'}" already tracked.`;
    } else {
      bmEl.textContent = 'No sufficiently similar claim found yet — this looks like a new narrative.';
    }

    // claim verification — a SEPARATE concept from narrative matching
    // above: independent fact-check evidence, not text similarity.
    const verifBadge = node.querySelector('.verification-badge');
    const verifExplanation = node.querySelector('.verification-explanation');
    const verifSourceList = node.querySelector('.verification-source-list');
    const verification = claim.verification;
    const statusColor = { Supported: 'tag-green', Contradicted: 'tag-red', Mixed: 'tag-amber', Unverified: 'tag-neutral' };
    const statusLabel = { Supported: '🟢 SUPPORTED', Contradicted: '🔴 CONTRADICTED', Mixed: '🟡 MIXED', Unverified: '⚪ UNVERIFIED' };

    verifSourceList.innerHTML = '';
    const factcheckContext = node.querySelector('.factcheck-context');
    const newsEvidenceList = node.querySelector('.news-evidence-list');
    if (factcheckContext) {
      factcheckContext.textContent = verification && verification.sources && verification.sources.length
        ? `${verification.sources.length} independent fact-check review${verification.sources.length === 1 ? '' : 's'} found.`
        : 'No independent fact-check review was found for this claim yet. This does not mean the claim is false.';
    }
    if (newsEvidenceList) {
      const newsEvidence = payload.news_evidence || [];
      newsEvidenceList.innerHTML = newsEvidence.length ? newsEvidence.map((a) => `
        <div class="evidence-item">
          ${a.url ? `<a href="${V.escapeHtml(a.url)}" target="_blank" rel="noopener">${V.escapeHtml(a.title || 'Open article')}</a>` : `<span style="color:#eeeaf8;font-size:.82rem;">${V.escapeHtml(a.title || 'Untitled article')}</span>`}
          <div class="meta">${V.escapeHtml(a.source_name || 'Unknown source')}${a.published_at ? ` · ${V.formatDate(a.published_at)}` : ''}</div>
        </div>
      `).join('') : '<div class="meta" style="color:#aaa5b9;font-size:.76rem;">No recent live news coverage matched this claim.</div>';
    }
    if (verification && verification.status) {
      verifBadge.textContent = statusLabel[verification.status] || `⚪ ${String(verification.status).toUpperCase()}`;
      verifBadge.className = `verification-hero-status verification-badge ${statusColor[verification.status] || 'tag-neutral'}`;
      verifExplanation.textContent = verification.explanation || '';
      if (verification.sources && verification.sources.length) {
        verification.sources.forEach((s) => {
          const row = document.createElement('div');
          row.className = 'source-row';
          const ratingPart = s.rating ? ` · ${V.escapeHtml(s.rating)}` : '';
          const datePart = s.review_date ? ` · ${V.formatDate(s.review_date)}` : '';
          const link = s.url
            ? `<a href="${V.escapeHtml(s.url)}" target="_blank" rel="noopener" class="btn btn-ghost-onpaper btn-sm">Open</a>`
            : '';
          row.innerHTML = `
            <div>
              <div class="source-name on-paper">${V.escapeHtml(s.publisher || 'Unknown publisher')}${ratingPart}</div>
              <div class="source-meta">${V.escapeHtml(s.title || '')}${datePart}</div>
            </div>
            ${link}
          `;
          verifSourceList.appendChild(row);
        });
      }
    } else {
      // Claims that never went through single text/image analysis
      // (news tracking, dataset import, reference data) simply were
      // never checked — that is shown honestly, not left blank/misleading.
      verifBadge.textContent = '⚪ UNVERIFIED';
      verifBadge.className = 'verification-hero-status verification-badge tag-neutral';
      verifExplanation.textContent = 'Verification was not run for this claim (it came from news tracking, dataset import, or the reference dataset rather than a single text/image analysis).';
    }

    // graph
    const graphContainer = node.querySelector('.graph-container');
    const graph = payload.graph || { nodes: [], edges: [] };
    targetEl.innerHTML = '';
    targetEl.appendChild(node);

    let graphApi = null;
    function buildGraph() {
      graphApi = createVerityGraph(graphContainer, {
        nodes: graph.nodes,
        edges: graph.edges,
        centerId: claim.id,
        onSelect: (nodeId) => highlightTimeline(nodeId),
      });
    }
    buildGraph();
    targetEl.querySelector('.zoom-in-btn').addEventListener('click', () => graphApi && graphApi.zoomIn());
    targetEl.querySelector('.zoom-out-btn').addEventListener('click', () => graphApi && graphApi.zoomOut());
    targetEl.querySelector('.zoom-reset-btn').addEventListener('click', () => graphApi && graphApi.reset());

    // timeline
    const timelineList = targetEl.querySelector('.timeline-list');
    const timeline = payload.timeline && payload.timeline.length ? payload.timeline : graph.nodes;
    timelineList.innerHTML = '';
    timeline.forEach((n) => {
      const row = document.createElement('div');
      row.className = 'timeline-row';
      row.dataset.nodeId = n.id;
      row.innerHTML = `
        <div class="timeline-date">${V.formatDate(n.published_at || n.created_at)}</div>
        <div class="timeline-dotcol"></div>
        <div class="timeline-text on-paper"><strong>${V.escapeHtml((n.text || '').slice(0, 90))}${n.text && n.text.length > 90 ? '…' : ''}</strong><div class="tsource">${V.escapeHtml(n.source_name || 'Unknown source')} · ${V.escapeHtml(n.narrative_label || '')}</div></div>
      `;
      row.addEventListener('click', () => {
        graphApi && graphApi.highlight(n.id);
        highlightTimeline(n.id);
      });
      timelineList.appendChild(row);
    });

    function highlightTimeline(nodeId) {
      $$('.timeline-row', timelineList).forEach((r) => r.classList.toggle('active-row', String(r.dataset.nodeId) === String(nodeId)));
    }


    targetEl.classList.add('show');
  }

  // ---------------------------------------------------------------
  // Analyze page
  // ---------------------------------------------------------------
  const inputTabs = $$('.input-tab[data-input]');
  const textPanel = $('#textInputPanel');
  const imagePanel = $('#imageInputPanel');
  inputTabs.forEach((tab) => tab.addEventListener('click', () => {
    inputTabs.forEach((t) => t.classList.toggle('active', t === tab));
    textPanel.style.display = tab.dataset.input === 'text' ? 'block' : 'none';
    imagePanel.style.display = tab.dataset.input === 'image' ? 'block' : 'none';
  }));

  const claimTextInput = $('#claimTextInput');
  claimTextInput.addEventListener('input', () => {
    $('#textCharCount').textContent = `${claimTextInput.value.length} / 8000 characters`;
  });

  function setBtnLoading(btn, loading, label) {
    btn.disabled = loading;
    btn.querySelector('.btn-label').innerHTML = loading ? '<span class="spinner"></span>' : label;
  }
  function showError(el, message) { el.textContent = message; el.classList.add('show'); }
  function hideError(el) { el.classList.remove('show'); }

  $('#analyzeTextBtn').addEventListener('click', async () => {
    const text = claimTextInput.value.trim();
    const errEl = $('#analyzeError');
    const loadingEl = $('#analyzeLoading');
    const resultsEl = $('#analyzeResults');
    hideError(errEl);
    resultsEl.classList.remove('show');

    if (!text) { showError(errEl, 'Please enter some text, a claim, or a headline to analyze.'); return; }

    const btn = $('#analyzeTextBtn');
    setBtnLoading(btn, true);
    loadingEl.style.display = 'flex';
    try {
      const data = await V.api('/api/analyze/text', { method: 'POST', body: { text } });
      renderResult(resultsEl, data);
    } catch (err) {
      showError(errEl, err.message);
    } finally {
      setBtnLoading(btn, false, 'Analyze claim');
      loadingEl.style.display = 'none';
    }
  });

  // --- Image upload ---
  const imageDropZone = $('#imageDropZone');
  const imageFileInput = $('#imageFileInput');
  const imagePreviewBox = $('#imagePreviewBox');
  let selectedImageFile = null;

  function handleImageFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    const errEl = $('#analyzeError');
    hideError(errEl);
    if (!['png', 'jpg', 'jpeg', 'webp'].includes(ext)) {
      showError(errEl, `Unsupported image format ".${ext}". Use PNG, JPG/JPEG, or WEBP.`);
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      showError(errEl, 'Image is too large (max 8 MB).');
      return;
    }
    selectedImageFile = file;
    $('#imageFileName').textContent = `${file.name} · ${(file.size / 1024).toFixed(1)} KB`;
    $('#imagePreviewThumb').src = URL.createObjectURL(file);
    imagePreviewBox.style.display = 'block';
    imageDropZone.style.display = 'none';
  }
  imageFileInput.addEventListener('change', (e) => { if (e.target.files[0]) handleImageFile(e.target.files[0]); });
  ['dragenter', 'dragover'].forEach((ev) => imageDropZone.addEventListener(ev, (e) => { e.preventDefault(); imageDropZone.classList.add('drag'); }));
  ['dragleave', 'drop'].forEach((ev) => imageDropZone.addEventListener(ev, (e) => { e.preventDefault(); imageDropZone.classList.remove('drag'); }));
  imageDropZone.addEventListener('drop', (e) => { const f = e.dataTransfer.files[0]; if (f) handleImageFile(f); });
  $('#imageClearBtn').addEventListener('click', () => {
    selectedImageFile = null;
    imageFileInput.value = '';
    imagePreviewBox.style.display = 'none';
    imageDropZone.style.display = 'block';
  });

  $('#analyzeImageBtn').addEventListener('click', async () => {
    if (!selectedImageFile) return;
    const errEl = $('#analyzeError');
    const loadingEl = $('#analyzeLoading');
    const resultsEl = $('#analyzeResults');
    hideError(errEl);
    resultsEl.classList.remove('show');

    const btn = $('#analyzeImageBtn');
    setBtnLoading(btn, true);
    loadingEl.style.display = 'flex';
    try {
      const formData = new FormData();
      formData.append('image', selectedImageFile);
      const data = await V.api('/api/analyze/image', { method: 'POST', body: formData, isForm: true });

      // Show what OCR actually read, before/alongside the analysis, per spec.
      if (data.ocr) {
        const ocrBox = document.createElement('div');
        ocrBox.className = 'ocr-preview';
        ocrBox.innerHTML = `<span class="lbl">Extracted text (OCR confidence ${data.ocr.confidence}%)</span>${V.escapeHtml(data.ocr.extracted_text)}`;
        imagePreviewBox.appendChild(ocrBox);
      }
      renderResult(resultsEl, data);
    } catch (err) {
      showError(errEl, err.message);
    } finally {
      setBtnLoading(btn, false, 'Extract text & analyze');
      loadingEl.style.display = 'none';
    }
  });

  // ---------------------------------------------------------------
  // Import page (CSV / TXT parsing — client-side, same as original prototype)
  // ---------------------------------------------------------------
  let datasetFormat = 'csv';
  let parsedRows = [];

  $$('.input-tab[data-format]').forEach((tab) => tab.addEventListener('click', () => {
    $$('.input-tab[data-format]').forEach((t) => t.classList.toggle('active', t === tab));
    datasetFormat = tab.dataset.format;
    const fileInput = $('#datasetFileInput');
    if (datasetFormat === 'csv') {
      fileInput.accept = '.csv,text/csv';
      $('#datasetDropTitle').textContent = 'Drop your CSV here';
      $('#datasetDropSub').textContent = 'Columns: claim · source · date';
    } else {
      fileInput.accept = '.txt,text/plain';
      $('#datasetDropTitle').textContent = 'Drop your text file here';
      $('#datasetDropSub').textContent = 'One claim per line';
    }
    resetDataset();
  }));

  function parseCSV(text) {
    return text.split(/\r?\n/).filter((l) => l.trim()).map((line) => {
      const parts = []; let current = ''; let quote = false;
      for (let i = 0; i < line.length; i++) {
        const c = line[i];
        if (c === '"') quote = !quote;
        else if (c === ',' && !quote) { parts.push(current.trim()); current = ''; }
        else current += c;
      }
      parts.push(current.trim());
      return parts;
    });
  }
  function extractClaimsFromCSV(rows) {
    if (!rows.length) return [];
    const headers = rows[0].map((h) => h.toLowerCase().trim());
    let ci = headers.findIndex((h) => ['claim', 'text', 'statement', 'content'].includes(h));
    if (ci === -1) ci = 0;
    const si = headers.findIndex((h) => ['source', 'platform'].includes(h));
    const di = headers.findIndex((h) => ['date', 'timestamp'].includes(h));
    return rows.slice(1).filter((r) => r[ci] && r[ci].trim()).map((r) => ({
      claim: r[ci].trim(),
      source: si >= 0 ? (r[si] || 'Unknown') : 'Unknown',
      date: di >= 0 ? (r[di] || null) : null,
    }));
  }

  const datasetDropZone = $('#datasetDropZone');
  const datasetFileInput = $('#datasetFileInput');
  function handleDatasetFile(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      if (datasetFormat === 'csv') {
        parsedRows = extractClaimsFromCSV(parseCSV(e.target.result));
      } else {
        parsedRows = e.target.result.split(/\r?\n/).map((x) => x.trim()).filter(Boolean)
          .map((claim) => ({ claim, source: 'Text file', date: null }));
      }
      showDatasetPreview(file);
    };
    reader.readAsText(file);
  }
  datasetFileInput.addEventListener('change', (e) => { if (e.target.files[0]) handleDatasetFile(e.target.files[0]); });
  ['dragenter', 'dragover'].forEach((ev) => datasetDropZone.addEventListener(ev, (e) => { e.preventDefault(); datasetDropZone.classList.add('drag'); }));
  ['dragleave', 'drop'].forEach((ev) => datasetDropZone.addEventListener(ev, (e) => { e.preventDefault(); datasetDropZone.classList.remove('drag'); }));
  datasetDropZone.addEventListener('drop', (e) => { const f = e.dataTransfer.files[0]; if (f) handleDatasetFile(f); });

  function showDatasetPreview(file) {
    $('#datasetPreviewBox').style.display = 'block';
    $('#datasetSummaryBox').style.display = 'none';
    $('#datasetFileName').textContent = `${file.name} · ${parsedRows.length} claims detected · ${(file.size / 1024).toFixed(1)} KB`;
    const tableEl = $('#datasetPreviewTable');
    if (!parsedRows.length) {
      tableEl.innerHTML = '<p class="result-meta on-paper">No claims found in this file.</p>';
      return;
    }
    tableEl.innerHTML = `<table class="data-table"><thead><tr><th>Claim</th><th>Source</th><th>Date</th></tr></thead><tbody>
      ${parsedRows.slice(0, 8).map((r) => `<tr><td class="on-paper">${V.escapeHtml(r.claim)}</td><td class="on-paper">${V.escapeHtml(r.source)}</td><td class="on-paper">${V.escapeHtml(r.date || '—')}</td></tr>`).join('')}
    </tbody></table>${parsedRows.length > 8 ? `<p class="result-meta on-paper" style="margin-top:8px;">+ ${parsedRows.length - 8} more rows</p>` : ''}`;
  }

  function resetDataset() {
    parsedRows = [];
    datasetFileInput.value = '';
    $('#datasetPreviewBox').style.display = 'none';
    $('#datasetSummaryBox').style.display = 'none';
    hideError($('#datasetError'));
  }
  $('#datasetClearBtn').addEventListener('click', resetDataset);

  $('#datasetAnalyzeBtn').addEventListener('click', async () => {
    if (!parsedRows.length) return;
    const errEl = $('#datasetError');
    const loadingEl = $('#datasetLoading');
    hideError(errEl);
    const btn = $('#datasetAnalyzeBtn');
    setBtnLoading(btn, true);
    loadingEl.style.display = 'flex';
    try {
      const data = await V.api('/api/analyze/batch', { method: 'POST', body: { items: parsedRows } });
      $('#dsCount').textContent = data.summary.claims_analyzed;
      $('#dsRelated').textContent = data.summary.related_count;
      $('#dsClusters').textContent = data.summary.clusters_found;
      const tableEl = $('#datasetResultsTable');
      tableEl.innerHTML = `<table class="data-table"><thead><tr><th>Claim</th><th>Similarity</th><th>Narrative</th><th>Status</th></tr></thead><tbody>
        ${data.results.map((r) => {
          const sim = r.best_match ? r.best_match.similarity : 0;
          const related = sim >= 30;
          return `<tr>
            <td class="on-paper"><strong>${V.escapeHtml(r.claim.text.slice(0, 80))}${r.claim.text.length > 80 ? '…' : ''}</strong><br><span class="result-meta on-paper" style="font-size:0.75rem;">${V.escapeHtml(r.claim.source_name)}</span></td>
            <td class="on-paper">${sim ? sim + '%' : '—'}</td>
            <td class="on-paper">${V.escapeHtml(r.claim.narrative_label || 'Unclustered')}</td>
            <td><span class="tag ${related ? 'tag-red' : 'tag-neutral'}">${related ? 'Related narrative' : 'Needs review'}</span></td>
          </tr>`;
        }).join('')}
      </tbody></table>`;
      $('#datasetSummaryBox').style.display = 'block';
      $('#datasetSummaryBox').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) {
      showError(errEl, err.message);
    } finally {
      setBtnLoading(btn, false, 'Analyze dataset');
      loadingEl.style.display = 'none';
    }
  });

  // ---------------------------------------------------------------
  // News tracker page
  // ---------------------------------------------------------------
  let newsGraphApi = null;
  const newsProgress = (percent, text) => {
    $('#newsProgressFill').style.width = `${percent}%`;
    $('#newsLoadingText').textContent = text;
  };

  function sentimentSummary(articles) {
    const vals = articles.map(a => a.sentiment && Number(a.sentiment.polarity)).filter(Number.isFinite);
    if (!vals.length) return 'sentiment unavailable';
    const avg = vals.reduce((a,b) => a+b, 0) / vals.length;
    if (avg > 0.15) return 'leaning positive';
    if (avg < -0.15) return 'leaning negative';
    return 'roughly neutral';
  }

  function renderNewsClusters(articles) {
    const groups = {};
    articles.forEach((a) => {
      const key = a.cluster_id || 'unclustered';
      (groups[key] ||= { label: a.narrative_label || 'Unclustered narrative', articles: [] }).articles.push(a);
    });
    const articleList = $('#articleList');
    articleList.innerHTML = Object.values(groups).map((group) => `
      <div class="news-cluster">
        <div class="news-cluster-head">
          <div><div class="news-cluster-title">${V.escapeHtml(group.label)}</div><div class="news-cluster-meta">${group.articles.length} article${group.articles.length === 1 ? '' : 's'} · ${V.escapeHtml(sentimentSummary(group.articles))}</div></div>
        </div>
        <div class="article-list">
          ${group.articles.map((a) => `
            <div class="article-row">
              <h4 class="on-paper">${a.url ? `<a href="${V.escapeHtml(a.url)}" target="_blank" rel="noopener">${V.escapeHtml(a.title)}</a>` : V.escapeHtml(a.title)}</h4>
              <p>${V.escapeHtml(a.description || '')}</p>
              <div class="a-meta">${V.escapeHtml(a.source_name)} · ${V.formatDate(a.published_at)}${a.sentiment && Number.isFinite(Number(a.sentiment.polarity)) ? ` · sentiment ${Number(a.sentiment.polarity).toFixed(2)}` : ''}</div>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('');
  }

  $('#newsTrackBtn').addEventListener('click', async () => {
    const query = $('#newsQueryInput').value.trim();
    const errEl = $('#newsError');
    const loadingEl = $('#newsLoading');
    const resultsEl = $('#newsResults');
    hideError(errEl); resultsEl.style.display = 'none';
    if (!query) { showError(errEl, 'Enter a topic to search for, e.g. "election fraud".'); return; }

    const btn = $('#newsTrackBtn');
    setBtnLoading(btn, true);
    loadingEl.style.display = 'flex';
    newsProgress(10, 'Fetching recent articles…');
    try {
      const data = await V.api('/api/news/track', { method: 'POST', body: { query } });
      const total = data.articles.length;
      newsProgress(55, `Analyzed ${total} of ${total} article${total === 1 ? '' : 's'}…`);

      const banner = $('#newsBanner');
      if (data.warning) {
        banner.textContent = data.warning;
        banner.className = `news-banner show ${data.is_live ? 'live' : 'offline'}`;
      } else {
        banner.textContent = `Showing live results from NewsAPI for "${data.query}".`;
        banner.className = 'news-banner show live';
      }

      newsProgress(78, 'Grouping articles into narrative clusters…');
      renderNewsClusters(data.articles);
      newsProgress(92, 'Building chronological evolution tree…');
      const graphContainer = $('#newsGraphContainer');
      newsGraphApi = createVerityGraph(graphContainer, {
        nodes: data.graph.nodes, edges: data.graph.edges,
        centerId: data.graph.nodes.length ? data.graph.nodes[data.graph.nodes.length - 1].id : null,
        onSelect: () => {},
      });
      newsProgress(100, `Done — ${total} article${total === 1 ? '' : 's'} analyzed.`);
      resultsEl.style.display = 'block';
    } catch (err) {
      showError(errEl, err.message);
    } finally {
      setBtnLoading(btn, false, 'Track topic');
      setTimeout(() => { loadingEl.style.display = 'none'; }, 250);
    }
  });
  $('#newsZoomIn').addEventListener('click', () => newsGraphApi && newsGraphApi.zoomIn());
  $('#newsZoomOut').addEventListener('click', () => newsGraphApi && newsGraphApi.zoomOut());
  $('#newsZoomReset').addEventListener('click', () => newsGraphApi && newsGraphApi.reset());

  // ---------------------------------------------------------------
  // History page
  // ---------------------------------------------------------------
  async function loadHistory() {
    const listEl = $('#historyList');
    $('#historyResults').classList.remove('show');
    listEl.innerHTML = '<div class="loading-row"><span class="spinner"></span> Loading history…</div>';
    try {
      const data = await V.api('/api/history');
      if (!data.history.length) {
        listEl.innerHTML = `<div class="doc state-box on-paper"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg><p>No searches yet — analyze a claim, import a dataset, or track a news topic to see it here.</p></div>`;
        return;
      }
      listEl.innerHTML = data.history.map((h) => `
        <div class="history-row" data-claim-id="${h.result_claim_id || ''}">
          <div>
            <div class="history-query">${V.escapeHtml(h.query.slice(0, 90))}</div>
            <div class="history-meta">${h.query_type} · ${V.timeAgo(h.created_at)}</div>
          </div>
          <span class="tag ${({Supported:'tag-green',Contradicted:'tag-red',Mixed:'tag-amber'}[h.claim && h.claim.verification && h.claim.verification.status] || 'tag-neutral')}">${V.escapeHtml(h.claim && h.claim.verification && h.claim.verification.status || h.query_type)}</span>
        </div>
      `).join('');
      $$('.history-row', listEl).forEach((row) => row.addEventListener('click', () => openHistoryEntry(row.dataset.claimId)));
    } catch (err) {
      listEl.innerHTML = `<div class="inline-error show">${V.escapeHtml(err.message)}</div>`;
    }
  }

  async function openHistoryEntry(claimId) {
    const resultsEl = $('#historyResults');
    if (!claimId) {
      resultsEl.innerHTML = '<div class="doc on-paper"><p>This search did not resolve to a single claim (e.g. a dataset import). Check the Import page summary for those results.</p></div>';
      resultsEl.classList.add('show');
      return;
    }
    resultsEl.innerHTML = '<div class="loading-row"><span class="spinner"></span> Loading claim…</div>';
    resultsEl.classList.add('show');
    try {
      const claimData = await V.api(`/api/claims/${claimId}`);
      const evoData = await V.api(`/api/evolution/${claimId}`);
      renderResult(resultsEl, {
        claim: claimData.claim,
        graph: claimData.graph,
        timeline: evoData.timeline,
        best_match: null,
      });
      resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) {
      resultsEl.innerHTML = `<div class="inline-error show">${V.escapeHtml(err.message)}</div>`;
    }
  }

  // ---------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------
  initUser();
  loadOverview();
})();
