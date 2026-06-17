from __future__ import annotations

import hashlib
import io
import json
import math
import os
import shutil
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Tuple

import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

try:
    import pyembroidery
except Exception:  # pragma: no cover - handled in the UI
    pyembroidery = None

try:
    from imagesearch import create_fingerprint_from_image, create_fingerprint_from_path, compare_fingerprints, IMGS_ENGINE_VERSION
except Exception:  # pragma: no cover - image search is optional
    create_fingerprint_from_image = None
    create_fingerprint_from_path = None
    compare_fingerprints = None
    IMGS_ENGINE_VERSION = "Image search unavailable"

try:
    from turboemb_engine import (
        TURBOEMB_ENGINE_VERSION,
        ensure_cpp_renderer,
        render_pattern_with_cpp,
        turboemb_postprocess_rgb,
    )
except Exception:  # pragma: no cover - native acceleration is optional
    TURBOEMB_ENGINE_VERSION = "TurboEmb v3 • Python fallback"
    ensure_cpp_renderer = None
    render_pattern_with_cpp = None
    turboemb_postprocess_rgb = None

try:
    from google_auth import get_google_user, clear_google_session, handle_google_oauth_callback, restore_google_session_from_server
except Exception:  # pragma: no cover - Google login is optional
    get_google_user = None
    clear_google_session = None
    handle_google_oauth_callback = None
    restore_google_session_from_server = None

try:
    from quality_profiles import image_quality_selector
except Exception:  # pragma: no cover - quality UI is optional
    image_quality_selector = None

try:
    from animation_engine import ANIMATION_ENGINE_VERSION, TURBO_UI_RELEASE, TURBO_UI_FEATURES
except Exception:  # pragma: no cover - animated UI metadata is optional
    ANIMATION_ENGINE_VERSION = "Animation S"
    TURBO_UI_RELEASE = "Turbo Engine UI"
    TURBO_UI_FEATURES = ["Animated hero glow", "Motion-safe cards", "4K generation callouts"]

try:
    from turbo_import_engine import (
        TURBO_IMPORT_ENGINE_VERSION,
        TURBO_IMPORT_ANIMATION_VERSION,
        ensure_turbo_import_native,
        filter_supported_drive_files,
    )
except Exception:  # pragma: no cover - turbo import is optional
    TURBO_IMPORT_ENGINE_VERSION = "TurboImport v1 • Python fallback"
    TURBO_IMPORT_ANIMATION_VERSION = "Animation S"
    ensure_turbo_import_native = None
    filter_supported_drive_files = None

try:
    from imgs_training import (
        IMGS_TRAINING_VERSION,
        TURBOTHINKER_ENGINE_VERSION,
        IMGS_TRAINING_TAG,
        TURBOTHINKER_TAG,
        IMGS_TRAINING_WARNING,
        IMGS_LABELS,
        ANNE_CATEGORY_TAGS,
        ANNE_CATEGORY_TAG_SLUGS,
        analyze_image_for_training,
        apply_imgs_training_to_item,
        build_training_index,
        candidate_search_groups,
        ensure_training_dirs,
        load_cached_fingerprint,
        load_corrections,
        load_training_index,
        record_training_correction,
        save_uploaded_training_image,
        summarize_training,
        prune_prediction_tags,
        add_manual_tags,
        analyze_selector_area,
        record_selector_area_training,
        build_seed_training_corpus_from_zip_bytes,
        build_ultrabrain_region_corpus_from_zip_bytes,
        load_seed_training_bank,
        load_ultrabrain_region_bank,
        train_turbothinker_student_model,
        load_turbothinker_student_summary,
        apply_student_model_memory,
        train_turbothinker_ultrabrain_model,
        load_turbothinker_ultrabrain_summary,
        apply_ultrabrain_memory,
        train_turbothinker_superbrain_model,
        load_turbothinker_superbrain_summary,
        apply_superbrain_memory,
        STUDENT_MODEL_VERSION,
        ULTRABRAIN_VERSION,
        SUPERBRAIN_VERSION,
        TAG_CATALOG,
    )
except Exception:  # pragma: no cover - IMGS training is optional
    IMGS_TRAINING_VERSION = "IMGS BetaV1 training unavailable"
    TURBOTHINKER_ENGINE_VERSION = "TurboThinker unavailable"
    IMGS_TRAINING_TAG = "IMGS Engine"
    TURBOTHINKER_TAG = "TurboThinker Engine"
    IMGS_TRAINING_WARNING = "IMGS training is unavailable in this build."
    IMGS_LABELS = ["unknown_review"]
    ANNE_CATEGORY_TAGS = []
    ANNE_CATEGORY_TAG_SLUGS = {}
    analyze_image_for_training = None
    apply_imgs_training_to_item = None
    build_training_index = None
    candidate_search_groups = None
    ensure_training_dirs = None
    load_cached_fingerprint = None
    load_corrections = None
    load_training_index = None
    record_training_correction = None
    save_uploaded_training_image = None
    summarize_training = None
    prune_prediction_tags = None
    add_manual_tags = None
    analyze_selector_area = None
    record_selector_area_training = None
    build_seed_training_corpus_from_zip_bytes = None
    build_ultrabrain_region_corpus_from_zip_bytes = None
    load_seed_training_bank = None
    load_ultrabrain_region_bank = None
    train_turbothinker_student_model = None
    load_turbothinker_student_summary = None
    apply_student_model_memory = None
    train_turbothinker_ultrabrain_model = None
    load_turbothinker_ultrabrain_summary = None
    apply_ultrabrain_memory = None
    train_turbothinker_superbrain_model = None
    load_turbothinker_superbrain_summary = None
    apply_superbrain_memory = None
    STUDENT_MODEL_VERSION = "TurboThinker Student unavailable"
    ULTRABRAIN_VERSION = "TurboThinker UltraBrain unavailable"
    SUPERBRAIN_VERSION = "TurboThinker SuperBrain unavailable"
    TAG_CATALOG = {}

try:
    from sync_engine import SYNC_ENGINE_VERSION, ensure_sync_native, sync_library_cache
except Exception:  # pragma: no cover - TurboSync is optional
    SYNC_ENGINE_VERSION = "TurboSync unavailable"
    ensure_sync_native = None
    sync_library_cache = None


APP_NAME = "EMBORGANIZER"
APP_VERSION = "v4.8.2"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "emborganizer_data_streamlit"
SESSIONS_DIR = DATA_DIR / "sessions"
STATIC_DIR = BASE_DIR / "static"
SUPPORTED_EXTENSIONS = {".dst", ".pes", ".jef", ".exp", ".vp3", ".hus", ".xxx", ".emb"}
DESIGN_UPLOAD_EXTENSIONS = sorted({ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS})
UPLOAD_EXTENSIONS = sorted(set(DESIGN_UPLOAD_EXTENSIONS) | {"zip"})
DEFAULT_PREVIEW_SIZE = int(os.environ.get("EMB_STREAMLIT_PREVIEW_SIZE", "1080"))
TURBO_4K_IMAGE_SIZE = max(512, min(int(os.environ.get("EMB_TURBO_4K_IMAGE_SIZE", "4096")), 4096))
DEFAULT_GENERATION_SIZE = max(512, min(int(os.environ.get("EMB_STREAMLIT_GENERATION_SIZE", str(TURBO_4K_IMAGE_SIZE))), 4096))
MAX_DRAW_SEGMENTS = int(os.environ.get("EMB_STREAMLIT_MAX_DRAW_SEGMENTS", "900000"))
ZIP_MAX_FILES = int(os.environ.get("EMB_STREAMLIT_ZIP_MAX_FILES", "1000"))
ZIP_MAX_BYTES = int(os.environ.get("EMB_STREAMLIT_ZIP_MAX_BYTES", str(300 * 1024 * 1024)))
FOLDER_MAX_FILES = int(os.environ.get("EMB_STREAMLIT_FOLDER_MAX_FILES", "5000"))
FOLDER_MAX_DESIGNS = int(os.environ.get("EMB_STREAMLIT_FOLDER_MAX_DESIGNS", "1500"))
FOLDER_MAX_BYTES = int(os.environ.get("EMB_STREAMLIT_FOLDER_MAX_BYTES", str(500 * 1024 * 1024)))
DIRECT_CONVERTER_MAX_FILES = int(os.environ.get("EMB_STREAMLIT_DIRECT_CONVERTER_MAX_FILES", "100"))
DIRECT_CONVERTER_MAX_BYTES = int(os.environ.get("EMB_STREAMLIT_DIRECT_CONVERTER_MAX_BYTES", str(200 * 1024 * 1024)))
TURBO_IMPORT_DEFAULT_SCAN_LIMIT = int(os.environ.get("EMB_TURBO_IMPORT_SCAN_LIMIT", "500"))
TURBO_IMPORT_DEFAULT_IMPORT_LIMIT = int(os.environ.get("EMB_TURBO_IMPORT_IMPORT_LIMIT", "250"))

