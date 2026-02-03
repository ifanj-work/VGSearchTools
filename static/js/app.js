document.addEventListener("DOMContentLoaded", () => {
  const qInput = document.getElementById("query");
  const searchBtn = document.getElementById("searchBtn");
  const resultsEl = document.getElementById("results");
  const resultsTitle = document.getElementById("resultsTitle");
  const rescanBtn = document.getElementById("rescanBtn");
  const scanStatus = document.getElementById("scanStatus");
  const sourcesInput = document.getElementById("sourcesInput");
  const saveSourcesBtn = document.getElementById("saveSourcesBtn");

  const modal = document.getElementById("modal");
  const modalClose = document.getElementById("modalClose");
  const modalImg = document.getElementById("modalImg");
  const modalFilename = document.getElementById("modalFilename");
  const modalPathSimple = document.getElementById("modalPathSimple");
  const modalDate = document.getElementById("modalDate");
  const modalEvent = document.getElementById("modalEvent");
  const modalSize = document.getElementById("modalSize");
  const modalFullPath = document.getElementById("modalFullPath");
  const openBtn = document.getElementById("openBtn");

  // Safety check
  if (!modal || !modalFilename) {
    console.error("Modal elements missing!", { modal });
  }

  function formatSize(bytes) {
    if (!bytes) return "Unknown";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function formatDate(isoDate) {
    if (!isoDate) return "Unknown";
    try {
      const d = new Date(isoDate);
      return d.toLocaleDateString("id-ID", { year: "numeric", month: "long" });
    } catch {
      return isoDate;
    }
  }

  function updateModalContent() {
    const it = lastResults[currentIndex];
    if (!it) return;

    if (modalImg) modalImg.src = `/thumbnail/${it.id}`;
    if (modalFilename) modalFilename.textContent = it.filename;

    // Logic for fields
    if (modalPathSimple) modalPathSimple.textContent = it.path; // Subheader under filename
    if (modalDate) modalDate.textContent = formatDate(it.date);
    if (modalEvent)
      modalEvent.textContent = it.folder
        ? it.folder.split(/[\\/]/).pop()
        : "Unknown"; // Just folder name
    if (modalSize) modalSize.textContent = formatSize(it.size);
    if (modalFullPath) modalFullPath.textContent = it.path;
  }

  // --- RESTORED FUNCTIONS ---
  let lastResults = [];
  let currentIndex = -1;
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
    } catch { }
  }

  function escHtml(s) {
    return s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
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
    const idx = lastResults.findIndex(x => x.id === id);
    if (idx === -1) return;

    currentIndex = idx;
    try {
      updateModalContent();
      modal.classList.remove('hidden');
    } catch (e) {
      console.error('Error opening modal:', e);
    }
    
    // Bind open button dynamically if needed, or static bind is fine but we need to ensure it links to current item
    if (openBtn) {
       openBtn.onclick = async () => {
        const it = lastResults[currentIndex];
        if (!it) return;
        try {
          await fetch('/open', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: it.id }) });
        } catch { }
      };
    }
  }

  function nextImage(e) {
    if (e) e.stopPropagation();
    if (currentIndex < lastResults.length - 1) {
      currentIndex++;
      updateModalContent();
    }
  }

  function prevImage(e) {
    if (e) e.stopPropagation();
    if (currentIndex > 0) {
      currentIndex--;
      updateModalContent();
    }
  }

  const prevBtn = document.getElementById("prevBtn");
  const nextBtn = document.getElementById("nextBtn");

  if (prevBtn) prevBtn.addEventListener("click", prevImage);
  if (nextBtn) nextBtn.addEventListener("click", nextImage);

  function closeModal() {
    if (modal) modal.classList.add("hidden");
    if (modalImg) modalImg.src = "";
    currentIndex = -1;
  }

  async function triggerRescan() {
    try {
      if (scanStatus) scanStatus.textContent = "Starting rescan…";
      await fetch("/rescan", { method: "POST" });
      pollScan();
    } catch {
      if (scanStatus) scanStatus.textContent = "Rescan failed";
    }
  }

  async function pollScan() {
    const tick = async () => {
      try {
        const r = await fetch("/rescan/status");
        const d = await r.json();
        const s = d.scan || {};
        const msg = s.running
          ? `Scanning… scanned: ${s.scanned || 0}, found: ${s.found || 0}`
          : s.message || "Idle";
        if (scanStatus) scanStatus.textContent = msg;
        if (s.running) setTimeout(tick, 1500);
      } catch {
        if (scanStatus) scanStatus.textContent = "Scan status unavailable";
      }
    };
    tick();
  }

  if (searchBtn) searchBtn.addEventListener("click", doSearch);
  if (qInput)
    qInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") doSearch();
    });
  if (rescanBtn) rescanBtn.addEventListener("click", triggerRescan);
  if (modalClose) modalClose.addEventListener("click", closeModal);
  if (modal)
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeModal();
    });

  // Keyboard navigation
  document.addEventListener("keydown", (e) => {
    if (modal && modal.classList.contains("hidden")) return;
    if (e.key === "ArrowLeft") prevImage();
    if (e.key === "ArrowRight") nextImage();
    if (e.key === "Escape") closeModal();
  });

  // Optional: auto-poll scan state on load
  pollScan();

  // Load current config and populate sources field
  (async () => {
    try {
      const r = await fetch("/config");
      const d = await r.json();
      if (sourcesInput && Array.isArray(d.source_dirs)) {
        sourcesInput.value = d.source_dirs.join("; ");
      }
    } catch {}
  })();

  // Load recent results on first screen
  const recent = loadRecent();
  if (recent && Array.isArray(recent.results)) {
    lastResults = recent.results;
    const title = recent.query
      ? `Recent search: "${recent.query}"`
      : "Recent searches";
    renderResults(lastResults, title);
  }

  async function saveSources() {
    try {
      const raw = sourcesInput.value.trim();
      const parts = raw
        .split(";")
        .map((s) => s.trim())
        .filter(Boolean);
      await fetch("/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_dirs: parts, persist: true }),
      });
      // Trigger rescan with the new sources
      await triggerRescan();
    } catch {
      if (scanStatus) scanStatus.textContent = "Save sources failed";
    }
  }
  if (saveSourcesBtn) saveSourcesBtn.addEventListener("click", saveSources);
});
