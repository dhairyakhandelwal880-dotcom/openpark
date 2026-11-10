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

  // __EXTEND_HOOK__

  if (window.__openpark) {
    UIPolish.boot();
  } else {
    window.addEventListener('openpark:ready', () => UIPolish.boot(), { once: true });
  }
})();
