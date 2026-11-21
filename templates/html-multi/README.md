# Multi-page app (`html`, type `multi`)

One HTML file per feature, one shared shell. Every page opens on its own from a folder (no server needed).

```
apps/<app>/
  index.html              home page
  <feature>/index.html    one folder per feature (slug: lowercase, hyphens)
  _shell/
    shell.json            page list: id, title, file, icon; drives the navigation
    shell.css             shared app CSS (shell layout, shared local blocks)
    top.html, foot.html   top bar + navigation, footer with the version label
    shell.js              theming attributes and the hash router (window.APP_SHELL)
    build.py              writes the shell into every page: build | check
```

## Rules

- Each page keeps its own copy of the DS CSS between the `ds.json > css.marker` comments and its own `<meta name="<version_label.meta>">`. `sync` updates them.
- Never edit between `<!-- SHELL:x -->` and `<!-- /SHELL:x -->`: edit the file in `_shell/`, then run `python3 apps/<app>/_shell/build.py build`.
- Before a handoff or PR, `python3 apps/<app>/_shell/build.py check` must print `Shell OK`.
- In `kit.config.json`, set the app's `build` to `python3 apps/<app>/_shell/build.py build` and `check` to `python3 apps/<app>/_shell/build.py check`.

## Add a page (after the new-page gate of `prototype`)

1. Copy `settings/index.html` to `<slug>/index.html`; change its title, page template and routes.
2. Add `{ "id", "title", "file": "<slug>/index.html", "icon" }` to `_shell/shell.json` (`"nav": false` hides it from the navigation).
3. Run `build`, then `check`.
4. Links between pages use relative paths to the file (`../<slug>/index.html#/`), never a site URL.
