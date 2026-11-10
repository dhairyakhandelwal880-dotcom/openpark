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

  // __EXTEND_HOOK__

  if (window.__openpark) {
    UIPolish.boot();
  } else {
    window.addEventListener('openpark:ready', () => UIPolish.boot(), { once: true });
  }
})();
