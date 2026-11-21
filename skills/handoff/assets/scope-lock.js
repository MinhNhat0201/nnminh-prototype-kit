/* Handoff scope lock (option b). Rendered by skills/handoff/scripts/pkg.py layer --kind lock.
   Do not edit the rendered copy: edit pkg.json > lock and render again.
   Out-of-scope UI stays visible and looks normal. Nothing is disabled, dimmed or restyled:
   a capture-phase listener on window stops the interaction before app code runs, then shows a DS toast. */
(function () {
  var C = /*@CONFIG@*/{};
  var ALLOW = C.allow.join(','), BLOCK = (C.block || []).join(',');
  var INTER = 'a,button,input,textarea,select,summary,label,[role=button],[role=link],[role=menuitem],[role=tab],' +
    '[role=switch],[role=checkbox],[role=option],[tabindex]:not([tabindex="-1"]),[contenteditable=true]';
  var FIELD = 'input:not([type=checkbox]):not([type=radio]):not([type=file]),textarea,select,[contenteditable=true]';
  var T = C.toast || {}, ms = T.ms || 5000, last = 0;

  function pageOf(href) {
    try { var u = new URL(href, location.href); return u.pathname.split('/').filter(Boolean).slice(-2).join('/'); }
    catch (e) { return null; }
  }
  function inPackage(href) {
    if (!C.pages || !C.pages.length) return true;
    var p = pageOf(href); if (p === null) return true;
    return C.pages.some(function (x) { return p === x || p.slice(-x.length - 1) === '/' + x || p === x.split('/').pop(); });
  }
  function allowed(el) {
    if (BLOCK && el.closest(BLOCK)) return false;
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
  function notice() {
    if (window.parent !== window) {
      try { if (window.parent.xHandoverNotice) { window.parent.xHandoverNotice(); return; } } catch (e) {}
    }
    var now = Date.now(); if (now - last < ms && document.querySelector('[data-x-scope]')) return; last = now;
    if (T.function && typeof window[T.function] === 'function') { window[T.function](C.msg); return; }
    var box = (T.container && document.querySelector(T.container)) || document.body;
    var old = box.querySelector('[data-x-scope]'); if (old) old.remove();
    var el = document.createElement('div');
    el.className = T.class || ''; el.setAttribute('role', 'status'); el.setAttribute('data-x-scope', '');
    var s = document.createElement('span'); s.textContent = C.msg; el.appendChild(s);
    var b = document.createElement('button'); b.type = 'button'; b.className = T.close_class || '';
    b.setAttribute('aria-label', C.close); b.textContent = '×';
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
  ['drop', 'paste'].forEach(function (k) {
    window.addEventListener(k, function (e) { if (e.target.closest && !allowed(e.target)) stop(e); }, true);
  });

  /* Fallback: navigation by code. Wrap the app's global navigation functions (pkg.json > lock.nav_functions,
     e.g. "routeOpen" or "appNav.go"); the first argument is the page key or URL. */
  function wrap() {
    (C.navFunctions || []).forEach(function (path) {
      var parts = path.split('.'), name = parts.pop(), obj = window;
      parts.forEach(function (p) { obj = obj && obj[p]; });
      if (!obj || typeof obj[name] !== 'function' || obj[name]._xScope) return;
      var fn = obj[name];
      obj[name] = function (target) {
        if (C.pages && C.pages.length && typeof target === 'string' && !inPackage(target) && C.pages.indexOf(target) < 0) {
          notice(); return;
        }
        return fn.apply(this, arguments);
      };
      obj[name]._xScope = 1;
    });
  }
  wrap(); document.addEventListener('DOMContentLoaded', wrap);
  var open = window.open, OK = C.openAllow ? new RegExp(C.openAllow) : null;
  window.open = function (u) {
    if ((OK && OK.test(String(u))) || (!OK && inPackage(String(u)))) return open.apply(window, arguments);
    notice(); return null;
  };
})();
