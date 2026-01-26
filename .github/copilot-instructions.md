<!-- .github/copilot-instructions.md generated/updated by assistant -->
# Copilot / AI agent instructions — Vivagoal Photo Finder

Purpose
- Quickly orient AI coding agents to this repo so they can make safe, correct edits.

Big picture
- Single-process Flask app serving a small web UI: [app.py](app.py) creates the app and registers routes.
- Photo indexing & search lives in [catalog.py](catalog.py). It maintains an in-memory `items` index, persists to `photo_catalog.json` and optionally mirrors data into SQLite (`photo_catalog.db`).
- Runtime assets: thumbnails in `thumbs/`, UI in `templates/` and `static/`.

Key workflows & commands
- Dev (foreground): run `start_server.bat 5000` or `python app.py` from project root. See [start_server.bat](start_server.bat) and [README.txt](README.txt).
- Prod: uses Waitress. Example: `waitress-serve --listen=0.0.0.0:5000 app:app` (task provided under workspace task "Run Waitress (production)").
- Scheduled service helper: [scripts/create_tasks.ps1](scripts/create_tasks.ps1) creates Task Scheduler entries used in production.

Important patterns & conventions
- Persistent state: default config saved to `app_config.json` (via `save_settings()` in [config.py](config.py)). When updating via the API (`POST /config`), the code intentionally writes only updated keys (see `save_settings(..., only_keys=...)`) — preserve that behavior.
- Catalog format: `photo_catalog.json` contains a top-level `items` list and a `version` field. Avoid wholesale rewrites that change schema without migration.
- Thumbnails: created on-demand by `CatalogManager.ensure_thumbnail()`; if Pillow (`PIL`) is unavailable the server may serve original images instead. Respect `cfg.thumb_size` and `thumbs/` layout.
- Scanning: `CatalogManager.scan_background()` starts a background thread and updates `scan_state`. Use `/rescan` and `/rescan/status` endpoints to trigger/check progress.
- Search: tokenized haystack search; if SQLite FTS is available it is used. Don't assume FTS is present — code falls back to Python filtering.
- Platform-specific behavior: `open_in_explorer()` is Windows-only and calls `explorer /select,`. Changes should preserve that intent.

Integration points & env var overrides
- Config loader honors env vars: `SOURCE_DIRS`, `CATALOG_FILE`, `DB_FILE`, `THUMBS_DIR`, `LOGS_DIR`, `THUMB_SIZE`, `SEARCH_LIMIT`, `UI_TITLE`, `UI_LOGO_URL` (see [config.py](config.py)).
- Optional libs: `Pillow` (thumbnails/EXIF), `exifread` (fallback EXIF parsing). Code branches depending on availability — prefer installing dependencies in `requirements.txt` when enabling features.

Safe edit guidelines for AI agents
- Prefer minimal, localized changes. Changing JSON schema, route payloads, or `photo_catalog.json` structure requires an explicit migration plan and tests (ask the human).
- When modifying config persistence, keep the `save_settings(..., only_keys=...)` merging behavior to avoid wiping user settings.
- Preserve background scan logic and the scan-state keys (`running`, `started_at`, `completed_at`, `scanned`, `found`, `errors`, `reused`, `message`). Frontend expects these keys.
- When touching thumbnails or image handling, account for the case when `PIL_AVAILABLE` is False.

Files to inspect first for most tasks
- App entry & routes: [app.py](app.py)
- Catalog, scanning, thumbnails, search: [catalog.py](catalog.py)
- Config loading & persistence: [config.py](config.py)
- Runtime settings and examples: [README.txt](README.txt)
- Scripts for production tasks: [scripts/create_tasks.ps1](scripts/create_tasks.ps1)

If you are uncertain
- Ask for clarification before changing the catalog schema or the public API routes (`/search`, `/rescan`, `/thumbnail/<id>`, `/download/<id>`, `/config`).

Quick examples (for human reviewers)
- Trigger a rescan (API): `POST /rescan` → JSON body optionally `{ "sources": ["Z:\\","G:\\"] }`.
- Fetch health: `GET /health`.

Questions? Add a short note in the PR describing why the change is safe for existing `photo_catalog.json` and the expected behavior for `thumbs/` regeneration.

----
Generated/updated to match repository layout on disk. Ask for edits or to expand migration/testing guidance.

Problem list (current known issues)
- Thumbnail generation is still synchronous in `CatalogManager.ensure_thumbnail()` and can block requests; consider adding a background worker or `ThreadPoolExecutor` to generate thumbnails asynchronously (see `catalog.py`).
- Scanning is single-process and single-threaded across source roots; for very large archives this can be slow. Consider parallelizing top-level `source_dirs` or moving the scanner to a separate worker process (`catalog.py` `_scan_sync_fast()`).
- Search currently returns slices and `total` (via `/search`), but there's no server-side caching, rate-limiting, or pagination links; add caching headers and optional rate-limiting middleware in `app.py`.
- No CI/tests: there are no automated tests or GitHub Actions configured. Add pytest unit tests for `catalog` behavior and a CI workflow to run them.
- No migration tooling for `photo_catalog.json` schema changes. Add a small `scripts/catalog_migrate.py` utility and document schema fields.
- Task Scheduler and service-run differences (UNC vs mapped drives) are documented in `README.txt`, but `start_server.bat` doesn't attempt to create venv/deps; consider improving `start_server.bat` to be more robust.
- Observability is minimal: `querylog` exists but structured logs/metrics (scan durations, DB size, thumbnail queue length) would help debugging.

