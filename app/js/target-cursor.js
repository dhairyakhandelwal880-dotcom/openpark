/* React Bits TargetCursor — High-Performance Bracket Reticle for OpenPark */
(function (global) {
  "use strict";

  const DEFAULTS = {
    targetSelector:
      ".cursor-target, button, .lot-card, .chip-btn, .hud-btn, .welcome-dest-card, .autocomplete-item, [data-cursor-label]",
    hoverDuration: 0.16,
    size: 32,
    cornerSize: 10,
    thickness: 2,
    padding: 6,
    dotSize: 4,
    cursorColor: "#00f2fe",
    cursorColorOnTarget: "#00f2fe",
    blendMode: "normal",
    matchRadius: true,
    showLabel: true,
    clickEffect: false,
    hideDefaultCursor: false, // Keep native 0ms hardware cursor for instant responsiveness
  };

  function isTouchOrReducedMotion() {
    if (typeof window === "undefined") return true;
    const coarse = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;
    const noHover = window.matchMedia && window.matchMedia("(hover: none)").matches;
    const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    return Boolean(coarse || noHover || reduced);
  }

  function injectStyles(cfg) {
    if (document.getElementById("rb-target-cursor-styles")) return;
    const style = document.createElement("style");
    style.id = "rb-target-cursor-styles";
    style.textContent = `
      #rb-target-cursor {
        position: fixed;
        top: 0;
        left: 0;
        width: ${cfg.size}px;
        height: ${cfg.size}px;
        margin-left: -${cfg.size / 2}px;
        margin-top: -${cfg.size / 2}px;
        pointer-events: none;
        z-index: 99999;
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.15s ease, visibility 0.15s ease, border-color 0.15s ease;
        will-change: transform, width, height;
      }
      #rb-target-cursor.is-visible {
        opacity: 0.85;
        visibility: visible;
      }
      #rb-target-cursor .tc-dot {
        display: none !important;
      }
      #rb-target-cursor .tc-box {
        position: relative;
        width: 100%;
        height: 100%;
        transform-origin: center center;
      }
      #rb-target-cursor .tc-corner {
        position: absolute;
        width: ${cfg.cornerSize}px;
        height: ${cfg.cornerSize}px;
        border-color: ${cfg.cursorColor};
        border-style: solid;
        box-sizing: border-box;
      }
      #rb-target-cursor.is-locked .tc-corner {
        border-color: ${cfg.cursorColorOnTarget};
      }
      #rb-target-cursor .tc-tl {
        top: 0; left: 0;
        border-width: ${cfg.thickness}px 0 0 ${cfg.thickness}px;
      }
      #rb-target-cursor .tc-tr {
        top: 0; right: 0;
        border-width: ${cfg.thickness}px ${cfg.thickness}px 0 0;
      }
      #rb-target-cursor .tc-bl {
        bottom: 0; left: 0;
        border-width: 0 0 ${cfg.thickness}px ${cfg.thickness}px;
      }
      #rb-target-cursor .tc-br {
        bottom: 0; right: 0;
        border-width: 0 ${cfg.thickness}px ${cfg.thickness}px 0;
      }
      #rb-target-cursor .tc-label {
        position: absolute;
        left: 50%;
        bottom: calc(100% + 6px);
        transform: translateX(-50%);
        padding: 2px 7px;
        border-radius: 4px;
        background: rgba(10, 16, 28, 0.92);
        border: 1px solid rgba(0, 242, 254, 0.45);
        color: #00f2fe;
        font-family: "JetBrains Mono", ui-monospace, monospace;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        white-space: nowrap;
        opacity: 0;
        pointer-events: none;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
      }
      #rb-target-cursor.is-locked .tc-label.has-text {
        opacity: 1;
      }
    `;
    document.head.appendChild(style);
  }

  function resolveLabel(el) {
    if (!el) return "";
    if (el.dataset && el.dataset.cursorLabel) return el.dataset.cursorLabel;
    if (el.classList.contains("lot-card")) return "Inspect";
    if (el.classList.contains("welcome-dest-card")) {
      const n = el.querySelector(".welcome-dest-name");
      return n ? n.textContent.trim() : "Open";
    }
    const aria = el.getAttribute("aria-label") || el.getAttribute("title");
    if (aria && aria.length <= 24) return aria;
    return "";
  }

  function initTargetCursor(userOpts) {
    if (isTouchOrReducedMotion()) return null;
    const cfg = Object.assign({}, DEFAULTS, userOpts || {});
    injectStyles(cfg);

    const old = document.getElementById("rb-target-cursor");
    if (old) old.remove();

    const root = document.createElement("div");
    root.id = "rb-target-cursor";
    root.setAttribute("aria-hidden", "true");
    root.innerHTML = `
      <div class="tc-box">
        <span class="tc-corner tc-tl"></span>
        <span class="tc-corner tc-tr"></span>
        <span class="tc-corner tc-bl"></span>
        <span class="tc-corner tc-br"></span>
      </div>
      <div class="tc-label"></div>
    `;

    document.body.appendChild(root);

    const labelEl = root.querySelector(".tc-label");
    const corners = {
      tl: root.querySelector(".tc-tl"),
      tr: root.querySelector(".tc-tr"),
      bl: root.querySelector(".tc-bl"),
      br: root.querySelector(".tc-br"),
    };

    let activeTarget = null;
    let cachedRect = null;
    let pendingRaf = 0;
    let lastEventTarget = null;

    const applyCornerRadius = (radiusPx) => {
      const r = cfg.matchRadius && radiusPx > 0 ? Math.min(16, radiusPx + 2) : 0;
      corners.tl.style.borderTopLeftRadius = r + "px";
      corners.tr.style.borderTopRightRadius = r + "px";
      corners.bl.style.borderBottomLeftRadius = r + "px";
      corners.br.style.borderBottomRightRadius = r + "px";
    };

    const lockToTarget = (target) => {
      activeTarget = target;
      root.classList.add("is-locked", "is-visible");

      cachedRect = target.getBoundingClientRect();
      const targetW = cachedRect.width + cfg.padding * 2;
      const targetH = cachedRect.height + cfg.padding * 2;
      const cx = cachedRect.left + cachedRect.width / 2;
      const cy = cachedRect.top + cachedRect.height / 2;

      applyCornerRadius(8);

      if (cfg.showLabel) {
        const txt = resolveLabel(target);
        if (txt) {
          labelEl.textContent = txt;
          labelEl.classList.add("has-text");
        } else {
          labelEl.textContent = "";
          labelEl.classList.remove("has-text");
        }
      }

      root.style.width = targetW + "px";
      root.style.height = targetH + "px";
      root.style.marginLeft = -targetW / 2 + "px";
      root.style.marginTop = -targetH / 2 + "px";
      root.style.transform = `translate3d(${cx}px, ${cy}px, 0)`;
    };

    const unlockTarget = () => {
      if (!activeTarget) return;
      activeTarget = null;
      cachedRect = null;
      root.classList.remove("is-locked", "is-visible");
      labelEl.classList.remove("has-text");
      applyCornerRadius(0);
    };

    // Coalesce pointer events into a single RAF frame without layout thrashing
    const onPointerMove = (ev) => {
      if (ev.pointerType !== "mouse") return;
      lastEventTarget = ev.target;

      if (!pendingRaf) {
        pendingRaf = requestAnimationFrame(() => {
          pendingRaf = 0;
          if (!lastEventTarget) return;

          const hovered = lastEventTarget.closest ? lastEventTarget.closest(cfg.targetSelector) : null;
          if (hovered && hovered !== activeTarget) {
            lockToTarget(hovered);
          } else if (!hovered && activeTarget) {
            unlockTarget();
          }
        });
      }
    };

    global.addEventListener("pointermove", onPointerMove, { passive: true });

    document.addEventListener("mouseleave", () => {
      unlockTarget();
    });

    return { lockToTarget, unlockTarget, config: cfg };
  }

  global.OpenParkTargetCursor = { init: initTargetCursor };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => initTargetCursor());
  } else {
    initTargetCursor();
  }
})(window);
