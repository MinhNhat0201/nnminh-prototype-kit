/* Shared script of every page: theming attributes and a small hash router.
   Source: _shell/shell.js. Edit it here, then run python3 _shell/build.py build. */
(function () {
  'use strict';
  var APP = '{{APP_ID}}';
  var THEMING = {{THEMING_JSON}};          // ds.json > theming
  var root = document.documentElement;

  function store(key, value) { try { localStorage.setItem(APP + ':' + key, value); } catch (e) {} }
  function stored(key) { try { return localStorage.getItem(APP + ':' + key); } catch (e) { return null; } }
  function setTheming(key, value, save) {
    var t = THEMING[key];
    if (!t || !t.attr) return;
    root.setAttribute(t.attr, value);
    if (save !== false) store(key, value);
  }
  Object.keys(THEMING).forEach(function (key) {
    var t = THEMING[key], v = stored(key);
    if (t && t.attr && v && (!t.values || t.values.indexOf(v) >= 0)) setTheming(key, v, false);
  });

  var mode = THEMING.mode;
  var modeBtn = document.getElementById('modeBtn');
  if (modeBtn) {
    if (!mode || !mode.attr || !mode.values || mode.values.length < 2) modeBtn.hidden = true;
    else modeBtn.addEventListener('click', function () {
      var light = mode.default || mode.values[0];
      var dark = mode.values.indexOf('dark') >= 0 ? 'dark' : mode.values.filter(function (v) { return v !== light; })[0];
      setTheming('mode', root.getAttribute(mode.attr) === dark ? light : dark);
    });
  }

  /* Hash router for the screens inside one page: #/ is the default, unknown hash goes to #/,
     Back and Forward work without reload. routes: [{ path: '/', title, render(params) -> Node }] */
  function router(routes, view, appName) {
    function match(path) {
      for (var i = 0; i < routes.length; i++) {
        var names = [];
        var rx = new RegExp('^' + routes[i].path.replace(/:([\w]+)/g, function (_, n) { names.push(n); return '([^/]+)'; }) + '/?$');
        var m = rx.exec(path);
        if (m) {
          var params = {};
          names.forEach(function (n, j) { params[n] = decodeURIComponent(m[j + 1]); });
          return { route: routes[i], params: params };
        }
      }
      return null;
    }
    function render() {
      var hit = match(location.hash.replace(/^#/, '') || '/');
      if (!hit) { location.replace('#/'); return; }
      view.replaceChildren(hit.route.render(hit.params));
      document.title = hit.route.title + ' · ' + appName;
      window.scrollTo(0, 0);
    }
    window.addEventListener('hashchange', render);
    render();
  }

  window.APP_SHELL = { app: APP, theming: THEMING, setTheming: setTheming, router: router };
})();
