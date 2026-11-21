/* Handoff scope hide (option c), guard part. Rendered by skills/handoff/scripts/pkg.py layer --kind hide,
   next to the <style id="x-handover-hide"> block that hides the listed selectors with display:none.
   Do not edit the rendered copy: edit pkg.json > hide and render again. App code and data stay unchanged. */
(function () {
  var C = /*@CONFIG@*/{};
  /* 1. Shortcuts of hidden features: stopped silently in the capture phase (no toast: there is no visible way in). */
  function combo(e) {
    return (e.ctrlKey ? 'Ctrl+' : '') + (e.metaKey ? 'Meta+' : '') + (e.altKey ? 'Alt+' : '') + (e.shiftKey ? 'Shift+' : '') + e.key;
  }
  window.addEventListener('keydown', function (e) {
    var k = combo(e);
    if ((C.shortcuts || []).some(function (s) { return s.toLowerCase() === k.toLowerCase(); })) {
      e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
    }
  }, true);
  /* 2. A route of a dropped page opened directly: go to the entry of the package, never show an empty page. */
  var RX = (C.droppedHashes || []).map(function (r) { return new RegExp(r); });
  function guard() {
    if (C.entry && RX.some(function (r) { return r.test(location.hash); })) location.replace(C.entry);
  }
  guard(); window.addEventListener('hashchange', guard);
  /* 3. A default tab or item that is hidden: select the first visible fallback ({"hidden": sel, "fallback": sel}). */
  function defaults() {
    (C.defaults || []).forEach(function (d) {
      var h = document.querySelector(d.hidden), f = document.querySelector(d.fallback);
      if (h && f && h.offsetParent === null && (h.getAttribute('aria-selected') === 'true' || h.classList.contains('active'))) f.click();
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', defaults); else defaults();
})();
