from __future__ import annotations

import json
import mimetypes
import secrets as py_secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote

import requests
import streamlit as st

try:
    from google_auth import get_google_tokens, get_google_user, google_oauth_config, persist_current_google_session
except Exception:  # pragma: no cover
    get_google_tokens = None  # type: ignore
    get_google_user = None  # type: ignore
    google_oauth_config = None  # type: ignore
    persist_current_google_session = None  # type: ignore

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_API = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
FOLDER_MIME = "application/vnd.google-apps.folder"
APP_PROGRESS_FILENAME = "EMBORGANIZER_PROGRESS_STREAMLIT.txt"
DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
DESIGN_EXTENSIONS = {".dst", ".pes", ".jef", ".exp", ".vp3", ".hus", ".xxx", ".emb"}


@dataclass(frozen=True)
class DriveOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: List[str]
    root_folder_name: str = "EMBORGANIZER"
    library_folder_name: str = "Library"
    preview_folder_name: str = "Previews"
    originals_folder_name: str = "Original Designs"
    converted_folder_name: str = "Converted Images"
    progress_folder_name: str = "Progress"
    debug: bool = False


def _get_section(name: str) -> Dict[str, Any]:
    try:
        section = st.secrets.get(name, {})  # type: ignore[attr-defined]
        if hasattr(section, "to_dict"):
            return dict(section.to_dict())
        return dict(section or {})
    except Exception:
        return {}


def _truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_scopes(raw: Any) -> List[str]:
    if isinstance(raw, str):
        parts = raw.replace(",", " ").split()
    else:
        parts = [str(item) for item in list(raw or [])]
    scopes: List[str] = []
    seen: set[str] = set()
    for item in parts:
        scope = item.strip().strip('"').strip("'")
        if scope and scope not in seen:
            scopes.append(scope)
            seen.add(scope)
    return scopes


def drive_oauth_config() -> Tuple[Optional[DriveOAuthConfig], List[str]]:
    """Return Drive sync config.

    v4.4 does not run a second Drive OAuth redirect. Drive permission is granted
    during Google sign-in using google_oauth.redirect_uri, so Google Cloud only
    needs the same redirect URI that already works for sign-in.
    """
    oauth = _get_section("google_oauth")
    drive = _get_section("google_drive")
    missing: List[str] = []

    client_id = str(oauth.get("client_id", "")).strip()
    client_secret = str(oauth.get("client_secret", "")).strip()
    redirect_uri = str(oauth.get("redirect_uri", "")).strip()

    if not client_id or client_id.startswith(("YOUR_", "PASTE_")):
        missing.append("google_oauth.client_id")
    if not client_secret or client_secret.startswith(("YOUR_", "PASTE_")):
        missing.append("google_oauth.client_secret")
    if not redirect_uri or redirect_uri.startswith(("https://YOUR", "http://YOUR")):
        missing.append("google_oauth.redirect_uri")

    scopes = [DRIVE_FILE_SCOPE]

    if missing:
        return None, missing

    return DriveOAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=scopes,
        root_folder_name=str(drive.get("root_folder_name", "EMBORGANIZER") or "EMBORGANIZER"),
        library_folder_name=str(drive.get("library_folder_name", "Library") or "Library"),
        preview_folder_name=str(drive.get("preview_folder_name", "Previews") or "Previews"),
        originals_folder_name=str(drive.get("originals_folder_name", "Original Designs") or "Original Designs"),
        converted_folder_name=str(drive.get("converted_folder_name", "Converted Images") or "Converted Images"),
        progress_folder_name=str(drive.get("progress_folder_name", "Progress") or "Progress"),
        debug=_truthy(drive.get("debug"), default=False),
    ), []


def drive_sync_enabled() -> bool:
    drive = _get_section("google_drive")
    oauth = _get_section("google_oauth")
    return _truthy(drive.get("enabled"), default=False) or _truthy(oauth.get("enable_gdrive_sync"), default=False)


