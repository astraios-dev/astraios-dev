# astraios.tech

Source for the Astraios website and pitch deck. The built site lives in
`site/`, which is what nginx serves at https://astraios.tech (fronted by
Cloudflare).

Astraios is a quantitative ML platform: ranked market signals for retail
traders and a paper-first auto-trading API for developers.

## What lives where

```
.
├── app/                          # React source (the thing you actually edit)
│   ├── index.html                # Vite entry template
│   └── src/
│       ├── App.jsx               # Sections, copy, team, nav
│       ├── styles.css            # Design tokens (dark theme), layout, responsive
│       └── main.jsx              # React root
├── public/                       # Raw assets copied verbatim into site/ by the build
│   ├── astraios-*-mask.png, astraios-system-map.png, favicons, icons
│   └── deck/
│       ├── index.html            # Standalone 11-slide pitch deck (keyboard + mouse)
│       └── astraios-pitch-deck.pdf   # Exported PDF, linked from the deck footer
├── scripts/
│   └── generate-visual-assets.mjs
├── site/                         # Build output — what nginx serves. Committed.
│   ├── index.html                # Regenerated every build
│   ├── assets/index-*.{css,js}   # Hashed bundles; old ones wiped each build
│   └── (public/ contents copied here verbatim)
├── package.json                  # Vite + React 19
└── vite.config.js
```

## Local development

```bash
npm install
npm run dev          # vite dev server on 127.0.0.1
```

Edits go into `app/src/` (or `public/` for raw assets and the deck). Never
hand-edit anything in `site/` — it's regenerated every build.

## Production build

```bash
npm run build
```

Vite writes the build directly into `site/` with `emptyOutDir: true`, so
stale bundles from previous builds get wiped. Commit the regenerated
`site/` tree — nginx serves it directly, no reload needed.

## Pitch deck

`/deck/` is a single hand-written HTML file — no build step. Edit
`public/deck/index.html` directly; the build copies it into `site/deck/`.

**Keyboard:** `→` / `Space` / `PageDown` advance · `←` / `PageUp` go back ·
`Home` / `End` jump to first/last.

**Deep-links:** `/deck/#4` opens slide 4.

### Exporting the PDF

Headless Chrome prints the deck against the site's own origin so the
mask-based logo and wordmark resolve correctly. Build first so `site/deck/`
is up to date:

```bash
# 0. Ensure site/ is current
npm run build

# 1. Serve site/ on a local port
python3 -m http.server 8731 --bind 127.0.0.1 --directory site &

# 2. Print to PDF (written back into the source copy under public/)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new \
  --disable-gpu \
  --no-pdf-header-footer \
  --hide-scrollbars \
  --virtual-time-budget=2500 \
  --print-to-pdf=public/deck/astraios-pitch-deck.pdf \
  http://127.0.0.1:8731/deck/

# 3. Stop the server, then rebuild so site/deck/ picks up the new PDF
pkill -f "python3 -m http.server 8731"
npm run build
```

Output is 11 pages at 1200×675 pt (16:9). The deck's `@media print` rules
hide the header/footer chrome and force every grid back to its intended
column count.

## Design language

- Dark palette — `--paper: #050505`, `--ink: #ffffff`, `--muted: #9a9a97`,
  `--line: #2a2a2a`.
- Georgia serif for display type (h1 / h2 / stat values); Inter for body.
- 96px vertical grid-line background across the `.site` and `.deck` shells.
- Numbered section labels with a trailing rule (`.section-label`, `.slide__label`).
- 1px-gap split grids for multi-panel sections (architecture, protocol,
  team, roadmap) — no shadows, no corner radii beyond `--radius: 6px` on
  action buttons and app-icon tiles.
- Status pill with pulsing dot in the header.

## Deployment

`site/` is what nginx serves on `astraios.tech`. The server config lives
at `/etc/nginx/sites-available/static-site.conf` with
`root /home/ubuntu/astraios-dev/site`. TLS is terminated at nginx via a
Let's Encrypt certificate (auto-renewed by certbot's systemd timer);
Cloudflare fronts the site with SSL mode set to Full (strict). After
`npm run build` the site is live — no additional deploy step. Commit the
updated `site/` tree together with your source edits under `app/` or
`public/`.

## Rollback

The repo is tagged at each known-good state. To roll back the served site:

```bash
git reset --hard v1.0-dark-theme
```

`v1.0-dark-theme` captures the dark-theme site + deck + PDF export as of the
initial commit. Add a new tag (`git tag -a vX.Y -m "..."`) before any risky
change you want a one-command restore path to.

## What is not tracked

- `node_modules/` — run `npm install` to recreate.
- `.claude/settings.local.json` — per-machine Claude Code permissions.
- `.backups/` — local-only tarball backups, if any.
- `.DS_Store` — macOS cruft.
