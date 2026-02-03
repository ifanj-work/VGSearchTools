from __future__ import annotations

import os
import time
import threading
import hashlib
import sqlite3
import concurrent.futures
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Set

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
        
        # Initialize DB
        self.db_path = self.cfg.db_file
        self.db_conn = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database with WAL mode and tables."""
        try:
            self.db_conn = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=10.0
            )
            self.db_conn.row_factory = sqlite3.Row
            
            cur = self.db_conn.cursor()
            # WAL mode for concurrency
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS photos (
                    id TEXT PRIMARY KEY,
                    path TEXT UNIQUE,
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
            # FTS5 for fast keyword search
            cur.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS photos_fts USING fts5(id, haystack)"
            )
            
            # Indices for filtering/sorting
            cur.execute("CREATE INDEX IF NOT EXISTS idx_photos_date ON photos(date)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_photos_year_month ON photos(year, month)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_photos_folder ON photos(folder)")
            
            self.db_conn.commit()
        except Exception as e:
            print(f"DB Init Error: {e}")
            self.db_conn = None

    def _make_haystack(self, item: Dict[str, Any]) -> str:
        return " ".join(
            [
                str(item.get("filename", "")),
                str(item.get("folder", "")),
                str(item.get("year", "")),
                f"{item.get('month', 0):02d}",
                str(item.get("date", "")),
            ]
        ).lower()

    @staticmethod
    def _norm_path(path: str) -> str:
        if not path:
            return ""
        return os.path.normcase(os.path.abspath(path))

    # ---------- Scanning ----------
    def scan_background(self) -> bool:
        if self.scan_state["running"]:
            return False
        t = threading.Thread(target=self._scan_worker, name="catalog-scan", daemon=True)
        self.scan_thread = t
        t.start()
        return True

    def _scan_worker(self) -> None:
        if not self.scan_lock.acquire(blocking=False):
            return
        
        # New DB connection for this thread
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            
            self.scan_state.update({
                "running": True,
                "started_at": _now_iso(),
                "completed_at": None,
                "scanned": 0,
                "found": 0,
                "errors": 0,
                "reused": 0,
                "message": "scanning",
            })
            
            scanned = 0
            found = 0
            errors = 0
            reused = 0
            
            # Get existing paths to check for updates
            cur = conn.cursor()
            cur.execute("SELECT path, mtime, size, id FROM photos")
            # Map norm_path -> (mtime, size, id)
            existing_map = {
                self._norm_path(row[0]): (row[1], row[2], row[3]) 
                for row in cur.fetchall()
            }
            
            # Files to process
            files_to_process: List[str] = []
            current_paths: Set[str] = set()
            
            filtersub = (self.cfg.lan_filter_subfolder or "").lower()
            
            # 1. Walk directories (fast)
            for base in self.cfg.source_dirs:
                if not base or not os.path.exists(base):
                    continue
                    
                for root, dirs, files in os.walk(base):
                    if filtersub and filtersub not in root.lower():
                        continue
                        
                    scanned += len(files)
                    self.scan_state["scanned"] = scanned
                    
                    for name in files:
                        ext = os.path.splitext(name)[1].lower()
                        if ext in self.cfg.extensions:
                            full_path = os.path.join(root, name)
                            files_to_process.append(full_path)
            
            # 2. Process files in parallel
            batch_size = 500
            updates: List[Tuple] = []
            
            def process_file_metadata(path: str):
                try:
                    st = os.stat(path)
                    norm = self._norm_path(path)
                    
                    prev = existing_map.get(norm)
                    # Check if modified
                    if prev:
                        pmtime, psize, pid = prev
                        if int(st.st_mtime) == pmtime and int(st.st_size) == psize:
                            return ("reuse", pid, norm)
                    
                    # Needs update/insert
                    item = self._build_item(path, st)
                    return ("update", item, norm)
                except Exception:
                    return ("error", None, None)

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                # Use as_completed for better responsiveness
                futures = {executor.submit(process_file_metadata, f): f for f in files_to_process}
                
                for future in concurrent.futures.as_completed(futures):
                    res_type, data, norm_path = future.result()
                    
                    if res_type == "reuse":
                        reused += 1
                        current_paths.add(norm_path)
                    elif res_type == "update" and data:
                        found += 1
                        current_paths.add(norm_path)
                        updates.append(data)
                    elif res_type == "error":
                        errors += 1
                    
                    # Batch commit
                    if len(updates) >= batch_size:
                        self._write_batch(conn, updates)
                        updates = []
                    
                    # Update status periodically
                    if (reused + found + errors) % 100 == 0:
                        self.scan_state.update({
                            "reused": reused,
                            "found": found,
                            "errors": errors
                        })
            
            # Flush remaining
            if updates:
                self._write_batch(conn, updates)
            
            # 3. Cleanup removed files
            all_existing_paths = set(existing_map.keys())
            removed_paths = all_existing_paths - current_paths
            
            if removed_paths:
                # Resolve IDs using existing_map
                ids_to_remove = []
                for p in removed_paths:
                    if p in existing_map:
                        ids_to_remove.append(existing_map[p][2]) # (mtime, size, id)
                
                if ids_to_remove:
                    self._remove_batch_ids(conn, ids_to_remove)
            
            self.scan_state.update({
                "running": False,
                "completed_at": _now_iso(),
                "message": "done",
                "reused": reused,
                "found": found,
                "errors": errors,
            })
            
        except Exception as e:
            self.scan_state.update({
                "running": False,
                "completed_at": _now_iso(),
                "message": f"error: {str(e)}",
            })
        finally:
            if conn:
                conn.close()
            self.scan_lock.release()

    def _write_batch(self, conn: sqlite3.Connection, items: List[Dict[str, Any]]) -> None:
        if not items:
            return
        
        photo_rows = [
            (
                it["id"], it["path"], it["filename"], it["folder"],
                it["size"], it["mtime"], it["date"],
                it["year"], it["month"], it["ext"]
            )
            for it in items
        ]
        
        fts_rows = [
            (it["id"], self._make_haystack(it)) 
            for it in items
        ]
        
        cur = conn.cursor()
        cur.executemany(
            """
            INSERT OR REPLACE INTO photos 
            (id, path, filename, folder, size, mtime, date, year, month, ext)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            photo_rows
        )
        cur.executemany(
            "INSERT OR REPLACE INTO photos_fts (id, haystack) VALUES (?, ?)", 
            fts_rows
        )
        conn.commit()

    def _remove_batch_ids(self, conn: sqlite3.Connection, ids: List[str]) -> None:
        if not ids:
            return
        cur = conn.cursor()
        # Process in chunks to respect SQLite limits
        chunk_size = 200
        for i in range(0, len(ids), chunk_size):
            batch = [(pid,) for pid in ids[i:i+chunk_size]]
            cur.executemany("DELETE FROM photos WHERE id = ?", batch)
            cur.executemany("DELETE FROM photos_fts WHERE id = ?", batch)
        conn.commit()

    # ---------- Item helpers ----------
    def _build_item(self, path: str, stat: os.stat_result) -> Dict[str, Any]:
        fid = stable_id_for_path(path)
        folder = os.path.dirname(path)
        fname = os.path.basename(path)
        date_taken = self._read_exif_date(path) or datetime.fromtimestamp(stat.st_mtime)
        return {
            "id": fid,
            "path": path,
            "filename": fname,
            "folder": folder,
            "size": int(stat.st_size),
            "mtime": int(stat.st_mtime),
            "date": date_taken.strftime("%Y-%m-%d"),
            "year": date_taken.year,
            "month": date_taken.month,
            "ext": os.path.splitext(fname)[1].lower(),
        }

    def _read_exif_date(self, path: str) -> Optional[datetime]:
        try:
            if PIL_AVAILABLE and Image:
                try:
                    with Image.open(path) as im:
                        exif = getattr(im, "_getexif", lambda: None)() or {}
                        dt = exif.get(36867) or exif.get(306)
                        if isinstance(dt, bytes):
                            dt = dt.decode(errors="ignore")
                        if isinstance(dt, str) and dt.strip():
                            return datetime.strptime(dt, "%Y:%m:%d %H:%M:%S")
                except Exception:
                    pass

            if EXIFREAD_AVAILABLE and exifread:
                try:
                    with open(path, "rb") as f:
                        tags = exifread.process_file(f, details=False, stop_tag="EXIF DateTimeOriginal")
                    dt = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
                    if dt:
                        return datetime.strptime(str(dt), "%Y:%m:%d %H:%M:%S")
                except Exception:
                    pass
        except Exception:
            pass
        return None

    # ---------- Thumbnails ----------
    def ensure_thumbnail(self, item_id: str, item: Optional[Dict[str, Any]] = None) -> str:
        if not item:
            item = self.get_item(item_id)
        if not item:
            raise FileNotFoundError("Item not found")
            
        src = item["path"]
        thumb_path = os.path.join(self.cfg.thumbs_dir, f"{item_id}.jpg")
        
        if os.path.exists(thumb_path):
            # Check staleness
            try:
                tstat = os.stat(thumb_path)
                if tstat.st_mtime >= item["mtime"]:
                    return thumb_path
            except OSError:
                pass
             
        # Generate
        if not PIL_AVAILABLE or not Image:
            return src
            
        try:
            tmp = thumb_path + ".tmp"
            with Image.open(src) as im:
                im = im.convert("RGB")
                im.thumbnail((self.cfg.thumb_size, self.cfg.thumb_size))
                im.save(tmp, "JPEG", quality=80)
            os.replace(tmp, thumb_path)
            return thumb_path
        except Exception:
            return src

    # ---------- Search ----------
    def search(
        self,
        query: str,
        limit: Optional[int] = None,
        offset: int = 0,
        year: Optional[int] = None,
        month: Optional[int] = None,
        sort: str = "date_desc",
    ) -> Tuple[List[Dict[str, Any]], int]:
        if not self.db_conn:
            return [], 0
            
        cur = self.db_conn.cursor()
        
        # Build query
        conditions = []
        params: List[Any] = []
        
        if year:
            conditions.append("year = ?")
            params.append(year)
        if month:
            conditions.append("month = ?")
            params.append(month)
            
        # Text Search
        query = (query or "").strip()
        if query:
            # Simple sanitization for FTS
            safe_query = "".join(c for c in query if c.isalnum() or c in " .-_")
            tokens = [f"{t}*" for t in safe_query.split() if t]
            if tokens:
                fts_expr = " AND ".join(tokens)
                # Join with FTS table
                conditions.append("id IN (SELECT id FROM photos_fts WHERE photos_fts MATCH ?)")
                params.append(fts_expr)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        # Count total
        count_sql = f"SELECT COUNT(1) FROM photos {where_clause}"
        try:
            cur.execute(count_sql, params)
            total = cur.fetchone()[0]
        except Exception:
            total = 0
            
        if total == 0:
            return [], 0
            
        # Sorting
        order_by = "date DESC"
        if sort == "date_asc":
            order_by = "date ASC"
        elif sort == "name_asc":
            order_by = "filename ASC"
        elif sort == "name_desc":
            order_by = "filename DESC"
            
        # Fetch Page
        lim = limit or self.cfg.search_limit
        off = max(0, offset)
        
        # Fixed: SELECT path column correctly (not literal string)
        sql = f"""
            SELECT id, filename, folder, date, year, month, path
            FROM photos 
            {where_clause}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """
        # Append limit/offset params
        q_params = params + [lim, off]
        
        cur.execute(sql, q_params)
        rows = cur.fetchall()
        
        results = []
        for r in rows:
            results.append(dict(r))
            
        return results, total

    # ---------- Utilities ----------
    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        if not self.db_conn:
            return None
        try:
            cur = self.db_conn.cursor()
            cur.execute("SELECT * FROM photos WHERE id = ?", (item_id,))
            row = cur.fetchone()
            if row:
                return dict(row)
        except Exception:
            pass
        return None

    def open_in_explorer(self, item_id: str) -> bool:
        item = self.get_item(item_id)
        if not item:
            return False
            
        path = item.get("path")
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
        count = 0
        if self.db_conn:
            try:
                cur = self.db_conn.cursor()
                cur.execute("SELECT COUNT(1) FROM photos")
                count = cur.fetchone()[0]
            except Exception:
                pass
                
        sources = []
        for d in self.cfg.source_dirs:
            if d:
                sources.append({"path": d, "exists": os.path.exists(d)})
                
        return {
            "ok": True,
            "count": count,
            "scan": self.scan_state.copy(),
            "sources": sources,
            "updated_at": _now_iso(),
        }
