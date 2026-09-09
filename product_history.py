"""Product history persistence for Sneakerness Studio."""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

HISTORY_DIR = Path("data/history_images")
HISTORY_FILE = Path("data/product_history.json")

_MIME_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _ensure_storage() -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text("[]", encoding="utf-8")


def load_history() -> list[dict[str, Any]]:
    """Return all history entries (unsorted)."""
    _ensure_storage()
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_history(entries: list[dict[str, Any]]) -> None:
    """Persist the full history list."""
    _ensure_storage()
    HISTORY_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_entry(entry_id: str) -> Optional[dict[str, Any]]:
    """Return one entry by id, or None."""
    for entry in load_history():
        if str(entry.get("id")) == str(entry_id):
            return entry
    return None


def delete_entry(entry_id: str) -> bool:
    """Remove entry by id and delete its image file if present."""
    entries = load_history()
    kept: list[dict[str, Any]] = []
    deleted: Optional[dict[str, Any]] = None
    for entry in entries:
        if str(entry.get("id")) == str(entry_id):
            deleted = entry
        else:
            kept.append(entry)
    if deleted is None:
        return False
    save_history(kept)
    image_path = deleted.get("image_path")
    if image_path:
        path = Path(image_path)
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                pass
    return True


def add_entry(
    entry: dict[str, Any],
    image_bytes: Optional[bytes] = None,
    mime_type: Optional[str] = None,
    source_image_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    Append a history entry.

    If image_bytes is provided, copies them under data/history_images/{id}.ext
    based on mime_type. Else if source_image_path exists, copies that file.
    """
    _ensure_storage()
    entries = load_history()

    new_entry = dict(entry)
    entry_id = str(new_entry.get("id") or uuid.uuid4().hex)
    new_entry["id"] = entry_id
    if not new_entry.get("created_at"):
        new_entry["created_at"] = datetime.now(timezone.utc).isoformat()

    image_path = new_entry.get("image_path")

    if image_bytes:
        ext = _MIME_EXT.get((mime_type or "image/jpeg").lower(), ".jpg")
        dest = HISTORY_DIR / f"{entry_id}{ext}"
        dest.write_bytes(image_bytes)
        image_path = dest.as_posix()
    elif source_image_path:
        src = Path(source_image_path)
        if src.is_file():
            ext = src.suffix.lower() if src.suffix else ".jpg"
            if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
                ext = ".jpg"
            dest = HISTORY_DIR / f"{entry_id}{ext}"
            shutil.copy2(src, dest)
            image_path = dest.as_posix()

    new_entry["image_path"] = image_path
    entries.append(new_entry)
    save_history(entries)
    return new_entry
