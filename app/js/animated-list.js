/* React Bits AnimatedList — Pop Stagger, Gradient Fades, Hover Select & Keyboard Nav for OpenPark Sidebar */
(function (global) {
  "use strict";

  const DEFAULT_CFG = {
    animation: "pop",
    theme: "dark",
    maxHeight: 440,
    radius: 14,
    gap: 8,
    stagger: 0.05,
    fadeSize: 56,
    frame: true,
    showGradients: true,
    displayScrollbar: true,
    selectOnHover: true,
    enableArrowNavigation: true,
    loop: false,
    animateOnce: false,
    initialSelectedIndex: -1,
    onItemSelect: null,
  };

  function reducedMotion() {
    return Boolean(
      global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function injectStyles(cfg) {
    if (document.getElementById("rb-animated-list-styles")) return;
    const style = document.createElement("style");
    style.id = "rb-animated-list-styles";
    style.textContent = `
      .al-frame {
        position: relative;
        width: 100%;
        border-radius: ${cfg.radius}px;
        ${cfg.frame ? "border: 1px solid rgba(255, 255, 255, 0.14); padding: 8px; background: rgba(12, 16, 26, 0.72);" : ""}
        overflow: hidden;
      }
      html[data-theme="light"] .al-frame {
        ${cfg.frame ? "border-color: rgba(15, 23, 42, 0.12); background: rgba(248, 250, 252, 0.85);" : ""}
      }
      .al-scroll {
        display: flex;
        flex-direction: column;
        gap: ${cfg.gap}px;
        max-height: ${cfg.maxHeight}px;
        overflow-y: auto;
        overscroll-behavior: contain;
        padding-right: 4px;
      }
      ${
        cfg.displayScrollbar
          ? `.al-scroll::-webkit-scrollbar { width: 6px; }
             .al-scroll::-webkit-scrollbar-track { background: transparent; }
             .al-scroll::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.22); border-radius: 99px; }
             html[data-theme="light"] .al-scroll::-webkit-scrollbar-thumb { background: rgba(15, 23, 42, 0.2); }`
          : `.al-scroll { scrollbar-width: none; } .al-scroll::-webkit-scrollbar { display: none; }`
      }
      .al-gradient-top,
      .al-gradient-bottom {
        position: absolute;
        left: 0;
        right: 0;
        height: ${cfg.fadeSize}px;
        pointer-events: none;
        z-index: 4;
        transition: opacity 0.22s ease;
        opacity: 0;
      }
      .al-gradient-top {
        top: 0;
        background: linear-gradient(to bottom, rgba(12, 16, 26, 0.96), rgba(12, 16, 26, 0));
      }
      .al-gradient-bottom {
        bottom: 0;
        background: linear-gradient(to top, rgba(12, 16, 26, 0.96), rgba(12, 16, 26, 0));
      }
      html[data-theme="light"] .al-gradient-top {
        background: linear-gradient(to bottom, rgba(248, 250, 252, 0.96), rgba(248, 250, 252, 0));
      }
      html[data-theme="light"] .al-gradient-bottom {
        background: linear-gradient(to top, rgba(248, 250, 252, 0.96), rgba(248, 250, 252, 0));
      }
      .al-scroll .lot-card {
        border-radius: ${Math.max(10, cfg.radius - 2)}px !important;
        transition: transform 0.16s ease, border-color 0.16s ease, background 0.16s ease, box-shadow 0.16s ease;
      }
      .al-scroll .lot-card.is-al-selected {
        border-color: rgba(10, 132, 255, 0.85) !important;
        box-shadow: 0 0 0 1px rgba(10, 132, 255, 0.45), 0 10px 24px rgba(0, 0, 0, 0.32) !important;
        transform: translateY(-1px);
      }
    `;
    document.head.appendChild(style);
  }

  class AnimatedListInstance {
    constructor(scrollEl, userOpts) {
      this.cfg = Object.assign({}, DEFAULT_CFG, userOpts || {});
      this.scrollEl = scrollEl;
      this.selectedIndex = this.cfg.initialSelectedIndex;
      this.frameEl = null;
      this.topGrad = null;
      this.bottomGrad = null;
      this._wrap();
      this._bind();
      this.refresh();
    }

    _wrap() {
      injectStyles(this.cfg);
      if (this.scrollEl.parentElement && this.scrollEl.parentElement.classList.contains("al-frame")) {
        this.frameEl = this.scrollEl.parentElement;
        this.topGrad = this.frameEl.querySelector(".al-gradient-top");
        this.bottomGrad = this.frameEl.querySelector(".al-gradient-bottom");
      } else {
        this.frameEl = document.createElement("div");
        this.frameEl.className = "al-frame";
        this.scrollEl.parentElement.insertBefore(this.frameEl, this.scrollEl);
        this.frameEl.appendChild(this.scrollEl);

        if (this.cfg.showGradients) {
          this.topGrad = document.createElement("div");
          this.topGrad.className = "al-gradient-top";
          this.bottomGrad = document.createElement("div");
          this.bottomGrad.className = "al-gradient-bottom";
          this.frameEl.appendChild(this.topGrad);
          this.frameEl.appendChild(this.bottomGrad);
        }
      }
      this.scrollEl.classList.add("al-scroll");
    }

    _syncVisibilityFromScrollEl() {
      if (!this.frameEl) return;
      const isHidden = this.scrollEl.style.display === "none";
      this.frameEl.style.display = isHidden ? "none" : "block";
    }

    _updateGradients() {
      if (!this.cfg.showGradients || !this.topGrad || !this.bottomGrad) return;
      const { scrollTop, scrollHeight, clientHeight } = this.scrollEl;
      const topAlpha = scrollTop > 4 ? Math.min(1, scrollTop / 24) : 0;
      const bottomDist = scrollHeight - (scrollTop + clientHeight);
      const bottomAlpha = bottomDist > 4 ? Math.min(1, bottomDist / 24) : 0;
      this.topGrad.style.opacity = String(topAlpha);
      this.bottomGrad.style.opacity = String(bottomAlpha);
    }

    getItems() {
      return Array.from(this.scrollEl.querySelectorAll(":scope > .lot-card"));
    }

    setSelected(index, scrollIntoView) {
      const items = this.getItems();
      if (!items.length) {
        this.selectedIndex = -1;
        return;
      }
      if (index < 0 || index >= items.length) {
        items.forEach((el) => el.classList.remove("is-al-selected"));
        this.selectedIndex = -1;
        return;
      }
      this.selectedIndex = index;
      items.forEach((el, i) => el.classList.toggle("is-al-selected", i === index));
      if (scrollIntoView) {
        items[index].scrollIntoView({ block: "nearest", behavior: reducedMotion() ? "auto" : "smooth" });
      }
    }

    animatePop() {
      const items = this.getItems();
      if (!items.length || reducedMotion()) return;
      if (global.gsap) {
        global.gsap.fromTo(
          items.slice(0, 20),
          { scale: 0.92, y: 12, opacity: 0 },
          {
            scale: 1,
            y: 0,
            opacity: 1,
            duration: 0.28,
            stagger: this.cfg.stagger,
            ease: "back.out(1.6)",
            clearProps: "transform,opacity",
            overwrite: "auto",
          }
        );
      }
    }

    refresh() {
      this._syncVisibilityFromScrollEl();
      this.setSelected(this.cfg.initialSelectedIndex, false);
      this.animatePop();
      requestAnimationFrame(() => this._updateGradients());
    }

    _bind() {
      this.scrollEl.addEventListener("scroll", () => this._updateGradients(), { passive: true });

      if (this.cfg.selectOnHover) {
        this.scrollEl.addEventListener("pointerover", (ev) => {
          const card = ev.target && ev.target.closest ? ev.target.closest(".lot-card") : null;
          if (!card || card.parentElement !== this.scrollEl) return;
          const idx = this.getItems().indexOf(card);
          if (idx >= 0) this.setSelected(idx, false);
        });
        this.scrollEl.addEventListener("mouseleave", () => {
          if (this.cfg.initialSelectedIndex === -1) this.setSelected(-1, false);
        });
      }

      this.scrollEl.addEventListener("click", (ev) => {
        const card = ev.target && ev.target.closest ? ev.target.closest(".lot-card") : null;
        if (!card || card.parentElement !== this.scrollEl) return;
        const idx = this.getItems().indexOf(card);
        if (idx >= 0) {
          this.setSelected(idx, false);
          if (typeof this.cfg.onItemSelect === "function") {
            this.cfg.onItemSelect(card, idx);
          }
        }
      });

      const obs = new MutationObserver(() => {
        this._syncVisibilityFromScrollEl();
        if (!this.cfg.animateOnce) {
          this.animatePop();
        }
        requestAnimationFrame(() => this._updateGradients());
      });
      obs.observe(this.scrollEl, { childList: true, attributes: true, attributeFilter: ["style"] });

      if (this.cfg.enableArrowNavigation) {
        document.addEventListener("keydown", (ev) => {
          if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp" && ev.key !== "Enter") return;
          const active = document.activeElement;
          const tag = active && active.tagName ? active.tagName.toLowerCase() : "";
          if (tag === "input" || tag === "textarea" || tag === "select") return;
          const welcome = document.getElementById("welcome-overlay");
          if (welcome && !welcome.classList.contains("is-hidden")) return;
          if (this.frameEl && this.frameEl.style.display === "none") return;

          const items = this.getItems();
          if (!items.length) return;

          if (ev.key === "ArrowDown") {
            ev.preventDefault();
            const next =
              this.selectedIndex < 0
                ? 0
                : this.cfg.loop
                ? (this.selectedIndex + 1) % items.length
                : Math.min(items.length - 1, this.selectedIndex + 1);
            this.setSelected(next, true);
          } else if (ev.key === "ArrowUp") {
            ev.preventDefault();
            const prev =
              this.selectedIndex < 0
                ? 0
                : this.cfg.loop
                ? (this.selectedIndex - 1 + items.length) % items.length
                : Math.max(0, this.selectedIndex - 1);
            this.setSelected(prev, true);
          } else if (ev.key === "Enter" && this.selectedIndex >= 0 && items[this.selectedIndex]) {
            ev.preventDefault();
            items[this.selectedIndex].click();
          }
        });
      }
    }
  }

  function initSidebarAnimatedLists() {
    const instances = [];
    ["ai-scan-results", "view-explore"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        instances.push(
          new AnimatedListInstance(el, {
            animation: "pop",
            theme: "dark",
            maxHeight: id === "ai-scan-results" ? 440 : 440,
            radius: 14,
            gap: 8,
            stagger: 0.05,
            fadeSize: 56,
            frame: true,
            showGradients: true,
            displayScrollbar: true,
            selectOnHover: true,
            enableArrowNavigation: true,
            loop: false,
            animateOnce: false,
            initialSelectedIndex: -1,
          })
        );
      }
    });
    return instances;
  }

  global.OpenParkAnimatedList = {
    AnimatedListInstance,
    initSidebar: initSidebarAnimatedLists,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSidebarAnimatedLists);
  } else {
    initSidebarAnimatedLists();
  }
})(window);