def token_has_drive_scope(tokens: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(tokens, dict):
        return False
    scopes = str(tokens.get("scope") or "")
    return DRIVE_FILE_SCOPE in scopes or "drive.file" in scopes


def token_has_drive_read_scope(tokens: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(tokens, dict):
        return False
    scopes = str(tokens.get("scope") or "")
    return token_has_drive_scope(tokens) or DRIVE_READONLY_SCOPE in scopes or "drive.readonly" in scopes

def get_drive_tokens() -> Optional[Dict[str, Any]]:
    # v4.4 preferred model: use the token received during Google sign-in and saved server-side.
    if get_google_tokens is not None:
        login_tokens = get_google_tokens()
        if token_has_drive_scope(login_tokens):
            st.session_state["google_drive_tokens"] = login_tokens
            return login_tokens

    # Backward compatibility for old v4.2 sessions that connected Drive separately.
    tokens = st.session_state.get("google_drive_tokens")
    if isinstance(tokens, dict) and tokens.get("access_token") and token_has_drive_scope(tokens):
        return tokens
    return None

def clear_drive_session() -> None:
    # Drive is now part of the Google sign-in token. This clears Drive cache only.
    for key in [
        "google_drive_tokens",
        "google_drive_state",
        "google_drive_started",
        "google_drive_folders",
        "google_drive_error",
        "gdrive_sync_enabled",
    ]:
        st.session_state.pop(key, None)


def build_drive_auth_url(config: DriveOAuthConfig) -> str:
    # Kept only for backward compatibility. v4.4 does not use separate Drive OAuth.
    return ""

def _query_value(name: str) -> str:
    try:
        value = st.query_params.get(name, "")
    except Exception:
        value = ""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def exchange_drive_code(config: DriveOAuthConfig, code: str) -> Dict[str, Any]:
    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "redirect_uri": config.redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=25,
    )
    if not response.ok:
        raise RuntimeError(f"Google Drive token exchange failed: HTTP {response.status_code}. {response.text[:900]}")
    tokens = response.json()
    tokens["created_at"] = int(time.time())
    tokens["scope"] = tokens.get("scope") or " ".join(config.scopes)
    return tokens


def refresh_drive_token(config: DriveOAuthConfig, tokens: Dict[str, Any]) -> Dict[str, Any]:
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("Drive access expired and no refresh token is available. Please reconnect Google Drive.")
    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=25,
    )
    if not response.ok:
        raise RuntimeError(f"Google Drive token refresh failed: HTTP {response.status_code}. {response.text[:900]}")
    updated = dict(tokens)
    updated.update(response.json())
    updated["refresh_token"] = refresh_token
    updated["created_at"] = int(time.time())
    st.session_state["google_drive_tokens"] = updated
    st.session_state["google_tokens"] = updated
    if persist_current_google_session is not None:
        try:
            persist_current_google_session()
        except Exception:
            pass
    return updated


def get_drive_access_token(config: DriveOAuthConfig) -> str:
    tokens = get_drive_tokens()
    if not tokens:
        raise RuntimeError("Google Drive permission was not granted at sign-in. Sign out, enable Drive sync in secrets, then sign in again.")
    created_at = int(tokens.get("created_at") or 0)
    expires_in = int(tokens.get("expires_in") or 3600)
    if created_at and time.time() > created_at + max(60, expires_in - 120):
        tokens = refresh_drive_token(config, tokens)
    return str(tokens["access_token"])


def handle_drive_oauth_callback(*, show_success: bool = True) -> bool:
    # v4.4: Drive permission is handled by the main Google sign-in callback.
    # Do not consume query params here, otherwise /google-drive can accidentally
    # process normal sign-in redirects with the wrong redirect URI.
    return False


def _drive_headers(config: DriveOAuthConfig) -> Dict[str, str]:
    return {"Authorization": f"Bearer {get_drive_access_token(config)}"}


def _drive_request(config: DriveOAuthConfig, method: str, url: str, **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {}) or {}
    merged = {**_drive_headers(config), **headers}
    response = requests.request(method, url, headers=merged, timeout=kwargs.pop("timeout", 30), **kwargs)
    if response.status_code == 401:
        # Try once after refresh.
        refresh_drive_token(config, get_drive_tokens() or {})
        merged = {**_drive_headers(config), **headers}
        response = requests.request(method, url, headers=merged, timeout=kwargs.pop("timeout", 30), **kwargs)
    return response


