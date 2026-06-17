from __future__ import annotations

import hashlib
import secrets as py_secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests
import streamlit as st

try:
    from google_server_auth_store import (
        delete_google_login,
        restore_google_login_to_session_state,
        save_google_login,
        server_session_metadata,
    )
except Exception:  # pragma: no cover - server auth persistence is optional
    delete_google_login = None  # type: ignore
    restore_google_login_to_session_state = None  # type: ignore
    save_google_login = None  # type: ignore
    server_session_metadata = None  # type: ignore

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

# v4.4 important change:
# Google sign-in is persisted on the server after login, then restored into
# Streamlit session_state on later reruns/page navigation. Drive permission is
# still requested during Google sign-in when enabled. Gmail remains disabled by
# default because gmail.readonly is a restricted scope.
DEFAULT_LOGIN_SCOPES = ["openid", "email", "profile"]
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
BLOCKED_LOGIN_SCOPE_MARKERS = (
    "gmail.",
    "mail.google.com",
    "/auth/gmail",
    "/auth/spreadsheets",
    "/auth/calendar",
)


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: List[str]
    strict_state: bool = False
    debug: bool = False
    enable_gdrive_sync: bool = False


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
    seen: set[str] = set()
    scopes: List[str] = []
    for item in parts:
        scope = str(item).strip().strip('"').strip("'")
        if scope and scope not in seen:
            scopes.append(scope)
            seen.add(scope)
    return scopes


def _dedupe_scopes(scopes: List[str]) -> List[str]:
    seen: set[str] = set()
    clean: List[str] = []
    for scope in scopes:
        lowered = scope.lower()
        if any(marker in lowered for marker in BLOCKED_LOGIN_SCOPE_MARKERS):
            # Do not request Gmail or other restricted APIs in the normal sign-in flow.
            continue
        if scope and scope not in seen:
            clean.append(scope)
            seen.add(scope)
    return clean


def _login_scopes(
    base_scopes: List[str],
    *,
    enable_gdrive_sync: bool,
    allow_extra_scopes: bool,
    enable_full_drive_turbo_import: bool = False,
) -> List[str]:
    # Always include normal identity scopes.
    scopes: List[str] = list(DEFAULT_LOGIN_SCOPES)

    # Only include extra non-Gmail scopes if explicitly requested.
    if allow_extra_scopes:
        scopes.extend(base_scopes)

    # v4.6 keeps Drive permission in the main login token so Turbo Import can
    # search app-visible Drive files immediately after sign-in.
    if enable_gdrive_sync:
        scopes.append(DRIVE_FILE_SCOPE)
        # Optional: lets Turbo Import search more than app-created/opened files.
        # This may require extra Google Cloud verification, so it stays opt-in.
        if enable_full_drive_turbo_import:
            scopes.append(DRIVE_READONLY_SCOPE)

    return _dedupe_scopes(scopes)


def google_oauth_config() -> Tuple[Optional[GoogleOAuthConfig], List[str]]:
    section = _get_section("google_oauth")
    missing: List[str] = []
    client_id = str(section.get("client_id", "")).strip()
    client_secret = str(section.get("client_secret", "")).strip()
    redirect_uri = str(section.get("redirect_uri", "")).strip()

    if not client_id or client_id.startswith(("PASTE_", "YOUR_")):
        missing.append("google_oauth.client_id")
    if not client_secret or client_secret.startswith(("PASTE_", "YOUR_")):
        missing.append("google_oauth.client_secret")
    if not redirect_uri or redirect_uri.startswith(("https://YOUR", "http://YOUR")):
        missing.append("google_oauth.redirect_uri")

    # Backward compatible: old secrets used `scopes`; new secrets can use `login_scopes`.
    raw_scopes = section.get("login_scopes", section.get("scopes", DEFAULT_LOGIN_SCOPES))
    allow_extra_scopes = _truthy(section.get("allow_extra_scopes"), default=False)

    drive_section = _get_section("google_drive")
    enable_gdrive_sync = (
        _truthy(section.get("enable_gdrive_sync"), default=False)
        or _truthy(drive_section.get("enabled"), default=False)
    )
    enable_full_drive_turbo_import = (
        _truthy(section.get("turbo_import_full_drive"), default=False)
        or _truthy(drive_section.get("turbo_import_full_drive"), default=False)
    )
    scopes = _login_scopes(
        _normalize_scopes(raw_scopes),
        enable_gdrive_sync=enable_gdrive_sync,
        allow_extra_scopes=allow_extra_scopes,
        enable_full_drive_turbo_import=enable_full_drive_turbo_import,
    )

    strict_state = _truthy(section.get("strict_state"), default=False)
    debug = _truthy(section.get("debug"), default=False)

    if missing:
        return None, missing
    return GoogleOAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=scopes,
        strict_state=strict_state,
        debug=debug,
        enable_gdrive_sync=enable_gdrive_sync,
    ), []


