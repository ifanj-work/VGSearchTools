from __future__ import annotations

import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request, send_file, abort

from config import load_config, save_settings
from catalog import CatalogManager


def create_app() -> Flask:
    app = Flask(__name__)
    cfg = load_config()
    catalog = CatalogManager(cfg)

    # Logging setup
    os.makedirs(cfg.logs_dir, exist_ok=True)
    log_path = os.path.join(cfg.logs_dir, "search.log")
    qlog = logging.getLogger("querylog")
    qlog.setLevel(logging.INFO)
    if not qlog.handlers:
        handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        qlog.addHandler(handler)

    @app.context_processor
    def inject_ui():
        return {"ui_title": catalog.cfg.ui_title, "ui_logo_url": catalog.cfg.ui_logo_url}

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.get("/search")
    def search():
        q = request.args.get("q", "")
        year = request.args.get("year")
        month = request.args.get("month")
        sort = request.args.get("sort") or "date_desc"
        limit = request.args.get("limit")
        offset = request.args.get("offset")
        year_i = int(year) if year and year.isdigit() else None
        month_i = int(month) if month and month.isdigit() else None
        lim = int(limit) if limit and str(limit).isdigit() else None
        off = int(offset) if offset and str(offset).isdigit() else 0

        results, total = catalog.search(q, limit=lim, offset=off, year=year_i, month=month_i, sort=sort)
        # Log query (log total matches, not just returned slice)
        try:
            qlog.info(f"query=%r total=%d returned=%d", q, total, len(results))
        except Exception:
            pass
        # Return minimal fields for listing
        payload = []
        for it in results:
            payload.append(
                {
                    "id": it["id"],
                    "filename": it["filename"],
                    "folder": it["folder"],
                    "date": it.get("date"),
                    "thumb": f"/thumbnail/{it['id']}",
                }
            )
        return jsonify({"results": payload, "total": total, "limit": lim or catalog.cfg.search_limit, "offset": off})

    @app.get("/thumbnail/<item_id>")
    def thumbnail(item_id: str):
        item = catalog.get_item(item_id)
        if not item:
            abort(404)
        path = catalog.ensure_thumbnail(item_id)
        if not os.path.exists(path):
            abort(404)
        # Let Flask infer mimetype from filename (supports fallback-to-original case)
        return send_file(path, as_attachment=False, conditional=True)

    @app.get("/download/<item_id>")
    def download(item_id: str):
        item = catalog.get_item(item_id)
        if not item:
            abort(404)
        path = item.get("path")
        if not path or not os.path.exists(path):
            abort(404)
        return send_file(path, as_attachment=True, download_name=item.get("filename"))

    @app.post("/open")
    def open_in_explorer():
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        item_id = data.get("id")
        if not item_id:
            abort(400)
        ok = catalog.open_in_explorer(item_id)
        return jsonify({"ok": ok})

    @app.post("/rescan")
    def rescan():
        # Optional: allow ad-hoc sources via JSON body
        data = request.get_json(silent=True) or {}
        new_sources = data.get("sources")
        if new_sources:
            if isinstance(new_sources, str):
                # Accept semicolon or comma separated string
                parts = [p.strip() for p in new_sources.replace(",", ";").split(";")]
                new_sources = [p for p in parts if p]
            if isinstance(new_sources, list):
                # Update runtime config immediately
                catalog.cfg.source_dirs = new_sources
        started = catalog.scan_background()
        return jsonify({"started": started, "scan": catalog.scan_state, "sources": catalog.cfg.source_dirs})

    @app.get("/rescan/status")
    def rescan_status():
        return jsonify({"scan": catalog.scan_state})

    @app.get("/health")
    def health():
        return jsonify(catalog.health())

    @app.get("/config")
    def get_config():
        return jsonify({
            "source_dirs": catalog.cfg.source_dirs,
            "lan_filter_subfolder": catalog.cfg.lan_filter_subfolder,
            "thumb_size": catalog.cfg.thumb_size,
            "search_limit": catalog.cfg.search_limit,
            "ui_title": catalog.cfg.ui_title,
            "ui_logo_url": catalog.cfg.ui_logo_url,
        })

    @app.post("/config")
    def set_config():
        data = request.get_json(silent=True) or {}
        persist = bool(data.get("persist", True))
        updated: Dict[str, Any] = {}
        if "source_dirs" in data:
            src = data["source_dirs"]
            if isinstance(src, str):
                parts = [p.strip() for p in src.replace(",", ";").split(";")]
                src = [p for p in parts if p]
            if isinstance(src, list):
                catalog.cfg.source_dirs = src
                updated["source_dirs"] = src
        if "lan_filter_subfolder" in data:
            catalog.cfg.lan_filter_subfolder = data["lan_filter_subfolder"] or None
            updated["lan_filter_subfolder"] = catalog.cfg.lan_filter_subfolder

        if "ui_title" in data:
            catalog.cfg.ui_title = str(data["ui_title"]) or "Vivagoal Photo Finder"
            updated["ui_title"] = catalog.cfg.ui_title

        if "ui_logo_url" in data:
            val = data["ui_logo_url"]
            catalog.cfg.ui_logo_url = (str(val) if val else None)
            updated["ui_logo_url"] = catalog.cfg.ui_logo_url

        # Persist selected settings
        saved = True
        if persist and updated:
            try:
                # Save only keys we updated to avoid overwriting other file content unexpectedly
                saved = save_settings(catalog.cfg, only_keys=list(updated.keys()))
            except Exception:
                saved = False
        return jsonify({"ok": True, "saved": saved, "updated": updated})

    return app


app = create_app()

if __name__ == "__main__":
    # For development; production should use waitress-serve
    app.run(host="0.0.0.0", port=5000, debug=True)