def _escape_drive_query_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def drive_about(config: DriveOAuthConfig) -> Dict[str, Any]:
    response = _drive_request(config, "GET", f"{DRIVE_API}/about", params={"fields": "user,storageQuota"})
    if not response.ok:
        raise RuntimeError(f"Drive status check failed: HTTP {response.status_code}. {response.text[:700]}")
    return response.json()




def list_drive_files(
    config: DriveOAuthConfig,
    *,
    query: str,
    max_files: int = 500,
    page_size: int = 100,
    fields: str = "files(id,name,mimeType,size,modifiedTime,webViewLink,parents,md5Checksum),nextPageToken",
) -> List[Dict[str, Any]]:
    """List Google Drive files visible to the current OAuth token."""
    results: List[Dict[str, Any]] = []
    page_token = ""
    limit = max(1, int(max_files or 1))
    while len(results) < limit:
        params: Dict[str, Any] = {
            "q": query,
            "spaces": "drive",
            "fields": fields,
            "pageSize": min(max(1, int(page_size or 100)), 1000),
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if page_token:
            params["pageToken"] = page_token
        response = _drive_request(config, "GET", f"{DRIVE_API}/files", params=params, timeout=45)
        if not response.ok:
            raise RuntimeError(f"Drive file search failed: HTTP {response.status_code}. {response.text[:700]}")
        payload = response.json()
        files = payload.get("files") or []
        if isinstance(files, list):
            results.extend([row for row in files if isinstance(row, dict)])
        page_token = str(payload.get("nextPageToken") or "")
        if not page_token or len(results) >= limit:
            break
    return results[:limit]


def _design_name_query() -> str:
    # Drive query language has name contains, not endswith; final filtering is done by TurboImport.
    parts: List[str] = []
    for ext in sorted(DESIGN_EXTENSIONS):
        suffix = _escape_drive_query_value(ext)
        parts.append(f"name contains '{suffix}'")
        parts.append(f"name contains '{suffix.upper()}'")
    return "(" + " or ".join(parts) + ")"


def search_drive_design_files(config: DriveOAuthConfig, *, max_files: int = 500) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Search Drive for embroidery design files visible to this app.

    With the default drive.file scope, Google only returns files/folders created
    or opened by this app, including EMBORGANIZER/Original Designs. If the user
    grants drive.readonly through the optional v4.6 setting, the same search can
    see matching files across more of the user's Drive.
    """
    tokens = get_drive_tokens()
    if not token_has_drive_read_scope(tokens):
        raise RuntimeError("Google Drive search permission is not available in the current sign-in token.")

    max_files = max(1, min(int(max_files or 500), 2000))
    base_q = f"trashed=false and mimeType!='{FOLDER_MIME}'"
    design_q = f"{base_q} and {_design_name_query()}"
    files = list_drive_files(config, query=design_q, max_files=max_files, page_size=min(1000, max_files))

    # Also check the app's Original Designs folder directly. This helps restore
    # designs uploaded by older EMBORGANIZER sessions, even when file names were
    # flattened for safe Drive upload.
    scan_notes: List[str] = ["global app-visible search"]
    try:
        root = find_folder(config, config.root_folder_name)
        if root and root.get("id"):
            originals = find_folder(config, config.originals_folder_name, str(root["id"]))
            if originals and originals.get("id"):
                parent_q = f"{base_q} and '{_escape_drive_query_value(str(originals['id']))}' in parents"
                files.extend(list_drive_files(config, query=parent_q, max_files=max_files, page_size=min(1000, max_files)))
                scan_notes.append(f"{config.root_folder_name}/{config.originals_folder_name}")
    except Exception as exc:
        scan_notes.append(f"Original Designs folder check skipped: {str(exc)[:120]}")

    seen: set[str] = set()
    unique: List[Dict[str, Any]] = []
    for row in files:
        file_id = str(row.get("id") or "")
        if file_id and file_id in seen:
            continue
        if file_id:
            seen.add(file_id)
        unique.append(row)
        if len(unique) >= max_files:
            break

    scopes = str((tokens or {}).get("scope") or "")
    mode = "full-drive-readonly" if (DRIVE_READONLY_SCOPE in scopes or "drive.readonly" in scopes) else "app-visible-drive-file"
    return unique, {"mode": mode, "notes": scan_notes, "max_files": max_files}


def download_drive_file(config: DriveOAuthConfig, file_id: str, target: Path) -> Dict[str, Any]:
    """Download one binary Google Drive file into target."""
    target.parent.mkdir(parents=True, exist_ok=True)
    response = _drive_request(
        config,
        "GET",
        f"{DRIVE_API}/files/{quote(str(file_id), safe='')}",
        params={"alt": "media", "supportsAllDrives": "true"},
        stream=True,
        timeout=120,
    )
    if not response.ok:
        raise RuntimeError(f"Drive download failed for {file_id}: HTTP {response.status_code}. {response.text[:700]}")
    total = 0
    tmp = target.with_suffix(target.suffix + ".download")
    with tmp.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            fh.write(chunk)
    tmp.replace(target)
    return {"path": str(target), "size_bytes": total}

def find_folder(config: DriveOAuthConfig, name: str, parent_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    q = f"name='{_escape_drive_query_value(name)}' and mimeType='{FOLDER_MIME}' and trashed=false"
    if parent_id:
        q += f" and '{_escape_drive_query_value(parent_id)}' in parents"
    response = _drive_request(
        config,
        "GET",
        f"{DRIVE_API}/files",
        params={
            "q": q,
            "spaces": "drive",
            "fields": "files(id,name,webViewLink)",
            "pageSize": 10,
        },
    )
    if not response.ok:
        raise RuntimeError(f"Drive folder lookup failed: HTTP {response.status_code}. {response.text[:700]}")
    files = response.json().get("files", [])
    return files[0] if files else None


def create_folder(config: DriveOAuthConfig, name: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {"name": name, "mimeType": FOLDER_MIME}
    if parent_id:
        metadata["parents"] = [parent_id]
    response = _drive_request(
        config,
        "POST",
        f"{DRIVE_API}/files",
        headers={"Content-Type": "application/json"},
        params={"fields": "id,name,webViewLink"},
        data=json.dumps(metadata),
    )
    if not response.ok:
        raise RuntimeError(f"Drive folder creation failed: HTTP {response.status_code}. {response.text[:700]}")
    return response.json()


def ensure_folder(config: DriveOAuthConfig, name: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
    existing = find_folder(config, name, parent_id=parent_id)
    if existing:
        return existing
    return create_folder(config, name, parent_id=parent_id)


def ensure_emborganizer_folders(config: DriveOAuthConfig) -> Dict[str, Dict[str, Any]]:
    cached = st.session_state.get("google_drive_folders")
    if isinstance(cached, dict) and cached.get("root", {}).get("id"):
        return cached  # type: ignore[return-value]

    root = ensure_folder(config, config.root_folder_name)
    library = ensure_folder(config, config.library_folder_name, root["id"])
    previews = ensure_folder(config, config.preview_folder_name, root["id"])
    originals = ensure_folder(config, config.originals_folder_name, root["id"])
    converted = ensure_folder(config, config.converted_folder_name, root["id"])
    progress = ensure_folder(config, config.progress_folder_name, root["id"])
    folders = {
        "root": root,
        "library": library,
        "previews": previews,
        "originals": originals,
        "converted": converted,
        "progress": progress,
    }
    st.session_state["google_drive_folders"] = folders
    return folders


def _metadata_part(metadata: Dict[str, Any], boundary: str) -> bytes:
    return (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
    ).encode("utf-8")


def _media_part(data: bytes, mime_type: str, boundary: str) -> bytes:
    return (
        f"--{boundary}\r\n"
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")


def upload_bytes_to_drive(
    config: DriveOAuthConfig,
    *,
    name: str,
    data: bytes,
    parent_id: str,
    mime_type: str = "application/octet-stream",
) -> Dict[str, Any]:
    boundary = "emborganizer_" + py_secrets.token_hex(12)
    metadata = {"name": name, "parents": [parent_id]}
    body = _metadata_part(metadata, boundary) + _media_part(data, mime_type, boundary)
    response = _drive_request(
        config,
        "POST",
        f"{DRIVE_UPLOAD_API}/files",
        headers={"Content-Type": f"multipart/related; boundary={boundary}"},
        params={"uploadType": "multipart", "fields": "id,name,webViewLink,size,md5Checksum"},
        data=body,
        timeout=90,
    )
    if not response.ok:
        raise RuntimeError(f"Drive upload failed for {name}: HTTP {response.status_code}. {response.text[:700]}")
    return response.json()


def upload_path_to_drive(config: DriveOAuthConfig, path: Path, parent_id: str, name: Optional[str] = None) -> Dict[str, Any]:
    mime_type, _ = mimetypes.guess_type(path.name)
    return upload_bytes_to_drive(
        config,
        name=name or path.name,
        data=path.read_bytes(),
        parent_id=parent_id,
        mime_type=mime_type or "application/octet-stream",
    )


def _safe_drive_filename(relative_path: str, fallback: str) -> str:
    clean = relative_path.replace("\\", "/").strip("/")
    if not clean:
        clean = fallback
    return clean.replace("/", "__")[:180]


def build_progress_text(items: List[Dict[str, Any]], paths: Any, *, include_runtime: bool = True) -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    folders = sorted({str(item.get("folder") or "Uploads") for item in items})
    formats = sorted({str((item.get("analysis") or {}).get("extension") or Path(item.get("name", "")).suffix.lower()) for item in items if item})
    total_bytes = sum(int((item.get("analysis") or {}).get("size_bytes") or 0) for item in items)
    lines = [
        "EMBORGANIZER STREAMLIT PROGRESS LOG",
        "====================================",
        f"Generated: {now}",
        "Current milestone: v4.6 Turbo Import, TurboEmb v3, C++ import scanner, Animation S",
        "",
        "Version progress:",
        "- v0.8.5: Original EMBORGANIZER app base; moved away from FastAPI runtime.",
        "- v1: Added Streamlit working app, previous-style GUI, TURBOEMB preview engine, C++ renderer with Python fallback, sharper 1080p previews.",
        "- v2: Focused on folder import; directory upload, ZIP fallback, folder preservation, duplicate controls, safer folder limits.",
        "- v3: Added direct converter URLs for DST/PES/JEF/EXP/VP3/HUS/XXX/EMB to PNG/JPG/WEBP.",
        "- v3.1: Fixed Streamlit page routing by adding the pages folder and converter page fallbacks.",
        "- v4: Added Google sign-in page and image quality selector profiles: 720p, 1080p, 2K, 4K, Custom.",
        "- v4.1: Rebuilt Google login to use safe login-only scopes: openid, email, profile.",
        "- v4.2: Added Google Drive connection page, Drive folder creation, library/progress/original/preview sync, and this progress .txt file.",
        "- v4.3: Rebuilt Drive sync so drive.file permission is requested during Google sign-in, avoiding /google-drive redirect_uri_mismatch. Added session Enable Google Drive sync toggle.",
        "- v4.4: Added server-side Google sign-in persistence under emborganizer_data_streamlit/auth_sessions and restore-on-rerun/page navigation.",
        "- v4.5: Launched Turbo Engine release with TurboEmb v3 labels, 4K image generation defaults, and Animation v1 GUI motion system.",
        "- v4.6: Added Turbo Import startup scan after Google sign-in, user-permission import from Google Drive, optional C++ native Drive manifest scanner, and Animation S import UI.",
        "",
        "Current local Streamlit session:",
        f"- Designs in library: {len(items)}",
        f"- Folders detected: {len(folders)}",
        f"- Formats detected: {', '.join(formats) if formats else 'none yet'}",
        f"- Approx original file storage: {total_bytes} bytes",
    ]
    if include_runtime:
        lines.extend([
            f"- Session root: {getattr(paths, 'root', '')}",
            f"- Uploads folder: {getattr(paths, 'uploads', '')}",
            f"- Previews folder: {getattr(paths, 'previews', '')}",
            f"- Library JSON: {getattr(paths, 'library_file', '')}",
        ])
    lines.extend([
        "",
        "Google setup status:",
        "- Sign in: v4.6 keeps v4.4 server-side sign-in saving and can include Google Drive file permission when enabled.",
        "- Drive: uses the sign-in token; no separate /google-drive OAuth redirect is required.",
        "- Gmail: optional future import feature; keep disabled until Drive sync is stable.",
        "",
        "Next recommended updates:",
        "- v5: Multi-account team library sync, deeper Drive restore rules, and cloud render queue.",
        "- v6: Gmail attachment import after Google verification/testing is ready.",
        "- Later: Saved image fingerprints and batch background rendering for very large libraries.",
        "",
        "Secrets reminder:",
        "[google_oauth] client_id, client_secret, redirect_uri",
        "[google_drive] enabled=true, root_folder_name",
        "Never commit real secrets to GitHub.",
    ])
    return "\n".join(lines) + "\n"


def write_progress_file(project_root: Path, items: Optional[List[Dict[str, Any]]] = None, paths: Any = None) -> Path:
    progress_path = project_root / APP_PROGRESS_FILENAME
    text = build_progress_text(items or [], paths or object(), include_runtime=paths is not None)
    progress_path.write_text(text, encoding="utf-8")
    return progress_path


def sync_to_drive(
    config: DriveOAuthConfig,
    items: List[Dict[str, Any]],
    paths: Any,
    *,
    upload_library: bool = True,
    upload_progress: bool = True,
    upload_originals: bool = False,
    upload_previews: bool = False,
    upload_exports: bool = False,
    max_files: int = 100,
) -> List[Dict[str, Any]]:
    folders = ensure_emborganizer_folders(config)
    results: List[Dict[str, Any]] = []
    tasks: List[Tuple[str, Path, str, str]] = []

    if upload_library and Path(getattr(paths, "library_file", "")).exists():
        tasks.append(("library", Path(paths.library_file), folders["library"]["id"], "library.json"))

    if upload_progress:
        progress_text = build_progress_text(items, paths, include_runtime=True).encode("utf-8")
        result = upload_bytes_to_drive(
            config,
            name=APP_PROGRESS_FILENAME,
            data=progress_text,
            parent_id=folders["progress"]["id"],
            mime_type="text/plain",
        )
        results.append({"type": "progress", "name": result.get("name"), "ok": True, "link": result.get("webViewLink")})

    if upload_originals:
        for item in items:
            source = Path(str(item.get("path", "")))
            if source.exists():
                name = _safe_drive_filename(str(item.get("relative_path") or source.name), source.name)
                tasks.append(("original", source, folders["originals"]["id"], name))

    if upload_previews:
        for item in items:
            preview = Path(str(item.get("preview_path", "")))
            if preview.exists():
                name = _safe_drive_filename(str(item.get("relative_path") or preview.name), preview.name)
                stem = Path(name).stem
                tasks.append(("preview", preview, folders["previews"]["id"], f"{stem}.webp"))

    if upload_exports:
        exports_folder = Path(getattr(paths, "exports", ""))
        if exports_folder.exists():
            for path in sorted(exports_folder.glob("*")):
                if path.is_file():
                    tasks.append(("export", path, folders["converted"]["id"], path.name))

    tasks = tasks[: max(0, int(max_files))]
    progress = st.progress(0, text="Preparing Google Drive sync…") if tasks else None
    for idx, (kind, path, parent_id, name) in enumerate(tasks, start=1):
        if progress:
            progress.progress((idx - 1) / max(1, len(tasks)), text=f"Uploading {idx}/{len(tasks)}: {name[:70]}")
        try:
            result = upload_path_to_drive(config, path, parent_id, name=name)
            results.append({"type": kind, "name": result.get("name"), "ok": True, "link": result.get("webViewLink")})
        except Exception as exc:
            results.append({"type": kind, "name": name, "ok": False, "error": str(exc)})
    if progress:
        progress.progress(1.0, text="Google Drive sync complete")
        time.sleep(0.25)
        progress.empty()
    return results


def render_drive_status(config: DriveOAuthConfig) -> None:
    tokens = get_drive_tokens()
    if not tokens:
        st.warning("Google Drive permission is not in the current Google sign-in token.")
        return
    scopes = str(tokens.get("scope") or "")
    st.success("Google Drive permission is active from sign-in.")
    with st.expander("Drive token details"):
        st.write("Scopes:")
        st.code(scopes or "scope not returned", language="text")
        st.write("Refresh token available:", bool(tokens.get("refresh_token")))
        st.write("Created at:", tokens.get("created_at"))


def _render_resignin_for_drive() -> None:
    st.error("Drive sync is enabled, but your current sign-in token does not include Google Drive file access.")
    st.write("Fix: update Streamlit Secrets as shown below, then sign out and sign in again so Google asks for Drive permission during login.")
    st.code(
        '''[google_oauth]
client_id = "YOUR_GOOGLE_CLIENT_ID"
client_secret = "YOUR_GOOGLE_CLIENT_SECRET"
redirect_uri = "https://emborganizer.streamlit.app"
login_scopes = ["openid", "email", "profile"]
enable_gdrive_sync = true
strict_state = false
debug = false

[google_drive]
enabled = true
root_folder_name = "EMBORGANIZER"
library_folder_name = "Library"
preview_folder_name = "Previews"
originals_folder_name = "Original Designs"
converted_folder_name = "Converted Images"
progress_folder_name = "Progress"''',
        language="toml",
    )
    st.info("Google Cloud redirect URI should stay the same one that already works for sign-in. Do not use /google-drive unless you also register that exact URI.")
    if st.button("Sign out so I can sign in with Drive permission", type="primary", width="stretch"):
        try:
            from google_auth import clear_google_session
            clear_google_session()
        except Exception:
            clear_drive_session()
        st.rerun()


def render_google_drive_page(paths: Any, items: List[Dict[str, Any]]) -> None:
    st.markdown(
        """
        <div class="emb-hero">
            <h1>Google Drive Sync</h1>
            <div class="emb-badge">EMBORGANIZER v4.6 Turbo Import + server-saved login + Drive</div>
            <p>Drive permission is requested during Google Sign In, sign-in data is saved server-side, and v4.6 can scan Drive for restorable embroidery designs after login.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    user = get_google_user() if get_google_user is not None else None
    if not user:
        st.warning("Sign in with Google first. Drive permission is included during sign-in when Drive sync is enabled.")
        if st.button("Go to Sign In", type="primary", width="stretch"):
            try:
                st.switch_page("pages/sign-in.py")
            except Exception:
                st.info("Open the Sign In page from the sidebar.")
        return
    if user.get("demo"):
        st.warning("Demo sessions cannot connect real Google Drive. Sign out, then sign in with your Google account.")
        return

    config, missing = drive_oauth_config()
    if missing or config is None:
        st.error("Google Drive is not ready because Streamlit Secrets are missing.")
        st.code("\n".join(missing), language="text")
        return

    if not drive_sync_enabled():
        st.warning("Google Drive sync is disabled in Streamlit Secrets.")
        st.code('''[google_oauth]
enable_gdrive_sync = true

[google_drive]
enabled = true''', language="toml")
        return

    st.markdown(f"Signed in as **{user.get('email')}**")
    st.caption(f"Drive uses the same OAuth redirect URI as sign-in: `{config.redirect_uri}`")

    enabled_for_session = st.toggle("Enable Google Drive sync for this session", value=st.session_state.get("gdrive_sync_enabled", True), key="gdrive_sync_enabled")
    if not enabled_for_session:
        st.info("Google Drive sync is paused for this browser session.")
        return

    tokens = get_drive_tokens()
    left, right = st.columns([0.62, 0.38])
    with left:
        render_drive_status(config)
    with right:
        if st.button("Refresh Drive status", width="stretch"):
            st.session_state.pop("google_drive_folders", None)
            st.rerun()
        if st.button("Pause Drive sync", width="stretch"):
            st.session_state["gdrive_sync_enabled"] = False
            st.rerun()

    if not tokens:
        _render_resignin_for_drive()
        return

    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Library files", f"{len(items):,}")
    c2.metric("Root folder", config.root_folder_name)
    c3.metric("Progress TXT", APP_PROGRESS_FILENAME)
    c4.metric("Drive scope", "drive.file")

    st.markdown("### Turbo Import from Google Drive")
    st.caption("v4.6 can scan Drive for DST/PES/JEF/EXP/VP3/HUS/XXX/EMB files visible to this app. Import starts only after your approval.")
    scan_limit = st.slider("Turbo Import scan limit", min_value=50, max_value=2000, value=500, step=50, key="drive_turbo_import_scan_limit")
    if st.button("Run Turbo Import Drive scan", type="secondary", width="stretch"):
        try:
            from turbo_import_engine import filter_supported_drive_files
            manifest, scan_info = search_drive_design_files(config, max_files=int(scan_limit))
            supported, engine_info = filter_supported_drive_files(manifest, DESIGN_EXTENSIONS)
            st.session_state["turbo_import_manifest"] = {
                "files": supported,
                "scan_info": scan_info,
                "engine_info": engine_info,
                "scanned_at": int(time.time()),
            }
            st.success(f"Turbo Import found {len(supported):,} supported design file{'s' if len(supported) != 1 else ''}.")
            with st.expander("Found design files", expanded=bool(supported)):
                for row in supported[:100]:
                    st.write(f"🧵 {row.get('name')} · {row.get('size', 'unknown size')}")
                if len(supported) > 100:
                    st.caption(f"Showing first 100 of {len(supported):,} files.")
                st.json({"scan": scan_info, "engine": engine_info})
        except Exception as exc:
            st.error("Turbo Import scan failed.")
            st.exception(exc)

    if st.button("Create / verify EMBORGANIZER Drive folders", type="secondary", width="stretch"):
        try:
            folders = ensure_emborganizer_folders(config)
            st.success("Google Drive folders are ready.")
            for key, folder in folders.items():
                st.write(f"✅ {key}: {folder.get('name')} — {folder.get('webViewLink', '')}")
        except Exception as exc:
            st.error("Could not create Google Drive folders.")
            st.exception(exc)

    with st.expander("Check Drive account status"):
        if st.button("Run Drive status check"):
            try:
                about = drive_about(config)
                drive_user = (about.get("user") or {}).get("emailAddress") or "Drive user"
                st.success(f"Drive API connected as {drive_user}.")
                st.json(about)
            except Exception as exc:
                st.error("Drive status check failed.")
                st.exception(exc)

    st.markdown("### Sync current Streamlit session to Google Drive")
    upload_library = st.checkbox("Upload library.json index", value=True)
    upload_progress = st.checkbox("Upload progress TXT file", value=True)
    upload_originals = st.checkbox("Upload original embroidery files", value=False)
    upload_previews = st.checkbox("Upload preview images", value=False)
    upload_exports = st.checkbox("Upload generated exports/converter ZIPs", value=False)
    max_files = st.slider("Max file uploads this sync", min_value=1, max_value=500, value=100, step=10)

    st.caption("Tip: Start with library.json + progress TXT. Turn on originals/previews after the folder test works.")
    if st.button("Sync to Google Drive now", type="primary", width="stretch"):
        try:
            results = sync_to_drive(
                config,
                items,
                paths,
                upload_library=upload_library,
                upload_progress=upload_progress,
                upload_originals=upload_originals,
                upload_previews=upload_previews,
                upload_exports=upload_exports,
                max_files=max_files,
            )
            ok_count = sum(1 for row in results if row.get("ok"))
            st.success(f"Google Drive sync complete: {ok_count}/{len(results)} uploaded.")
            with st.expander("Upload results", expanded=True):
                for row in results:
                    icon = "✅" if row.get("ok") else "⚠️"
                    link = row.get("link")
                    if link:
                        st.markdown(f"{icon} **{row.get('type')}** · [{row.get('name')}]({link})")
                    else:
                        st.write(f"{icon} {row.get('type')} · {row.get('name')} {row.get('error', '')}")
        except Exception as exc:
            st.error("Google Drive sync failed.")
            st.exception(exc)

    st.markdown("### Local progress TXT")
    try:
        project_root = Path(__file__).resolve().parent
        progress_path = write_progress_file(project_root, items, paths)
        st.download_button(
            "Download EMBORGANIZER progress TXT",
            data=progress_path.read_bytes(),
            file_name=APP_PROGRESS_FILENAME,
            mime="text/plain",
            width="stretch",
        )
    except Exception as exc:
        st.warning(f"Could not prepare progress TXT download: {exc}")
