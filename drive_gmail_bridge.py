"""Local Google Drive / Gmail sign-in bridge for EMBORGANIZER.

This restores the old site pages without forcing an external API dependency. The
app can be used in three levels:
1. Public Drive file/folder link tools (requests only).
2. Local OAuth config stored outside git in local_config/google_connections.json.
3. Optional Drive/Gmail API calls after the user pastes an OAuth code locally.

No secrets are committed by default; local_config/ is gitignored.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

GOOGLE_BRIDGE_VERSION = "Google Drive + Gmail Sign Bridge v5.4.3"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
USERINFO_SCOPE = "openid email profile"
DEFAULT_SCOPES = f"{DRIVE_SCOPE} {GMAIL_SCOPE} {USERINFO_SCOPE}"


def _json_read(path: Path, default: Any) -> Any:
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _json_write(path: Path, data: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def config_path(app_root: Path) -> Path:
    return Path(app_root) / "local_config" / "google_connections.json"


def load_google_config(app_root: Path) -> Dict[str, Any]:
    data = _json_read(config_path(app_root), {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("client_id", "")
    data.setdefault("client_secret", "")
    data.setdefault("redirect_uri", "http://localhost:8501")
    data.setdefault("scopes", DEFAULT_SCOPES)
    data.setdefault("tokens", {})
    data.setdefault("created_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    return data


def save_google_config(app_root: Path, updates: Dict[str, Any]) -> Dict[str, Any]:
    data = load_google_config(app_root)
    data.update({k: v for k, v in updates.items() if v is not None})
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _json_write(config_path(app_root), data)
    return data


def google_status(app_root: Path) -> Dict[str, Any]:
    cfg = load_google_config(app_root)
    tokens = cfg.get("tokens") or {}
    return {
        "configured": bool(cfg.get("client_id") and cfg.get("client_secret")),
        "token_saved": bool(tokens.get("access_token")),
        "refresh_token_saved": bool(tokens.get("refresh_token")),
        "redirect_uri": cfg.get("redirect_uri"),
        "scopes": cfg.get("scopes"),
        "config_file": str(config_path(app_root)),
        "requests_available": requests is not None,
    }


def build_oauth_url(app_root: Path, state: str = "emborganizer") -> str:
    cfg = load_google_config(app_root)
    params = {
        "client_id": cfg.get("client_id", ""),
        "redirect_uri": cfg.get("redirect_uri", "http://localhost:8501"),
        "response_type": "code",
        "scope": cfg.get("scopes") or DEFAULT_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "include_granted_scopes": "true",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)


def exchange_oauth_code(app_root: Path, code: str) -> Dict[str, Any]:
    if requests is None:
        return {"ok": False, "error": "requests is not installed"}
    cfg = load_google_config(app_root)
    payload = {
        "code": code.strip(),
        "client_id": cfg.get("client_id"),
        "client_secret": cfg.get("client_secret"),
        "redirect_uri": cfg.get("redirect_uri"),
        "grant_type": "authorization_code",
    }
    r = requests.post("https://oauth2.googleapis.com/token", data=payload, timeout=25)
    if r.status_code >= 400:
        return {"ok": False, "status": r.status_code, "error": r.text[:500]}
    token = r.json()
    token["created_at"] = int(time.time())
    cfg["tokens"] = token
    save_google_config(app_root, cfg)
    return {"ok": True, "token_saved": True, "expires_in": token.get("expires_in"), "scope": token.get("scope")}


def refresh_access_token(app_root: Path) -> Dict[str, Any]:
    if requests is None:
        return {"ok": False, "error": "requests is not installed"}
    cfg = load_google_config(app_root)
    tokens = cfg.get("tokens") or {}
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return {"ok": False, "error": "No refresh token saved"}
    payload = {
        "client_id": cfg.get("client_id"),
        "client_secret": cfg.get("client_secret"),
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    r = requests.post("https://oauth2.googleapis.com/token", data=payload, timeout=25)
    if r.status_code >= 400:
        return {"ok": False, "status": r.status_code, "error": r.text[:500]}
    new_token = r.json()
    tokens.update(new_token)
    tokens["created_at"] = int(time.time())
    cfg["tokens"] = tokens
    save_google_config(app_root, cfg)
    return {"ok": True, "token_saved": True, "expires_in": tokens.get("expires_in")}


def access_token(app_root: Path) -> Optional[str]:
    cfg = load_google_config(app_root)
    tokens = cfg.get("tokens") or {}
    tok = tokens.get("access_token")
    created = int(tokens.get("created_at") or 0)
    expires = int(tokens.get("expires_in") or 0)
    if tok and expires and time.time() > created + expires - 90:
        refreshed = refresh_access_token(app_root)
        if refreshed.get("ok"):
            cfg = load_google_config(app_root)
            tok = (cfg.get("tokens") or {}).get("access_token")
    return tok


def parse_drive_id(text: str) -> Dict[str, str]:
    text = str(text or "").strip()
    folder_match = re.search(r"/folders/([a-zA-Z0-9_-]+)", text)
    file_match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", text)
    id_match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", text)
    if folder_match:
        return {"type": "folder", "id": folder_match.group(1)}
    if file_match:
        return {"type": "file", "id": file_match.group(1)}
    if id_match:
        return {"type": "file", "id": id_match.group(1)}
    if re.fullmatch(r"[a-zA-Z0-9_-]{15,}", text):
        return {"type": "unknown", "id": text}
    return {"type": "unknown", "id": ""}


def _auth_headers(app_root: Path) -> Dict[str, str]:
    tok = access_token(app_root)
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def drive_list_files(app_root: Path, folder_id: str = "", query: str = "", page_size: int = 50) -> Dict[str, Any]:
    if requests is None:
        return {"ok": False, "error": "requests is not installed", "files": []}
    headers = _auth_headers(app_root)
    if not headers:
        return {"ok": False, "error": "Google token is not connected", "files": []}
    q_parts: List[str] = ["trashed=false"]
    if folder_id:
        q_parts.append(f"'{folder_id}' in parents")
    if query:
        safe = query.replace("'", "\\'")
        q_parts.append(f"name contains '{safe}'")
    params = {
        "q": " and ".join(q_parts),
        "pageSize": int(page_size),
        "fields": "files(id,name,mimeType,size,modifiedTime,webViewLink)",
        "orderBy": "modifiedTime desc",
    }
    r = requests.get("https://www.googleapis.com/drive/v3/files", headers=headers, params=params, timeout=30)
    if r.status_code >= 400:
        return {"ok": False, "status": r.status_code, "error": r.text[:500], "files": []}
    return {"ok": True, "files": r.json().get("files", [])}


def drive_download_file(app_root: Path, file_id: str, out_dir: Path, filename: str = "") -> Dict[str, Any]:
    if requests is None:
        return {"ok": False, "error": "requests is not installed"}
    headers = _auth_headers(app_root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if headers:
        meta_r = requests.get(f"https://www.googleapis.com/drive/v3/files/{file_id}", headers=headers, params={"fields": "id,name,mimeType,size"}, timeout=20)
        meta = meta_r.json() if meta_r.status_code < 400 else {}
        name = filename or meta.get("name") or f"drive_{file_id}"
        r = requests.get(f"https://www.googleapis.com/drive/v3/files/{file_id}", headers=headers, params={"alt": "media"}, timeout=120)
    else:
        # Public link fallback.
        name = filename or f"drive_{file_id}"
        sess = requests.Session()
        r = sess.get("https://drive.google.com/uc", params={"export": "download", "id": file_id}, timeout=120, stream=True)
        # Handle large public file confirmation token.
        token = None
        for k, v in r.cookies.items():
            if k.startswith("download_warning"):
                token = v
                break
        if token:
            r = sess.get("https://drive.google.com/uc", params={"export": "download", "confirm": token, "id": file_id}, timeout=120, stream=True)
    if r.status_code >= 400:
        return {"ok": False, "status": r.status_code, "error": r.text[:500]}
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".", " ") else "_" for ch in name).strip() or f"drive_{file_id}"
    out_path = out_dir / safe
    with out_path.open("wb") as fh:
        for chunk in r.iter_content(1024 * 1024):
            if chunk:
                fh.write(chunk)
    return {"ok": True, "path": str(out_path), "name": safe, "size": out_path.stat().st_size, "used_oauth": bool(headers)}


def gmail_profile(app_root: Path) -> Dict[str, Any]:
    if requests is None:
        return {"ok": False, "error": "requests is not installed"}
    headers = _auth_headers(app_root)
    if not headers:
        return {"ok": False, "error": "Google token is not connected"}
    r = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=headers, timeout=20)
    if r.status_code >= 400:
        return {"ok": False, "status": r.status_code, "error": r.text[:500]}
    data = r.json()
    return {"ok": True, "email": data.get("email"), "name": data.get("name"), "picture": data.get("picture")}


def gmail_recent_messages(app_root: Path, max_results: int = 10) -> Dict[str, Any]:
    if requests is None:
        return {"ok": False, "error": "requests is not installed", "messages": []}
    headers = _auth_headers(app_root)
    if not headers:
        return {"ok": False, "error": "Google token is not connected", "messages": []}
    params = {"maxResults": int(max_results), "q": "newer_than:30d"}
    r = requests.get("https://gmail.googleapis.com/gmail/v1/users/me/messages", headers=headers, params=params, timeout=25)
    if r.status_code >= 400:
        return {"ok": False, "status": r.status_code, "error": r.text[:500], "messages": []}
    ids = [m.get("id") for m in r.json().get("messages", []) if m.get("id")]
    messages = []
    for mid in ids[:int(max_results)]:
        mr = requests.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}", headers=headers, params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]}, timeout=20)
        if mr.status_code < 400:
            payload = mr.json()
            headers_list = (payload.get("payload") or {}).get("headers") or []
            hmap = {h.get("name", "").lower(): h.get("value", "") for h in headers_list}
            messages.append({"id": mid, "subject": hmap.get("subject"), "from": hmap.get("from"), "date": hmap.get("date"), "snippet": payload.get("snippet")})
    return {"ok": True, "messages": messages}
