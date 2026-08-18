# AGENTS.md

## Project

People Counter: FastAPI backend (`src/`) + vanilla HTML/CSS/JS dashboard (`web/`). YOLO person detection + line-crossing counting, with video-file and ONVIF IP-camera sources.

## Design system (client-facing — keep it this way)

The dashboard is for a non-technical client. It must look like a product, not a terminal.

### Principles
- Plain language. No jargon: no "telemetry", "calibration geometry", "pipeline", "FPS/latency", no "north_to_south". Say "People in", "Set counting line", "Which way do people move when they enter?".
- The three counts are the hero: big, tabular-nums, high-contrast. Controls live in a slim sidebar.
- Fewer decisions per panel. Prefer visual controls (arrow grids, segmented toggles, chips) over dropdowns + explanatory paragraphs + Save buttons.
- One card level max — never cards nested in cards. Avoid walls of text next to controls.

### Tokens (in `web/style.css`)
- Font: Plus Jakarta Sans only (no mono except none). Set on `:root`.
- Light + dark theme via `:root[data-theme="dark"]` variable overrides. Toggle button + `localStorage` in `app.js` (`setupTheme`). Add new colors as variables, never hardcode.
- Palette: warm paper `--bg #f6f4f1`, white `--surface`, charcoal `--ink #28231d`. Accents: in `--in #2f9e63`, out `--out #e0654f`, current `--current #d97706`, each with a `-soft` tint.
- Radius: 16px cards, 10px controls, 999px pills. Single soft shadow.

### i18n
- EN/FR via `data-i18n="key"` attributes + the `I18N` dictionary in `app.js` (`t(key, ...params)`). New user-facing strings MUST be added to both `en` and `fr` and referenced via `t()` or a `data-i18n` attribute — never hardcoded.

### Impeccable anti-patterns to avoid
- No purple-to-blue gradients, no Inter, no gray text on colored backgrounds, no nested cards, no bounce/elastic easing, no pure black (`#000`) — always tinted.

### Component vocabulary
- Buttons: `.btn`, `.btn-dark` (primary), `.btn-success`, `.btn-ghost`, `.btn-block`. Focus-visible outline required.
- Selects/inputs: `.control-select`, `.control-input` (rounded, bordered, green focus ring).
- Chips/segments: `.seg`, `.seg-btn`, `.camera-chip`, `.profile-chip`, `.dir-btn`, `.line-pill`.

## Backend notes
- `web/` is served statically by FastAPI; frontend talks to `/api/*` and `/ws/*`.
- Camera flow: `GET /api/cameras` (discover) → `POST /api/cameras/profiles` (credentials) → `POST /api/cameras/connect` (`profile_token`). Blocking ONVIF calls run via `run_in_executor`.
- Server starts with no source (`--source` omitted) and waits until one is chosen in the UI.

## Checks
- Frontend JS: `node --check web/app.js`
- Backend tests: `.venv\Scripts\python.exe -m unittest discover -s tests`