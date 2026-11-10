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

  UIPolish.register('mapLegendClickFilter', () => {
    const legend = document.getElementById('map-legend-pill');
    if (!legend) return;
    legend.addEventListener('click', (e) => {
      const item = e.target.closest('[data-legend-cat]');
      const filterRow = document.getElementById('ai-filter-row');
      if (!item || !filterRow) return;
      const cat = item.getAttribute('data-legend-cat');
      const targetBtn = filterRow.querySelector(`[data-ai-cat="${window.__aiActiveCat === cat ? 'all' : cat}"]`);
      if (targetBtn) targetBtn.click();
    });
  });

  UIPolish.register('aiPolygonHoverTooltip', (up) => {
    const tip = document.createElement('div');
    tip.id = 'ai-map-tooltip';
    tip.className = 'ai-map-tooltip';
    document.body.appendChild(tip);

    const bindMapHover = () => {
      const ctx = up.getCtx();
      const map = ctx.MapEngine && ctx.MapEngine.map;
      if (!map) return false;
      map.on('mousemove', 'ai-scan-fill', (e) => {
        const f = e.features && e.features[0];
        if (!f) return;
        const p = f.properties || {};
        map.getCanvas().style.cursor = 'pointer';
        tip.innerHTML = `
          <div style="font-weight:700;margin-bottom:2px;">${p.name || 'Discovered Space'}</div>
          <div style="color:var(--text-secondary);">AI Fit <strong>${p.ai_score || 85}%</strong> &bull; ~${p.estimated_spots || 20} bays</div>
        `;
        tip.style.left = `${e.point.x}px`;
        tip.style.top = `${e.point.y}px`;
        tip.classList.add('visible');
      });
      map.on('mouseleave', 'ai-scan-fill', () => {
        map.getCanvas().style.cursor = '';
        tip.classList.remove('visible');
      });
      map.on('movestart', () => tip.classList.remove('visible'));
      return true;
    };

    if (!bindMapHover()) {
      const t = setInterval(() => { if (bindMapHover()) clearInterval(t); }, 400);
    }
  });

  UIPolish.register('favoritesStore', () => {
    const FAV_KEY = 'openpark_favorite_lots_v1';
    window.__openparkFavs = {
      getSet() {
        try { return new Set(JSON.parse(localStorage.getItem(FAV_KEY) || '[]').map(String)); }
        catch { return new Set(); }
      },
      has(id) { return this.getSet().has(String(id)); },
      toggle(id) {
        const s = this.getSet();
        const key = String(id);
        if (s.has(key)) s.delete(key);
        else s.add(key);
        try { localStorage.setItem(FAV_KEY, JSON.stringify(Array.from(s))); } catch {}
        window.dispatchEvent(new CustomEvent('openpark:favs-updated'));
        return s.has(key);
      }
    };
  });

  UIPolish.register('exploreSortBarUI', () => {
    const viewExplore = document.getElementById('view-explore');
    if (!viewExplore || document.getElementById('explore-sort-bar')) return;

    const bar = document.createElement('div');
    bar.id = 'explore-sort-bar';
    bar.className = 'explore-sort-bar';
    bar.setAttribute('role', 'group');
    bar.setAttribute('aria-label', 'Sort parking lots');
    bar.innerHTML = `
      <span class="explore-sort-label">Sort:</span>
      <button type="button" class="explore-sort-chip active" data-sort="distance">Nearest</button>
      <button type="button" class="explore-sort-chip" data-sort="spots">Most Free</button>
      <button type="button" class="explore-sort-chip" data-sort="price">Lowest Price</button>
      <button type="button" class="explore-sort-chip" data-sort="saved">⭐ Saved</button>
    `;
    viewExplore.insertAdjacentElement('beforebegin', bar);
    window.__exploreSortMode = 'distance';
  });

  UIPolish.register('exploreSortLogic', (up) => {
    const bar = document.getElementById('explore-sort-bar');
    const viewExplore = document.getElementById('view-explore');
    if (!bar || !viewExplore) return;

    const parseCardMetrics = (card) => {
      const distText = (card.querySelector('.lot-dist')?.textContent || '999').split('km')[0];
      const spotsText = card.querySelector('.status-pill strong')?.textContent || '0';
      const priceText = (card.querySelector('.lot-price')?.textContent || '999').replace(/[^0-9]/g, '');
      const title = (card.querySelector('.lot-title')?.textContent || '').trim();
      return {
        dist: parseFloat(distText) || 999,
        spots: parseInt(spotsText, 10) || 0,
        price: parseInt(priceText, 10) || 999,
        title
      };
    };

    let sortingNow = false;
    const applySortAndFavs = () => {
      if (sortingNow) return;
      sortingNow = true;
      try {
        const mode = window.__exploreSortMode || 'distance';
        const cards = Array.from(viewExplore.querySelectorAll('.lot-card'));
        if (!cards.length) return;

        const ctx = up.getCtx();
        const lots = (ctx.STATE && ctx.STATE.lots) || [];
        cards.forEach((card) => {
          const title = (card.querySelector('.lot-title')?.textContent || '').trim();
          const matched = lots.find((l) => l.name === title);
          if (matched) card.dataset.lotId = String(matched.id);
        });

        cards.sort((a, b) => {
          const ma = parseCardMetrics(a);
          const mb = parseCardMetrics(b);
          if (mode === 'spots') return mb.spots - ma.spots;
          if (mode === 'price') return ma.price - mb.price;
          return ma.dist - mb.dist;
        });
        cards.forEach((c) => {
          const isFav = window.__openparkFavs && c.dataset.lotId ? window.__openparkFavs.has(c.dataset.lotId) : false;
          c.style.display = (mode === 'saved' && !isFav) ? 'none' : '';
          viewExplore.appendChild(c);
        });

        let emptySaved = document.getElementById('saved-empty-msg');
        if (mode === 'saved' && cards.every((c) => c.style.display === 'none')) {
          if (!emptySaved) {
            emptySaved = document.createElement('div');
            emptySaved.id = 'saved-empty-msg';
            emptySaved.style.cssText = 'text-align:center;padding:28px 12px;color:var(--text-secondary);font-size:13px;';
            emptySaved.innerHTML = '⭐ No saved parking lots yet.<br><span style="font-size:11.5px;">Tap the star on any lot card to bookmark it.</span>';
            viewExplore.appendChild(emptySaved);
          }
        } else if (emptySaved) {
          emptySaved.remove();
        }
      } finally {
        sortingNow = false;
      }
    };

    bar.addEventListener('click', (e) => {
      const chip = e.target.closest('.explore-sort-chip');
      if (!chip) return;
      bar.querySelectorAll('.explore-sort-chip').forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
      window.__exploreSortMode = chip.getAttribute('data-sort') || 'distance';
      applySortAndFavs();
    });

    new MutationObserver(applySortAndFavs).observe(viewExplore, { childList: true });
    window.addEventListener('openpark:favs-updated', applySortAndFavs);
  });

  UIPolish.register('lotCardBookmarkButtons', (up) => {
    const viewExplore = document.getElementById('view-explore');
    if (!viewExplore) return;

    const decorateCards = () => {
      const ctx = up.getCtx();
      const lots = (ctx.STATE && ctx.STATE.lots) || [];
      viewExplore.querySelectorAll('.lot-card').forEach((card) => {
        const hdr = card.querySelector('.lot-card-header');
        if (!hdr || hdr.querySelector('.fav-toggle-btn')) return;
        const title = (card.querySelector('.lot-title')?.textContent || '').trim();
        const lot = lots.find((l) => l.name === title);
        const lotId = lot ? lot.id : title;
        card.dataset.lotId = String(lotId);

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'fav-toggle-btn';
        const saved = window.__openparkFavs ? window.__openparkFavs.has(lotId) : false;
        btn.classList.toggle('is-saved', saved);
        btn.textContent = saved ? '★' : '☆';
        btn.title = saved ? 'Remove from Saved Lots' : 'Bookmark Parking Lot';
        btn.setAttribute('aria-label', btn.title);
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const nowSaved = window.__openparkFavs.toggle(lotId);
          btn.classList.toggle('is-saved', nowSaved);
          btn.textContent = nowSaved ? '★' : '☆';
          up.toast(nowSaved ? `⭐ Saved ${title}` : `Removed ${title}`, 'info', 1600);
        });
        hdr.appendChild(btn);
      });
    };

    new MutationObserver(decorateCards).observe(viewExplore, { childList: true });
    window.addEventListener('openpark:favs-updated', () => {
      viewExplore.querySelectorAll('.lot-card').forEach((card) => {
        const btn = card.querySelector('.fav-toggle-btn');
        if (!btn || !card.dataset.lotId) return;
        const saved = window.__openparkFavs.has(card.dataset.lotId);
        btn.classList.toggle('is-saved', saved);
        btn.textContent = saved ? '★' : '☆';
      });
    });
    decorateCards();
  });

  UIPolish.register('selectedLotCardHighlight', () => {
    const viewExplore = document.getElementById('view-explore');
    if (!viewExplore) return;
    viewExplore.addEventListener('click', (e) => {
      const card = e.target.closest('.lot-card');
      if (!card) return;
      viewExplore.querySelectorAll('.lot-card.is-selected').forEach((c) => c.classList.remove('is-selected'));
      card.classList.add('is-selected');
    });
  });

  UIPolish.register('sidebarBackToTop', () => {
    const scroller = document.querySelector('.sidebar-views');
    if (!scroller || document.getElementById('btn-sidebar-top')) return;
    const btn = document.createElement('button');
    btn.id = 'btn-sidebar-top';
    btn.type = 'button';
    btn.className = 'sidebar-scroll-top pressable';
    btn.innerHTML = '↑ Top';
    btn.setAttribute('aria-label', 'Scroll back to top of results');
    scroller.appendChild(btn);

    scroller.addEventListener('scroll', () => {
      btn.classList.toggle('visible', scroller.scrollTop > 220);
    }, { passive: true });
    btn.addEventListener('click', () => {
      scroller.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });

  UIPolish.register('exploreTabBadgeCount', (up) => {
    const tabExplore = document.getElementById('tab-explore');
    const aiList = document.getElementById('ai-scan-results');
    const lotsCountEl = document.getElementById('total-lots-count');
    if (!tabExplore) return;

    const updateTabLabel = () => {
      const ctx = up.getCtx();
      const aiCount = (ctx.AIScannerEngine && Array.isArray(ctx.AIScannerEngine.results)) ? ctx.AIScannerEngine.results.length : 0;
      const lotCount = lotsCountEl ? parseInt(lotsCountEl.textContent || '0', 10) : 0;
      tabExplore.textContent = aiCount > 0 ? `Explore (${aiCount} AI)` : lotCount > 0 ? `Explore (${lotCount})` : 'Explore';
    };

    if (aiList) new MutationObserver(updateTabLabel).observe(aiList, { childList: true });
    if (lotsCountEl) new MutationObserver(updateTabLabel).observe(lotsCountEl, { childList: true, characterData: true, subtree: true });
  });

  UIPolish.register('aiCardQuickLinks', (up) => {
    const resultsEl = document.getElementById('ai-scan-results');
    if (!resultsEl) return;

    const enhanceAiCards = () => {
      const ctx = up.getCtx();
      const spots = (ctx.AIScannerEngine && ctx.AIScannerEngine.results) || [];
      resultsEl.querySelectorAll('.lot-card').forEach((card, idx) => {
        const spot = spots[idx];
        if (!spot || card.querySelector('.ai-card-actions')) return;
        const bar = document.createElement('div');
        bar.className = 'ai-card-actions';
        bar.style.cssText = 'display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;';
        bar.innerHTML = `
          <a href="https://maps.google.com/?q=${spot.lat},${spot.lon}" target="_blank" rel="noopener" class="recent-search-chip" style="text-decoration:none;">🗺️ Maps</a>
          <button type="button" class="recent-search-chip" data-copy-coord="${spot.lat.toFixed(5)}, ${spot.lon.toFixed(5)}">📋 Copy GPS</button>
        `;
        bar.addEventListener('click', (e) => {
          e.stopPropagation();
          const cp = e.target.closest('[data-copy-coord]');
          if (cp) up.copyText(cp.getAttribute('data-copy-coord'), `Copied ${spot.name} GPS`);
        });
        card.appendChild(bar);
      });
    };

    new MutationObserver(enhanceAiCards).observe(resultsEl, { childList: true });
  });

  UIPolish.register('hudAiScanCounterBadge', (up) => {
    const hudBtn = document.getElementById('btn-hud-ai-scan');
    const resultsEl = document.getElementById('ai-scan-results');
    if (!hudBtn || !resultsEl) return;

    hudBtn.style.position = 'relative';
    const dot = document.createElement('span');
    dot.id = 'hud-ai-count-badge';
    dot.style.cssText = 'position:absolute;top:-4px;right:-4px;min-width:16px;height:16px;padding:0 4px;border-radius:999px;background:#ff9500;color:#fff;font-size:9.5px;font-weight:800;display:none;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(0,0,0,0.25);';
    hudBtn.appendChild(dot);

    new MutationObserver(() => {
      const ctx = up.getCtx();
      const count = (ctx.AIScannerEngine && ctx.AIScannerEngine.results) ? ctx.AIScannerEngine.results.length : 0;
      dot.style.display = count > 0 ? 'inline-flex' : 'none';
      dot.textContent = count > 99 ? '99+' : String(count);
    }).observe(resultsEl, { childList: true });
  });

  UIPolish.register('aiMapPanRescanBanner', (up) => {
    const banner = document.getElementById('ai-scan-banner');
    if (!banner) return;

    const btnRescan = document.createElement('button');
    btnRescan.id = 'btn-ai-rescan-area';
    btnRescan.type = 'button';
    btnRescan.className = 'apple-glass pressable';
    btnRescan.style.cssText = 'position:fixed;top:74px;left:50%;transform:translateX(-50%);z-index:22;padding:7px 14px;border-radius:999px;font-size:12px;font-weight:600;color:var(--apple-blue);display:none;align-items:center;gap:6px;cursor:pointer;';
    btnRescan.innerHTML = '<span>🔄</span><span>Re-scan Empty Grounds Here</span>';
    document.body.appendChild(btnRescan);

    let lastScanCenter = null;
    const haversineKm = (a, b) => {
      const r = 6371, dLat = (b.lat - a.lat) * Math.PI / 180, dLon = (b.lng - a.lng) * Math.PI / 180;
      const x = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * Math.PI / 180) * Math.cos(b.lat * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
      return 2 * r * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
    };

    const bind = () => {
      const ctx = up.getCtx();
      const map = ctx.MapEngine && ctx.MapEngine.map;
      if (!map) return false;
      new MutationObserver(() => {
        if (banner.style.display !== 'none') {
          lastScanCenter = map.getCenter();
          btnRescan.style.display = 'none';
        } else {
          lastScanCenter = null;
          btnRescan.style.display = 'none';
        }
      }).observe(banner, { attributes: true, attributeFilter: ['style'] });

      map.on('moveend', () => {
        if (!lastScanCenter || banner.style.display === 'none') return;
        const welcome = document.getElementById('welcome-overlay');
        if (welcome && !welcome.classList.contains('hidden')) return;
        const movedKm = haversineKm(lastScanCenter, map.getCenter());
        btnRescan.style.display = movedKm >= 0.6 ? 'inline-flex' : 'none';
      });
      return true;
    };

    btnRescan.addEventListener('click', () => {
      btnRescan.style.display = 'none';
      const ctx = up.getCtx();
      if (ctx.AIScannerEngine) ctx.AIScannerEngine.scanCurrentArea();
    });

    if (!bind()) {
      const t = setInterval(() => { if (bind()) clearInterval(t); }, 450);
    }
  });

  UIPolish.register('aiClearFilterReset', (up) => {
    const clearBtn = document.getElementById('btn-ai-clear');
    if (!clearBtn) return;
    clearBtn.addEventListener('click', () => {
      window.__aiActiveCat = 'all';
      const ctx = up.getCtx();
      const map = ctx.MapEngine && ctx.MapEngine.map;
      if (map) {
        ['ai-scan-fill', 'ai-scan-outline'].forEach((id) => {
          if (map.getLayer(id)) map.setFilter(id, null);
        });
      }
      const rescan = document.getElementById('btn-ai-rescan-area');
      if (rescan) rescan.style.display = 'none';
    });
  });

  // __EXTEND_HOOK__

  if (window.__openpark) {
    UIPolish.boot();
  } else {
    window.addEventListener('openpark:ready', () => UIPolish.boot(), { once: true });
  }
})();
