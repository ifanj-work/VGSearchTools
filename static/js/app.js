(() => {
  const qInput = document.getElementById('query');
  const searchBtn = document.getElementById('searchBtn');
  const resultsEl = document.getElementById('results');
  const resultsTitle = document.getElementById('resultsTitle');
  const rescanBtn = document.getElementById('rescanBtn');
  const scanStatus = document.getElementById('scanStatus');
  const sourcesInput = document.getElementById('sourcesInput');
  const saveSourcesBtn = document.getElementById('saveSourcesBtn');

  const modal = document.getElementById('modal');
  const modalClose = document.getElementById('modalClose');
  const modalImg = document.getElementById('modalImg');
  const modalMeta = document.getElementById('modalMeta');
  const downloadBtn = document.getElementById('downloadBtn');
  const openBtn = document.getElementById('openBtn');

  let lastResults = [];
  const STORAGE_KEY = 'vg_recent_results';

  function loadRecent() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const data = JSON.parse(raw);
      if (!data || !Array.isArray(data.results)) return null;
      return data;
    } catch {
      return null;
    }
  }

  function saveRecent(query, results) {
    try {
      const payload = { query, results, ts: Date.now() };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch {}
  }

  function escHtml(s) {
    return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  async function doSearch() {
    const q = qInput.value.trim();
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    resultsEl.innerHTML = '<div class="muted">Searching…</div>';
    try {
      const r = await fetch(`/search?${params.toString()}`);
      const data = await r.json();
      lastResults = data.results || [];
      saveRecent(q, lastResults);
      renderResults(lastResults, q ? `Results for "${q}"` : 'Recent searches');
    } catch (e) {
      resultsEl.innerHTML = '<div class="muted">Search failed.</div>';
    }
  }

  function renderResults(items, title) {
    if (resultsTitle) {
      resultsTitle.textContent = title || 'Recent searches';
    }
    if (!items.length) { resultsEl.innerHTML = '<div class="muted">No results.</div>'; return; }
    const html = items.map(it => `
      <div class="card" data-id="${it.id}">
        <img src="${it.thumb}" alt="${escHtml(it.filename)}">
        <div class="info">
          <div class="name" title="${escHtml(it.filename)}">${escHtml(it.filename)}</div>
          <div class="meta" title="${escHtml(it.folder)}">${escHtml(it.folder)}</div>
          <div class="meta">${escHtml(it.date || '')}</div>
        </div>
      </div>
    `).join('');
    resultsEl.innerHTML = html;
    resultsEl.querySelectorAll('.card').forEach(card => {
      card.addEventListener('click', () => openModal(card.getAttribute('data-id')));
    });
  }

  function openModal(id) {
    const it = lastResults.find(x => x.id === id);
    if (!it) return;
    modalImg.src = `/thumbnail/${id}`;
    modalMeta.textContent = `${it.filename} — ${it.folder} — ${it.date || ''}`;
    downloadBtn.href = `/download/${id}`;
    modal.classList.remove('hidden');
    openBtn.onclick = async () => {
      try {
        await fetch('/open', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ id }) });
      } catch {}
    };
  }

  function closeModal() { modal.classList.add('hidden'); modalImg.src=''; }

  async function triggerRescan() {
    try {
      scanStatus.textContent = 'Starting rescan…';
      await fetch('/rescan', { method: 'POST' });
      pollScan();
    } catch {
      scanStatus.textContent = 'Rescan failed';
    }
  }

  async function pollScan() {
    const tick = async () => {
      try {
        const r = await fetch('/rescan/status');
        const d = await r.json();
        const s = d.scan || {};
        const msg = s.running ? `Scanning… scanned: ${s.scanned || 0}, found: ${s.found || 0}` : (s.message || 'Idle');
        scanStatus.textContent = msg;
        if (s.running) setTimeout(tick, 1500);
      } catch {
        scanStatus.textContent = 'Scan status unavailable';
      }
    };
    tick();
  }

  searchBtn.addEventListener('click', doSearch);
  qInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') doSearch(); });
  rescanBtn.addEventListener('click', triggerRescan);
  modalClose.addEventListener('click', closeModal);
  modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

  // Optional: auto-poll scan state on load
  pollScan();

  // Load current config and populate sources field
  (async () => {
    try {
      const r = await fetch('/config');
      const d = await r.json();
      if (Array.isArray(d.source_dirs)) {
        sourcesInput.value = d.source_dirs.join('; ');
      }
      // Populate year options from catalog count if provided (optional future enhancement)
    } catch {}
  })();

  // Load recent results on first screen
  const recent = loadRecent();
  if (recent && Array.isArray(recent.results)) {
    lastResults = recent.results;
    const title = recent.query ? `Recent search: "${recent.query}"` : 'Recent searches';
    renderResults(lastResults, title);
  }

  async function saveSources() {
    try {
      const raw = sourcesInput.value.trim();
      const parts = raw.split(';').map(s => s.trim()).filter(Boolean);
      await fetch('/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_dirs: parts, persist: true })
      });
      // Trigger rescan with the new sources
      await triggerRescan();
    } catch {
      scanStatus.textContent = 'Save sources failed';
    }
  }
  saveSourcesBtn.addEventListener('click', saveSources);
})();
