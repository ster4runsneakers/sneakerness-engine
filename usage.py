"""Free vs Pro monthly generate limits for Sneaker Image Studio."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple

USAGE_FILE = Path("data/usage.json")
FREE_MONTHLY_LIMIT = 5
# Owner can set PRO_ACCESS_CODE in Streamlit secrets or env; fallback for local/testing:
FALLBACK_PRO_CODE = "STUDIO-PRO"
LEMON_CHECKOUT_URL = (
    "https://sneakerimageengine.lemonsqueezy.com/checkout/buy/"
    "68cb2fc4-a76f-40b3-b17c-247392288e05"
)


def current_month() -> str:
    return datetime.now().strftime("%Y-%m")


def get_pro_access_code() -> str:
    """Prefer st.secrets, then env, then documented fallback."""
    try:
        import streamlit as st

        code = st.secrets.get("PRO_ACCESS_CODE")
        if code:
            return str(code).strip()
    except Exception:
        pass
    env = os.environ.get("PRO_ACCESS_CODE")
    if env:
        return str(env).strip()
    return FALLBACK_PRO_CODE


def _ensure_file() -> None:
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not USAGE_FILE.exists():
        USAGE_FILE.write_text("{}", encoding="utf-8")


def load_all() -> dict[str, Any]:
    _ensure_file()
    try:
        data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def save_all(data: dict[str, Any]) -> None:
    _ensure_file()
    USAGE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ensure_device_id(session_state: Any) -> str:
    """Stable-ish id stored once in session_state."""
    if "usage_device_id" not in session_state:
        session_state["usage_device_id"] = str(uuid.uuid4())
    return str(session_state["usage_device_id"])


def _default_record(pro: bool = False) -> dict[str, Any]:
    return {"month": current_month(), "count": 0, "pro": bool(pro)}


def get_record(device_id: str) -> dict[str, Any]:
    all_data = load_all()
    rec = all_data.get(device_id)
    if not isinstance(rec, dict):
        return _default_record()
    month = current_month()
    pro = bool(rec.get("pro", False))
    if rec.get("month") != month:
        return {"month": month, "count": 0, "pro": pro}
    try:
        count = int(rec.get("count") or 0)
    except (TypeError, ValueError):
        count = 0
    return {"month": month, "count": max(0, count), "pro": pro}


def save_record(device_id: str, record: dict[str, Any]) -> None:
    all_data = load_all()
    all_data[device_id] = {
        "month": record.get("month") or current_month(),
        "count": int(record.get("count") or 0),
        "pro": bool(record.get("pro", False)),
    }
    save_all(all_data)


def sync_session(session_state: Any) -> None:
    """Merge disk + session into session_state and persist."""
    device_id = ensure_device_id(session_state)
    rec = get_record(device_id)
    month = current_month()
    session_pro = bool(session_state.get("usage_pro", False))
    pro = session_pro or bool(rec.get("pro", False))
    count = int(rec.get("count") or 0)
    if session_state.get("usage_month") == month:
        try:
            count = max(count, int(session_state.get("usage_count") or 0))
        except (TypeError, ValueError):
            pass
    session_state["usage_pro"] = pro
    session_state["usage_count"] = count
    session_state["usage_month"] = month
    save_record(device_id, {"month": month, "count": count, "pro": pro})


def is_pro(session_state: Any) -> bool:
    return bool(session_state.get("usage_pro", False))


def usage_counts(session_state: Any) -> Tuple[int, int]:
    """Return (used, limit) for Free UI."""
    month = current_month()
    if session_state.get("usage_month") != month:
        return 0, FREE_MONTHLY_LIMIT
    try:
        used = int(session_state.get("usage_count") or 0)
    except (TypeError, ValueError):
        used = 0
    return max(0, used), FREE_MONTHLY_LIMIT


def remaining(session_state: Any) -> Optional[int]:
    """None if Pro (unlimited), else remaining free generates."""
    if is_pro(session_state):
        return None
    used, limit = usage_counts(session_state)
    return max(0, limit - used)


def can_generate(session_state: Any) -> bool:
    if is_pro(session_state):
        return True
    rem = remaining(session_state)
    return rem is None or rem > 0


def record_generate(session_state: Any) -> None:
    """Increment Free generate count (no-op for Pro count display, still persists)."""
    device_id = ensure_device_id(session_state)
    month = current_month()
    if session_state.get("usage_month") != month:
        session_state["usage_month"] = month
        session_state["usage_count"] = 0
    if not is_pro(session_state):
        try:
            session_state["usage_count"] = int(session_state.get("usage_count") or 0) + 1
        except (TypeError, ValueError):
            session_state["usage_count"] = 1
    save_record(
        device_id,
        {
            "month": session_state.get("usage_month") or month,
            "count": int(session_state.get("usage_count") or 0),
            "pro": bool(session_state.get("usage_pro", False)),
        },
    )


def try_unlock(session_state: Any, code: str) -> bool:
    expected = get_pro_access_code()
    if (code or "").strip().upper() != str(expected).strip().upper():
        return False
    session_state["usage_pro"] = True
    device_id = ensure_device_id(session_state)
    month = current_month()
    count = 0
    if session_state.get("usage_month") == month:
        try:
            count = int(session_state.get("usage_count") or 0)
        except (TypeError, ValueError):
            count = 0
    session_state["usage_month"] = month
    session_state["usage_count"] = count
    save_record(device_id, {"month": month, "count": count, "pro": True})
    return True
