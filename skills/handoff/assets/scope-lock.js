/* Handoff scope lock (option b). Rendered by skills/handoff/scripts/pkg.py layer --kind lock.
   Do not edit the rendered copy: edit pkg.json > lock and render again.
   Out-of-scope UI stays visible and looks normal. Nothing is disabled, dimmed or restyled:
   a capture-phase listener on window stops the interaction before app code runs, then shows a DS toast. */
(function () {
  var C = /*@CONFIG@*/{};
  var ALLOW = C.allow.join(','), BLOCK = (C.block || []).join(','), PAGES = C.pages || [], KEYS = C.pageKeys || {};
  var INTER = 'a,button,input,textarea,select,summary,label,[role=button],[role=link],[role=menuitem],[role=tab],' +
    '[role=switch],[role=checkbox],[role=option],[tabindex]:not([tabindex="-1"]),[contenteditable=true]';
  var FIELD = 'input:not([type=checkbox]):not([type=radio]):not([type=file]),textarea,select,[contenteditable=true]';
  var T = C.toast || {}, ms = T.ms || 5000, last = 0;

  /* State the package needs on load (pkg.json > lock.seed): keys are set only when absent. */
  ['localStorage', 'sessionStorage'].forEach(function (k) {
    var S = (C.seed || {})[k]; if (!S) return;
    try { Object.keys(S).forEach(function (n) { if (window[k].getItem(n) === null) window[k].setItem(n, String(S[n])); }); } catch (e) {}
  });

  /* Pages are compared as paths relative to the package root, after the URL is resolved (no suffix matching).
     The root is found from the current page: the longest entry of pages that ends the current path. */
  function norm(p) { p = decodeURIComponent(p); return /\/$/.test(p) ? p + 'index.html' : p; }
  var here = norm(location.pathname), ROOT = null;
  PAGES.slice().sort(function (a, b) { return b.length - a.length; }).some(function (p) {
    if (here === '/' + p || here.slice(-p.length - 1) === '/' + p) { ROOT = here.slice(0, here.length - p.length); return true; }
    return false;
  });
  function relPath(href) {
    try {
      var u = new URL(href, location.href);
      if (u.origin !== location.origin) return null;
      var p = norm(u.pathname);
      if (ROOT === null) return p.replace(/^\//, '');
      return p.indexOf(ROOT) === 0 ? p.slice(ROOT.length) : null;
    } catch (e) { return undefined; }
  }
  function inPackage(href) {
    if (!PAGES.length) return true;
    var p = relPath(href);
    if (p === undefined) return true;
    return p !== null && PAGES.indexOf(p) >= 0;
  }
  function condition(w) {
    try {
      return (!w.hash || new RegExp(w.hash).test(location.hash)) && (!w.path || new RegExp(w.path).test(location.pathname));
    } catch (e) { return false; }
  }
  function allowed(el) {
    if (BLOCK && el.closest(BLOCK)) return false;
    var w = (C.allowWhen || []).filter(function (x) { return el.closest(x.sel); });
    if (w.length) return w.every(condition);       /* per-route rule overrides allow */
    var a = el.closest('a[href]');
    if (a && !/^(#|javascript:)/.test(a.getAttribute('href')) && !inPackage(a.href)) return false;
    return !!el.closest(ALLOW);
  }
  function interactive(el) {
    if (el.closest(INTER)) return true;
    for (var n = el, i = 0; n && n.nodeType === 1 && i < 4; n = n.parentElement, i++) {
      if (getComputedStyle(n).cursor === 'pointer') return true;
    }
    return false;
  }
  var X_ICON = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
  function notice() {
    if (window.parent !== window) {
      try { if (window.parent.xHandoverNotice) { window.parent.xHandoverNotice(); return; } } catch (e) {}
    }
    var now = Date.now(); if (now - last < ms && document.querySelector('[data-x-scope]')) return; last = now;
    if (T.function) {
      var parts = T.function.split('.'), fn = window, ctx = window;
      parts.forEach(function (p) { ctx = fn; fn = fn && fn[p]; });
      if (typeof fn === 'function') { fn.apply(ctx, [C.msg].concat(T.args || [])); return; }
    }
    var box = (T.container && document.querySelector(T.container)) || document.body;
    var old = box.querySelector('[data-x-scope]'); if (old) old.remove();
    var el = document.createElement('div');
    el.className = T.class || ''; el.setAttribute('role', 'status'); el.setAttribute('data-x-scope', '');
    if (T.icon) el.insertAdjacentHTML('beforeend', T.icon);
    var s = document.createElement('span'); s.textContent = C.msg; el.appendChild(s);
    var b = document.createElement('button'); b.type = 'button'; b.className = T.close_class || '';
    b.setAttribute('aria-label', C.close); b.title = C.close; b.innerHTML = T.close_html || X_ICON;
    b.addEventListener('click', function () { el.remove(); }); el.appendChild(b);
    box.appendChild(el); setTimeout(function () { el.remove(); }, ms);
  }
  window.xHandoverNotice = notice;
  function stop(e) { e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation(); notice(); }
  function out(el) { return el && el.nodeType === 1 && !allowed(el) && interactive(el); }

  window.addEventListener('click', function (e) { if (out(e.target)) stop(e); }, true);
  window.addEventListener('keydown', function (e) {
    if ((e.key === 'Enter' || e.key === ' ') && out(e.target) && !e.target.matches('input,textarea')) stop(e);
  }, true);
  window.addEventListener('pointerdown', function (e) {
    var el = e.target; if (el && el.nodeType === 1 && el.closest(FIELD) && !allowed(el)) { e.preventDefault(); notice(); }
  }, true);
  window.addEventListener('focusin', function (e) {
    var el = e.target; if (el && el.nodeType === 1 && el.matches(FIELD) && !allowed(el)) { el.blur(); notice(); }
  }, true);
  /* Shortcuts of features outside the scope (pkg.json > lock.shortcuts, e.g. "F1", "Ctrl+k"): toast. */
  function combo(e) {
    return (e.ctrlKey ? 'Ctrl+' : '') + (e.metaKey ? 'Meta+' : '') + (e.altKey ? 'Alt+' : '') + (e.shiftKey ? 'Shift+' : '') + e.key;
  }
  window.addEventListener('keydown', function (e) {
    var k = combo(e).toLowerCase();
    if ((C.shortcuts || []).some(function (x) { return x.toLowerCase() === k; })) stop(e);
  }, true);
  /* Drag and drop: dragover/dragenter outside the scope are stopped too, so no drop zone lights up. */
  ['drop', 'paste'].forEach(function (k) {
    window.addEventListener(k, function (e) { if (e.target.closest && !allowed(e.target)) stop(e); }, true);
  });
  ['dragover', 'dragenter'].forEach(function (k) {
    window.addEventListener(k, function (e) {
      if (e.target.closest && !allowed(e.target)) { e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation(); }
    }, true);
  });

  /* Fallback: navigation by code. Wrap the app's global navigation functions (pkg.json > lock.nav_functions,
     e.g. "routeOpen" or "appNav.go"); the first argument is a page key (pkg.json > lock.page_keys maps keys to
     files) or a URL. */
  function targetOk(target) {
    if (!PAGES.length || typeof target !== 'string') return true;
    if (Object.prototype.hasOwnProperty.call(KEYS, target)) return PAGES.indexOf(KEYS[target]) >= 0;
    if (PAGES.indexOf(target) >= 0) return true;   /* page keys listed in pages (before page_keys existed) */
    return inPackage(target);
  }
  function wrap() {
    (C.navFunctions || []).forEach(function (path) {
      var parts = path.split('.'), name = parts.pop(), obj = window;
      parts.forEach(function (p) { obj = obj && obj[p]; });
      if (!obj || typeof obj[name] !== 'function' || obj[name]._xScope) return;
      var fn = obj[name];
      obj[name] = function (target) {
        if (!targetOk(target)) { notice(); return; }
        return fn.apply(this, arguments);
      };
      obj[name]._xScope = 1;
    });
  }
  wrap(); document.addEventListener('DOMContentLoaded', wrap);
  /* window.open: a page of the package (resolved URL) is always allowed; open_allow (regex) adds more,
     tested on the URL as written and as resolved. */
  var open = window.open, OK = C.openAllow ? new RegExp(C.openAllow) : null;
  window.open = function (u) {
    var raw = String(u == null ? '' : u), abs;
    try { abs = new URL(raw, location.href).href; } catch (e) { abs = raw; }
    var mine = PAGES.length ? inPackage(raw) : !OK;   /* no pages listed: open_allow alone decides, as before */
    if (!raw || mine || (OK && (OK.test(raw) || OK.test(abs)))) return open.apply(window, arguments);
    notice(); return null;
  };
})();
