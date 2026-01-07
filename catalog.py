from __future__ import annotations

import json
import os
import threading
import hashlib
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from PIL import Image, UnidentifiedImageError  # type: ignore

    PIL_AVAILABLE = True
except Exception:
    Image = None  # type: ignore
    UnidentifiedImageError = Exception  # type: ignore
    PIL_AVAILABLE = False

try:
    import exifread  # type: ignore

    EXIFREAD_AVAILABLE = True
except Exception:
    exifread = None  # type: ignore
    EXIFREAD_AVAILABLE = False

from config import AppConfig


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def stable_id_for_path(path: str) -> str:
    """Stable hex id based on abs path (case-insensitive on Windows) + size + mtime."""
    try:
        st = os.stat(path)
        basis = f"{os.path.abspath(path).lower()}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8")
    except OSError:
        basis = os.path.abspath(path).lower().encode("utf-8")
    return hashlib.sha1(basis).hexdigest()


class CatalogManager:
    def __init__(self, config: AppConfig):
        self.cfg = config
        self.items: Dict[str, Dict[str, Any]] = {}
        self.path_by_id: Dict[str, str] = {}
        self.id_by_path: Dict[str, str] = {}
        self.scan_lock = threading.Lock()
        self.scan_thread: Optional[threading.Thread] = None
        self.scan_state: Dict[str, Any] = {
            "running": False,
            "started_at": None,
            "completed_at": None,
            "scanned": 0,
            "found": 0,
            "errors": 0,
            "reused": 0,
            "message": "idle",
        }
        os.makedirs(self.cfg.thumbs_dir, exist_ok=True)
        os.makedirs(self.cfg.logs_dir, exist_ok=True)
        self._load_catalog()
        self._init_db()

    # ---------- Persistence ----------
    def _load_catalog(self) -> None:
        if not os.path.exists(self.cfg.catalog_file):
            return
        try:
            with open(self.cfg.catalog_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_items = data.get("items", []) or []
            for it in raw_items:
                if "haystack" not in it:
                    it["haystack"] = self._make_haystack(it)
            self.items = {it["id"]: it for it in raw_items}
            self._rebuild_indexes()
        except Exception:
            self.items = {}
            self.path_by_id = {}
            self.id_by_path = {}

    def _save_catalog(self) -> None:
        data = {
            "version": 1,
            "updated_at": _now_iso(),
            "count": len(self.items),
            "items": list(self.items.values()),
        }
        tmp = self.cfg.catalog_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, self.cfg.catalog_file)

    # ---------- SQLite (optional, for fast search) ----------
    def _init_db(self) -> None:
        self.db_enabled = False
        self.db_path = self.cfg.db_file
        try:
            self.db_conn = sqlite3.connect(self.db_path, check_same_thread=False)
        except Exception:
            self.db_conn = None
            return

        try:
            cur = self.db_conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS photos (
                    id TEXT PRIMARY KEY,
                    path TEXT,
                    filename TEXT,
                    folder TEXT,
                    size INTEGER,
                    mtime INTEGER,
                    date TEXT,
                    year INTEGER,
                    month INTEGER,
                    ext TEXT
                )
                """
            )
            # FTS5 for fast keyword search (fallback to in-memory if unavailable)
            cur.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS photos_fts USING fts5(id, haystack)"
            )
            self.db_conn.commit()
            self.db_enabled = True
        except Exception:
            self.db_enabled = False
            try:
                self.db_conn.close()
            except Exception:
                pass
            self.db_conn = None

        if self.db_enabled:
            # If DB is empty but we have items from JSON, seed it
            try:
                cur = self.db_conn.cursor()
                cur.execute("SELECT COUNT(1) FROM photos")
                count = cur.fetchone()[0]
                if count == 0 and self.items:
                    self._db_sync(self.items, set())
            except Exception:
                pass

    def _db_sync(self, items: Dict[str, Dict[str, Any]], removed_ids: set[str]) -> None:
        if not self.db_enabled or not self.db_conn:
            return
        try:
            cur = self.db_conn.cursor()
            cur.execute("BEGIN")
            if items:
                rows = [
                    (
                        it["id"],
                        it.get("path", ""),
                        it.get("filename", ""),
                        it.get("folder", ""),
                        int(it.get("size", 0)),
                        int(it.get("mtime", 0)),
                        it.get("date", ""),
                        int(it.get("year", 0)),
                        int(it.get("month", 0)),
                        it.get("ext", ""),
                    )
                    for it in items.values()
                ]
                cur.executemany(
                    """
                    INSERT OR REPLACE INTO photos
                    (id, path, filename, folder, size, mtime, date, year, month, ext)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                fts_rows = [(it["id"], it.get("haystack", "")) for it in items.values()]
                cur.executemany(
                    "INSERT OR REPLACE INTO photos_fts (id, haystack) VALUES (?, ?)", fts_rows
                )
            if removed_ids:
                del_rows = [(rid,) for rid in removed_ids]
                cur.executemany("DELETE FROM photos WHERE id = ?", del_rows)
                cur.executemany("DELETE FROM photos_fts WHERE id = ?", del_rows)
            self.db_conn.commit()
        except Exception:
            try:
                self.db_conn.rollback()
            except Exception:
                pass

    def _fts_query(self, tokens: List[str]) -> str:
        safe = []
        for t in tokens:
            cleaned = "".join(ch for ch in t if ch.isalnum() or ch in ("_", "-", "."))
            if cleaned:
                safe.append(f"{cleaned}*")
        return " AND ".join(safe)

    def _rebuild_indexes(self) -> None:
        self.path_by_id = {k: v.get("path", "") for k, v in self.items.items()}
        self.id_by_path = {}
        for item_id, path in self.path_by_id.items():
            if not path:
                continue
            norm = self._norm_path(path)
            self.id_by_path[norm] = item_id

    def _make_haystack(self, item: Dict[str, Any]) -> str:
        return " ".join(
            [
                str(item.get("filename", "")),
                str(item.get("folder", "")),
                str(item.get("year", "")),
                f"{item.get('month', ''):02d}",
                str(item.get("date", "")),
            ]
        ).lower()

    @staticmethod
    def _norm_path(path: str) -> str:
        if not path:
            return ""
        return os.path.normcase(os.path.abspath(path))

    @staticmethod
    def _is_metadata_current(item: Dict[str, Any], st: os.stat_result) -> bool:
        return int(item.get("mtime", 0)) == int(st.st_mtime) and int(item.get("size", 0)) == int(st.st_size)

    # ---------- Scanning ----------
    def scan_background(self) -> bool:
        if self.scan_state["running"]:
            return False
        t = threading.Thread(target=self._scan_safe, name="catalog-scan", daemon=True)
        self.scan_thread = t
        t.start()
        return True

    def _scan_safe(self) -> None:
        if not self.scan_lock.acquire(blocking=False):
            return
        try:
            self.scan_state.update(
                {
                    "running": True,
                    "started_at": _now_iso(),
                    "completed_at": None,
                    "scanned": 0,
                    "found": 0,
                    "errors": 0,
                    "message": "scanning",
                }
            )
            self._scan_sync_fast()
            self.scan_state.update(
                {
                    "running": False,
                    "completed_at": _now_iso(),
                    "message": "done",
                }
            )
        except Exception as e:
            self.scan_state.update(
                {
                    "running": False,
                    "completed_at": _now_iso(),
                    "message": f"error: {e}",
                }
            )
        finally:
            try:
                self._save_catalog()
            finally:
                self.scan_lock.release()

    def _scan_sync(self) -> None:
        # Legacy wrapper; delegate to optimized scanner
        return self._scan_sync_fast()

    def _scan_sync_fast(self) -> None:
        """Optimized scanner using scandir and reuse of unchanged items."""
        new_items: Dict[str, Dict[str, Any]] = {}
        scanned = 0
        found = 0
        errors = 0
        reused = 0
        filtersub = (self.cfg.lan_filter_subfolder or "").lower()

        old_ids = set(self.items.keys())
        existing_by_path = {self._norm_path(v.get("path", "")): v for v in self.items.values()}

        def walk_dir(base_path: str) -> None:
            nonlocal scanned, found, errors, reused
            stack: List[str] = [base_path]
            while stack:
                current = stack.pop()
                scanned += 1
                self.scan_state["scanned"] = scanned
                if filtersub and filtersub not in current.lower():
                    continue
                try:
                    with os.scandir(current) as it:
                        entries = list(it)
                except OSError:
                    continue
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext not in self.cfg.extensions:
                            continue
                        st = entry.stat(follow_symlinks=False)
                        norm = self._norm_path(entry.path)
                        prev = existing_by_path.get(norm)
                        if prev and self._is_metadata_current(prev, st):
                            if not prev.get("haystack"):
                                prev["haystack"] = self._make_haystack(prev)
                            new_items[prev["id"]] = prev
                            reused += 1
                            if reused % 500 == 0:
                                self.scan_state["reused"] = reused
                            continue
                        item = self._build_item(entry.path, stat=st)
                        new_items[item["id"]] = item
                        found += 1
                        if found % 200 == 0:
                            self.scan_state["found"] = found
                    except Exception:
                        errors += 1
                        self.scan_state["errors"] = errors

        for base in self.cfg.source_dirs:
            if not base:
                continue
            try:
                if not os.path.exists(base):
                    continue
            except Exception:
                continue
            walk_dir(base)
        removed_ids = old_ids - set(new_items.keys())
        self._db_sync(new_items, removed_ids)
        self.items = new_items
        self._rebuild_indexes()
        self.scan_state["found"] = found
        self.scan_state["errors"] = errors
        self.scan_state["reused"] = reused

    # ---------- Item helpers ----------
    def _build_item(self, path: str, stat: os.stat_result | None = None) -> Dict[str, Any]:
        st = stat or os.stat(path)
        fid = stable_id_for_path(path)
        folder = os.path.dirname(path)
        fname = os.path.basename(path)
        date_taken = self._read_exif_date(path) or datetime.fromtimestamp(st.st_mtime)
        date_str = date_taken.strftime("%Y-%m-%d")
        year = date_taken.year
        month = date_taken.month
        item = {
            "id": fid,
            "path": path,
            "filename": fname,
            "folder": folder,
            "size": int(st.st_size),
            "mtime": int(st.st_mtime),
            "date": date_str,
            "year": year,
            "month": month,
            "ext": os.path.splitext(fname)[1].lower(),
        }
        item["haystack"] = self._make_haystack(item)
        return item

    def _read_exif_date(self, path: str) -> Optional[datetime]:
        if PIL_AVAILABLE and Image is not None:  # type: ignore
            try:
                with Image.open(path) as im:  # type: ignore
                    exif = getattr(im, "_getexif", lambda: None)() or {}
                    dt = exif.get(36867) or exif.get(306)  # DateTimeOriginal / DateTime
                    if isinstance(dt, bytes):
                        dt = dt.decode(errors="ignore")
                    if isinstance(dt, str) and dt.strip():
                        try:
                            return datetime.strptime(dt, "%Y:%m:%d %H:%M:%S")
                        except Exception:
                            pass
            except (UnidentifiedImageError, OSError, AttributeError):
                return None
        if EXIFREAD_AVAILABLE and exifread is not None:
            try:
                with open(path, "rb") as f:
                    tags = exifread.process_file(f, details=False, stop_tag="EXIF DateTimeOriginal")
                dt = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
                if dt:
                    s = str(dt)
                    try:
                        return datetime.strptime(s, "%Y:%m:%d %H:%M:%S")
                    except Exception:
                        pass
            except Exception:
                return None
        return None

    # ---------- Thumbnails ----------
    def ensure_thumbnail(self, item_id: str) -> str:
        item = self.items.get(item_id)
        if not item:
            raise FileNotFoundError("Item not found")
        src = item["path"]
        if not PIL_AVAILABLE or Image is None:
            return src
        thumb = os.path.join(self.cfg.thumbs_dir, f"{item_id}.jpg")
        try:
            if os.path.exists(thumb):
                tstat = os.stat(thumb)
                if tstat.st_mtime >= item["mtime"]:
                    return thumb
        except OSError:
            pass
        try:
            with Image.open(src) as im:  # type: ignore
                im.load()
                im = im.convert("RGB")
                im.thumbnail((self.cfg.thumb_size, self.cfg.thumb_size))
                im.save(thumb, format="JPEG", quality=85)
        except Exception:
            try:
                if PIL_AVAILABLE and Image is not None:
                    img = Image.new("RGB", (64, 64), color=(30, 30, 35))  # type: ignore
                    img.save(thumb, format="JPEG", quality=70)
                    return thumb
            except Exception:
                pass
            return src
        return thumb

    # ---------- Search ----------
    def search(
        self,
        query: str,
        limit: Optional[int] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        sort: str = "date_desc",
    ) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        tokens = [t for t in q.lower().split() if t]
        lim = limit or self.cfg.search_limit

        def matches(it: Dict[str, Any]) -> bool:
            if year and it.get("year") != year:
                return False
            if month and it.get("month") != month:
                return False
            if not tokens:
                return True
            hay = it.get("haystack")
            if not hay:
                hay = self._make_haystack(it)
                it["haystack"] = hay
            return all(tok in hay for tok in tokens)

        results: List[Dict[str, Any]] = []
        if tokens and self.db_enabled and self.db_conn:
            try:
                fts_q = self._fts_query(tokens)
                if fts_q:
                    cur = self.db_conn.cursor()
                    fetch_limit = max(lim * 5, 500)
                    cur.execute(
                        "SELECT id FROM photos_fts WHERE photos_fts MATCH ? LIMIT ?",
                        (fts_q, fetch_limit),
                    )
                    ids = [row[0] for row in cur.fetchall()]
                    for pid in ids:
                        it = self.items.get(pid)
                        if it and matches(it):
                            results.append(it)
                else:
                    results = [it for it in self.items.values() if matches(it)]
            except Exception:
                results = [it for it in self.items.values() if matches(it)]
        else:
            results = [it for it in self.items.values() if matches(it)]

        if sort == "date_asc":
            results.sort(key=lambda x: (x.get("date", ""), x.get("filename", "")))
        elif sort == "name_asc":
            results.sort(key=lambda x: x.get("filename", "").lower())
        elif sort == "name_desc":
            results.sort(key=lambda x: x.get("filename", "").lower(), reverse=True)
        else:  # default date_desc
            results.sort(key=lambda x: (x.get("date", ""), x.get("filename", "")), reverse=True)

        return results[:lim]

    # ---------- Utilities ----------
    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        return self.items.get(item_id)

    def open_in_explorer(self, item_id: str) -> bool:
        path = self.path_by_id.get(item_id)
        if not path or not os.path.exists(path):
            return False
        if os.name != "nt":
            return False
        try:
            import subprocess

            subprocess.Popen(
                ["explorer", "/select,", os.path.normpath(path)],
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False

    def health(self) -> Dict[str, Any]:
        sources = []
        for d in self.cfg.source_dirs:
            if not d:
                continue
            exists = os.path.exists(d)
            sources.append({"path": d, "exists": exists})
        return {
            "ok": True,
            "count": len(self.items),
            "scan": self.scan_state.copy(),
            "sources": sources,
            "updated_at": _now_iso(),
        }
