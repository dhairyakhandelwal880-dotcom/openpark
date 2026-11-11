/* React Bits TargetCursor — GSAP Reticle Bracket Cursor for OpenPark */
(function (global) {
  "use strict";

  const DEFAULTS = {
    targetSelector:
      ".cursor-target, button, .lot-card, .chip-btn, .hud-btn, .welcome-dest-card, .autocomplete-item, [data-cursor-label]",
    spinDuration: 2,
    hoverDuration: 0.2,
    size: 36,
    cornerSize: 12,
    thickness: 3,
    padding: 6,
    dotSize: 4,
    cursorColor: "#ffffff",
    cursorColorOnTarget: "#ffffff",
    blendMode: "difference",
    parallaxOn: true,
    matchRadius: true,
    showLabel: true,
    clickEffect: true,
    hideDefaultCursor: true,
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
      ${cfg.hideDefaultCursor ? "html.tc-hide-cursor, html.tc-hide-cursor * { cursor: none !important; }" : ""}
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
        mix-blend-mode: ${cfg.blendMode};
        opacity: 0;
        will-change: transform, width, height;
      }
      #rb-target-cursor.is-visible {
        opacity: 1;
      }
      #rb-target-cursor .tc-dot {
        position: fixed;
        top: 0;
        left: 0;
        width: ${cfg.dotSize}px;
        height: ${cfg.dotSize}px;
        margin-left: -${cfg.dotSize / 2}px;
        margin-top: -${cfg.dotSize / 2}px;
        border-radius: 50%;
        background: ${cfg.cursorColor};
        pointer-events: none;
        z-index: 100000;
      }
      #rb-target-cursor .tc-box {
        position: relative;
        width: 100%;
        height: 100%;
        transform-origin: center center;
        will-change: transform;
      }
      #rb-target-cursor .tc-corner {
        position: absolute;
        width: ${cfg.cornerSize}px;
        height: ${cfg.cornerSize}px;
        border-color: ${cfg.cursorColor};
        border-style: solid;
        transition: border-color ${cfg.hoverDuration}s ease, border-radius ${cfg.hoverDuration}s ease;
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
        bottom: calc(100% + 8px);
        transform: translateX(-50%);
        padding: 2px 8px;
        border-radius: 4px;
        background: ${cfg.cursorColorOnTarget};
        color: #09090b;
        font-family: "JetBrains Mono", ui-monospace, monospace;
        font-size: 10.5px;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        white-space: nowrap;
        opacity: 0;
        pointer-events: none;
        transition: opacity ${cfg.hoverDuration}s ease;
      }
      #rb-target-cursor.is-locked .tc-label.has-text {
        opacity: 1;
      }
      @keyframes tcSpinFallback {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
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

    if (cfg.hideDefaultCursor) {
      document.documentElement.classList.add("tc-hide-cursor");
    }

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

    const dot = document.createElement("div");
    dot.id = "rb-target-cursor-dot";
    dot.style.cssText =
      `position:fixed;top:0;left:0;width:${cfg.dotSize}px;height:${cfg.dotSize}px;` +
      `margin-left:-${cfg.dotSize / 2}px;margin-top:-${cfg.dotSize / 2}px;border-radius:50%;` +
      `background:${cfg.cursorColor};mix-blend-mode:${cfg.blendMode};pointer-events:none;z-index:100000;opacity:0;`;

    document.body.appendChild(root);
    document.body.appendChild(dot);

    const box = root.querySelector(".tc-box");
    const labelEl = root.querySelector(".tc-label");
    const corners = {
      tl: root.querySelector(".tc-tl"),
      tr: root.querySelector(".tc-tr"),
      bl: root.querySelector(".tc-bl"),
      br: root.querySelector(".tc-br"),
    };

    let mouseX = global.innerWidth / 2;
    let mouseY = global.innerHeight / 2;
    let activeTarget = null;
    let spinTween = null;

    const startSpin = () => {
      if (!cfg.spinDuration || cfg.spinDuration <= 0) return;
      if (global.gsap) {
        if (spinTween) spinTween.kill();
        spinTween = global.gsap.to(box, {
          rotation: "+=360",
          duration: cfg.spinDuration,
          repeat: -1,
          ease: "none",
        });
      } else {
        box.style.animation = `tcSpinFallback ${cfg.spinDuration}s linear infinite`;
      }
    };

    const stopSpin = () => {
      if (spinTween) {
        spinTween.kill();
        spinTween = null;
      }
      box.style.animation = "none";
      if (global.gsap) {
        global.gsap.to(box, { rotation: 0, duration: cfg.hoverDuration, ease: "power2.out" });
      } else {
        box.style.transform = "rotate(0deg)";
      }
    };

    startSpin();

    const applyCornerRadius = (radiusPx) => {
      const r = cfg.matchRadius && radiusPx > 0 ? Math.min(18, radiusPx + Math.round(cfg.padding / 2)) : 0;
      corners.tl.style.borderTopLeftRadius = r + "px";
      corners.tr.style.borderTopRightRadius = r + "px";
      corners.bl.style.borderBottomLeftRadius = r + "px";
      corners.br.style.borderBottomRightRadius = r + "px";
    };

    const lockToTarget = (target) => {
      activeTarget = target;
      root.classList.add("is-locked");
      stopSpin();

      const rect = target.getBoundingClientRect();
      const targetW = rect.width + cfg.padding * 2;
      const targetH = rect.height + cfg.padding * 2;
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;

      const cs = global.getComputedStyle(target);
      const rawRadius = parseFloat(cs.borderTopLeftRadius || "0") || 0;
      applyCornerRadius(rawRadius);

      if (cfg.showLabel) {
        const txt = resolveLabel(target);
        labelEl.textContent = txt;
        labelEl.classList.toggle("has-text", Boolean(txt));
      }

      if (global.gsap) {
        global.gsap.to(root, {
          x: cx,
          y: cy,
          marginLeft: -targetW / 2,
          marginTop: -targetH / 2,
          width: targetW,
          height: targetH,
          duration: cfg.hoverDuration,
          ease: "power3.out",
          overwrite: "auto",
        });
      } else {
        root.style.width = targetW + "px";
        root.style.height = targetH + "px";
        root.style.marginLeft = -targetW / 2 + "px";
        root.style.marginTop = -targetH / 2 + "px";
        root.style.transform = `translate3d(${cx}px, ${cy}px, 0)`;
      }
    };

    const unlockTarget = () => {
      if (!activeTarget) return;
      activeTarget = null;
      root.classList.remove("is-locked");
      labelEl.classList.remove("has-text");
      applyCornerRadius(0);
      startSpin();

      if (global.gsap) {
        global.gsap.to(root, {
          x: mouseX,
          y: mouseY,
          marginLeft: -cfg.size / 2,
          marginTop: -cfg.size / 2,
          width: cfg.size,
          height: cfg.size,
          duration: cfg.hoverDuration,
          ease: "power2.out",
          overwrite: "auto",
        });
      } else {
        root.style.width = cfg.size + "px";
        root.style.height = cfg.size + "px";
        root.style.marginLeft = -cfg.size / 2 + "px";
        root.style.marginTop = -cfg.size / 2 + "px";
        root.style.transform = `translate3d(${mouseX}px, ${mouseY}px, 0)`;
      }
    };

    global.addEventListener("pointermove", (ev) => {
      if (ev.pointerType !== "mouse") return;
      mouseX = ev.clientX;
      mouseY = ev.clientY;
      root.classList.add("is-visible");
      dot.style.opacity = "1";

      if (global.gsap) {
        global.gsap.set(dot, { x: mouseX, y: mouseY });
      } else {
        dot.style.transform = `translate3d(${mouseX}px, ${mouseY}px, 0)`;
      }

      const hovered = ev.target && ev.target.closest ? ev.target.closest(cfg.targetSelector) : null;
      if (hovered && hovered !== activeTarget) {
        lockToTarget(hovered);
        return;
      }
      if (!hovered && activeTarget) {
        unlockTarget();
        return;
      }

      if (activeTarget) {
        if (!document.body.contains(activeTarget)) {
          unlockTarget();
          return;
        }
        const rect = activeTarget.getBoundingClientRect();
        let cx = rect.left + rect.width / 2;
        let cy = rect.top + rect.height / 2;
        if (cfg.parallaxOn) {
          cx += Math.max(-5, Math.min(5, (mouseX - cx) * 0.08));
          cy += Math.max(-5, Math.min(5, (mouseY - cy) * 0.08));
        }
        if (global.gsap) {
          global.gsap.to(root, { x: cx, y: cy, duration: 0.12, ease: "power2.out", overwrite: "auto" });
        } else {
          root.style.transform = `translate3d(${cx}px, ${cy}px, 0)`;
        }
      } else {
        if (global.gsap) {
          global.gsap.to(root, { x: mouseX, y: mouseY, duration: 0.12, ease: "power2.out", overwrite: "auto" });
        } else {
          root.style.transform = `translate3d(${mouseX}px, ${mouseY}px, 0)`;
        }
      }
    });

    if (cfg.clickEffect) {
      global.addEventListener("pointerdown", (ev) => {
        if (ev.pointerType !== "mouse") return;
        if (global.gsap) {
          global.gsap.to([root, dot], { scale: 0.84, duration: 0.09, ease: "power2.out" });
        }
      });
      global.addEventListener("pointerup", (ev) => {
        if (ev.pointerType !== "mouse") return;
        if (global.gsap) {
          global.gsap.to([root, dot], { scale: 1, duration: 0.18, ease: "back.out(2)" });
        }
      });
    }

    document.addEventListener("mouseleave", () => {
      root.classList.remove("is-visible");
      dot.style.opacity = "0";
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
