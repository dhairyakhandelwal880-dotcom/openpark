/* React Bits JellyRadio — Elastic Swell, Neighbor Barge Push & Stagger Ripple for Every Bar */
(function (global) {
  "use strict";

  const CFG = {
    barSelector:
      ".filter-chip-row, .segmented-control, .welcome-mode-row, #ai-filter-row, #explore-sort-bar, #map-style-switcher",
    chipColor: "#27272a",
    activeColor: "#f5f5f5",
    textColor: "#f5f5f5",
    activeTextColor: "#18181b",
    gap: 8,
    radius: 18,
    swell: 0.2,
    barge: 6,
    shrink: 0.05,
    jelly: 1,
    bounce: 0.25,
    staggerMs: 22,
  };

  function reducedMotion() {
    return Boolean(
      global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function injectStyles() {
    if (document.getElementById("rb-jelly-radio-styles")) return;
    const s = document.createElement("style");
    s.id = "rb-jelly-radio-styles";
    s.textContent = `
      .jelly-bar {
        display: flex !important;
        align-items: center !important;
        gap: ${CFG.gap}px !important;
      }
      .jelly-bar > .jelly-pill {
        flex-shrink: 0;
        border-radius: ${CFG.radius}px !important;
        background: ${CFG.chipColor} !important;
        color: ${CFG.textColor} !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        will-change: transform;
        transform-origin: center center;
        transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease;
      }
      .segmented-control.jelly-bar > .jelly-pill {
        flex: 1 1 0;
        justify-content: center;
        text-align: center;
      }
      .jelly-bar > .jelly-pill.active,
      .jelly-bar > .jelly-pill[aria-selected="true"] {
        background: ${CFG.activeColor} !important;
        color: ${CFG.activeTextColor} !important;
        border-color: transparent !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.28) !important;
      }
      html[data-theme="light"] .jelly-bar > .jelly-pill {
        background: #e4e4e7 !important;
        color: #18181b !important;
        border-color: rgba(24, 24, 27, 0.1) !important;
      }
      html[data-theme="light"] .jelly-bar > .jelly-pill.active,
      html[data-theme="light"] .jelly-bar > .jelly-pill[aria-selected="true"] {
        background: #18181b !important;
        color: #f5f5f5 !important;
      }
    `;
    document.head.appendChild(s);
  }

  function getPills(bar) {
    return Array.from(bar.children).filter(
      (el) => el.tagName === "BUTTON" || el.getAttribute("role") === "tab"
    );
  }

  function triggerJellyRipple(bar, hitIdx) {
    if (reducedMotion() || !global.gsap) return;
    const pills = getPills(bar);
    if (!pills.length || hitIdx < 0) return;

    const elasticAmp = Math.max(0.8, 1 + CFG.bounce);
    const period = Math.max(0.28, 0.44 / Math.max(0.4, CFG.jelly));

    pills.forEach((pill, i) => {
      const dist = Math.abs(i - hitIdx);
      const delay = (dist * CFG.staggerMs) / 1000;

      if (dist === 0) {
        global.gsap.killTweensOf(pill);
        global.gsap.fromTo(
          pill,
          { scaleX: 1 + CFG.swell, scaleY: 1 - CFG.swell * 0.45, x: 0 },
          {
            scaleX: 1,
            scaleY: 1,
            x: 0,
            duration: 0.48,
            ease: `elastic.out(${elasticAmp}, ${period})`,
            clearProps: "transform",
          }
        );
      } else {
        const dir = i < hitIdx ? -1 : 1;
        const pushX = dir * (CFG.barge / Math.max(1, dist * 0.85));
        const targetScale = Math.max(0.9, 1 - CFG.shrink);
        global.gsap.killTweensOf(pill);
        global.gsap.to(pill, {
          x: pushX,
          scale: targetScale,
          duration: 0.12,
          delay,
          ease: "power2.out",
          onComplete: () => {
            global.gsap.to(pill, {
              x: 0,
              scale: 1,
              duration: 0.36,
              ease: `elastic.out(${elasticAmp}, 0.45)`,
              clearProps: "transform",
            });
          },
        });
      }
    });
  }

  function enhanceBar(bar) {
    if (!bar) return;
    if (!bar.classList.contains("jelly-bar")) bar.classList.add("jelly-bar");
    getPills(bar).forEach((p) => {
      if (!p.classList.contains("jelly-pill")) p.classList.add("jelly-pill");
    });

    if (bar.dataset.jellyBound === "1") return;
    bar.dataset.jellyBound = "1";

    bar.addEventListener("pointerenter", (ev) => {
      if (reducedMotion() || !global.gsap || ev.pointerType !== "mouse") return;
      const pill = ev.target && ev.target.closest ? ev.target.closest(".jelly-pill") : null;
      if (!pill || pill.parentElement !== bar) return;
      const pills = getPills(bar);
      const idx = pills.indexOf(pill);
      if (idx < 0) return;

      global.gsap.to(pill, { scale: 1 + CFG.swell * 0.35, duration: 0.16, ease: "power2.out", overwrite: "auto" });
      if (idx > 0) global.gsap.to(pills[idx - 1], { x: -CFG.barge * 0.45, duration: 0.16, ease: "power2.out", overwrite: "auto" });
      if (idx < pills.length - 1) global.gsap.to(pills[idx + 1], { x: CFG.barge * 0.45, duration: 0.16, ease: "power2.out", overwrite: "auto" });
    }, true);

    bar.addEventListener("pointerleave", (ev) => {
      if (reducedMotion() || !global.gsap || ev.pointerType !== "mouse") return;
      const pill = ev.target && ev.target.closest ? ev.target.closest(".jelly-pill") : null;
      if (!pill || pill.parentElement !== bar) return;
      global.gsap.to(getPills(bar), { x: 0, scale: 1, duration: 0.24, ease: "power2.out", clearProps: "transform" });
    }, true);

    bar.addEventListener("click", (ev) => {
      const pill = ev.target && ev.target.closest ? ev.target.closest(".jelly-pill") : null;
      if (!pill || pill.parentElement !== bar) return;
      const pills = getPills(bar);
      const hitIdx = pills.indexOf(pill);
      if (hitIdx >= 0) triggerJellyRipple(bar, hitIdx);
    });
  }

  function enhanceAllBars() {
    injectStyles();
    document.querySelectorAll(CFG.barSelector).forEach(enhanceBar);
  }

  function boot() {
    enhanceAllBars();
    // Re-attach safely when dynamic bars (#ai-filter-row, #explore-sort-bar, #map-style-switcher) mount
    let timer = null;
    const obs = new MutationObserver(() => {
      if (timer) return;
      timer = requestAnimationFrame(() => {
        timer = null;
        document.querySelectorAll(CFG.barSelector).forEach(enhanceBar);
      });
    });
    obs.observe(document.body, { childList: true, subtree: true });
  }

  global.OpenParkJellyRadio = { init: boot, enhanceAllBars, triggerJellyRipple };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})(window);