for folder in [DATA_DIR, SESSIONS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class SessionPaths:
    root: Path
    uploads: Path
    previews: Path
    converted: Path
    exports: Path
    library_file: Path


def init_page(page_title: str = APP_NAME) -> None:
    st.set_page_config(page_title=page_title, page_icon="🧵", layout="wide")
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800;900&display=swap');
        :root {
            --emb-navy:#0f172a;
            --emb-navy-2:#111827;
            --emb-text:#0f172a;
            --emb-muted:#64748b;
            --emb-cyan:#21d6d2;
            --emb-soft:#eef7fb;
            --emb-card:#ffffff;
            --emb-line:#dbe4f0;
            --emb-orange:#f5a400;
        }
        html, body, [class*="css"] { font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
        .stApp { background: #f2f6fb; color: var(--emb-text); }
        .block-container { padding-top: 1.6rem; padding-left: 2rem; padding-right: 2rem; max-width: 1500px; }
        [data-testid="stSidebarNav"], section[data-testid="stSidebar"] nav, div[data-testid="stSidebarNav"],
        [data-testid="stSidebarUserContent"] > div:first-child:has(a[href*="dst-to"]),
        [data-testid="stSidebarUserContent"] nav { display:none !important; height:0 !important; visibility:hidden !important; }
        [data-testid="stSidebar"] > div:first-child { padding-top: 1.1rem; }
        [data-testid="stSidebar"] { background: linear-gradient(180deg,#0f172a 0%,#111827 100%); border-right: 1px solid rgba(255,255,255,.06); }
        [data-testid="stSidebar"] * { color: #e5edf8; }
        [data-testid="stSidebar"] .stButton button { background:#f5a400; color:#111827; border:0; border-radius:999px; font-weight:900; padding:.55rem 1rem; }
        [data-testid="stSidebar"] [role="radiogroup"] { gap: .55rem; }
        [data-testid="stSidebar"] label[data-baseweb="radio"] {
            background: rgba(15,23,42,.55); border:1px solid rgba(148,163,184,.22); border-radius:18px; padding:14px 16px; margin:7px 0;
        }
        [data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {
            background:#123f47; border-color:#14b8a6; box-shadow: inset 0 0 0 1px rgba(20,184,166,.2);
        }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color:#fff; }
        .emb-sidebar-title { font-size:1.45rem; line-height:1; font-weight:900; letter-spacing:-.04em; color:#fff; margin-top:.4rem; }
        .emb-sidebar-version { color:#9aa7ba; font-weight:600; margin:.25rem 0 .85rem; }
        .emb-side-ad { margin:1.4rem 0; padding:1.05rem; border-radius:22px; background:#f8fafc; color:#64748b !important; text-align:center; border:1px dashed #cbd5e1; }
        .emb-side-ad * { color:#64748b !important; }
        .emb-side-ad b { color:#94a3b8 !important; letter-spacing:.08em; font-size:.76rem; }
        .emb-ad-top { border:1px dashed #cbd5e1; border-radius:24px; padding:1.1rem; text-align:center; color:#7b8ca8; background:rgba(255,255,255,.6); margin-bottom:1.45rem; }
        .emb-ad-top b { color:#8b9ab2; letter-spacing:.08em; font-size:.76rem; }
        .emb-hero {
            position:relative; overflow:hidden; border-radius:32px; padding:2.1rem 2rem 1.9rem; background:
            radial-gradient(circle at 97% 6%, rgba(217,231,146,.75) 0 10%, transparent 14%),
            radial-gradient(circle at 88% 34%, rgba(45,212,191,.20), transparent 28%),
            linear-gradient(100deg,#ffffff 0%,#ffffff 56%,#eaffff 100%);
            border:1px solid #dbe6f1; box-shadow:0 18px 40px rgba(15,23,42,.08); margin-bottom:1.35rem;
        }
        .emb-hero h1 { font-size:clamp(2.2rem,4vw,3.65rem); letter-spacing:-.055em; margin:0; color:#0f172a; font-weight:900; }
        .emb-hero-head { display:flex; align-items:center; gap:1.2rem; position:relative; z-index:2; }
        .emb-hero-logo { width:min(360px,32vw); min-width:230px; max-width:380px; height:auto; max-height:128px; object-fit:contain; border-radius:24px; background:rgba(255,255,255,.78); box-shadow:0 18px 40px rgba(15,23,42,.13); padding:.55rem .8rem; border:1px solid rgba(203,213,225,.72); }
        @media (max-width: 900px) { .emb-hero-head { flex-direction:column; align-items:flex-start; } .emb-hero-logo { width:100%; min-width:0; max-width:420px; } }
        .emb-clean-note { background:#ecfeff; color:#155e75; border:1px solid #67e8f9; border-radius:18px; padding:.78rem 1rem; font-weight:800; }
        .emb-training-card { background:linear-gradient(180deg,#fff,#f8fbff); border:1px solid #dbe4f0; border-radius:24px; padding:1rem; box-shadow:0 10px 24px rgba(15,23,42,.06); }
        .emb-hero p { color:#64748b; font-size:1.05rem; line-height:1.55; max-width:1120px; margin:.3rem 0 1.25rem; }
        .emb-badge { display:inline-flex; align-items:center; gap:.35rem; background:#cffafe; border:1px solid #22d3ee; color:#155e75; border-radius:999px; padding:.33rem .75rem; font-weight:900; font-size:.82rem; letter-spacing:.015em; margin:.9rem 0 .2rem; }
        .emb-stat-row { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:1rem; }
        .emb-stat { background:rgba(255,255,255,.92); border:1px solid #dbe4f0; border-radius:20px; padding:1.25rem 1.35rem; box-shadow:0 4px 18px rgba(15,23,42,.04); }
        .emb-stat b { display:block; color:#0f172a; font-size:1.85rem; font-weight:900; letter-spacing:-.04em; }
        .emb-stat span { color:#475569; font-weight:600; }
        .emb-panel { background:#fff; border:1px solid #dbe4f0; border-radius:26px; padding:1.55rem; box-shadow:0 12px 32px rgba(15,23,42,.07); margin-bottom:1.1rem; }
        .emb-panel h2, .emb-panel h3 { color:#0f172a; letter-spacing:-.035em; }
        .emb-card { border:1px solid #e2e8f0; border-radius:22px; padding:14px; background:#ffffff; box-shadow:0 8px 24px rgba(15,23,42,.05); min-height:100%; }
        .emb-card img { border-radius:16px; }
        .emb-muted { color:#64748b; font-size:0.92rem; line-height:1.45; }
        .emb-pill { display:inline-block; padding:.22rem .55rem; border:1px solid #bae6fd; background:#ecfeff; border-radius:999px; font-size:.78rem; color:#155e75; font-weight:800; margin-right:.25rem; margin-bottom:.25rem; }
        .emb-step { display:inline-flex; align-items:center; justify-content:center; width:34px; height:34px; border-radius:999px; background:#b5f4eb; color:#0f766e; font-weight:900; margin-bottom:.6rem; }
        div[data-testid="stMetric"] { background:#fff; border:1px solid #dbe4f0; border-radius:20px; padding:1rem 1.2rem; box-shadow:0 7px 22px rgba(15,23,42,.05); }
        [data-testid="stMetricValue"] { font-size:1.65rem; font-weight:900; color:#0f172a; }
        .stTabs [data-baseweb="tab-list"] { gap:.6rem; }
        .stTabs [data-baseweb="tab"] { border-radius:999px; padding:.45rem 1rem; background:#fff; border:1px solid #dbe4f0; }
        .emb-hero::before { content:""; position:absolute; inset:-45%; background:conic-gradient(from 90deg, rgba(34,211,238,.0), rgba(34,211,238,.35), rgba(245,164,0,.22), rgba(15,23,42,.0)); animation:emb-spin 20s linear infinite; pointer-events:none; }
        .emb-hero::after { content:""; position:absolute; inset:0; background:radial-gradient(circle at 72% 20%, rgba(255,255,255,.72), transparent 23%); pointer-events:none; }
        .emb-hero > * { position:relative; z-index:1; }
        .emb-turbo-orb { position:absolute; width:160px; height:160px; border-radius:999px; filter:blur(4px); opacity:.36; z-index:0; pointer-events:none; animation:emb-float 7s ease-in-out infinite; }
        .emb-turbo-orb.orb-one { right:8%; top:14%; background:#22d3ee; }
        .emb-turbo-orb.orb-two { right:20%; bottom:-36px; background:#f5a400; animation-delay:-2.8s; }
        .emb-badge { animation:emb-glow 2.8s ease-in-out infinite; }
        .emb-stat, .emb-panel, .emb-card, div[data-testid="stMetric"] { transition:transform .22s ease, box-shadow .22s ease, border-color .22s ease; animation:emb-rise .55s ease both; }
        .emb-stat:hover, .emb-panel:hover, .emb-card:hover, div[data-testid="stMetric"]:hover { transform:translateY(-3px); box-shadow:0 18px 38px rgba(15,23,42,.10); border-color:#67e8f9; }
        .emb-engine-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:1rem; margin:1rem 0 1.2rem; }
        .emb-engine-card { position:relative; overflow:hidden; border-radius:24px; padding:1.2rem; background:linear-gradient(135deg,#ffffff,#ecfeff); border:1px solid #bae6fd; box-shadow:0 12px 30px rgba(8,145,178,.10); }
        .emb-engine-card b { display:block; color:#0f172a; font-size:1.2rem; letter-spacing:-.03em; margin-bottom:.25rem; }
        .emb-engine-card span { color:#64748b; font-size:.92rem; line-height:1.45; }
        .emb-engine-card::after { content:""; position:absolute; width:90px; height:90px; right:-30px; top:-30px; border-radius:999px; background:rgba(34,211,238,.24); animation:emb-pulse 3.6s ease-in-out infinite; }
        @keyframes emb-spin { to { transform:rotate(360deg); } }
        @keyframes emb-float { 0%,100% { transform:translateY(0) scale(1); } 50% { transform:translateY(-16px) scale(1.06); } }
        @keyframes emb-glow { 0%,100% { box-shadow:0 0 0 rgba(34,211,238,0); } 50% { box-shadow:0 0 28px rgba(34,211,238,.32); } }
        @keyframes emb-rise { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
        @keyframes emb-pulse { 0%,100% { transform:scale(1); opacity:.45; } 50% { transform:scale(1.22); opacity:.22; } }
        @media (prefers-reduced-motion: reduce) { .emb-hero::before, .emb-turbo-orb, .emb-badge, .emb-stat, .emb-panel, .emb-card, div[data-testid="stMetric"], .emb-engine-card::after { animation:none !important; transition:none !important; } }
        @media (max-width:900px){ .emb-stat-row, .emb-engine-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .block-container { padding-left:1rem; padding-right:1rem; } }
        @media (max-width:640px){ .emb-stat-row { grid-template-columns:1fr; } .emb-hero { padding:1.3rem; border-radius:24px; } }
        </style>
        """,
        unsafe_allow_html=True,
    )
    try:
        animation_s_css = (STATIC_DIR / "animation_s.css").read_text(encoding="utf-8")
        st.markdown(f"<style>{animation_s_css}</style>", unsafe_allow_html=True)
    except Exception:
        pass
    inject_ui_js()
    if restore_google_session_from_server is not None:
        restore_google_session_from_server()

def inject_ui_js() -> None:
    """Reserved for future UI enhancements.

    Streamlit 1.58 deprecates the old inline components.html path. The core
    app no longer depends on injected JavaScript, so this function intentionally
    stays no-op to keep deploy logs clean and future-safe.
    """
    return None

def get_session_id() -> str:
    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid.uuid4().hex[:16]
    return st.session_state.session_id


def get_paths() -> SessionPaths:
    session_id = get_session_id()
    root = SESSIONS_DIR / session_id
    paths = SessionPaths(
        root=root,
        uploads=root / "uploads",
        previews=root / "previews",
        converted=root / "converted",
        exports=root / "exports",
        library_file=root / "library.json",
    )
    for folder in [paths.root, paths.uploads, paths.previews, paths.converted, paths.exports]:
        folder.mkdir(parents=True, exist_ok=True)
    return paths


def safe_name(value: str, max_len: int = 100) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._- ()[]" else "_" for ch in str(value)).strip(" ._")
    return (cleaned or "file")[:max_len]


def safe_relative_path(name: str) -> Path:
    # Streamlit may preserve relative paths for some upload modes. Keep folders, but sanitize every part.
    parts = []
    for part in PurePosixPath(str(name).replace("\\", "/")).parts:
        if part in {"", ".", ".."}:
            continue
        parts.append(safe_name(part, 90))
    if not parts:
        parts = [f"upload_{uuid.uuid4().hex[:8]}"]
    return Path(*parts)


def is_supported_design(path_or_name: str | Path) -> bool:
    return Path(str(path_or_name)).suffix.lower() in SUPPORTED_EXTENSIONS


def human_size(num: int) -> str:
    value = float(num or 0)
    for unit in ["B", "KB", "MB", "GB"]:
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


def file_sha256(path: Path, limit_bytes: int = 0) -> str:
    h = hashlib.sha256()
    total = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            if limit_bytes and total + len(chunk) > limit_bytes:
                chunk = chunk[: max(0, limit_bytes - total)]
            h.update(chunk)
            total += len(chunk)
            if limit_bytes and total >= limit_bytes:
                break
    return h.hexdigest()


def load_library(paths: SessionPaths) -> List[Dict[str, Any]]:
    try:
        if paths.library_file.exists():
            data = json.loads(paths.library_file.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def save_library(paths: SessionPaths, items: List[Dict[str, Any]]) -> None:
    paths.library_file.parent.mkdir(parents=True, exist_ok=True)
    paths.library_file.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def command_value(command: int) -> int:
    try:
        mask = getattr(pyembroidery, "COMMAND_MASK", 0xFF) if pyembroidery else 0xFF
        return int(command) & int(mask)
    except Exception:
        return int(command or 0) & 0xFF


def command_constants() -> Dict[str, int]:
    if pyembroidery is None:
        return {"STITCH": 0, "JUMP": 1, "TRIM": 2, "STOP": 3, "END": 4, "COLOR_CHANGE": 5}
    return {
        "STITCH": int(getattr(pyembroidery, "STITCH", 0)),
        "JUMP": int(getattr(pyembroidery, "JUMP", 1)),
        "TRIM": int(getattr(pyembroidery, "TRIM", 2)),
        "STOP": int(getattr(pyembroidery, "STOP", 3)),
        "END": int(getattr(pyembroidery, "END", 4)),
        "COLOR_CHANGE": int(getattr(pyembroidery, "COLOR_CHANGE", 5)),
    }


def read_pattern(path: Path):
    if pyembroidery is None:
        raise RuntimeError("pyembroidery is not installed. Install requirements.txt and restart Streamlit.")
    pattern = pyembroidery.read(str(path))
    if pattern is None:
        raise RuntimeError("Could not read this embroidery file.")
    return pattern


def thread_to_rgb(thread: Any, index: int = 0) -> Tuple[int, int, int]:
    palette = [
        (20, 83, 45), (185, 28, 28), (37, 99, 235), (147, 51, 234), (202, 138, 4),
        (219, 39, 119), (8, 145, 178), (51, 65, 85), (22, 163, 74), (249, 115, 22),
    ]
    try:
        if hasattr(thread, "hex_color"):
            hex_value = str(thread.hex_color()).strip().lstrip("#")
            if len(hex_value) >= 6:
                return tuple(int(hex_value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
        value = getattr(thread, "color", None)
        if isinstance(value, int):
            return ((value >> 16) & 255, (value >> 8) & 255, value & 255)
        if isinstance(value, str):
            hex_value = value.strip().lstrip("#")
            if len(hex_value) >= 6:
                return tuple(int(hex_value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
        if all(hasattr(thread, attr) for attr in ["get_red", "get_green", "get_blue"]):
            return (int(thread.get_red()), int(thread.get_green()), int(thread.get_blue()))
    except Exception:
        pass
    return palette[index % len(palette)]


def pattern_bounds(stitches: Iterable[Tuple[float, float, int]]) -> Optional[Tuple[float, float, float, float]]:
    xs: List[float] = []
    ys: List[float] = []
    for stitch in stitches:
        if len(stitch) < 2:
            continue
        xs.append(float(stitch[0]))
        ys.append(float(stitch[1]))
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def placeholder_image(path: Path, output_path: Path, message: str, size: int = 900) -> None:
    img = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(img)
    title = path.name[:42]
    try:
        font_big = ImageFont.truetype("DejaVuSans-Bold.ttf", max(24, size // 26))
        font_small = ImageFont.truetype("DejaVuSans.ttf", max(16, size // 42))
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
    draw.rounded_rectangle((30, 30, size - 30, size - 30), radius=24, outline=(203, 213, 225), width=3)
    draw.text((size // 2, size // 2 - 42), "🧵", anchor="mm", font=font_big, fill=(15, 118, 110))
    draw.text((size // 2, size // 2 + 6), title, anchor="mm", font=font_big, fill=(15, 23, 42))
    draw.text((size // 2, size // 2 + 52), message[:80], anchor="mm", font=font_small, fill=(100, 116, 139))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="WEBP", quality=95)


def render_design(path: Path, output_path: Path, size: int = DEFAULT_PREVIEW_SIZE, output_format: str = "WEBP") -> Tuple[bool, Dict[str, Any]]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if pyembroidery is None:
        placeholder_image(path, output_path, "Install pyembroidery to render stitches", min(size, 1200))
        return False, {"error": "pyembroidery is not installed"}

    try:
        pattern = read_pattern(path)
        if render_pattern_with_cpp is not None:
            cpp_ok, cpp_info = render_pattern_with_cpp(
                pattern,
                output_path,
                size=size,
                output_format=output_format,
                final_output=(size >= 1500 or output_format.upper().replace("JPG", "JPEG") != "WEBP"),
            )
            if cpp_ok:
                return True, cpp_info

        stitches = list(getattr(pattern, "stitches", []) or [])
        if not stitches:
            placeholder_image(path, output_path, "No stitch data found", min(size, 1200))
            return False, {"error": "No stitch data found"}

        bounds = pattern_bounds(stitches)
        if not bounds:
            placeholder_image(path, output_path, "Could not determine design bounds", min(size, 1200))
            return False, {"error": "Could not determine design bounds"}

        min_x, min_y, max_x, max_y = bounds
        width = max(1.0, max_x - min_x)
        height = max(1.0, max_y - min_y)
        padding = max(32, int(size * 0.08))
        usable = max(1, size - padding * 2)
        scale = min(usable / width, usable / height)
        offset_x = (size - width * scale) / 2.0
        offset_y = (size - height * scale) / 2.0

        def transform(x: float, y: float) -> Tuple[int, int]:
            tx = int(round((float(x) - min_x) * scale + offset_x))
            ty = int(round((float(y) - min_y) * scale + offset_y))
            return tx, ty

        supersample = 2 if size <= 1600 else 1
        draw_size = size * supersample
        img = Image.new("RGB", (draw_size, draw_size), "white")
        draw = ImageDraw.Draw(img)

        threadlist = list(getattr(pattern, "threadlist", []) or [])
        colors = [thread_to_rgb(thread, i) for i, thread in enumerate(threadlist)] or [(15, 118, 110)]
        constants = command_constants()
        stitch_cmd = command_value(constants["STITCH"])
        color_change_cmds = {command_value(constants.get("COLOR_CHANGE", 5)), command_value(constants.get("STOP", 3))}
        jump_cmds = {command_value(constants.get("JUMP", 1)), command_value(constants.get("TRIM", 2))}

        last: Optional[Tuple[int, int]] = None
        color_index = 0
        drawn = 0
        step = 1
        if len(stitches) > MAX_DRAW_SEGMENTS:
            step = max(1, len(stitches) // MAX_DRAW_SEGMENTS)
        line_width = max(1, int(round(size / 900))) * supersample

        for idx, stitch in enumerate(stitches):
            if len(stitch) < 3:
                continue
            x, y, cmd = float(stitch[0]), float(stitch[1]), command_value(int(stitch[2]))
            point = transform(x, y)
            point = (point[0] * supersample, point[1] * supersample)
            if cmd in color_change_cmds:
                color_index = min(color_index + 1, max(0, len(colors) - 1))
                last = point
                continue
            if cmd in jump_cmds:
                last = point
                continue
            if cmd == stitch_cmd and last is not None and idx % step == 0:
                draw.line([last, point], fill=colors[color_index % len(colors)], width=line_width)
                drawn += 1
            last = point

        if supersample > 1:
            img = img.resize((size, size), Image.Resampling.LANCZOS)
        img = ImageOps.autocontrast(img, cutoff=0)

        fmt = output_format.upper().replace("JPG", "JPEG")
        save_kwargs: Dict[str, Any] = {}
        if fmt in {"JPEG", "WEBP"}:
            save_kwargs["quality"] = 96
        if fmt == "PNG":
            save_kwargs["compress_level"] = 1
        img.save(output_path, format=fmt, **save_kwargs)
        return True, {"stitches": len(stitches), "drawn_segments": drawn, "bounds": [round(v, 2) for v in bounds]}
    except Exception as exc:
        placeholder_image(path, output_path, f"Render failed: {exc}", min(size, 1200))
        return False, {"error": str(exc)}


def analyze_design(path: Path) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "extension": path.suffix.lower(),
        "stitches": None,
        "colors": None,
        "width": None,
        "height": None,
        "read_ok": False,
        "error": "",
    }
    if pyembroidery is None:
        info["error"] = "pyembroidery not installed"
        return info
    try:
        pattern = read_pattern(path)
        stitches = list(getattr(pattern, "stitches", []) or [])
        bounds = pattern_bounds(stitches)
        info.update(
            {
                "stitches": len(stitches),
                "colors": len(list(getattr(pattern, "threadlist", []) or [])) or None,
                "read_ok": True,
            }
        )
        if bounds:
            min_x, min_y, max_x, max_y = bounds
            info["width"] = round(max_x - min_x, 2)
            info["height"] = round(max_y - min_y, 2)
    except Exception as exc:
        info["error"] = str(exc)
    return info



def create_item_for_file(
    paths: SessionPaths,
    file_path: Path,
    source_label: str = "upload",
    relative_path: Optional[Path] = None,
    preview_sha: Optional[str] = None,
) -> Dict[str, Any]:
    digest = preview_sha or file_sha256(file_path)
    if relative_path is None:
        rel = file_path.relative_to(paths.uploads) if file_path.is_relative_to(paths.uploads) else Path(file_path.name)
    else:
        rel = relative_path
    rel_text = rel.as_posix()
    # v2 keeps folder context, so duplicate designs can live in different folders when requested.
    item_id = hashlib.sha256(f"{digest}::{rel_text}".encode("utf-8")).hexdigest()[:16]
    preview_path = paths.previews / f"{digest[:16]}.webp"
    if not preview_path.exists():
        ok, render_info = render_design(file_path, preview_path, size=DEFAULT_PREVIEW_SIZE, output_format="WEBP")
    else:
        ok, render_info = True, {"engine": "preview_cache", "sha256": digest[:16]}
    analysis = analyze_design(file_path)
    item = {
        "id": item_id,
        "name": file_path.name,
        "stem": file_path.stem,
        "path": str(file_path),
        "relative_path": rel_text,
        "folder": str(PurePosixPath(rel_text).parent if PurePosixPath(rel_text).parent.as_posix() != "." else "Uploads"),
        "source": source_label,
        "sha256": digest,
        "preview_path": str(preview_path),
        "preview_ok": ok,
        "render_info": render_info,
        "analysis": analysis,
        "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    # IMGS BetaV1 local training/cache: classify preview once at import time and save JSON.
    if apply_imgs_training_to_item is not None and preview_path.exists():
        try:
            item = apply_imgs_training_to_item(paths.root, item, force=False)
        except Exception as exc:
            item["imgs_training"] = {
                "engine": IMGS_TRAINING_VERSION,
                "engine_tag": IMGS_TRAINING_TAG,
                "status": "error",
                "predicted_type": "unknown_review",
                "confidence": 0,
                "error": str(exc)[:180],
            }
    return item


def merge_library(existing: List[Dict[str, Any]], new_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged = {item.get("id"): item for item in existing if item.get("id")}
    for item in new_items:
        merged[item["id"]] = item
    return sorted(merged.values(), key=lambda item: (item.get("relative_path", "").lower(), item.get("name", "").lower()))


def uploaded_file_size(uploaded_file: Any) -> int:
    size = getattr(uploaded_file, "size", None)
    if isinstance(size, int) and size >= 0:
        return size
    try:
        return len(uploaded_file.getbuffer())
    except Exception:
        return 0


def summarize_uploaded_files(uploaded_files: List[Any], allow_zip: bool = False) -> Dict[str, Any]:
    total_files = len(uploaded_files or [])
    supported = 0
    zips = 0
    unsupported = 0
    total_bytes = 0
    folders: set[str] = set()
    extensions: Dict[str, int] = {}
    for uploaded in uploaded_files or []:
        rel = safe_relative_path(getattr(uploaded, "name", "upload"))
        suffix = rel.suffix.lower()
        total_bytes += uploaded_file_size(uploaded)
        if suffix == ".zip" and allow_zip:
            zips += 1
            supported += 1
        elif suffix in SUPPORTED_EXTENSIONS:
            supported += 1
        else:
            unsupported += 1
        folder = PurePosixPath(rel.as_posix()).parent.as_posix()
        if folder not in {"", "."}:
            folders.add(folder)
        extensions[suffix or "[none]"] = extensions.get(suffix or "[none]", 0) + 1
    return {
        "total_files": total_files,
        "supported": supported,
        "zip_files": zips,
        "unsupported": unsupported,
        "total_bytes": total_bytes,
        "folders": len(folders),
        "extensions": extensions,
    }


def existing_sha_set(items: List[Dict[str, Any]]) -> set[str]:
    return {str(item.get("sha256")) for item in items if item.get("sha256")}


def save_uploaded_design(uploaded_file: Any, paths: SessionPaths, import_root: Optional[str] = None) -> Optional[Path]:
    rel = safe_relative_path(uploaded_file.name)
    if not is_supported_design(rel):
        return None
    if import_root:
        rel = Path(safe_name(import_root, 70)) / rel
    target = paths.uploads / rel
    if target.exists():
        target = target.with_name(f"{target.stem}_{uuid.uuid4().hex[:6]}{target.suffix.lower()}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(uploaded_file.getbuffer())
    return target


def zip_member_safe(name: str) -> bool:
    if not name or name.startswith(("/", "\\")):
        return False
    path = PurePosixPath(name.replace("\\", "/"))
    return all(part not in {"", ".", ".."} for part in path.parts)


def import_zip(uploaded_file: Any, paths: SessionPaths) -> Tuple[List[Path], List[str]]:
    imported: List[Path] = []
    warnings: List[str] = []
    zip_root = paths.uploads / f"zip_{safe_name(Path(uploaded_file.name).stem, 50)}_{uuid.uuid4().hex[:8]}"
    zip_root.mkdir(parents=True, exist_ok=True)
    data = io.BytesIO(uploaded_file.getbuffer())
    total_bytes = 0

    try:
        with zipfile.ZipFile(data) as zf:
            members = [info for info in zf.infolist() if not info.is_dir()]
            if len(members) > ZIP_MAX_FILES:
                raise RuntimeError(f"ZIP has {len(members)} files; limit is {ZIP_MAX_FILES}.")
            for info in members:
                if not zip_member_safe(info.filename):
                    warnings.append(f"Skipped unsafe ZIP member: {info.filename}")
                    continue
                total_bytes += int(info.file_size or 0)
                if total_bytes > ZIP_MAX_BYTES:
                    raise RuntimeError(f"ZIP extracted size exceeds {human_size(ZIP_MAX_BYTES)}.")
                rel = safe_relative_path(info.filename)
                if not is_supported_design(rel):
                    continue
                target = zip_root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                imported.append(target)
    except zipfile.BadZipFile:
        warnings.append(f"Could not read ZIP: {uploaded_file.name}")
    except Exception as exc:
        warnings.append(str(exc))
    return imported, warnings


def _relative_to_uploads(paths: SessionPaths, file_path: Path) -> Path:
    try:
        return file_path.relative_to(paths.uploads)
    except Exception:
        return Path(file_path.name)


def import_uploads(
    uploaded_files: List[Any],
    paths: SessionPaths,
    existing_items: Optional[List[Dict[str, Any]]] = None,
    source_label: str = "upload",
    duplicate_policy: str = "skip",
    import_root: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    imported_paths: List[Path] = []
    warnings: List[str] = []
    skipped_unsupported = 0
    total_bytes = 0
    supported_count = 0

    if source_label.startswith("folder") and len(uploaded_files) > FOLDER_MAX_FILES:
        warnings.append(f"Folder has {len(uploaded_files):,} files; limit is {FOLDER_MAX_FILES:,}.")
        return [], warnings

    for uploaded in uploaded_files:
        total_bytes += uploaded_file_size(uploaded)
        if total_bytes > FOLDER_MAX_BYTES and source_label.startswith("folder"):
            warnings.append(f"Folder upload is larger than {human_size(FOLDER_MAX_BYTES)}. Import stopped before rendering.")
            return [], warnings
        suffix = Path(uploaded.name).suffix.lower()
        if suffix == ".zip":
            paths_from_zip, zip_warnings = import_zip(uploaded, paths)
            imported_paths.extend(paths_from_zip)
            warnings.extend(zip_warnings)
            supported_count += len(paths_from_zip)
        elif suffix in SUPPORTED_EXTENSIONS:
            supported_count += 1
            if source_label.startswith("folder") and supported_count > FOLDER_MAX_DESIGNS:
                warnings.append(f"Folder has more than {FOLDER_MAX_DESIGNS:,} supported designs. Import stopped to protect the app.")
                break
            saved = save_uploaded_design(uploaded, paths, import_root=import_root)
            if saved:
                imported_paths.append(saved)
        else:
            skipped_unsupported += 1


    if skipped_unsupported:
        warnings.append(f"Skipped {skipped_unsupported:,} unsupported file{'s' if skipped_unsupported != 1 else ''}.")

    existing_items = existing_items or []
    existing_shas = existing_sha_set(existing_items)
    skip_duplicates = duplicate_policy.lower().startswith("skip")
    duplicate_count = 0
    render_paths: List[Tuple[Path, str]] = []
    for file_path in imported_paths:
        digest = file_sha256(file_path)
        if skip_duplicates and digest in existing_shas:
            duplicate_count += 1
            continue
        render_paths.append((file_path, digest))
        existing_shas.add(digest)

    if duplicate_count:
        warnings.append(f"Skipped {duplicate_count:,} exact duplicate design{'s' if duplicate_count != 1 else ''} by SHA-256.")

    progress = st.progress(0, text="Preparing folder previews…") if render_paths else None
    new_items: List[Dict[str, Any]] = []
    for idx, (file_path, digest) in enumerate(render_paths, start=1):
        if progress:
            folder = _relative_to_uploads(paths, file_path).parent.as_posix()
            label = file_path.name if folder in {"", "."} else f"{folder}/{file_path.name}"
            progress.progress((idx - 1) / max(1, len(render_paths)), text=f"TURBO rendering {idx:,}/{len(render_paths):,}: {label[:80]}")
        new_items.append(create_item_for_file(paths, file_path, source_label=source_label, preview_sha=digest))
    if progress:
        progress.progress(1.0, text="Folder import complete")
        time.sleep(0.25)
        progress.empty()
    return new_items, warnings

def image_bytes(path: Path) -> bytes:
    return path.read_bytes()


def group_items_by_folder(items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        folder = str(PurePosixPath(item.get("relative_path", item.get("name", ""))).parent)
        if folder in {".", ""}:
            folder = "Uploads"
        grouped.setdefault(folder, []).append(item)
    return grouped


def filter_items(items: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    q = (query or "").strip().lower()
    if not q:
        return items
    return [item for item in items if q in item.get("name", "").lower() or q in item.get("relative_path", "").lower()]


def item_caption(item: Dict[str, Any]) -> str:
    analysis = item.get("analysis", {}) or {}
    parts = [Path(item.get("relative_path", item.get("name", ""))).as_posix()]
    if analysis.get("stitches") is not None:
        parts.append(f"{analysis['stitches']:,} stitches")
    if analysis.get("colors") is not None:
        parts.append(f"{analysis['colors']} colors")
    size = analysis.get("size_bytes")
    if size:
        parts.append(human_size(int(size)))
    return " • ".join(parts)


def render_library_grid(items: List[Dict[str, Any]]) -> None:
    if not items:
        st.info("No designs match the current search.")
        return
    columns = st.columns(3)
    for index, item in enumerate(items):
        with columns[index % 3]:
            st.markdown('<div class="emb-card">', unsafe_allow_html=True)
            preview_path = Path(item.get("preview_path", ""))
            if preview_path.exists():
                st.image(str(preview_path), width="stretch")
            else:
                st.empty()
            st.markdown(f"**{item.get('name', 'design')}**")
            st.markdown(f"<div class='emb-muted'>{item_caption(item)}</div>", unsafe_allow_html=True)
            if item.get("analysis", {}).get("error"):
                st.warning(item["analysis"]["error"], icon="⚠️")
            st.markdown("</div>", unsafe_allow_html=True)


def convert_items(items: List[Dict[str, Any]], paths: SessionPaths, output_format: str, image_size: int) -> Tuple[Path, List[Dict[str, Any]]]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_dir = paths.converted / f"batch_{stamp}_{uuid.uuid4().hex[:6]}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    ext = "jpg" if output_format.upper() == "JPEG" else output_format.lower()
    results: List[Dict[str, Any]] = []
    progress = st.progress(0, text="Starting conversion…")
    for idx, item in enumerate(items, start=1):
        source = Path(item["path"])
        output_name = f"{safe_name(source.stem, 80)}.{ext}"
        output_path = batch_dir / output_name
        progress.progress((idx - 1) / max(1, len(items)), text=f"Converting {source.name}")
        ok, info = render_design(source, output_path, size=image_size, output_format=output_format)
        results.append({"name": source.name, "output_path": str(output_path), "ok": ok, "info": info})
    progress.progress(1.0, text="Packaging images…")
    zip_path = paths.exports / f"emborganizer_images_{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for result in results:
            output_path = Path(result["output_path"])
            if output_path.exists():
                zf.write(output_path, output_path.name)
    progress.empty()
    return zip_path, results


def make_library_zip(items: List[Dict[str, Any]], paths: SessionPaths) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    zip_path = paths.exports / f"emborganizer_originals_{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            source = Path(item.get("path", ""))
            if source.exists():
                arcname = item.get("relative_path") or source.name
                zf.write(source, arcname)
    return zip_path


def best_image_matches(
    query_image: Image.Image,
    items: List[Dict[str, Any]],
    limit: int = 6,
    use_imgs_type_filter: bool = True,
) -> List[Dict[str, Any]]:
    if create_fingerprint_from_image is None or create_fingerprint_from_path is None or compare_fingerprints is None:
        return []
    query_fp = create_fingerprint_from_image(query_image)

    query_groups: List[str] = []
    if use_imgs_type_filter and analyze_image_for_training is not None:
        try:
            query_analysis = analyze_image_for_training(query_image, "query_image")
            if apply_student_model_memory is not None:
                query_analysis = apply_student_model_memory(get_paths().root, query_analysis)
            if apply_ultrabrain_memory is not None:
                query_analysis = apply_ultrabrain_memory(get_paths().root, query_analysis)
            if apply_superbrain_memory is not None:
                query_analysis = apply_superbrain_memory(get_paths().root, query_analysis)
            pred = query_analysis.get("prediction") or {}
            query_groups = list(pred.get("search_groups") or [])
        except Exception:
            query_groups = []

    candidate_items = items
    if query_groups:
        filtered = []
        allowed = set(query_groups)
        for item in items:
            train = item.get("imgs_training") or {}
            item_type = str(train.get("predicted_type") or "")
            item_groups = set(train.get("search_groups") or [])
            if item_type in allowed or item_groups.intersection(allowed):
                filtered.append(item)
        # Safety fallback: if old libraries have no training cache, still search all.
        if filtered:
            candidate_items = filtered

    scored: List[Dict[str, Any]] = []
    progress = st.progress(0, text=f"Comparing inside IMGS cache group ({len(candidate_items):,} candidates)…")
    for idx, item in enumerate(candidate_items, start=1):
        preview_path = Path(item.get("preview_path", ""))
        if not preview_path.exists():
            continue
        progress.progress((idx - 1) / max(1, len(candidate_items)), text=f"Checking {item.get('name', 'design')}")
        try:
            train = item.get("imgs_training") or {}
            target_fp = None
            if load_cached_fingerprint is not None:
                target_fp = load_cached_fingerprint(train.get("fingerprint_path"))
            if target_fp is None:
                target_fp = create_fingerprint_from_path(preview_path)
            score = compare_fingerprints(query_fp, target_fp)
            # Small bonus if the cached IMGS type agreed with the query search group.
            if query_groups:
                item_type = str(train.get("predicted_type") or "")
                if item_type in set(query_groups):
                    score = dict(score)
                    score["score"] = min(100.0, float(score.get("score") or 0) + 1.5)
                    verification = dict(score.get("verification") or {})
                    verification["imgs_type_filter"] = {"query_groups": query_groups, "item_type": item_type, "bonus": 1.5}
                    score["verification"] = verification
            scored.append({"item": item, "score": score})
        except Exception:
            continue
    progress.progress(1.0, text="Search complete")
    progress.empty()
    return sorted(scored, key=lambda row: row.get("score", {}).get("score", 0), reverse=True)[:limit]


def sidebar_import(paths: SessionPaths, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    with st.sidebar:
        logo = STATIC_DIR / "logo.png"
        if logo.exists():
            st.image(str(logo), width=96)
        st.header("Import designs")
        uploaded_files = st.file_uploader(
            "Upload embroidery files or ZIP folders",
            type=UPLOAD_EXTENSIONS,
            accept_multiple_files=True,
            help="Supported: DST, PES, JEF, EXP, VP3, HUS, XXX, EMB, and ZIP.",
        )
        if st.button("Import uploaded files", type="primary", width="stretch", disabled=not uploaded_files):
            new_items, warnings = import_uploads(list(uploaded_files or []), paths)
            items = merge_library(items, new_items)
            if build_training_index is not None:
                try:
                    build_training_index(paths.root, items)
                except Exception:
                    pass
            if sync_library_cache is not None:
                try:
                    sync_library_cache(paths.root, items)
                except Exception:
                    pass
            save_library(paths, items)
            if new_items:
                st.success(f"Imported {len(new_items)} design{'s' if len(new_items) != 1 else ''}.")
            for warning in warnings[:5]:
                st.warning(warning)
            st.rerun()

        st.divider()
        st.subheader("Session")
        st.caption(f"Session: `{get_session_id()}`")
        st.caption(f"Storage: `{paths.root.name}`")
        if st.button("Clear this session", width="stretch"):
            shutil.rmtree(paths.root, ignore_errors=True)
            for key in ["session_id"]:
                st.session_state.pop(key, None)
            st.rerun()
    return items


def page_header(items: List[Dict[str, Any]]) -> None:
    left, right = st.columns([0.72, 0.28])
    with left:
        st.title("🧵 EMBORGANIZER")
        st.caption("Streamlit embroidery previewer, organizer, converter, and visual image search.")
    with right:
        st.markdown(" ")
        if pyembroidery is None:
            st.error("pyembroidery is missing. Install `requirements.txt` to render real stitch previews.")
        else:
            st.success("Streamlit model ready")
    total_size = sum(int((item.get("analysis") or {}).get("size_bytes") or 0) for item in items)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Designs", f"{len(items):,}")
    c2.metric("Folders", f"{len(group_items_by_folder(items)):,}" if items else "0")
    c3.metric("Storage", human_size(total_size))
    c4.metric("Renderer", "pyembroidery" if pyembroidery else "missing")


def library_tab(items: List[Dict[str, Any]], paths: SessionPaths) -> None:
    query = st.text_input("Search library", placeholder="Search by file or folder name")
    visible = filter_items(items, query)
    if not items:
        st.info("Upload embroidery files or a ZIP from the sidebar to begin.")
        return

    toolbar_left, toolbar_right = st.columns([0.72, 0.28])
    with toolbar_left:
        st.write(f"Showing **{len(visible)}** of **{len(items)}** imported designs.")
    with toolbar_right:
        zip_path = make_library_zip(visible, paths) if visible and st.button("Prepare originals ZIP", width="stretch") else None
        if zip_path and zip_path.exists():
            st.download_button("Download originals ZIP", data=zip_path.read_bytes(), file_name=zip_path.name, mime="application/zip", width="stretch")

    grouped = group_items_by_folder(visible)
    for folder, folder_items in grouped.items():
        with st.expander(f"📁 {folder} · {len(folder_items)} design{'s' if len(folder_items) != 1 else ''}", expanded=len(grouped) <= 2):
            render_library_grid(folder_items)


def converter_tab(items: List[Dict[str, Any]], paths: SessionPaths) -> None:
    if not items:
        st.info("Import designs first, then convert them to PNG, JPG, or WEBP.")
        return
    st.subheader("Convert embroidery files to images")
    names = [f"{item['relative_path']}" for item in items]
    selected_names = st.multiselect("Choose designs", names, default=names[: min(12, len(names))])
    selected_set = set(selected_names)
    selected_items = [item for item in items if item["relative_path"] in selected_set]
    col1, col2 = st.columns(2)
    with col1:
        format_label = st.selectbox("Output format", ["PNG", "JPEG", "WEBP"], index=0)
    with col2:
        image_size = st.slider("Turbo 4K image size", min_value=900, max_value=4096, value=DEFAULT_GENERATION_SIZE, step=100)
    if st.button("Convert selected designs", type="primary", disabled=not selected_items):
        zip_path, results = convert_items(selected_items, paths, format_label, int(image_size))
        ok_count = sum(1 for row in results if row["ok"])
        st.success(f"Converted {ok_count} of {len(results)} design files.")
        st.download_button("Download converted images ZIP", data=zip_path.read_bytes(), file_name=zip_path.name, mime="application/zip", width="stretch")
        with st.expander("Conversion details"):
            for row in results:
                status = "✅" if row["ok"] else "⚠️"
                st.write(f"{status} {row['name']} → `{Path(row['output_path']).name}`")


def image_search_tab(items: List[Dict[str, Any]]) -> None:
    if not items:
        st.info("Import designs first, then upload a reference image to find the closest design.")
        return
    st.subheader("Visual image search")
    st.caption(f"Engine: {IMGS_ENGINE_VERSION} · {IMGS_TRAINING_VERSION}")
    st.caption(IMGS_TRAINING_WARNING)
    query_file = st.file_uploader("Upload a reference image", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=False)
    c1, c2 = st.columns([0.35, 0.65])
    with c1:
        limit = st.slider("Results", 1, 12, 6)
    with c2:
        use_imgs_type_filter = st.checkbox("Use IMGS type sorting cache for faster search", value=True, help="BetaV1 first guesses the uploaded image type, then searches only similar cached design groups. Turn off if results look wrong.")
    if query_file is not None:
        query_image = Image.open(query_file).convert("RGB")
        left, right = st.columns([0.25, 0.75])
        with left:
            st.image(query_image, caption="Reference image", width="stretch")
        with right:
            if analyze_image_for_training is not None:
                try:
                    q_analysis = analyze_image_for_training(query_image, query_file.name)
                    if apply_student_model_memory is not None:
                        q_analysis = apply_student_model_memory(get_paths().root, q_analysis)
                    if apply_ultrabrain_memory is not None:
                        q_analysis = apply_ultrabrain_memory(get_paths().root, q_analysis)
                    if apply_superbrain_memory is not None:
                        q_analysis = apply_superbrain_memory(get_paths().root, q_analysis)
                    pred = q_analysis.get("prediction") or {}
                    st.markdown(f"**IMGS query read:** `{pred.get('predicted_type', 'unknown_review')}` · confidence `{pred.get('confidence', 0)}%`")
                    st.caption("Search groups: " + ", ".join(pred.get("search_groups") or []))
                    with st.expander("Query IMGS BetaV1 JSON"):
                        st.json(q_analysis)
                except Exception as exc:
                    st.caption(f"IMGS query read unavailable: {exc}")
        if st.button("Find closest designs", type="primary"):
            matches = best_image_matches(query_image, items, limit=int(limit), use_imgs_type_filter=bool(use_imgs_type_filter))
            if not matches:
                st.warning("Image search is unavailable or no previews could be compared.")
                return
            for rank, match in enumerate(matches, start=1):
                item = match["item"]
                score = match["score"]
                train = item.get("imgs_training") or {}
                cols = st.columns([0.18, 0.82])
                with cols[0]:
                    preview_path = Path(item.get("preview_path", ""))
                    if preview_path.exists():
                        st.image(str(preview_path), width="stretch")
                with cols[1]:
                    st.markdown(f"### #{rank} · {item.get('name', 'design')}")
                    st.write(item_caption(item))
                    st.caption(f"IMGS type: {train.get('predicted_type', 'not trained')} · {train.get('confidence', 0)}%")
                    st.metric(score.get("label", "Match"), f"{score.get('score', 0):.2f}%")
                    with st.expander("Verification details"):
                        st.json(score.get("verification", {}))


def help_tab(paths: SessionPaths) -> None:
    st.subheader("About this Streamlit build")
    st.write(
        "This version runs directly in Streamlit. It imports embroidery files, renders previews with `pyembroidery` and Pillow, "
        "converts designs to images, and performs local visual matching against generated previews."
    )
    st.markdown(
        """
        <span class="emb-pill">No FastAPI runtime</span>
        <span class="emb-pill">No Uvicorn server</span>
        <span class="emb-pill">Streamlit Cloud ready</span>
        <span class="emb-pill">Local session storage</span>
        """,
        unsafe_allow_html=True,
    )
    st.code("streamlit run streamlit_app.py", language="bash")
    st.write("Session files are stored here:")
    st.code(str(paths.root), language="text")
    st.warning(
        "Streamlit Community Cloud storage is ephemeral. For permanent multi-user storage, connect an external database or object storage later."
    )



def total_library_size(items: List[Dict[str, Any]]) -> int:
    return sum(int((item.get("analysis") or {}).get("size_bytes") or 0) for item in items)


def engine_status() -> Dict[str, Any]:
    available = False
    status: Dict[str, Any] = {"message": "Python renderer active", "available": False}
    if ensure_cpp_renderer is not None:
        try:
            available, status = ensure_cpp_renderer()
        except Exception as exc:
            status = {"message": f"Python fallback active: {exc}", "available": False}
    return {**status, "available": bool(available), "engine_version": TURBOEMB_ENGINE_VERSION, "animation_version": ANIMATION_ENGINE_VERSION}




def _truthy_local(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _secret_section(name: str) -> Dict[str, Any]:
    try:
        section = st.secrets.get(name, {})  # type: ignore[attr-defined]
        if hasattr(section, "to_dict"):
            return dict(section.to_dict())
        return dict(section or {})
    except Exception:
        return {}


def turbo_import_enabled() -> bool:
    drive = _secret_section("google_drive")
    return _truthy_local(drive.get("turbo_import_enabled"), default=True)


def _turbo_import_auto_scan_key(user: Dict[str, Any]) -> str:
    return f"{user.get('email','').strip().lower()}::{APP_VERSION}"


def maybe_run_turbo_import_scan_once(paths: SessionPaths, items: List[Dict[str, Any]]) -> None:
    """Run the v4.8 Drive scan once after startup/login, then cache the manifest."""
    if not turbo_import_enabled() or filter_supported_drive_files is None:
        return
    if get_google_user is None:
        return
    user = get_google_user()
    if not user or user.get("demo"):
        return
    cache = st.session_state.get("turbo_import_manifest")
    if isinstance(cache, dict) and cache.get("files") is not None:
        return
    done_key = st.session_state.get("turbo_import_auto_scan_key")
    current_key = _turbo_import_auto_scan_key(user)
    if done_key == current_key:
        return

    try:
        from google_drive import drive_oauth_config, drive_sync_enabled, get_drive_tokens, search_drive_design_files, DESIGN_EXTENSIONS

        if not drive_sync_enabled():
            st.session_state["turbo_import_auto_scan_key"] = current_key
            return
        config, missing = drive_oauth_config()
        if missing or config is None or not get_drive_tokens():
            st.session_state["turbo_import_auto_scan_key"] = current_key
            return
        drive = _secret_section("google_drive")
        max_files = int(drive.get("turbo_import_scan_limit", TURBO_IMPORT_DEFAULT_SCAN_LIMIT) or TURBO_IMPORT_DEFAULT_SCAN_LIMIT)
        manifest, scan_info = search_drive_design_files(config, max_files=max_files)
        supported, engine_info = filter_supported_drive_files(manifest, DESIGN_EXTENSIONS)
        st.session_state["turbo_import_manifest"] = {
            "files": supported,
            "scan_info": scan_info,
            "engine_info": engine_info,
            "scanned_at": int(time.time()),
            "auto": True,
        }
        st.session_state["turbo_import_auto_scan_key"] = current_key
    except Exception as exc:
        st.session_state["turbo_import_manifest"] = {
            "files": [],
            "error": str(exc),
            "scanned_at": int(time.time()),
            "auto": True,
        }
        st.session_state["turbo_import_auto_scan_key"] = current_key


def _drive_import_target(paths: SessionPaths, drive_file: Dict[str, Any], index: int = 0) -> Path:
    name = safe_name(str(drive_file.get("name") or f"drive_design_{index}.dst"), 120)
    target_dir = paths.uploads / "Google Drive Turbo Import"
    target = target_dir / name
    suffix = target.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        target = target.with_suffix(".emb")
    counter = 1
    while target.exists():
        target = target.with_name(f"{target.stem}_{counter}{target.suffix}")
        counter += 1
    return target


def run_turbo_import_from_drive(paths: SessionPaths, existing_items: List[Dict[str, Any]], files: List[Dict[str, Any]], limit: int) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    new_items: List[Dict[str, Any]] = []
    if not files:
        return new_items, warnings
    try:
        from google_drive import drive_oauth_config, download_drive_file
        config, missing = drive_oauth_config()
        if missing or config is None:
            return [], ["Google Drive config is missing: " + ", ".join(missing)]
    except Exception as exc:
        return [], [f"Google Drive import is unavailable: {exc}"]

    existing_shas = existing_sha_set(existing_items)
    selected = list(files)[: max(1, int(limit or 1))]
    progress = st.progress(0, text="Starting Turbo Import from Google Drive…")
    for idx, row in enumerate(selected, start=1):
        name = str(row.get("name") or f"drive_design_{idx}.emb")
        try:
            progress.progress((idx - 1) / max(1, len(selected)), text=f"Turbo importing {idx}/{len(selected)}: {name[:70]}")
            target = _drive_import_target(paths, row, idx)
            download_drive_file(config, str(row.get("id") or ""), target)
            digest = file_sha256(target)
            if digest in existing_shas:
                warnings.append(f"Skipped duplicate from Drive: {name}")
                try:
                    target.unlink(missing_ok=True)
                except Exception:
                    pass
                continue
            rel = _relative_to_uploads(paths, target)
            item = create_item_for_file(paths, target, source_label="google_drive_turbo_import_v46", relative_path=rel, preview_sha=digest)
            item["drive_import"] = {
                "id": row.get("id"),
                "name": row.get("name"),
                "webViewLink": row.get("webViewLink"),
                "modifiedTime": row.get("modifiedTime"),
                "engine": TURBO_IMPORT_ENGINE_VERSION,
            }
            new_items.append(item)
            existing_shas.add(digest)
        except Exception as exc:
            warnings.append(f"Could not import {name}: {str(exc)[:180]}")
    progress.progress(1.0, text="Turbo Import complete")
    time.sleep(0.25)
    progress.empty()
    return new_items, warnings


def render_turbo_import_card(paths: SessionPaths, items: List[Dict[str, Any]], *, compact: bool = False) -> None:
    if not turbo_import_enabled():
        return
    manifest = st.session_state.get("turbo_import_manifest")
    if not isinstance(manifest, dict):
        return
    files = list(manifest.get("files") or [])
    error = manifest.get("error")
    if error and not compact:
        st.info(f"Turbo Import startup scan could not run yet: {error}")
        return
    if not files:
        if not compact:
            st.caption("Turbo Import startup scan found no Google Drive design files visible to this app yet.")
        return

    engine_info = manifest.get("engine_info") or {}
    scan_info = manifest.get("scan_info") or {}
    st.markdown(
        f"""
        <div class="emb-turbo-import-card">
            <span class="emb-turbo-import-badge">v4.8 Turbo Import + Sync · {TURBO_IMPORT_ANIMATION_VERSION}</span>
            <h3>Google Drive designs found</h3>
            <div class="emb-scan-beam"></div>
            <p class="emb-muted">Found <b>{len(files):,}</b> supported embroidery design file{'s' if len(files) != 1 else ''} in Google Drive. EMBORGANIZER will not download/import them until you approve.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Drive designs", f"{len(files):,}")
    c2.metric("Scanner", "C++" if engine_info.get("native_available") else "Python")
    c3.metric("Mode", str(scan_info.get("mode") or "Drive"))
    with st.expander("Preview found Drive designs"):
        for row in files[:80]:
            size = row.get("size") or row.get("size_bytes") or ""
            st.write(f"🧵 {row.get('name')} {('· ' + str(size) + ' bytes') if size else ''}")
        if len(files) > 80:
            st.caption(f"Showing first 80 of {len(files):,} files.")
        st.json({"scan": scan_info, "engine": engine_info})

    max_default = min(len(files), TURBO_IMPORT_DEFAULT_IMPORT_LIMIT)
    import_limit = st.slider("How many Drive designs to import now", min_value=1, max_value=max(1, len(files)), value=max(1, max_default), step=1, key="turbo_import_limit")
    permit = st.checkbox("I allow EMBORGANIZER to download these Google Drive designs into this server session.", key="turbo_import_user_permit")
    if st.button("Allow and run Turbo Import", type="primary", width="stretch", disabled=not permit):
        new_items, warnings = run_turbo_import_from_drive(paths, items, files, int(import_limit))
        merged = merge_library(items, new_items)
        save_library(paths, merged)
        st.session_state.pop("turbo_import_manifest", None)
        if new_items:
            st.success(f"Turbo Import added {len(new_items):,} design{'s' if len(new_items) != 1 else ''} from Google Drive.")
        else:
            st.info("Turbo Import completed, but no new designs were added.")
        for warning in warnings[:8]:
            st.warning(warning)
        st.rerun()
    if st.button("Ignore these Drive designs for now", width="stretch"):
        st.session_state.pop("turbo_import_manifest", None)
        st.rerun()

def top_ad() -> None:
    """v4.8 keeps the main GUI clean; no ad placeholders are rendered."""
    return None


def sidebar_nav() -> str:
    with st.sidebar:
        logo = STATIC_DIR / "logo.png"
        if logo.exists():
            st.image(str(logo), width=230)
        st.markdown('<div class="emb-sidebar-title">emborganizer</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="emb-sidebar-version">Version {APP_VERSION.replace("v", "")}</div>', unsafe_allow_html=True)
        user = get_google_user() if get_google_user is not None else None
        if user:
            st.markdown(f"<div style='font-size:.86rem;color:#cbd5e1;margin:.25rem 0 .45rem;'>Signed in as<br/><b>{user.get('email','Google user')}</b></div>", unsafe_allow_html=True)
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Drive", width="stretch"):
                    st.info("Choose Google Drive from the main menu. v4.8 keeps Drive inside the main GUI.")
            with col_b:
                if st.button("Sign out", width="stretch"):
                    if clear_google_session is not None:
                        clear_google_session()
                    try:
                        from google_drive import clear_drive_session
                        clear_drive_session()
                    except Exception:
                        pass
                    st.rerun()
        else:
            if st.button("Google sign-in", width="content"):
                st.info("Open the Google Drive page from the menu. v4.8 keeps sign-in inside the main app so the native page list does not show.")
        nav = st.radio(
            "Navigation",
            ["Dashboard", "Turbo Import & Sync", "Library", "TurboThinker Training", "Google Drive", "IMGS Search", "Convert to Image", "DST to PNG / JPG"],
            label_visibility="collapsed",
            index=0,
        )
        st.markdown(
            """
            <div class="emb-clean-note" style="background:rgba(236,254,255,.12);color:#bae6fd;border-color:rgba(103,232,249,.35);margin:.85rem 0 1rem;">v4.8 clean GUI · all tools are inside this main app</div>
            <div style="font-size:.82rem; line-height:1.8; color:#e5edf8;margin-top:1rem;">TurboEmb v3 · TurboImport · TurboSync · TurboThinker</div>
            """,
            unsafe_allow_html=True,
        )
        return nav


def _logo_data_uri() -> str:
    try:
        import base64
        logo = STATIC_DIR / "logo.png"
        if logo.exists():
            return base64.b64encode(logo.read_bytes()).decode("ascii")
    except Exception:
        pass
    return ""


def hero_dashboard(items: List[Dict[str, Any]]) -> None:
    folders = len(group_items_by_folder(items)) if items else 0
    formats = len({(item.get("analysis") or {}).get("extension") or Path(item.get("name", "")).suffix.lower() for item in items}) if items else 0
    status = engine_status()
    engine_badge = "C++ Turbo ready" if status.get("available") else "Python fallback safe"
    st.markdown(
        f"""
        <div class="emb-hero">
            <div class="emb-turbo-orb orb-one"></div>
            <div class="emb-turbo-orb orb-two"></div>
            <div class="emb-hero-head">
                <img class="emb-hero-logo" src="data:image/png;base64,{_logo_data_uri()}" />
                <div>
                    <h1>Turbo Engine v5.1 — SuperBrain TurboThinker, Turbo Import & TurboSync.</h1>
                    <div class="emb-badge">TurboEmb v3 · TurboSync · TurboThinker Training · {TURBO_IMPORT_ANIMATION_VERSION} · {engine_badge}</div>
                </div>
            </div>
            <p>Clean main GUI with the clear emborganizer logo, ZIP/folder import, local IMGS training, UltraBrain ensemble model, AI-student weights, JSON cache, virtual type folders, C++ assisted TurboSync, and fast divided search. The training code stays in engine files so the main app look remains smooth.</p>
            <div class="emb-stat-row">
                <div class="emb-stat"><b>{folders:,}</b><span>Folders</span></div>
                <div class="emb-stat"><b>{len(items):,}</b><span>Design files</span></div>
                <div class="emb-stat"><b>{formats:,}</b><span>Formats</span></div>
                <div class="emb-stat"><b>{APP_VERSION}</b><span>App version</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def dashboard_page(items: List[Dict[str, Any]], paths: SessionPaths) -> None:
    top_ad()
    hero_dashboard(items)
    status = engine_status()
    st.markdown(
        """
        <div class="emb-panel">
            <h2>How EMBORGANIZER works</h2>
            <p class="emb-muted">Upload embroidery folders, then EMBORGANIZER creates quick visual previews for DST, PES, JEF, VP3, EXP, HUS, XXX, and EMB files. It is built for embroidery designers, digitizers, sellers, and collectors who need to identify files visually instead of opening each design one by one.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="emb-engine-grid">
            <div class="emb-engine-card"><b>TurboEmb v3</b><span>Turbo renderer pipeline with C++ acceleration when available and safe Python fallback on hosts without a compiler.</span></div>
            <div class="emb-engine-card"><b>TurboImport v1</b><span>Startup Google Drive scan, user-permission import, optional C++ native manifest filter, and safe Python fallback.</span></div>
            <div class="emb-engine-card"><b>{TURBO_IMPORT_ANIMATION_VERSION}</b><span>Animated Drive scan card, moving scan beam, hover panels, and reduced-motion safety.</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<span class="emb-step">1</span>', unsafe_allow_html=True)
        st.markdown("**Import / Scan**")
        st.caption("Select a browser folder, upload a ZIP folder, or import a few individual files.")
    with c2:
        st.markdown('<span class="emb-step">2</span>', unsafe_allow_html=True)
        st.markdown("**TurboEmb v3 Render**")
        st.caption("C++ renders stitch paths first when available, then Pillow sharpens up to 4K output.")
    with c3:
        st.markdown('<span class="emb-step">3</span>', unsafe_allow_html=True)
        st.markdown("**TurboSync + TurboThinker**")
        st.caption("Sort by IMGS type, save JSON cache, build virtual type folders, and search smaller groups fast.")
    st.markdown("<br/>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Storage", human_size(total_library_size(items)))
    m2.metric("Preview size", f"{DEFAULT_PREVIEW_SIZE}px")
    m3.metric("Engine", "TurboEmb v3" if status.get("available") else "Python fallback")
    m4.metric("4K output", f"{TURBO_4K_IMAGE_SIZE}px")
    with st.expander("TurboEmb v3 + Turbo Import + Animation S engine details"):
        st.write(status.get("message", "Engine status unavailable"))
        st.json({"engine": TURBOEMB_ENGINE_VERSION, "animation": ANIMATION_ENGINE_VERSION, "ui_release": TURBO_UI_RELEASE, "cpp_available": status.get("available"), "preview_size": DEFAULT_PREVIEW_SIZE, "generation_default": DEFAULT_GENERATION_SIZE, "max_draw_segments": MAX_DRAW_SEGMENTS, "ui_features": TURBO_UI_FEATURES})
        if ensure_turbo_import_native is not None:
            st.json({"turbo_import_native": ensure_turbo_import_native()[1]})
        else:
            st.write("TurboImport native scanner module is not loaded; Python fallback is active.")
        if ensure_sync_native is not None:
            st.json({"turbo_sync_native": ensure_sync_native()[1], "sync_engine": SYNC_ENGINE_VERSION})
        else:
            st.write("TurboSync module is not loaded; Python fallback is active.")
    render_turbo_import_card(paths, items)



def render_upload_summary(summary: Dict[str, Any]) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Files seen", f"{summary.get('total_files', 0):,}")
    c2.metric("Design files", f"{summary.get('supported', 0):,}")
    c3.metric("Folders", f"{summary.get('folders', 0):,}")
    c4.metric("Upload size", human_size(int(summary.get('total_bytes', 0))))
    if summary.get("unsupported"):
        st.caption(f"Unsupported files are ignored: {summary['unsupported']:,}")


def run_import_and_save(
    uploaded_files: List[Any],
    paths: SessionPaths,
    items: List[Dict[str, Any]],
    source_label: str,
    duplicate_policy: str,
    import_root: Optional[str] = None,
) -> None:
    new_items, warnings = import_uploads(
        list(uploaded_files or []),
        paths,
        existing_items=items,
        source_label=source_label,
        duplicate_policy=duplicate_policy,
        import_root=import_root,
    )
    merged_items = merge_library(items, new_items)
    if build_training_index is not None:
        try:
            build_training_index(paths.root, merged_items)
        except Exception:
            pass
    if sync_library_cache is not None:
        try:
            sync_library_cache(paths.root, merged_items)
        except Exception:
            pass
    save_library(paths, merged_items)
    if new_items:
        st.success(f"Imported {len(new_items):,} design{'s' if len(new_items) != 1 else ''} with folder structure preserved.")
    else:
        st.info("No new supported embroidery designs were imported.")
    for warning in warnings[:10]:
        st.warning(warning)
    st.rerun()


def import_scan_page(items: List[Dict[str, Any]], paths: SessionPaths) -> None:
    top_ad()
    st.markdown(
        '<div class="emb-panel"><h2>Turbo Import & Sync v5.0</h2><p class="emb-muted">ZIP/folder import, duplicate skipping, smooth previews, local IMGS JSON cache, C++ assisted TurboSync manifests, and fast divided search.</p></div>',
        unsafe_allow_html=True,
    )
    render_turbo_import_card(paths, items)
    st.markdown(" ")
    t_folder, t_zip, t_files = st.tabs(["📁 Folder Import v2", "🗜️ ZIP Folder", "🧵 Individual Files"])

    with t_folder:
        st.markdown("### Select an embroidery folder")
        st.caption("Best for real design collections. Folder and subfolder names are preserved in the Library view.")
        folder_files = st.file_uploader(
            "Choose a folder",
            type=DESIGN_UPLOAD_EXTENSIONS,
            accept_multiple_files="directory",
            help="Select a folder containing DST, PES, JEF, EXP, VP3, HUS, XXX, or EMB designs.",
            key="folder_import_v2",
        )
        folder_summary = summarize_uploaded_files(list(folder_files or []), allow_zip=False)
        if folder_files:
            render_upload_summary(folder_summary)
            if folder_summary["total_files"] > FOLDER_MAX_FILES:
                st.error(f"This folder has {folder_summary['total_files']:,} files. Current safety limit is {FOLDER_MAX_FILES:,}.")
            if folder_summary["supported"] > FOLDER_MAX_DESIGNS:
                st.error(f"This folder has {folder_summary['supported']:,} supported designs. Current safety limit is {FOLDER_MAX_DESIGNS:,}.")
            if folder_summary["total_bytes"] > FOLDER_MAX_BYTES:
                st.error(f"This folder is {human_size(folder_summary['total_bytes'])}. Current safety limit is {human_size(FOLDER_MAX_BYTES)}.")
        duplicate_policy = st.radio(
            "Duplicate handling",
            ["Skip exact duplicates", "Keep duplicates by folder path"],
            horizontal=True,
            help="Skip is safest for large folders. Keep duplicates preserves repeated designs across different folders.",
            key="folder_duplicate_policy",
        )
        folder_root = st.text_input(
            "Optional library folder name",
            placeholder="Example: Spring collection 2026",
            help="Leave blank to use the selected folder paths exactly as uploaded.",
            key="folder_root_name",
        )
        can_import_folder = bool(folder_files) and folder_summary["supported"] > 0 and folder_summary["total_files"] <= FOLDER_MAX_FILES and folder_summary["supported"] <= FOLDER_MAX_DESIGNS and folder_summary["total_bytes"] <= FOLDER_MAX_BYTES
        if st.button("Run Turbo folder import", type="primary", width="stretch", disabled=not can_import_folder):
            run_import_and_save(list(folder_files or []), paths, items, "folder_v2", duplicate_policy, import_root=folder_root.strip() or None)

    with t_zip:
        st.markdown("### Upload a ZIP folder")
        st.caption("Use this when browser folder upload is unavailable, or when sending a collection as one file.")
        zip_files = st.file_uploader(
            "Upload one or more ZIP folders",
            type=["zip"],
            accept_multiple_files=True,
            help="ZIP contents are scanned safely and supported embroidery files are imported.",
            key="zip_import_v2",
        )
        if zip_files:
            render_upload_summary(summarize_uploaded_files(list(zip_files or []), allow_zip=True))
        zip_duplicate_policy = st.radio(
            "ZIP duplicate handling",
            ["Skip exact duplicates", "Keep duplicates by folder path"],
            horizontal=True,
            key="zip_duplicate_policy",
        )
        if st.button("Import ZIP folder", type="primary", width="stretch", disabled=not zip_files):
            run_import_and_save(list(zip_files or []), paths, items, "zip_v2", zip_duplicate_policy)

    with t_files:
        st.markdown("### Upload individual embroidery files")
        st.caption("Quick mode for testing a few files before importing a full folder.")
        design_files = st.file_uploader(
            "Upload embroidery files",
            type=DESIGN_UPLOAD_EXTENSIONS,
            accept_multiple_files=True,
            help="Supported: DST, PES, JEF, EXP, VP3, HUS, XXX, EMB.",
            key="files_import_v2",
        )
        if design_files:
            render_upload_summary(summarize_uploaded_files(list(design_files or []), allow_zip=False))
        file_duplicate_policy = st.radio(
            "File duplicate handling",
            ["Skip exact duplicates", "Keep duplicates by folder path"],
            horizontal=True,
            key="file_duplicate_policy",
        )
        if st.button("Import files", type="primary", width="stretch", disabled=not design_files):
            run_import_and_save(list(design_files or []), paths, items, "file_v2", file_duplicate_policy)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current library", f"{len(items):,} files")
    col2.metric("Folder limit", f"{FOLDER_MAX_DESIGNS:,} designs")
    col3.metric("Size limit", human_size(FOLDER_MAX_BYTES))
    col4.metric("Preview", f"{DEFAULT_PREVIEW_SIZE}px")

    st.markdown("### TurboSync cache")
    st.caption("Builds virtual type folders and fast search manifests after import, without moving your original files.")
    if st.button("Run TurboSync cache rebuild", width="stretch", disabled=not items):
        if sync_library_cache is None:
            st.error("TurboSync engine is unavailable in this build.")
        else:
            sync_summary = sync_library_cache(paths.root, items)
            st.success("TurboSync cache rebuilt.")
            st.json(sync_summary)

    if st.button("Clear this session", width="stretch"):
        shutil.rmtree(paths.root, ignore_errors=True)
        st.session_state.pop("session_id", None)
        st.rerun()

    st.markdown("### Supported formats")
    st.markdown(" ".join(f'<span class="emb-pill">{ext.upper().lstrip(".")}</span>' for ext in sorted(SUPPORTED_EXTENSIONS)), unsafe_allow_html=True)

    st.markdown("### Direct converter URL")
    st.markdown("Use the `DST to PNG / JPG` menu item inside this main GUI for direct conversion without adding files to the library.")

def library_page(items: List[Dict[str, Any]], paths: SessionPaths) -> None:
    top_ad()
    st.markdown('<div class="emb-panel"><h2>Library</h2><p class="emb-muted">Browse generated previews with folder grouping and quick search.</p></div>', unsafe_allow_html=True)
    library_tab(items, paths)


def convert_page(items: List[Dict[str, Any]], paths: SessionPaths) -> None:
    top_ad()
    if not items:
        st.info("Import designs first, then convert them to clean images.")
        return
    st.markdown('<div class="emb-panel"><h2>Turbo 4K Image Generation</h2><p class="emb-muted">Generate clean and sharp design images with TurboEmb v3. v4.8 keeps 4K output for product/listing images while previews remain lightweight.</p><p class="emb-muted"><b>Direct:</b> use the built-in <code>DST to PNG / JPG</code> menu item for upload-to-image conversion without importing into the library.</p></div>', unsafe_allow_html=True)
    names = [f"{item['relative_path']}" for item in items]
    selected_names = st.multiselect("Choose designs", names, default=names[: min(12, len(names))])
    selected_set = set(selected_names)
    selected_items = [item for item in items if item["relative_path"] in selected_set]
    col1, col2 = st.columns([1, 3])
    with col1:
        format_label = st.selectbox("Output format", ["PNG", "JPEG", "WEBP"], index=0)
    with col2:
        if image_quality_selector is not None:
            quality = image_quality_selector(key_prefix="library_convert", default="4K ultra", max_size=4096)
            image_size = int(quality["size"])
        else:
            image_size = st.number_input("Square image size", min_value=512, max_value=4096, value=DEFAULT_GENERATION_SIZE, step=64)
    if st.button("Generate Turbo 4K images", type="primary", disabled=not selected_items):
        zip_path, results = convert_items(selected_items, paths, format_label, int(image_size))
        ok_count = sum(1 for row in results if row["ok"])
        st.success(f"Generated {ok_count} of {len(results)} TurboEmb image files at {int(image_size)}px.")
        st.download_button("Download generated images ZIP", data=zip_path.read_bytes(), file_name=zip_path.name, mime="application/zip", width="stretch")
        with st.expander("Generation details"):
            for row in results:
                status_icon = "✅" if row["ok"] else "⚠️"
                engine = (row.get("info") or {}).get("engine", "renderer")
                st.write(f"{status_icon} {row['name']} → `{Path(row['output_path']).name}` · {engine}")



def imgs_training_page(items: List[Dict[str, Any]], paths: SessionPaths) -> None:
    top_ad()
    st.markdown(
        f"""<div class=\"emb-panel\"><h2>TurboThinker Training Center <span class=\"emb-pill\">BETA</span></h2><p class=\"emb-muted\"><b>{TURBOTHINKER_TAG}</b> · {TURBOTHINKER_ENGINE_VERSION}</p><p class=\"emb-muted\"><b>{IMGS_TRAINING_TAG}</b> · {IMGS_TRAINING_VERSION}</p><p class=\"emb-clean-note\">{IMGS_TRAINING_WARNING}</p></div>""",
        unsafe_allow_html=True,
    )
    if ensure_training_dirs is None:
        st.error("IMGS Training module is unavailable in this build.")
        return
    ensure_training_dirs(paths.root)

    summary = summarize_training(items) if summarize_training is not None else {"trained": 0, "total": len(items), "counts": {}}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Library designs", f"{len(items):,}")
    c2.metric("IMGS trained", f"{int(summary.get('trained', 0)):,}")
    c3.metric("Known types", f"{len(summary.get('counts', {}) or {}):,}")
    corrections_count = 0
    if load_corrections is not None:
        corrections_count = len((load_corrections(paths.root).get("samples") or []))
    c4.metric("Corrections", f"{corrections_count:,}")

    t_train, t_supergui, t_library, t_resync, t_data = st.tabs(["🧠 TurboThinker teach", "🧬 TurboThinker GUI", "🏷️ Library tags", "🔄 Resync + Sync", "📦 Local data"])

    with t_train:
        st.markdown("### Teach TurboThinker with image samples")
        st.caption("Upload PNG/JPG/WEBP previews or screenshots. v5.0 adds UltraBrain ensemble recognition on top of the real local AI-student model, keeps `multi_design_preview` first when needed, and improves when you correct tags locally.")
        opt1, opt2, opt3 = st.columns([0.34, 0.33, 0.33])
        with opt1:
            auto_remove_low_tags = st.checkbox(
                "Auto-remove weak leftover tags",
                value=True,
                help="Drops low-score type tags after TurboThinker thinks, so old/weak labels do not pollute training samples.",
                key="imgs_auto_remove_low_tags",
            )
        with opt2:
            tag_min_score = st.slider("Weak tag cutoff", 0.10, 0.60, 0.24, 0.02, key="imgs_tag_cutoff")
        with opt3:
            fixed_selector_size = st.slider("Fixed selector size", 80, 640, 280, 20, key="imgs_fixed_selector_size", help="Use this crop box to study a fixed area like bottom-left, top-right, hand, neck, etc.")

        st.markdown("#### 300+ ZIP visual pre-training")
        seed_bank = load_seed_training_bank(paths.root) if load_seed_training_bank is not None else {}
        seed_summary = (seed_bank.get("summary") or {}) if isinstance(seed_bank, dict) else {}
        if seed_summary.get("images_indexed"):
            st.success(f"Visual seed bank ready: {int(seed_summary.get('images_indexed', 0)):,} images indexed · {seed_summary.get('count_by_type', {})}")
        student_summary = load_turbothinker_student_summary(paths.root) if load_turbothinker_student_summary is not None else {"exists": False}
        ultra_summary = load_turbothinker_ultrabrain_summary(paths.root) if load_turbothinker_ultrabrain_summary is not None else {"exists": False}
        region_bank = load_ultrabrain_region_bank(paths.root) if load_ultrabrain_region_bank is not None else {}
        region_summary = (region_bank.get("summary") or {}) if isinstance(region_bank, dict) else {}
        if ultra_summary.get("exists"):
            ts = ultra_summary.get("training_summary") or {}
            st.success(f"v5.0 UltraBrain ready: {int(ts.get('rows') or 0):,} visual rows · {ultra_summary.get('labels_with_weights', 0)} trained label heads · {ultra_summary.get('knn_memory_rows', 0):,} visual memory rows · no filename labels")
        else:
            st.warning("v5.0 UltraBrain is not trained yet. Build seed bank, train v4.9 student, then train UltraBrain below.")
        if student_summary.get("exists"):
            st.success(f"v4.9 AI-student weights ready: {student_summary.get('training_rows', 0):,} visual rows · {student_summary.get('labels', 0)} output labels · no filename labels")
        else:
            st.warning("v4.9 AI-student weights not trained yet. Build seed bank, then train the student model below.")
        if region_summary.get("region_rows_indexed"):
            st.info(f"UltraBrain region bank ready: {int(region_summary.get('region_rows_indexed') or 0):,} crop/part rows from {int(region_summary.get('images_seen') or 0):,} images.")
        st.caption("Upload your TR files ZIP here. TurboThinker builds a local visual seed bank from the images only; file names are saved only as source IDs, never as labels. v4.9 trains local weights; v5.0 UltraBrain adds ensemble recognition, prototypes, KNN memory, and tag graph reasoning.")
        z1, z2, z3 = st.columns([0.48, 0.22, 0.30])
        with z1:
            zip_training_upload = st.file_uploader(
                "Bulk training ZIP",
                type=["zip"],
                accept_multiple_files=False,
                key="imgs_bulk_training_zip_upload",
            )
        with z2:
            zip_limit = st.number_input("Max ZIP images", min_value=10, max_value=5000, value=500, step=50, key="imgs_bulk_zip_limit")
        with z3:
            save_detail_json = st.checkbox("Save per-image JSON", value=True, key="imgs_bulk_zip_detail_json")
            build_region_bank = st.checkbox("Also build UltraBrain crop bank", value=True, key="imgs_build_ultra_region_bank")
            crops_per_image = st.slider("Crops/image", 4, 10, 8, 1, key="imgs_ultra_crops_per_image")
        if zip_training_upload is not None and st.button("Build / refresh visual seed bank from ZIP", type="primary", key="imgs_build_seed_bank"):
            if build_seed_training_corpus_from_zip_bytes is None:
                st.error("Seed-bank trainer is unavailable in this build.")
            else:
                with st.spinner("TurboThinker is reading the ZIP visually and building the local seed bank…"):
                    bank = build_seed_training_corpus_from_zip_bytes(
                        paths.root,
                        zip_training_upload.getvalue(),
                        corpus_name=zip_training_upload.name,
                        limit=int(zip_limit),
                        tag_min_score=float(tag_min_score),
                        save_detail_json=bool(save_detail_json),
                    )
                st.success(f"Seed bank built: {int((bank.get('summary') or {}).get('images_indexed', 0)):,} images indexed without filename labels.")
                st.json(bank.get("summary") or {})
                if build_region_bank and build_ultrabrain_region_corpus_from_zip_bytes is not None:
                    with st.spinner("UltraBrain is making crop/region training rows from the ZIP…"):
                        rbank = build_ultrabrain_region_corpus_from_zip_bytes(
                            paths.root,
                            zip_training_upload.getvalue(),
                            corpus_name=f"{zip_training_upload.name}_regions",
                            limit=int(zip_limit),
                            crops_per_image=int(crops_per_image),
                            tag_min_score=float(tag_min_score),
                        )
                    st.success(f"UltraBrain crop bank built: {int((rbank.get('summary') or {}).get('region_rows_indexed', 0)):,} crop/part rows.")
                    st.json(rbank.get("summary") or {})

        st.markdown("#### v4.9 real AI-student weight training")
        st.caption("This trains and saves actual local model weights from the visual seed bank plus your corrected samples. It still runs fully local and does not learn from filenames.")
        ctrain1, ctrain2 = st.columns([0.45, 245])
        with ctrain1:
            student_epochs = st.slider("Student training epochs", 80, 800, 340, 20, key="imgs_student_epochs")
        with ctrain2:
            include_corrections = st.checkbox("Use my saved corrections as stronger labels", value=True, key="imgs_student_use_corrections")
        if st.button("Train / refresh v4.9 AI-student model weights", type="primary", key="imgs_train_student_model"):
            if train_turbothinker_student_model is None:
                st.error("Student model trainer is unavailable in this build.")
            else:
                with st.spinner("Training local TurboThinker Student model weights from image features…"):
                    report = train_turbothinker_student_model(
                        paths.root,
                        epochs=int(student_epochs),
                        include_seed_bank=True,
                        include_user_corrections=bool(include_corrections),
                    )
                st.success(f"AI-student model trained: {report.get('training_summary', {}).get('rows', 0):,} rows · weights saved locally.")
                st.json(report)

        st.markdown("#### v5.0 UltraBrain recognition engine")
        st.caption("This trains the bigger local brain: AI-student scores + prototype memory + nearest-neighbor visual memory + embroidery tag graph. It is still fully local and filename-free.")
        cultra1, cultra2 = st.columns([0.45, 245])
        with cultra1:
            ultra_epochs = st.slider("UltraBrain training epochs", 80, 700, 260, 20, key="imgs_ultra_epochs")
        with cultra2:
            ultra_use_corrections = st.checkbox("Use saved corrections in UltraBrain", value=True, key="imgs_ultra_use_corrections")
        if st.button("Train / refresh v5.0 UltraBrain", type="primary", key="imgs_train_ultrabrain"):
            if train_turbothinker_ultrabrain_model is None:
                st.error("UltraBrain trainer is unavailable in this build.")
            else:
                with st.spinner("Training local UltraBrain ensemble recognition model…"):
                    report = train_turbothinker_ultrabrain_model(
                        paths.root,
                        epochs=int(ultra_epochs),
                        include_seed_bank=True,
                        include_user_corrections=bool(ultra_use_corrections),
                    )
                ts = report.get("training_summary") or {}
                st.success(f"UltraBrain trained: {int(ts.get('rows') or 0):,} rows · {report.get('labels_with_weights', 0)} label heads · {report.get('knn_memory_rows', 0):,} memory rows saved locally.")
                st.json(report)

        st.markdown("#### v5.3 SuperBrain cortex training")
        st.caption("This is the bigger brain layer: multi-cortex visual expansion, teacher-correction priority, label capsules, larger local memory, and failure diagnosis. It is still local and honest—corrections teach it more than auto guesses.")
        csuper1, csuper2, csuper3 = st.columns([0.33, 0.33, 0.34])
        with csuper1:
            super_aug = st.slider("SuperBrain augmentation", 2, 8, 4, 1, key="imgs_super_aug")
        with csuper2:
            super_use_corrections = st.checkbox("Use saved corrections in SuperBrain", value=True, key="imgs_super_use_corrections")
        with csuper3:
            st.caption("Best workflow: correct 20–50 samples per type, then train SuperBrain.")
        if st.button("Train / refresh v5.3 SuperBrain", type="primary", key="imgs_train_superbrain"):
            if train_turbothinker_superbrain_model is None:
                st.error("SuperBrain trainer is unavailable in this build.")
            else:
                with st.spinner("Training local SuperBrain cortex model from seed bank and teacher corrections…"):
                    report = train_turbothinker_superbrain_model(
                        paths.root,
                        include_seed_bank=True,
                        include_user_corrections=bool(super_use_corrections),
                        augmentation_multiplier=int(super_aug),
                    )
                ts = report.get("training_summary") or {}
                st.success(f"SuperBrain trained: {int(ts.get('training_rows_after_visual_augmentation') or 0):,} rows · {report.get('labels_with_capsules', 0)} label capsules · {report.get('memory_rows', 0):,} memory rows saved locally.")
                st.json(report)

        upload = st.file_uploader(
            "Upload training images",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="imgs_training_image_upload",
        )
        if not upload:
            st.info("Upload a few known samples first: front neck, back neck, cut work, short hand, full hand, heavy work, and mixed preview images.")
        for uploaded in list(upload or []):
            try:
                img = Image.open(uploaded).convert("RGB")
                analysis = analyze_image_for_training(img, uploaded.name) if analyze_image_for_training is not None else {}
                if apply_student_model_memory is not None:
                    analysis = apply_student_model_memory(paths.root, analysis)
                if apply_ultrabrain_memory is not None:
                    analysis = apply_ultrabrain_memory(paths.root, analysis)
                if apply_superbrain_memory is not None:
                    analysis = apply_superbrain_memory(paths.root, analysis)
                pred = analysis.get("prediction") or {}
                if auto_remove_low_tags and prune_prediction_tags is not None:
                    pred = prune_prediction_tags(pred, min_score=float(tag_min_score))
                    analysis = dict(analysis)
                    analysis["prediction"] = pred
                sample_id, saved_path = save_uploaded_training_image(paths.root, img, uploaded.name) if save_uploaded_training_image is not None else (hashlib.sha256(uploaded.name.encode()).hexdigest()[:16], None)
                st.markdown("---")
                cols = st.columns([0.25, 0.75])
                with cols[0]:
                    st.image(img, caption=uploaded.name, width="stretch")
                with cols[1]:
                    st.markdown(f"**Auto guess:** `{pred.get('predicted_type', 'unknown_review')}` · confidence `{pred.get('confidence', 0)}%")
                    st.caption("Tags: " + ", ".join(pred.get("tags") or []))
                    thinker = analysis.get("turbothinker") or {}
                    if thinker:
                        st.caption(f"TurboThinker: {thinker.get('image_mode', 'single')} · estimated files {thinker.get('unique_design_file_count', {}).get('min', 1)}–{thinker.get('unique_design_file_count', {}).get('max', 1)} · parts {len(thinker.get('parts_detected') or [])}")
                    reasons = pred.get("reason") or []
                    if reasons:
                        st.markdown("**Why it thinks this:**")
                        for reason in reasons[:6]:
                            st.caption("• " + str(reason))

                    default_label = pred.get("predicted_type") if pred.get("predicted_type") in IMGS_LABELS else "unknown_review"
                    default_idx = IMGS_LABELS.index(default_label) if default_label in IMGS_LABELS else IMGS_LABELS.index("unknown_review")
                    final_label = st.selectbox("Correct primary design type", IMGS_LABELS, index=default_idx, key=f"imgs_label_{sample_id}")

                    st.markdown("#### Multi-preview / category tags")
                    suggested = [t for t in (pred.get("tags") or []) if isinstance(t, str)]
                    default_categories = []
                    for cat in ANNE_CATEGORY_TAGS:
                        slug = ANNE_CATEGORY_TAG_SLUGS.get(cat, "") if isinstance(ANNE_CATEGORY_TAG_SLUGS, dict) else ""
                        if cat in suggested or slug in suggested:
                            default_categories.append(cat)
                    anne_tags = st.multiselect(
                        "Anne category tags to save",
                        ANNE_CATEGORY_TAGS,
                        default=default_categories,
                        key=f"anne_category_tags_{sample_id}",
                        help="These are optional search tags. They do not replace the primary IMGS type.",
                    )
                    custom_tags_text = st.text_input(
                        "Add new tags",
                        key=f"imgs_custom_tags_{sample_id}",
                        placeholder="Example: flower_border, heavy_outline, triangle_arc, sleeve_net",
                    )
                    custom_tags = [t.strip() for t in custom_tags_text.replace(";", ",").split(",") if t.strip()]
                    notes = st.text_input("Optional note", key=f"imgs_note_{sample_id}", placeholder="Example: actually boat style back neck with net work")

                    with st.expander("Fixed area selector / local crop reader"):
                        w, h = img.size
                        box = min(int(fixed_selector_size), max(32, w), max(32, h))
                        max_x = max(0, w - box)
                        max_y = max(0, h - box)
                        sx = st.slider("Selector X", 0, max_x, 0, key=f"imgs_sel_x_{sample_id}")
                        sy_default = min(max_y, max(0, h - box))
                        sy = st.slider("Selector Y", 0, max_y, sy_default, key=f"imgs_sel_y_{sample_id}")
                        crop_box = (sx, sy, min(w, sx + box), min(h, sy + box))
                        crop = img.crop(crop_box)
                        st.image(crop, caption=f"Selected area {sx},{sy} size {box}px", width="stretch")
                        if analyze_selector_area is not None:
                            selector_result = analyze_selector_area(img, f"{uploaded.name}_crop_{sx}_{sy}_{box}", crop_box)
                            crop_analysis = selector_result.get("analysis") or {}
                            crop_tags = selector_result.get("selector_tags") or []
                            crop_reasons = selector_result.get("selector_reasons") or []
                        else:
                            crop_analysis = analyze_image_for_training(crop, f"{uploaded.name}_crop_{sx}_{sy}_{box}") if analyze_image_for_training is not None else {}
                            selector_result = {"analysis": crop_analysis, "selector_tags": (crop_analysis.get("prediction") or {}).get("tags") or [], "selector_reasons": (crop_analysis.get("prediction") or {}).get("reason") or [], "crop_box": list(crop_box)}
                            crop_tags = selector_result.get("selector_tags") or []
                            crop_reasons = selector_result.get("selector_reasons") or []
                        crop_pred = crop_analysis.get("prediction") or {}
                        st.markdown(f"**Crop response:** `{crop_pred.get('predicted_type', 'unknown_review')}` · confidence `{crop_pred.get('confidence', 0)}%`")
                        st.caption("Selector tags: " + ", ".join(crop_tags))
                        for reason in crop_reasons[:6]:
                            st.caption("• " + str(reason))
                        crop_save_tags = list(anne_tags) + list(custom_tags) + list(crop_tags)
                        if st.button("Save this selector area", key=f"imgs_save_selector_{sample_id}"):
                            crop_path = paths.root / "imgs_training" / "crops" / f"{sample_id}_{sx}_{sy}_{box}.png"
                            crop_path.parent.mkdir(parents=True, exist_ok=True)
                            crop.save(crop_path, format="PNG", optimize=True)
                            if record_selector_area_training is not None:
                                record_selector_area_training(
                                    paths.root,
                                    parent_sample_id=sample_id,
                                    source_name=uploaded.name,
                                    selector_result=selector_result,
                                    crop_image_path=str(crop_path),
                                    final_tags=crop_save_tags,
                                    notes=notes,
                                )
                                st.success("Saved selector crop JSON locally for future TurboThinker training.")
                        st.caption("This selector is for teaching/review. Move the box to flowers, border, hand, neck, or stitched-photo areas and save the useful tags above.")

                    manual_tags = []
                    manual_tags.extend(anne_tags)
                    manual_tags.extend(custom_tags)
                    # For mixed previews, keep the first tag explicit even if the user changes primary label.
                    if (analysis.get("turbothinker") or {}).get("image_mode") == "multi_design_preview" and "multi_design_preview" not in manual_tags:
                        manual_tags.insert(0, "multi_design_preview")

                    if st.button("Save correction / training sample", key=f"imgs_save_{sample_id}", type="primary"):
                        if record_training_correction is not None:
                            record_training_correction(
                                paths.root,
                                sample_id=sample_id,
                                source_name=uploaded.name,
                                analysis=analysis,
                                final_label=final_label,
                                notes=notes,
                                sample_image_path=str(saved_path) if saved_path else None,
                                manual_tags=manual_tags,
                                auto_remove_low_tags=auto_remove_low_tags,
                                tag_min_score=float(tag_min_score),
                            )
                            st.success(f"Saved local training correction as `{final_label}` with {len(manual_tags)} manual/category tags.")
                    with st.expander("TurboThinker / IMGS JSON"):
                        st.json(analysis)
            except Exception as exc:
                st.warning(f"Could not read {getattr(uploaded, 'name', 'image')}: {exc}")

    with t_supergui:
        st.markdown("### TurboThinker GUI — train, test, diagnose")
        st.caption("This panel is for first teaching the brain, then checking why it fails. It shows model strength, nearest memory, failure warnings, and JSON details without cluttering the main dashboard.")
        sg_seed = load_seed_training_bank(paths.root) if load_seed_training_bank is not None else {}
        sg_seed_summary = (sg_seed.get("summary") or {}) if isinstance(sg_seed, dict) else {}
        sg_student = load_turbothinker_student_summary(paths.root) if load_turbothinker_student_summary is not None else {}
        sg_ultra = load_turbothinker_ultrabrain_summary(paths.root) if load_turbothinker_ultrabrain_summary is not None else {}
        sg_super = load_turbothinker_superbrain_summary(paths.root) if load_turbothinker_superbrain_summary is not None else {}
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Seed images", f"{int(sg_seed_summary.get('images_indexed') or 0):,}")
        m2.metric("Student", "ready" if sg_student.get("exists") else "missing")
        m3.metric("UltraBrain", "ready" if sg_ultra.get("exists") else "missing")
        m4.metric("SuperBrain", "ready" if sg_super.get("exists") else "missing")
        if sg_super.get("exists"):
            sts = sg_super.get("training_summary") or {}
            st.success(f"SuperBrain active: {int(sts.get('training_rows_after_visual_augmentation') or 0):,} training rows · {sg_super.get('labels_with_capsules', 0)} label capsules · {sg_super.get('memory_rows', 0):,} memory rows · local/no API.")
        else:
            st.warning("SuperBrain is not trained yet. Use the teach tab: build seed bank → save corrections → train v5.3 SuperBrain.")

        st.markdown("#### Test the brain on one image")
        test_file = st.file_uploader("Upload image to test TurboThinker", type=["png", "jpg", "jpeg", "webp"], key="superbrain_test_upload")
        if test_file is not None:
            try:
                img = Image.open(test_file).convert("RGB")
                analysis = analyze_image_for_training(img, test_file.name) if analyze_image_for_training is not None else {}
                if apply_student_model_memory is not None:
                    analysis = apply_student_model_memory(paths.root, analysis)
                if apply_ultrabrain_memory is not None:
                    analysis = apply_ultrabrain_memory(paths.root, analysis)
                if apply_superbrain_memory is not None:
                    analysis = apply_superbrain_memory(paths.root, analysis)
                pred = analysis.get("prediction") or {}
                left, right = st.columns([0.32, 0.68])
                with left:
                    st.image(img, caption=test_file.name, width="stretch")
                with right:
                    st.markdown(f"**Prediction:** `{pred.get('predicted_type', 'unknown_review')}` · confidence `{pred.get('confidence', 0)}%`")
                    st.caption("Tags: " + ", ".join(pred.get("tags") or []))
                    if pred.get("superbrain_failure_notes"):
                        st.markdown("**Failure / teaching notes:**")
                        for note in pred.get("superbrain_failure_notes")[:5]:
                            st.warning(str(note))
                    if pred.get("superbrain_neighbors"):
                        st.markdown("**Closest visual memory rows:**")
                        for row in pred.get("superbrain_neighbors")[:6]:
                            st.caption(f"• sim {row.get('similarity')} · {', '.join(row.get('labels') or [])} · {row.get('source')}")
                    with st.expander("Score table"):
                        st.json(pred.get("superbrain_label_probabilities") or pred.get("scores") or {})
                    with st.expander("Full TurboThinker JSON"):
                        st.json(analysis)
            except Exception as exc:
                st.warning(f"Could not test image: {exc}")

        st.markdown("#### Teacher correction shortcut")
        st.caption("When the brain is wrong, upload the same image in the Teach tab, set the correct primary label/tags, save correction, then train SuperBrain again. Corrections are intentionally stronger than auto seed guesses.")
        with st.expander("Brain status JSON"):
            st.json({
                "seed_bank": sg_seed_summary,
                "student": sg_student,
                "ultrabrain": sg_ultra,
                "superbrain": sg_super,
            })

    with t_library:
        st.markdown("### Current library IMGS tags")
        counts = summary.get("counts", {}) or {}
        if counts:
            st.json(counts)
        else:
            st.info("No IMGS tags saved yet. Run Resync Cache or import new designs.")
        q = st.text_input("Filter library tags", placeholder="front_neck, cut_work, file name…", key="imgs_library_filter")
        q_lower = q.strip().lower()
        rows = []
        for item in items:
            train = item.get("imgs_training") or {}
            row_text = " ".join([str(item.get("name", "")), str(item.get("relative_path", "")), str(train.get("predicted_type", "")), " ".join(train.get("tags") or [])]).lower()
            if q_lower and q_lower not in row_text:
                continue
            rows.append((item, train))
        for item, train in rows[:120]:
            cols = st.columns([0.12, 243, 0.35])
            with cols[0]:
                preview_path = Path(item.get("preview_path", ""))
                if preview_path.exists():
                    st.image(str(preview_path), width="stretch")
            with cols[1]:
                st.markdown(f"**{item.get('name', 'design')}**")
                st.caption(item_caption(item))
            with cols[2]:
                st.markdown(f"`{train.get('predicted_type', 'not trained')}` · {train.get('confidence', 0)}%")
                st.caption(", ".join(train.get("tags") or []))
        if len(rows) > 120:
            st.caption(f"Showing first 120 of {len(rows):,} matching designs.")

    with t_resync:
        st.markdown("### Rebuild IMGS JSON cache + TurboSync manifests")
        st.caption("This scans generated previews, guesses the design type, writes per-design JSON/fingerprint cache, updates `imgs_index.json`, and builds virtual type folders for fast search.")
        st.warning(IMGS_TRAINING_WARNING)
        force = st.checkbox("Force rebuild existing JSON", value=False, key="imgs_force_resync")
        if st.button("Resync IMGS training cache", type="primary", disabled=not items):
            if apply_imgs_training_to_item is None or build_training_index is None:
                st.error("IMGS training functions are unavailable.")
            else:
                updated: List[Dict[str, Any]] = []
                progress = st.progress(0, text="Starting IMGS cache resync…")
                for idx, item in enumerate(items, start=1):
                    progress.progress((idx - 1) / max(1, len(items)), text=f"IMGS reading {idx:,}/{len(items):,}: {item.get('name', 'design')[:70]}")
                    try:
                        updated.append(apply_imgs_training_to_item(paths.root, dict(item), force=bool(force)))
                    except Exception as exc:
                        bad = dict(item)
                        bad["imgs_training"] = {"engine": IMGS_TRAINING_VERSION, "engine_tag": IMGS_TRAINING_TAG, "status": "error", "predicted_type": "unknown_review", "confidence": 0, "error": str(exc)[:180]}
                        updated.append(bad)
                build_training_index(paths.root, updated)
                if sync_library_cache is not None:
                    sync_library_cache(paths.root, updated)
                save_library(paths, updated)
                progress.progress(1.0, text="IMGS cache resync complete")
                time.sleep(0.25)
                progress.empty()
                st.success("IMGS training cache and TurboSync manifests rebuilt and saved to the local session.")
                st.rerun()

    with t_data:
        st.markdown("### Local saved data")
        root = paths.root / "imgs_training"
        st.code(str(root), language="text")
        index = load_training_index(paths.root) if load_training_index is not None else {}
        corrections = load_corrections(paths.root) if load_corrections is not None else {}
        with st.expander("imgs_index.json"):
            st.json(index)
        with st.expander("corrections.json"):
            st.json(corrections)
        if root.exists():
            zip_path = paths.exports / f"imgs_training_cache_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip"
            if st.button("Package IMGS training cache as ZIP"):
                with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for file in root.rglob("*"):
                        if file.is_file():
                            zf.write(file, file.relative_to(root.parent).as_posix())
                st.download_button("Download IMGS training cache ZIP", data=zip_path.read_bytes(), file_name=zip_path.name, mime="application/zip", width="stretch")

def search_page(items: List[Dict[str, Any]]) -> None:
    top_ad()
    st.markdown('<div class="emb-panel"><h2>IMGS Search <span class="emb-pill">BETA</span></h2><p class="emb-muted">Upload a reference image. TurboThinker reads the type first, then IMGS searches the smallest useful cache group.</p></div>', unsafe_allow_html=True)
    image_search_tab(items)


def main() -> None:
    init_page()
    if handle_google_oauth_callback is not None:
        # Supports OAuth redirect_uri values that point to the root app URL instead of /sign-in.
        if handle_google_oauth_callback(show_success=False):
            return
    paths = get_paths()
    items = load_library(paths)
    maybe_run_turbo_import_scan_once(paths, items)
    nav = sidebar_nav()
    if nav == "Dashboard":
        dashboard_page(items, paths)
    elif nav == "Turbo Import & Sync":
        import_scan_page(items, paths)
    elif nav == "Library":
        library_page(items, paths)
    elif nav == "TurboThinker Training":
        imgs_training_page(items, paths)
    elif nav == "Google Drive":
        from google_drive import render_google_drive_page
        render_google_drive_page(paths, items)
    elif nav == "IMGS Search":
        search_page(items)
    elif nav == "Convert to Image":
        convert_page(items, paths)
    elif nav == "DST to PNG / JPG":
        from direct_converter import render_direct_converter_page
        render_direct_converter_page(
            page_title="DST to PNG / JPG Converter",
            default_format="PNG",
            route_label="main-gui",
        )


if __name__ == "__main__":
    main()
