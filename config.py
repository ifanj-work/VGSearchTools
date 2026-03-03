import os
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

# Maps file extensions to logical file-type categories
FILE_TYPE_MAP: Dict[str, str] = {
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".bmp": "image",
    ".webp": "image", ".tif": "image", ".tiff": "image",
    ".mp4": "video", ".mov": "video", ".avi": "video",
    ".mkv": "video", ".wmv": "video", ".webm": "video",
    ".psd": "psd",
}


def get_file_type(ext: str) -> str:
    """Return 'image', 'video', or 'psd' for a given extension."""
    return FILE_TYPE_MAP.get(ext.lower(), "image")


@dataclass
class AppConfig:
    # Source directories to scan (Windows paths by default)
    source_dirs: List[str] = field(default_factory=lambda: [r"Z:\\", r"G:\\"])  # LAN and Google Drive
    # Optional filter: only index files whose path contains this substring
    lan_filter_subfolder: Optional[str] = None
    # File extensions considered as photos/images/videos/psd
    extensions: List[str] = field(
        default_factory=lambda: [
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".webp",
            ".tif",
            ".tiff",
            # Video formats
            ".mp4",
            ".mov",
            ".avi",
            ".mkv",
            ".wmv",
            ".webm",
            # PSD
            ".psd",
        ]
    )
    # Catalog and thumbs relative to CWD by default
    catalog_file: str = "photo_catalog.json"
    db_file: str = "photo_catalog.db"
    thumbs_dir: str = "thumbs"
    logs_dir: str = "logs"
    # Thumbnail size (max dimension)
    thumb_size: int = 512
    # Search result limit
    search_limit: int = 500
    # UI customization
    ui_title: str = "Vivagoal Photo Finder"
    ui_logo_url: Optional[str] = "/static/img/logo.svg"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        if not data:
            return
        for key in [
            "source_dirs",
            "lan_filter_subfolder",
            "extensions",
            "catalog_file",
            "db_file",
            "thumbs_dir",
            "logs_dir",
            "thumb_size",
            "search_limit",
            "ui_title",
            "ui_logo_url",
        ]:
            if key in data and data[key] is not None:
                setattr(self, key, data[key])


def _split_paths(value: str | None) -> List[str]:
    if not value:
        return []
    # Accept semicolon or comma separated
    parts = [p.strip() for p in value.replace(",", ";").split(";")]
    return [p for p in parts if p]


SETTINGS_FILE = "app_config.json"


def _load_settings_file() -> Optional[Dict[str, Any]]:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_settings(cfg: AppConfig, only_keys: Optional[List[str]] = None) -> bool:
    try:
        # Merge with existing settings to avoid wiping unrelated keys
        existing: Dict[str, Any] = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f) or {}
            except Exception:
                existing = {}

        data = cfg.to_dict()
        if only_keys is not None:
            # Update only requested keys, keep others intact
            for k in only_keys:
                if k in data:
                    existing[k] = data[k]
            merged = existing
        else:
            merged = data

        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def load_config() -> AppConfig:
    # Optional: load .env if present
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
    except Exception:
        pass

    cfg = AppConfig()

    # Load persisted settings (overrides defaults)
    persisted = _load_settings_file()
    if persisted:
        cfg.update_from_dict(persisted)

    src_env = os.getenv("SOURCE_DIRS")
    if src_env:
        cfg.source_dirs = _split_paths(src_env)

    lf = os.getenv("LAN_FILTER_SUBFOLDER")
    if lf:
        cfg.lan_filter_subfolder = lf

    cf = os.getenv("CATALOG_FILE")
    if cf:
        cfg.catalog_file = cf

    dbf = os.getenv("DB_FILE")
    if dbf:
        cfg.db_file = dbf

    td = os.getenv("THUMBS_DIR")
    if td:
        cfg.thumbs_dir = td

    ld = os.getenv("LOGS_DIR")
    if ld:
        cfg.logs_dir = ld

    ts = os.getenv("THUMB_SIZE")
    if ts and ts.isdigit():
        cfg.thumb_size = int(ts)

    sl = os.getenv("SEARCH_LIMIT")
    if sl and sl.isdigit():
        cfg.search_limit = int(sl)

    ut = os.getenv("UI_TITLE")
    if ut:
        cfg.ui_title = ut

    ul = os.getenv("UI_LOGO_URL")
    if ul:
        cfg.ui_logo_url = ul

    return cfg
