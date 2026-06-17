from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets as py_secrets
import time
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_AUTH_DIR = BASE_DIR / "emborganizer_data_streamlit" / "auth_sessions"
AUTH_DIR = Path(os.environ.get("EMB_AUTH_SESSIONS_DIR", str(DEFAULT_AUTH_DIR)))
SESSION_STATE_KEY = "google_server_session_key"
SECRET_FILE = AUTH_DIR / ".server_secret"
SESSION_FILE_SUFFIX = ".json"
DEFAULT_MAX_AGE_DAYS = 30


def _get_section(name: str) -> Dict[str, Any]:
    try:
        section = st.secrets.get(name, {})  # type: ignore[attr-defined]
        if hasattr(section, "to_dict"):
            return dict(section.to_dict())
        return dict(section or {})
    except Exception:
        return {}


def _truthy(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def server_auth_enabled() -> bool:
    section = _get_section("auth_session")
    return _truthy(section.get("enabled", os.environ.get("EMB_AUTH_SESSION_ENABLED")), default=True)


def max_age_seconds() -> int:
    section = _get_section("auth_session")
    raw = section.get("max_age_days", os.environ.get("EMB_AUTH_SESSION_MAX_AGE_DAYS", DEFAULT_MAX_AGE_DAYS))
    try:
        days = max(1, int(raw))
    except Exception:
        days = DEFAULT_MAX_AGE_DAYS
    return days * 24 * 60 * 60


def _server_secret() -> str:
    """Return a stable secret used only to hash server-side session IDs."""
    section = _get_section("auth_session")
    configured = str(section.get("server_secret") or os.environ.get("EMB_AUTH_SERVER_SECRET") or "").strip()
    if configured:
        return configured

    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    if SECRET_FILE.exists():
        try:
            existing = SECRET_FILE.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        except Exception:
            pass

    generated = py_secrets.token_urlsafe(48)
    try:
        SECRET_FILE.write_text(generated, encoding="utf-8")
        try:
            os.chmod(SECRET_FILE, 0o600)
        except Exception:
            pass
    except Exception:
        # Last-resort fallback for read-only deployments. Sessions still work for
        # the current process, but will not survive a server restart.
        generated = os.environ.setdefault("EMB_AUTH_EPHEMERAL_SECRET", generated)
    return generated


def _session_digest(session_key: str) -> str:
    secret = _server_secret().encode("utf-8")
    return hmac.new(secret, session_key.encode("utf-8"), hashlib.sha256).hexdigest()


def _session_file(session_key: str) -> Path:
    return AUTH_DIR / f"{_session_digest(session_key)}{SESSION_FILE_SUFFIX}"


def _safe_json(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except Exception:
        if isinstance(value, dict):
            return {str(k): _safe_json(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_safe_json(v) for v in value]
        return str(value)


def ensure_server_session_key() -> str:
    key = st.session_state.get(SESSION_STATE_KEY)
    if not isinstance(key, str) or len(key) < 24:
        key = py_secrets.token_urlsafe(32)
        st.session_state[SESSION_STATE_KEY] = key
    return key


def get_server_session_key() -> Optional[str]:
    key = st.session_state.get(SESSION_STATE_KEY)
    return key if isinstance(key, str) and key else None


def save_google_login(
    *,
    user: Dict[str, Any],
    tokens: Dict[str, Any],
    drive_tokens: Optional[Dict[str, Any]] = None,
) -> Optional[Path]:
    """Persist the current Google sign-in on the app server.

    The browser only keeps an opaque random session key in Streamlit's normal
    session state. User profile data and OAuth tokens are saved in the server's
    emborganizer_data_streamlit/auth_sessions folder.
    """
    if not server_auth_enabled():
        return None
    if not isinstance(user, dict) or not user.get("email"):
        return None
    if not isinstance(tokens, dict) or not tokens.get("access_token"):
        return None

    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    session_key = ensure_server_session_key()
    path = _session_file(session_key)
    now = int(time.time())
    created_at = now
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            created_at = int(previous.get("created_at") or now)
        except Exception:
            created_at = now

    email = str(user.get("email", "")).strip().lower()
    record = {
        "schema": "emborganizer.google_signin.server_session.v1",
        "created_at": created_at,
        "updated_at": now,
        "email_hash": hashlib.sha256(email.encode("utf-8")).hexdigest() if email else "",
        "user": _safe_json(user),
        "tokens": _safe_json(tokens),
        "drive_tokens": _safe_json(drive_tokens if drive_tokens is not None else tokens),
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except Exception:
        pass
    tmp.replace(path)
    return path


def load_google_login() -> Optional[Dict[str, Any]]:
    if not server_auth_enabled():
        return None
    session_key = get_server_session_key()
    if not session_key:
        return None
    path = _session_file(session_key)
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    updated_at = int(record.get("updated_at") or record.get("created_at") or 0)
    if updated_at and time.time() - updated_at > max_age_seconds():
        delete_google_login()
        return None

    user = record.get("user")
    tokens = record.get("tokens")
    if not isinstance(user, dict) or not user.get("email"):
        return None
    if not isinstance(tokens, dict) or not tokens.get("access_token"):
        return None
    return record


def restore_google_login_to_session_state() -> bool:
    record = load_google_login()
    if not record:
        return False
    user = record.get("user")
    tokens = record.get("tokens")
    drive_tokens = record.get("drive_tokens")
    if isinstance(user, dict) and user.get("email"):
        st.session_state["google_user"] = user
    if isinstance(tokens, dict) and tokens.get("access_token"):
        st.session_state["google_tokens"] = tokens
    if isinstance(drive_tokens, dict) and drive_tokens.get("access_token"):
        st.session_state["google_drive_tokens"] = drive_tokens
    return True


def delete_google_login() -> None:
    session_key = get_server_session_key()
    if session_key:
        try:
            path = _session_file(session_key)
            if path.exists():
                path.unlink()
        except Exception:
            pass
    st.session_state.pop(SESSION_STATE_KEY, None)


def server_session_metadata() -> Dict[str, Any]:
    session_key = get_server_session_key()
    if not session_key:
        return {"enabled": server_auth_enabled(), "saved": False, "auth_dir": str(AUTH_DIR)}
    path = _session_file(session_key)
    meta: Dict[str, Any] = {"enabled": server_auth_enabled(), "saved": path.exists(), "auth_dir": str(AUTH_DIR)}
    if path.exists():
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            meta.update(
                {
                    "created_at": record.get("created_at"),
                    "updated_at": record.get("updated_at"),
                    "email_hash": record.get("email_hash"),
                }
            )
        except Exception:
            pass
    return meta