def restore_google_session_from_server() -> bool:
    if restore_google_login_to_session_state is None:
        return False
    if st.session_state.get("google_user") and st.session_state.get("google_tokens"):
        return False
    try:
        return bool(restore_google_login_to_session_state())
    except Exception:
        return False


def persist_current_google_session() -> None:
    if save_google_login is None:
        return
    user = st.session_state.get("google_user")
    tokens = st.session_state.get("google_tokens")
    drive_tokens = st.session_state.get("google_drive_tokens")
    if isinstance(user, dict) and isinstance(tokens, dict):
        try:
            save_google_login(user=user, tokens=tokens, drive_tokens=drive_tokens if isinstance(drive_tokens, dict) else None)
        except Exception:
            # Never break login just because disk persistence failed.
            pass


def get_google_user() -> Optional[Dict[str, Any]]:
    user = st.session_state.get("google_user")
    if not (isinstance(user, dict) and user.get("email")):
        restore_google_session_from_server()
        user = st.session_state.get("google_user")
    return user if isinstance(user, dict) and user.get("email") else None


def get_google_tokens() -> Optional[Dict[str, Any]]:
    tokens = st.session_state.get("google_tokens")
    if not (isinstance(tokens, dict) and tokens.get("access_token")):
        restore_google_session_from_server()
        tokens = st.session_state.get("google_tokens")
    return tokens if isinstance(tokens, dict) and tokens.get("access_token") else None


def clear_google_session() -> None:
    if delete_google_login is not None:
        try:
            delete_google_login()
        except Exception:
            pass
    for key in [
        "google_user",
        "google_tokens",
        "google_oauth_state",
        "google_oauth_started",
        "google_oauth_error",
        "google_drive_tokens",
        "google_drive_folders",
        "turbo_import_manifest",
        "turbo_import_auto_scan_key",
        "turbo_import_user_permit",
    ]:
        st.session_state.pop(key, None)


def use_demo_login(email: str = "demo@emborganizer.local", name: str = "Demo User") -> None:
    st.session_state["google_user"] = {
        "email": email,
        "name": name,
        "picture": "",
        "sub": hashlib.sha256(email.encode("utf-8")).hexdigest(),
        "email_verified": True,
        "demo": True,
    }
    st.session_state["google_tokens"] = {"access_token": "demo-session", "created_at": int(time.time()), "demo": True}
    persist_current_google_session()


def build_google_auth_url(config: GoogleOAuthConfig) -> str:
    state = py_secrets.token_urlsafe(24)
    st.session_state["google_oauth_state"] = state
    st.session_state["google_oauth_started"] = int(time.time())
    params = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "scope": " ".join(config.scopes),
        "access_type": "offline" if config.enable_gdrive_sync else "online",
        "include_granted_scopes": "true" if config.enable_gdrive_sync else "false",
        "prompt": "consent" if config.enable_gdrive_sync else "select_account",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def _query_value(name: str) -> str:
    try:
        value = st.query_params.get(name, "")
    except Exception:
        value = ""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def exchange_code_for_tokens(config: GoogleOAuthConfig, code: str) -> Dict[str, Any]:
    payload = {
        "code": code,
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "redirect_uri": config.redirect_uri,
        "grant_type": "authorization_code",
    }
    response = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=20)
    if not response.ok:
        detail = response.text[:900]
        raise RuntimeError(f"Google token exchange failed: HTTP {response.status_code}. {detail}")
    tokens = response.json()
    tokens["created_at"] = int(time.time())
    return tokens


def fetch_google_userinfo(access_token: str) -> Dict[str, Any]:
    response = requests.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=20)
    if not response.ok:
        detail = response.text[:900]
        raise RuntimeError(f"Google userinfo failed: HTTP {response.status_code}. {detail}")
    return response.json()


def handle_google_oauth_callback(*, show_success: bool = True) -> bool:
    code = _query_value("code")
    error = _query_value("error")
    error_description = _query_value("error_description")
    if error:
        msg = f"Google sign-in was cancelled or blocked: {error}"
        if error_description:
            msg += f" — {error_description}"
        st.error(msg)
        return True
    if not code:
        return False

    config, missing = google_oauth_config()
    if missing or config is None:
        st.error("Google returned a login code, but OAuth secrets are not configured correctly.")
        st.code("\n".join(missing), language="text")
        return True

    returned_state = _query_value("state")
    expected_state = st.session_state.get("google_oauth_state")
    if config.strict_state and expected_state and returned_state != expected_state:
        st.error("Google sign-in state check failed. Please click Sign in again.")
        return True

    try:
        tokens = exchange_code_for_tokens(config, code)
        user = fetch_google_userinfo(tokens["access_token"])
        st.session_state["google_tokens"] = tokens
        if DRIVE_FILE_SCOPE in str(tokens.get("scope", "")) or "drive.file" in str(tokens.get("scope", "")):
            # Keep one-token model: Drive sync uses the Google sign-in token.
            st.session_state["google_drive_tokens"] = tokens
        st.session_state["google_user"] = {
            "email": user.get("email", ""),
            "name": user.get("name") or user.get("email", "Google user"),
            "picture": user.get("picture", ""),
            "sub": user.get("sub", ""),
            "email_verified": bool(user.get("email_verified", False)),
            "demo": False,
        }
        persist_current_google_session()
        for key in ["google_oauth_state", "google_oauth_started", "google_oauth_error"]:
            st.session_state.pop(key, None)
        try:
            st.query_params.clear()
        except Exception:
            pass
        if show_success:
            st.success(f"Signed in as {st.session_state['google_user'].get('email')}.")
        st.rerun()
        return True
    except Exception as exc:
        st.error("Google sign-in failed while finishing the login inside EMBORGANIZER.")
        st.exception(exc)
        return True


