(() => {
  // Dashboard Elements
  const qInput = document.getElementById('headerSearchInput');
  const resultsEl = document.getElementById('results');
  const resultCountBadge = document.getElementById('resultCountBadge');
  const rescanBtn = document.getElementById('rescanBtn');
  const scanStatus = document.getElementById('scanStatus');
  const sourcesInput = document.getElementById('sourcesInput');
  const saveSourcesBtn = document.getElementById('saveSourcesBtn');
  
  // Modal Elements
  const modal = document.getElementById('modal');
  const modalClose = document.getElementById('modalClose');
  const modalImg = document.getElementById('modalImg');
  const modalFilename = document.getElementById('modalFilename');
  const modalFilepath = document.getElementById('modalFilepath');
  const modalDate = document.getElementById('modalDate');
  const modalEvent = document.getElementById('modalEvent');
  const modalSize = document.getElementById('modalSize');
  const modalPath = document.getElementById('modalPath');
  const downloadBtn = document.getElementById('downloadBtn');
  const openBtn = document.getElementById('openBtn');
  const modalPrev = document.getElementById('modalPrev');
  const modalNext = document.getElementById('modalNext');
  const modalCounter = document.getElementById('modalCounter');

  // P0 + P1 Elements
  const statusIndicator = document.getElementById('statusIndicator');
  const scanProgress = document.getElementById('scanProgress');
  const progressFill = document.getElementById('progressFill');
  const progressText = document.getElementById('progressText');
  const lastScanEl = document.getElementById('lastScan');
  const toastContainer = document.getElementById('toastContainer');

  // Settings Modal Elements
  const settingsModal = document.getElementById('settingsModal');
  const settingsClose = document.getElementById('settingsClose');
  const settingsOverlay = settingsModal?.querySelector('.settings-overlay');
  
  // Find Settings nav item by text content
  const settingsNav = Array.from(document.querySelectorAll('.nav-item')).find(item => 
    item.textContent.trim().includes('Settings')
  );

  // Sorting & View Elements
  const sortDropdown = document.getElementById('sortDropdown');
  const viewGridBtn = document.getElementById('viewGrid');
  const viewListBtn = document.getElementById('viewList');

  // Create Search Preview Dynamically
  const searchPreview = document.createElement('div');
  searchPreview.id = 'searchPreview';
  searchPreview.className = 'search-preview';
  searchPreview.innerHTML = `
    <div class="search-preview-count" id="previewCount">0 results</div>
    <div class="search-preview-hint">Press Enter to search</div>
  `;
  // Append to header-search container
  if (qInput) {
    qInput.parentElement.appendChild(searchPreview);
  }
  const previewCount = searchPreview.querySelector('#previewCount');

  // ========== State ==========
  let lastResults = [];
  let currentModalIndex = -1;
  let activeFileType = '';     // '' = all, 'image', 'video', 'psd'
  let activeSort = 'date_desc';
  let viewMode = 'grid';       // 'grid' or 'list'
  const STORAGE_KEY = 'vg_recent_results';

  // ========== Persistence ==========
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

  // ========== Helpers ==========
  function escHtml(s) {
    return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function formatFileSize(bytes) {
    if (!bytes) return '-';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
  }

  function getBadgeClass(fileType, ext) {
    if (fileType === 'video') return 'badge-video';
    if (fileType === 'psd') return 'badge-psd';
    if (['JPG', 'JPEG', 'PNG'].includes(ext)) return 'badge-primary';
    return 'badge-dark';
  }

  function getTypeIcon(fileType) {
    if (fileType === 'video') return 'videocam';
    if (fileType === 'psd') return 'palette';
    return '';
  }

  // ========== Search ==========
  async function doSearch() {
    const q = qInput ? qInput.value.trim() : '';
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (activeFileType) params.set('file_type', activeFileType);
    if (activeSort) params.set('sort', activeSort);
    
    // Show skeleton loading state
    showSkeletonCards();
    searchPreview.classList.remove('visible');
    
    try {
      const r = await fetch(`/search?${params.toString()}`);
      const data = await r.json();
      lastResults = data.results || [];
      saveRecent(q, lastResults);
      renderCurrentView(lastResults);
    } catch (e) {
      showEmptyState('Search failed. Please try again.');
    }
  }

  function showSkeletonCards() {
    const skeletons = Array(8).fill(null).map(() => `
      <div class="card skeleton-card" style="height: 300px;">
        <div class="skeleton-img" style="height: 100%; width: 100%; background: rgba(255,255,255,0.05); animation: pulse 1.5s infinite;"></div>
      </div>
    `).join('');
    resultsEl.innerHTML = skeletons;
  }

  function showEmptyState(message = 'No files found') {
    resultsEl.innerHTML = `
      <div class="empty-state" style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-secondary);">
        <span class="material-symbols-outlined" style="font-size: 48px; color: var(--text-secondary); opacity: 0.5;">image_not_supported</span>
        <div class="empty-title" style="margin-top: 16px; font-weight: 700;">${message}</div>
        <div class="empty-text" style="font-size: 12px; margin-top: 8px;">Try adjusting your search or filters</div>
      </div>
    `;
    if (resultCountBadge) resultCountBadge.textContent = '0 Results';
  }

  // ========== Render: decides grid vs list ==========
  function renderCurrentView(items) {
    if (viewMode === 'list') {
      renderListView(items);
    } else {
      renderGridView(items);
    }
  }

  // ========== Grid View ==========
  function renderGridView(items) {
    if (resultCountBadge) {
      resultCountBadge.textContent = `${items.length} Result${items.length !== 1 ? 's' : ''}`;
    }

    if (!items.length) { 
      showEmptyState(); 
      return; 
    }

    // Make sure results container is in grid mode
    resultsEl.classList.remove('list-view');
    resultsEl.classList.add('grid');
    
    const html = items.map((it, index) => {
      const fileExt = it.filename ? it.filename.split('.').pop().toUpperCase() : 'FILE';
      const fileType = it.file_type || 'image';
      const badgeClass = getBadgeClass(fileType, fileExt);
      const typeIcon = getTypeIcon(fileType);
      
      return `
        <div class="card" data-id="${it.id}" data-index="${index}" tabindex="0">
          <div class="card-image-wrapper">
            <img 
              src="${it.thumb}" 
              alt="${escHtml(it.filename)}"
              loading="lazy"
              onload="this.style.opacity='1'"
              onerror="this.style.opacity='0.5'"
            >
            ${typeIcon ? `<div class="card-type-icon"><span class="material-symbols-outlined">${typeIcon}</span></div>` : ''}
            <div class="card-overlay">
              <button class="card-action-btn secondary" title="Copy Filename" onclick="event.stopPropagation(); copyToClipboard('${escHtml(it.filename)}')">
                <span class="material-symbols-outlined">content_copy</span>
              </button>
              <button class="card-action-btn secondary" title="Open Location" onclick="event.stopPropagation(); openFileLocation('${it.id}')">
                <span class="material-symbols-outlined">folder_open</span>
              </button>
              <button class="card-action-btn primary" title="View Details" onclick="event.stopPropagation(); openModal(${index})">
                <span class="material-symbols-outlined">visibility</span>
              </button>
            </div>
            <div class="card-badges">
              <span class="card-badge ${badgeClass}">${fileExt}</span>
            </div>
          </div>
          <div class="card-info">
            <div class="card-title" title="${escHtml(it.filename)}">${escHtml(it.filename)}</div>
            <div class="card-meta">
              <span>${escHtml(it.date || '')}</span>
              <span>${it.size ? formatFileSize(it.size) : ''}</span>
            </div>
          </div>
        </div>
      `;
    }).join('');
    
    resultsEl.innerHTML = html;
    bindCardEvents();
  }

  // ========== List View ==========
  function renderListView(items) {
    if (resultCountBadge) {
      resultCountBadge.textContent = `${items.length} Result${items.length !== 1 ? 's' : ''}`;
    }

    if (!items.length) { 
      showEmptyState(); 
      return; 
    }

    // Switch to list mode
    resultsEl.classList.remove('grid');
    resultsEl.classList.add('list-view');
    
    const html = items.map((it, index) => {
      const fileExt = it.filename ? it.filename.split('.').pop().toUpperCase() : 'FILE';
      const fileType = it.file_type || 'image';
      const badgeClass = getBadgeClass(fileType, fileExt);
      const typeIcon = getTypeIcon(fileType);
      
      return `
        <div class="list-row" data-id="${it.id}" data-index="${index}" tabindex="0">
          <div class="list-row-thumb">
            <img src="${it.thumb}" alt="${escHtml(it.filename)}" loading="lazy" onload="this.style.opacity='1'" onerror="this.style.opacity='0.5'">
            ${typeIcon ? `<span class="list-type-icon material-symbols-outlined">${typeIcon}</span>` : ''}
          </div>
          <div class="list-row-info">
            <div class="list-row-name" title="${escHtml(it.filename)}">${escHtml(it.filename)}</div>
            <div class="list-row-folder">${escHtml(it.folder || '')}</div>
          </div>
          <div class="list-row-meta">
            <span class="card-badge ${badgeClass}">${fileExt}</span>
          </div>
          <div class="list-row-meta">${escHtml(it.date || '-')}</div>
          <div class="list-row-meta">${it.size ? formatFileSize(it.size) : '-'}</div>
          <div class="list-row-actions">
            <button class="card-action-btn secondary" title="Copy Filename" onclick="event.stopPropagation(); copyToClipboard('${escHtml(it.filename)}')">
              <span class="material-symbols-outlined">content_copy</span>
            </button>
            <button class="card-action-btn secondary" title="Open Location" onclick="event.stopPropagation(); openFileLocation('${it.id}')">
              <span class="material-symbols-outlined">folder_open</span>
            </button>
          </div>
        </div>
      `;
    }).join('');
    
    resultsEl.innerHTML = html;
    bindCardEvents();
  }

  function bindCardEvents() {
    resultsEl.querySelectorAll('.card, .list-row').forEach(el => {
      el.addEventListener('click', () => openModal(el.getAttribute('data-index')));
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') openModal(el.getAttribute('data-index'));
      });
    });
  }

  // ========== Card Actions ==========
  window.openFileLocation = async (id) => {
    try {
      await fetch('/open', { 
        method: 'POST', 
        headers: {'Content-Type': 'application/json'}, 
        body: JSON.stringify({ id }) 
      });
      showToast('Opening file location...', 'success');
    } catch {
      showToast('Failed to open location', 'error');
    }
  };

  window.copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      showToast('Filename copied!', 'success');
    });
  };

  window.renderResults = renderCurrentView;

  // ========== Modal ==========
  function openModal(index) {
    currentModalIndex = parseInt(index);
    updateModalContent();
    modal.classList.remove('hidden');
  }

  function updateModalContent() {
    const it = lastResults[currentModalIndex];
    if (!it) return;
    
    modalImg.src = `/thumbnail/${it.id}`;
    modalFilename.textContent = it.filename || 'Unknown';
    modalFilepath.textContent = it.folder || '';
    modalDate.textContent = it.date || '-';
    modalEvent.textContent = it.folder ? it.folder.split('\\').pop() : '-';
    modalSize.textContent = it.size ? formatFileSize(it.size) : '-';
    modalPath.textContent = it.full_path || it.folder || '-';
    downloadBtn.href = `/download/${it.id}`;
    
    if(modalCounter) modalCounter.textContent = `${currentModalIndex + 1} of ${lastResults.length}`;
    
    modalPrev.classList.toggle('hidden', currentModalIndex === 0);
    modalNext.classList.toggle('hidden', currentModalIndex === lastResults.length - 1);
    
    openBtn.onclick = () => openFileLocation(it.id);
  }

  function closeModal() { 
    modal.classList.add('hidden'); 
    modalImg.src=''; 
    currentModalIndex = -1;
  }

  function navigateModal(direction) {
    const newIndex = currentModalIndex + direction;
    if (newIndex >= 0 && newIndex < lastResults.length) {
      currentModalIndex = newIndex;
      updateModalContent();
    }
  }

  // ========== Scan ==========
  async function triggerRescan() {
    try {
      scanStatus.textContent = 'Starting...';
      await fetch('/rescan', { method: 'POST' });
      pollScanEnhanced();
    } catch {
      scanStatus.textContent = 'Failed';
    }
  }

  let lastScanTime = null;
  function updateLastScanTime() {
    if (!lastScanTime || !lastScanEl) return;
    const now = Date.now();
    const diff = now - lastScanTime;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    
    if (hours > 0) lastScanEl.textContent = `Last scan: ${hours}h ago`;
    else if (minutes > 0) lastScanEl.textContent = `Last scan: ${minutes}m ago`;
    else lastScanEl.textContent = `Last scan: just now`;
  }
  setInterval(updateLastScanTime, 60000);

  async function pollScanEnhanced() {
    const tick = async () => {
      try {
        const r = await fetch('/rescan/status');
        const d = await r.json();
        const s = d.scan || {};
        
        if (s.running) {
          if(statusIndicator) statusIndicator.classList.add('active');
          if(scanProgress) scanProgress.classList.add('visible');
          
          const scanned = s.scanned || 0;
          const found = s.found || 0;
          const progress = scanned > 0 ? Math.min((scanned / 10000) * 100, 100) : 0;
          
          if(progressFill) progressFill.style.width = `${progress}%`;
          if(progressText) progressText.textContent = `Scanned: ${scanned} | Found: ${found}`;
          if(scanStatus) scanStatus.textContent = `Scanning...`;
          
          setTimeout(tick, 1500);
        } else {
          if(statusIndicator) statusIndicator.classList.remove('active');
          if(scanProgress) scanProgress.classList.remove('visible');
          if(scanStatus) scanStatus.textContent = s.message || 'Idle';
          
          if (s.message && s.message !== 'Idle') {
            lastScanTime = Date.now();
            updateLastScanTime();
          }
        }
      } catch {
        if(scanStatus) scanStatus.textContent = 'Status unavailable';
      }
    };
    tick();
  }

  // ========== Toast ==========
  function showToast(message, type = 'info', duration = 3000) {
    if(!toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
    toast.innerHTML = `<div class="toast-icon">${icons[type] || icons.info}</div><div class="toast-message">${message}</div>`;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.animation = 'slideInRight 0.3s ease reverse';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  // ========== Settings ==========
  async function saveSources() {
    try {
      const raw = sourcesInput.value.trim();
      const parts = raw.split(';').map(s => s.trim()).filter(Boolean);
      await fetch('/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_dirs: parts, persist: true })
      });
      showToast('Sources saved successfully!', 'success');
      await triggerRescan();
    } catch {
      showToast('Failed to save sources', 'error');
    }
  }

  // ========== Event Listeners ==========
  if(qInput) qInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') doSearch(); });
  if(rescanBtn) rescanBtn.addEventListener('click', triggerRescan);
  if(modalClose) modalClose.addEventListener('click', closeModal);
  if(modal) modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });
  if(modalPrev) modalPrev.addEventListener('click', () => navigateModal(-1));
  if(modalNext) modalNext.addEventListener('click', () => navigateModal(1));
  if(saveSourcesBtn) {
    saveSourcesBtn.removeEventListener('click', saveSources);
    saveSourcesBtn.addEventListener('click', saveSources);
  }

  // Settings Modal Handlers
  function openSettings() {
    if(settingsModal) settingsModal.classList.remove('hidden');
  }

  function closeSettings() {
    if(settingsModal) settingsModal.classList.add('hidden');
  }

  if(settingsNav) {
    settingsNav.addEventListener('click', (e) => {
      e.preventDefault();
      openSettings();
    });
  }

  if(settingsClose) settingsClose.addEventListener('click', closeSettings);
  if(settingsOverlay) settingsOverlay.addEventListener('click', closeSettings);

  // ========== Filter Chips ==========
  document.querySelectorAll('.filter-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeFileType = chip.getAttribute('data-filter') || '';
      doSearch();
    });
  });

  const clearFiltersBtn = document.querySelector('.clear-filters');
  if(clearFiltersBtn) {
    clearFiltersBtn.addEventListener('click', () => {
      document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
      const firstChip = document.querySelector('.filter-chip');
      if(firstChip) firstChip.classList.add('active');
      activeFileType = '';
      doSearch();
    });
  }

  // ========== Sort Dropdown ==========
  if(sortDropdown) {
    sortDropdown.addEventListener('change', () => {
      activeSort = sortDropdown.value;
      doSearch();
    });
  }

  // ========== Grid / List View Toggle ==========
  if(viewGridBtn) {
    viewGridBtn.addEventListener('click', () => {
      viewMode = 'grid';
      viewGridBtn.classList.add('active');
      viewListBtn.classList.remove('active');
      renderCurrentView(lastResults);
    });
  }

  if(viewListBtn) {
    viewListBtn.addEventListener('click', () => {
      viewMode = 'list';
      viewListBtn.classList.add('active');
      viewGridBtn.classList.remove('active');
      renderCurrentView(lastResults);
    });
  }

  // ========== Debounce ==========
  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func(...args), wait);
    };
  }

  // ========== Search Preview ==========
  const showSearchPreview = debounce(async (query) => {
    if (query.length < 2) {
      searchPreview.classList.remove('visible');
      return;
    }
    try {
      const r = await fetch(`/search?q=${encodeURIComponent(query)}`);
      const data = await r.json();
      const count = (data.results || []).length;
      if(previewCount) previewCount.textContent = `${count} result${count !== 1 ? 's' : ''} found`;
      searchPreview.classList.add('visible');
    } catch (e) { searchPreview.classList.remove('visible'); }
  }, 500);

  if(qInput) {
    qInput.addEventListener('input', () => {
      const query = qInput.value.trim();
      if (query) showSearchPreview(query);
      else searchPreview.classList.remove('visible');
    });
  }

  document.addEventListener('click', (e) => {
    if (qInput && !qInput.contains(e.target) && !searchPreview.contains(e.target)) {
      searchPreview.classList.remove('visible');
    }
  });

  // ========== Keyboard Navigation ==========
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) { closeModal(); return; }
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      if(qInput) { qInput.focus(); qInput.select(); }
      return;
    }
    if (!modal.classList.contains('hidden')) {
      if (e.key === 'ArrowLeft') navigateModal(-1);
      else if (e.key === 'ArrowRight') navigateModal(1);
      return;
    }
  });

  // ========== Init ==========
  pollScanEnhanced();
  (async () => {
    try {
      const r = await fetch('/config');
      const d = await r.json();
      if (Array.isArray(d.source_dirs) && sourcesInput) sourcesInput.value = d.source_dirs.join('; ');
    } catch {}
  })();

  const recent = loadRecent();
  if (recent && Array.isArray(recent.results)) {
    lastResults = recent.results;
    if(qInput && recent.query) qInput.value = recent.query;
    renderCurrentView(lastResults);
  }
})();
