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

  // __EXTEND_HOOK__

  if (window.__openpark) {
    UIPolish.boot();
  } else {
    window.addEventListener('openpark:ready', () => UIPolish.boot(), { once: true });
  }
})();