def render_sign_in_status_card() -> None:
    user = get_google_user()
    if not user:
        st.info("You are not signed in yet.")
        return
    cols = st.columns([1, 4])
    picture = str(user.get("picture") or "")
    with cols[0]:
        if picture:
            st.image(picture, width=72)
        else:
            st.markdown("### 👤")
    with cols[1]:
        label = "Demo session" if user.get("demo") else "Google login connected"
        st.markdown(f"### {user.get('name') or 'Google user'}")
        st.write(user.get("email"))
        tokens = get_google_tokens() or {}
        scopes = str(tokens.get("scope") or "")
        drive_status = "Drive sync permission granted" if (DRIVE_FILE_SCOPE in scopes or "drive.file" in scopes) else "Drive sync permission not granted yet"
        st.caption(f"{label}. {drive_status}.")
        if server_session_metadata is not None:
            try:
                meta = server_session_metadata()
                if meta.get("enabled") and meta.get("saved"):
                    st.caption("Server-side sign-in data is saved for this app session.")
                elif meta.get("enabled"):
                    st.caption("Server-side sign-in saving is enabled, but no saved record was found yet.")
            except Exception:
                pass


def _render_secret_help() -> None:
    st.error("Google sign-in is not ready because Streamlit Secrets are missing.")
    st.write("Add these keys in Streamlit Cloud → App → Settings → Secrets:")
    st.code(
        '''[google_oauth]\nclient_id = "YOUR_GOOGLE_CLIENT_ID"\nclient_secret = "YOUR_GOOGLE_CLIENT_SECRET"\nredirect_uri = "https://emborganizer.streamlit.app"\nlogin_scopes = ["openid", "email", "profile"]\nenable_gdrive_sync = true\nstrict_state = false\ndebug = false\n\n[google_drive]\nenabled = true\nroot_folder_name = "EMBORGANIZER"\n\n[auth_session]\nenabled = true\n# Use a long random value in production so saved sessions survive restarts.\nserver_secret = "CHANGE_ME_TO_A_LONG_RANDOM_SECRET"\nmax_age_days = 30''',
        language="toml",
    )
    st.warning("Add the same redirect_uri value in Google Cloud → Credentials → Authorized redirect URIs.")


def render_google_sign_in_page() -> None:
    st.markdown(
        """
        <div class="emb-hero">
            <h1>Sign in</h1>
            <div class="emb-badge">EMBORGANIZER v4.6 Turbo Import + server-saved login</div>
            <p>Google sign-in is saved on the app server after login, then restored during app reruns and page navigation. v4.6 also prepares Turbo Import so Drive designs can be scanned after login and imported only with your approval.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    handled = handle_google_oauth_callback(show_success=True)
    if handled:
        return

    user = get_google_user()
    if user:
        render_sign_in_status_card()
        if st.button("Sign out", type="secondary", width="stretch"):
            clear_google_session()
            st.rerun()
        return

    config, missing = google_oauth_config()
    if missing or config is None:
        _render_secret_help()
        st.markdown("---")
        st.write("Temporary app test mode:")
        if st.button("Continue with demo session", type="secondary", width="stretch"):
            use_demo_login()
            st.rerun()
        return

    auth_url = build_google_auth_url(config)
    st.link_button("Continue with Google", auth_url, type="primary", width="stretch")
    if config.enable_gdrive_sync:
        st.caption("This login asks for: openid, email, profile, and Google Drive file access for EMBORGANIZER sync + Turbo Import. Optional full-Drive search is used only if you enabled turbo_import_full_drive in secrets.")
    else:
        st.caption("This login asks only for: openid, email, profile.")

    if config.debug:
        with st.expander("OAuth debug info"):
            st.write("Redirect URI configured in secrets:")
            st.code(config.redirect_uri, language="text")
            st.write("Scopes actually sent to Google:")
            st.code("\n".join(config.scopes), language="text")
            st.write("Generated Google URL:")
            st.code(auth_url, language="text")

    st.markdown("---")
    st.write("Need to test the rest of the app while Google Cloud is still being configured?")
    if st.button("Continue with demo session", type="secondary", width="stretch"):
        use_demo_login()
        st.rerun()
