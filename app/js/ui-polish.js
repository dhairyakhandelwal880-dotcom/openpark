/* OpenPark UI & UX Enhancements Module */
(() => {
  const UIPolish = {
    getCtx() {
      return window.__openpark || {};
    },
    toast(msg, type = 'info', ms = 2200) {
      const ctx = this.getCtx();
      if (ctx.ParkingApp && typeof ctx.ParkingApp.showToast === 'function') {
        ctx.ParkingApp.showToast(msg, type, ms);
      }
    },
    isTyping(target) {
      if (!target) return false;
      const tag = (target.tagName || '').toLowerCase();
      return tag === 'input' || tag === 'textarea' || tag === 'select' || target.isContentEditable;
    },
    copyText(text, label = 'Copied') {
      if (!text) return;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(String(text)).then(() => this.toast(`📋 ${label}`, 'success', 1800)).catch(() => {});
      }
    },
    modules: [],
    register(name, initFn) {
      this.modules.push({ name, initFn });
    },
    boot() {
      this.modules.forEach((m) => {
        try {
          m.initFn(this);
        } catch (err) {
          console.warn('[UIPolish]', m.name, err);
        }
      });
    }
  };

  window.OpenParkUIPolish = UIPolish;

  UIPolish.register('escapeDismiss', (up) => {
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      const scModal = document.getElementById('modal-shortcuts');
      if (scModal && scModal.classList.contains('open')) {
        scModal.classList.remove('open');
        return;
      }
      for (const id of ['modal-receipt', 'modal-report', 'modal-traccar']) {
        const el = document.getElementById(id);
        if (el && el.classList.contains('open')) {
          el.classList.remove('open');
          return;
        }
      }
      const drawer = document.getElementById('parking-drawer');
      if (drawer && drawer.classList.contains('open')) {
        drawer.classList.remove('open');
        return;
      }
      const welcome = document.getElementById('welcome-overlay');
      if (welcome && !welcome.classList.contains('hidden')) {
        const ctx = up.getCtx();
        if (ctx.WelcomeController && typeof ctx.WelcomeController.hide === 'function') {
          ctx.WelcomeController.hide();
        }
      }
    });
  });

  UIPolish.register('modalBackdropDismiss', () => {
    ['modal-receipt', 'modal-report', 'modal-traccar'].forEach((id) => {
      const backdrop = document.getElementById(id);
      if (!backdrop) return;
      backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) backdrop.classList.remove('open');
      });
    });
  });

  UIPolish.register('slashSearchShortcut', (up) => {
    document.addEventListener('keydown', (e) => {
      if (e.key !== '/' || up.isTyping(e.target) || e.metaKey || e.ctrlKey) return;
      e.preventDefault();
      const welcome = document.getElementById('welcome-overlay');
      const targetId = (welcome && !welcome.classList.contains('hidden')) ? 'welcome-search-input' : 'search-input';
      const el = document.getElementById(targetId);
      if (el) {
        el.focus();
        el.select();
      }
    });
  });

  UIPolish.register('themeShortcut', (up) => {
    document.addEventListener('keydown', (e) => {
      if (e.key.toLowerCase() !== 't' || up.isTyping(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
      const btn = document.getElementById('btn-theme');
      if (btn) btn.click();
    });
  });

  UIPolish.register('aiScanShortcut', (up) => {
    document.addEventListener('keydown', (e) => {
      if (e.key.toLowerCase() !== 'a' || up.isTyping(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
      const welcome = document.getElementById('welcome-overlay');
      if (welcome && !welcome.classList.contains('hidden')) return;
      const ctx = up.getCtx();
      if (ctx.AIScannerEngine && typeof ctx.AIScannerEngine.scanCurrentArea === 'function') {
        ctx.AIScannerEngine.scanCurrentArea();
      }
    });
  });

  UIPolish.register('nearMeShortcut', (up) => {
    document.addEventListener('keydown', (e) => {
      if (e.key.toLowerCase() !== 'g' || up.isTyping(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
      const nearBtn = document.getElementById('btn-welcome-nearby') || document.getElementById('btn-my-location');
      if (nearBtn) nearBtn.click();
    });
  });

  UIPolish.register('shortcutsHelpModal', (up) => {
    const createModal = () => {
      if (document.getElementById('modal-shortcuts')) return document.getElementById('modal-shortcuts');
      const modal = document.createElement('div');
      modal.className = 'modal-backdrop';
      modal.id = 'modal-shortcuts';
      modal.setAttribute('role', 'dialog');
      modal.setAttribute('aria-modal', 'true');
      modal.innerHTML = `
        <div class="modal-sheet glass-surface" style="max-width: 390px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <span style="font-weight:700;font-size:15px;color:var(--text-primary);">⌨️ Keyboard Shortcuts</span>
            <button id="modal-shortcuts-close" aria-label="Close shortcuts dialog" style="background:none;border:none;color:var(--text-secondary);cursor:pointer;font-size:18px;line-height:1;">&times;</button>
          </div>
          <div style="display:grid;gap:7px;font-size:12.5px;color:var(--text-primary);">
            <div style="display:flex;justify-content:space-between;"><span>Focus Search Box</span><span class="kbd-hint">/</span></div>
            <div style="display:flex;justify-content:space-between;"><span>AI Scan Map Grounds</span><span class="kbd-hint">A</span></div>
            <div style="display:flex;justify-content:space-between;"><span>Parking Near Me</span><span class="kbd-hint">G</span></div>
            <div style="display:flex;justify-content:space-between;"><span>Toggle Dark / Light Glass</span><span class="kbd-hint">T</span></div>
            <div style="display:flex;justify-content:space-between;"><span>Snap to Debrecan House</span><span class="kbd-hint">C</span></div>
            <div style="display:flex;justify-content:space-between;"><span>Navigate Autocomplete</span><span class="kbd-hint">&uarr; / &darr;</span></div>
            <div style="display:flex;justify-content:space-between;"><span>Dismiss Modal / Drawer</span><span class="kbd-hint">Esc</span></div>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
      modal.addEventListener('click', (e) => {
        if (e.target === modal || e.target.id === 'modal-shortcuts-close') modal.classList.remove('open');
      });
      return modal;
    };

    document.addEventListener('keydown', (e) => {
      if (e.key !== '?' || up.isTyping(e.target)) return;
      e.preventDefault();
      createModal().classList.toggle('open');
    });
  });

  UIPolish.register('sidebarAutocompleteNav', () => {
    const bindDropdownKeyboard = (inputId, listId) => {
      const input = document.getElementById(inputId);
      const list = document.getElementById(listId);
      if (!input || !list) return;
      let activeIdx = -1;

      const syncHighlight = () => {
        const items = Array.from(list.querySelectorAll('.autocomplete-item'));
        items.forEach((el, idx) => el.classList.toggle('is-active', idx === activeIdx));
        if (activeIdx >= 0 && items[activeIdx]) {
          items[activeIdx].scrollIntoView({ block: 'nearest' });
        }
      };

      const obs = new MutationObserver(() => { activeIdx = -1; });
      obs.observe(list, { childList: true });

      input.addEventListener('keydown', (e) => {
        if (!list.classList.contains('open')) return;
        const items = Array.from(list.querySelectorAll('.autocomplete-item'));
        if (!items.length) return;
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          activeIdx = (activeIdx + 1) % items.length;
          syncHighlight();
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          activeIdx = (activeIdx <= 0 ? items.length - 1 : activeIdx - 1);
          syncHighlight();
        } else if (e.key === 'Enter' && activeIdx >= 0 && items[activeIdx]) {
          e.preventDefault();
          e.stopImmediatePropagation();
          items[activeIdx].click();
        }
      }, true);
    };

    bindDropdownKeyboard('search-input', 'search-autocomplete-box');
    bindDropdownKeyboard('welcome-search-input', 'welcome-autocomplete-box');
  });

  UIPolish.register('searchClearAndEscape', () => {
    const input = document.getElementById('search-input');
    const clearBtn = document.getElementById('search-clear');
    const list = document.getElementById('search-autocomplete-box');
    if (!input || !clearBtn) return;

    const syncClear = () => {
      clearBtn.style.opacity = input.value.trim().length > 0 ? '1' : '0';
      clearBtn.style.pointerEvents = input.value.trim().length > 0 ? 'auto' : 'none';
    };
    input.addEventListener('input', syncClear);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && input.value.trim().length > 0) {
        input.value = '';
        if (list) list.classList.remove('open');
        syncClear();
      }
    });
    clearBtn.addEventListener('click', () => {
      setTimeout(syncClear, 20);
    });
    syncClear();
  });

  UIPolish.register('searchSpinnerAndKbd', () => {
    const wrapper = document.querySelector('.search-wrapper');
    const clearBtn = document.getElementById('search-clear');
    if (!wrapper || !clearBtn) return;

    const spinner = document.createElement('span');
    spinner.className = 'search-spinner';
    spinner.setAttribute('aria-hidden', 'true');

    const kbd = document.createElement('span');
    kbd.className = 'kbd-hint';
    kbd.textContent = '/';
    kbd.title = 'Press / to search';

    wrapper.insertBefore(spinner, clearBtn);
    wrapper.insertBefore(kbd, clearBtn);

    const input = document.getElementById('search-input');
    if (input) {
      const updateKbd = () => {
        kbd.style.display = (document.activeElement === input || input.value.trim().length > 0) ? 'none' : '';
      };
      input.addEventListener('focus', updateKbd);
      input.addEventListener('blur', updateKbd);
      input.addEventListener('input', updateKbd);
    }

    const origFetch = window.fetch;
    let activeSearchReqs = 0;
    window.fetch = function (...args) {
      const url = String(args[0] || '');
      const isPlaceSearch = url.includes('/api/traccar/search') || url.includes('/api/places/search');
      if (isPlaceSearch) {
        activeSearchReqs++;
        wrapper.classList.add('is-loading');
      }
      return origFetch.apply(this, args).finally(() => {
        if (isPlaceSearch) {
          activeSearchReqs = Math.max(0, activeSearchReqs - 1);
          if (activeSearchReqs === 0) wrapper.classList.remove('is-loading');
        }
      });
    };
  });

  UIPolish.register('recentSearchesStore', () => {
    const KEY = 'openpark_recent_searches_v1';
    window.__openparkRecent = {
      load() {
        try {
          return JSON.parse(localStorage.getItem(KEY) || '[]').slice(0, 5);
        } catch { return []; }
      },
      save(query) {
        const clean = (query || '').trim();
        if (clean.length < 2) return;
        const items = [clean, ...this.load().filter((x) => x.toLowerCase() !== clean.toLowerCase())].slice(0, 5);
        try { localStorage.setItem(KEY, JSON.stringify(items)); } catch {}
        window.dispatchEvent(new CustomEvent('openpark:recent-updated'));
      },
      clear() {
        try { localStorage.removeItem(KEY); } catch {}
        window.dispatchEvent(new CustomEvent('openpark:recent-updated'));
      }
    };

    const hookAutocomplete = (boxId) => {
      const box = document.getElementById(boxId);
      if (!box) return;
      box.addEventListener('click', (e) => {
        const item = e.target.closest('.autocomplete-item');
        if (!item) return;
        const titleEl = item.querySelector('.autocomplete-title, strong, span') || item;
        const txt = (titleEl.textContent || '').trim().split('\n')[0].slice(0, 42);
        if (txt) window.__openparkRecent.save(txt);
      }, true);
    };
    hookAutocomplete('search-autocomplete-box');
    hookAutocomplete('welcome-autocomplete-box');
  });

  UIPolish.register('sidebarRecentPills', () => {
    const header = document.querySelector('.sidebar-header');
    const searchInput = document.getElementById('search-input');
    const chipRow = header ? header.querySelector('.filter-chip-row') : null;
    if (!header || !searchInput || !chipRow) return;

    const row = document.createElement('div');
    row.className = 'recent-searches-row';
    row.id = 'sidebar-recent-row';
    header.insertBefore(row, chipRow);

    const render = () => {
      const items = (window.__openparkRecent && window.__openparkRecent.load()) || [];
      if (!items.length) {
        row.style.display = 'none';
        row.innerHTML = '';
        return;
      }
      row.style.display = 'flex';
      row.innerHTML = '<span style="font-size:10.5px;color:var(--text-secondary);font-weight:600;">Recent:</span>' +
        items.map((q) => `<button type="button" class="recent-search-chip" data-rq="${q.replace(/"/g, '&quot;')}">🕒 ${q}</button>`).join('') +
        '<button type="button" class="recent-search-chip" data-clear-recent="1" title="Clear search history">Clear</button>';
    };

    row.addEventListener('click', (e) => {
      if (e.target.closest('[data-clear-recent]')) {
        window.__openparkRecent.clear();
        return;
      }
      const btn = e.target.closest('[data-rq]');
      if (!btn) return;
      searchInput.value = btn.getAttribute('data-rq');
      searchInput.focus();
      searchInput.dispatchEvent(new Event('input', { bubbles: true }));
    });

    window.addEventListener('openpark:recent-updated', render);
    render();
  });

  UIPolish.register('welcomeRecentPills', () => {
    const box = document.querySelector('.welcome-search-box');
    const wInput = document.getElementById('welcome-search-input');
    if (!box || !wInput) return;

    const row = document.createElement('div');
    row.className = 'recent-searches-row';
    row.id = 'welcome-recent-row';
    box.appendChild(row);

    const render = () => {
      const items = (window.__openparkRecent && window.__openparkRecent.load()) || [];
      if (!items.length) {
        row.style.display = 'none';
        row.innerHTML = '';
        return;
      }
      row.style.display = 'flex';
      row.innerHTML = '<span style="font-size:11px;color:var(--text-secondary);font-weight:600;">Recent:</span>' +
        items.slice(0, 3).map((q) => `<button type="button" class="recent-search-chip" data-wq="${q.replace(/"/g, '&quot;')}">🕒 ${q}</button>`).join('');
    };

    row.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-wq]');
      if (!btn) return;
      wInput.value = btn.getAttribute('data-wq');
      wInput.focus();
      wInput.dispatchEvent(new Event('input', { bubbles: true }));
    });

    window.addEventListener('openpark:recent-updated', render);
    render();
  });

  UIPolish.register('welcomeTimeGreeting', () => {
    const el = document.getElementById('welcome-greeting');
    if (!el) return;
    const hr = new Date().getHours();
    const icon = hr < 12 ? '🌅 Good morning' : hr < 17 ? '☀️ Good afternoon' : hr < 21 ? '🌆 Good evening' : '🌙 Good night';
    el.textContent = `${icon} • OpenPark Smart Mobility`;
  });

  UIPolish.register('welcomeThemeIconSync', () => {
    const wBtn = document.getElementById('btn-welcome-theme');
    const mainThemeBtn = document.getElementById('btn-theme');
    if (!wBtn) return;

    const syncIcon = () => {
      const theme = document.documentElement.getAttribute('data-theme');
      const sysDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      const isDark = theme === 'dark' || (!theme && sysDark);
      wBtn.textContent = isDark ? '☀️' : '🌙';
      wBtn.title = isDark ? 'Switch to Light Liquid Glass' : 'Switch to Dark Liquid Glass';
    };

    if (mainThemeBtn) mainThemeBtn.addEventListener('click', () => setTimeout(syncIcon, 30));
    wBtn.addEventListener('click', () => setTimeout(syncIcon, 30));
    syncIcon();
  });

  UIPolish.register('welcomeEmptySearchNudge', () => {
    const wGo = document.getElementById('btn-welcome-go');
    const wInput = document.getElementById('welcome-search-input');
    const pill = document.querySelector('.welcome-search-pill');
    if (!wGo || !wInput || !pill) return;

    wGo.addEventListener('click', () => {
      if (wInput.value.trim().length < 2) {
        pill.classList.remove('input-nudge');
        void pill.offsetWidth;
        pill.classList.add('input-nudge');
        wInput.focus();
      }
    });
  });

  UIPolish.register('themePersistenceSync', () => {
    const THEME_KEY = 'openpark_theme_pref';
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === 'dark' || saved === 'light') {
      document.documentElement.setAttribute('data-theme', saved);
    }
    const saveCurrentTheme = () => {
      setTimeout(() => {
        const cur = document.documentElement.getAttribute('data-theme');
        if (cur === 'dark' || cur === 'light') localStorage.setItem(THEME_KEY, cur);
      }, 40);
    };
    const btn = document.getElementById('btn-theme');
    const wBtn = document.getElementById('btn-welcome-theme');
    if (btn) btn.addEventListener('click', saveCurrentTheme);
    if (wBtn) wBtn.addEventListener('click', saveCurrentTheme);
  });

  UIPolish.register('welcomeKeyboardFooterHint', () => {
    const card = document.querySelector('.welcome-card');
    if (!card || document.getElementById('welcome-kbd-footer')) return;
    const footer = document.createElement('div');
    footer.id = 'welcome-kbd-footer';
    footer.className = 'kbd-hint';
    footer.style.cssText = 'width:100%;height:auto;padding:4px 0 0;background:none;border:none;font-family:inherit;font-size:11px;justify-content:center;gap:10px;';
    footer.innerHTML = '<span>Press <b>/</b> to search</span><span>•</span><span><b>G</b> Parking Near Me</span><span>•</span><span><b>?</b> Shortcuts</span>';
    card.appendChild(footer);
  });

  UIPolish.register('welcomeFocusHandoff', () => {
    const openBtn = document.getElementById('btn-open-welcome');
    const wInput = document.getElementById('welcome-search-input');
    if (!openBtn || !wInput) return;
    openBtn.addEventListener('click', () => {
      setTimeout(() => wInput.focus(), 160);
    });
  });

  UIPolish.register('welcomeChipsAriaSync', () => {
    const row = document.getElementById('welcome-mode-row');
    if (!row) return;
    const sync = () => {
      row.querySelectorAll('.chip-btn').forEach((b) => {
        b.setAttribute('aria-pressed', b.classList.contains('active') ? 'true' : 'false');
      });
    };
    row.addEventListener('click', () => setTimeout(sync, 20));
    sync();
  });

  UIPolish.register('exploreChipsAriaSync', () => {
    const row = document.getElementById('explore-filter-chips');
    if (!row) return;
    const sync = () => {
      row.querySelectorAll('.chip-btn').forEach((b) => {
        b.setAttribute('aria-pressed', b.classList.contains('active') ? 'true' : 'false');
      });
    };
    row.addEventListener('click', () => setTimeout(sync, 20));
    sync();
  });

  UIPolish.register('recordEnterQueries', () => {
    ['search-input', 'welcome-search-input'].forEach((id) => {
      const inp = document.getElementById(id);
      if (!inp) return;
      inp.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && inp.value.trim().length >= 2 && window.__openparkRecent) {
          window.__openparkRecent.save(inp.value.trim());
        }
      });
    });
  });

  UIPolish.register('ariaLiveAnnouncer', () => {
    const region = document.createElement('div');
    region.id = 'ui-sr-announcer';
    region.setAttribute('aria-live', 'polite');
    region.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;';
    document.body.appendChild(region);
    window.__announceUI = (msg) => { region.textContent = msg; };

    const aiSummary = document.getElementById('ai-scan-summary-text');
    if (aiSummary) {
      new MutationObserver(() => {
        window.__announceUI(aiSummary.textContent || '');
      }).observe(aiSummary, { childList: true, characterData: true, subtree: true });
    }
  });

  UIPolish.register('aiFilterStripUI', () => {
    const banner = document.getElementById('ai-scan-banner');
    const resultsEl = document.getElementById('ai-scan-results');
    if (!banner || !resultsEl || document.getElementById('ai-filter-row')) return;

    const filterRow = document.createElement('div');
    filterRow.id = 'ai-filter-row';
    filterRow.className = 'ai-filter-row';
    filterRow.style.display = 'none';
    filterRow.innerHTML = `
      <button type="button" class="ai-filter-pill active" data-ai-cat="all">All</button>
      <button type="button" class="ai-filter-pill" data-ai-cat="empty_ground">🟩 Empty Grounds</button>
      <button type="button" class="ai-filter-pill" data-ai-cat="mall_parking">🛍️ Malls</button>
      <button type="button" class="ai-filter-pill" data-ai-cat="legal_bay">🅿️ Legal Bays</button>
    `;
    banner.insertAdjacentElement('afterend', filterRow);
  });

  UIPolish.register('aiFilterCardsLogic', (up) => {
    const filterRow = document.getElementById('ai-filter-row');
    const banner = document.getElementById('ai-scan-banner');
    const resultsEl = document.getElementById('ai-scan-results');
    if (!filterRow || !banner || !resultsEl) return;

    window.__aiActiveCat = 'all';
    const applyFilter = () => {
      const ctx = up.getCtx();
      const spots = (ctx.AIScannerEngine && ctx.AIScannerEngine.results) || [];
      const hasData = spots.length > 0 && banner.style.display !== 'none';
      filterRow.style.display = hasData ? 'flex' : 'none';

      const counts = { all: spots.length, empty_ground: 0, mall_parking: 0, legal_bay: 0 };
      spots.forEach((s) => { if (counts[s.category] !== undefined) counts[s.category]++; });

      filterRow.querySelectorAll('.ai-filter-pill').forEach((btn) => {
        const cat = btn.getAttribute('data-ai-cat');
        const labelBase = cat === 'all' ? 'All' : cat === 'empty_ground' ? '🟩 Grounds' : cat === 'mall_parking' ? '🛍️ Malls' : '🅿️ Bays';
        btn.textContent = `${labelBase} (${counts[cat] || 0})`;
        btn.classList.toggle('active', cat === window.__aiActiveCat);
      });

      const cards = Array.from(resultsEl.querySelectorAll('.lot-card'));
      cards.forEach((card, idx) => {
        const spot = spots[idx];
        if (!spot) return;
        card.dataset.aiCategory = spot.category;
        const show = window.__aiActiveCat === 'all' || spot.category === window.__aiActiveCat;
        card.style.display = show ? '' : 'none';
      });
    };

    filterRow.addEventListener('click', (e) => {
      const btn = e.target.closest('.ai-filter-pill');
      if (!btn) return;
      window.__aiActiveCat = btn.getAttribute('data-ai-cat') || 'all';
      applyFilter();
      window.dispatchEvent(new CustomEvent('openpark:ai-filter-changed', { detail: window.__aiActiveCat }));
    });

    new MutationObserver(applyFilter).observe(resultsEl, { childList: true });
    new MutationObserver(applyFilter).observe(banner, { attributes: true, attributeFilter: ['style'] });
  });

  UIPolish.register('aiMapPolygonFilterSync', (up) => {
    window.addEventListener('openpark:ai-filter-changed', (e) => {
      const cat = e.detail || 'all';
      const ctx = up.getCtx();
      const map = ctx.MapEngine && ctx.MapEngine.map;
      if (!map) return;
      const expr = cat === 'all' ? null : ['==', ['get', 'category'], cat];
      ['ai-scan-fill', 'ai-scan-outline'].forEach((layerId) => {
        if (map.getLayer(layerId)) map.setFilter(layerId, expr);
      });
    });
  });

  UIPolish.register('aiScanSkeletonLoader', (up) => {
    const labelEl = document.getElementById('btn-ai-scan-label');
    const resultsEl = document.getElementById('ai-scan-results');
    if (!labelEl || !resultsEl) return;

    new MutationObserver(() => {
      const txt = (labelEl.textContent || '').toLowerCase();
      if (txt.includes('reading map') && !resultsEl.querySelector('.lot-card')) {
        resultsEl.style.display = 'flex';
        resultsEl.innerHTML = [1, 2, 3].map(() => `
          <div class="ui-skeleton-card" aria-hidden="true">
            <div class="ui-skeleton-line" style="width: 68%;"></div>
            <div class="ui-skeleton-line" style="width: 44%; height: 8px;"></div>
          </div>
        `).join('');
      }
    }).observe(labelEl, { childList: true, characterData: true, subtree: true });
  });

  UIPolish.register('mapLegendPill', () => {
    if (document.getElementById('map-legend-pill')) return;
    const legend = document.createElement('div');
    legend.id = 'map-legend-pill';
    legend.className = 'apple-glass map-legend-pill';
    legend.setAttribute('role', 'region');
    legend.setAttribute('aria-label', 'Parking polygon legend');
    legend.innerHTML = `
      <span data-legend-cat="empty_ground" style="cursor:pointer;" title="Filter Empty Grounds"><span class="legend-dot" style="background:#ff9500;"></span>Empty Ground</span>
      <span data-legend-cat="mall_parking" style="cursor:pointer;" title="Filter Mall Plazas"><span class="legend-dot" style="background:#0071e3;"></span>Mall Lot</span>
      <span data-legend-cat="legal_bay" style="cursor:pointer;" title="Filter Legal Bays"><span class="legend-dot" style="background:#34c759;"></span>Legal Bay</span>
    `;
    document.body.appendChild(legend);
  });

  // __EXTEND_HOOK__

  if (window.__openpark) {
    UIPolish.boot();
  } else {
    window.addEventListener('openpark:ready', () => UIPolish.boot(), { once: true });
  }
})();
