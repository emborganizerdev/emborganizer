from __future__ import annotations

import shutil
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
from PIL import Image

from streamlit_app import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_GENERATION_SIZE,
    DEFAULT_PREVIEW_SIZE,
    DESIGN_UPLOAD_EXTENSIONS,
    DIRECT_CONVERTER_MAX_BYTES,
    DIRECT_CONVERTER_MAX_FILES,
    STATIC_DIR,
    SUPPORTED_EXTENSIONS,
    UPLOAD_EXTENSIONS,
    engine_status,
    get_paths,
    human_size,
    import_zip,
    init_page,
    is_supported_design,
    render_design,
    safe_name,
    safe_relative_path,
    top_ad,
    uploaded_file_size,
)

try:
    from google_auth import get_google_user, clear_google_session
except Exception:  # pragma: no cover
    get_google_user = None
    clear_google_session = None

try:
    from quality_profiles import image_quality_selector
except Exception:  # pragma: no cover
    image_quality_selector = None


def _mime_for_format(output_format: str) -> str:
    fmt = output_format.upper().replace("JPG", "JPEG")
    if fmt == "PNG":
        return "image/png"
    if fmt == "JPEG":
        return "image/jpeg"
    if fmt == "WEBP":
        return "image/webp"
    return "application/octet-stream"


def _extension_for_format(output_format: str) -> str:
    fmt = output_format.upper().replace("JPG", "JPEG")
    if fmt == "JPEG":
        return "jpg"
    return fmt.lower()


def _relative_to_upload_root(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except Exception:
        return Path(path.name)


def _write_direct_upload(uploaded_file: Any, input_root: Path) -> Optional[Path]:
    rel = safe_relative_path(getattr(uploaded_file, "name", "design"))
    if not is_supported_design(rel):
        return None
    target = input_root / rel
    if target.exists():
        target = target.with_name(f"{target.stem}_{uuid.uuid4().hex[:6]}{target.suffix.lower()}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(uploaded_file.getbuffer())
    return target


def collect_direct_converter_sources(uploaded_files: List[Any], paths: Any) -> Tuple[Path, List[Path], List[str]]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    input_root = paths.uploads / f"direct_converter_{stamp}_{uuid.uuid4().hex[:6]}"
    input_root.mkdir(parents=True, exist_ok=True)
    sources: List[Path] = []
    warnings: List[str] = []
    total_bytes = 0

    for uploaded in uploaded_files:
        total_bytes += uploaded_file_size(uploaded)
        if total_bytes > DIRECT_CONVERTER_MAX_BYTES:
            warnings.append(f"Direct converter upload stopped at {human_size(total_bytes)}. Current limit is {human_size(DIRECT_CONVERTER_MAX_BYTES)}.")
            break

        suffix = Path(getattr(uploaded, "name", "")).suffix.lower()
        if suffix == ".zip":
            zip_sources, zip_warnings = import_zip(uploaded, paths)
            sources.extend(zip_sources)
            warnings.extend(zip_warnings)
        elif suffix in SUPPORTED_EXTENSIONS:
            saved = _write_direct_upload(uploaded, input_root)
            if saved:
                sources.append(saved)
        else:
            warnings.append(f"Skipped unsupported file: {getattr(uploaded, 'name', 'file')}")

        if len(sources) > DIRECT_CONVERTER_MAX_FILES:
            warnings.append(f"Only the first {DIRECT_CONVERTER_MAX_FILES:,} supported design files were processed to protect the app.")
            sources = sources[:DIRECT_CONVERTER_MAX_FILES]
            break

    return input_root, sources, warnings


def convert_direct_sources(
    sources: List[Path],
    input_root: Path,
    paths: Any,
    output_format: str,
    image_size: int,
) -> Tuple[List[Dict[str, Any]], Optional[Path]]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fmt = output_format.upper().replace("JPG", "JPEG")
    ext = _extension_for_format(fmt)
    output_root = paths.converted / f"direct_converter_{stamp}_{uuid.uuid4().hex[:6]}"
    output_root.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []
    progress = st.progress(0, text="Starting TurboEmb v3 4K image generation…")

    for idx, source in enumerate(sources, start=1):
        try:
            rel = _relative_to_upload_root(source, input_root)
            if rel == Path(source.name):
                # ZIP imports are created outside the direct input root. Keep only the readable tail path.
                try:
                    parts = list(PurePosixPath(source.as_posix()).parts)
                    rel = Path(*parts[-min(4, len(parts)):])
                except Exception:
                    rel = Path(source.name)
            output_rel = rel.with_suffix(f".{ext}")
            output_rel = Path(*[safe_name(part, 90) for part in output_rel.parts])
            output_path = output_root / output_rel
            output_path.parent.mkdir(parents=True, exist_ok=True)
            progress.progress((idx - 1) / max(1, len(sources)), text=f"Generating {idx:,}/{len(sources):,}: {source.name}")
            ok, info = render_design(source, output_path, size=int(image_size), output_format=fmt)
            results.append({
                "source": str(source),
                "name": source.name,
                "relative_output": output_rel.as_posix(),
                "output_path": str(output_path),
                "ok": bool(ok),
                "info": info,
            })
        except Exception as exc:
            results.append({"source": str(source), "name": source.name, "relative_output": source.name, "output_path": "", "ok": False, "info": {"error": str(exc)}})

    progress.progress(1.0, text="Packaging generated images…")
    zip_path: Optional[Path] = None
    if results:
        zip_path = paths.exports / f"emborganizer_{ext}_images_{stamp}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for result in results:
                output_path = Path(result.get("output_path", ""))
                if output_path.exists():
                    zf.write(output_path, result.get("relative_output") or output_path.name)
    progress.empty()
    return results, zip_path


def render_direct_sidebar() -> None:
    with st.sidebar:
        logo = STATIC_DIR / "logo.png"
        if logo.exists():
            st.image(str(logo), width=135)
        st.markdown('<div class="emb-sidebar-title">emborganizer</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="emb-sidebar-version">Version {APP_VERSION.replace("v", "")}</div>', unsafe_allow_html=True)
        user = get_google_user() if get_google_user is not None else None
        if user:
            st.markdown(f"<div style='font-size:.86rem;color:#cbd5e1;margin:.25rem 0 .45rem;'>Signed in as<br/><b>{user.get('email','Google user')}</b></div>", unsafe_allow_html=True)
            if st.button("Sign out", width="content", key="direct_signout"):
                if clear_google_session is not None:
                    clear_google_session()
                st.rerun()
        else:
            st.page_link("pages/sign-in.py", label="Sign in", icon="🔐")
        st.page_link("streamlit_app.py", label="Dashboard", icon="🏠")
        st.page_link("pages/dst-to-png.py", label="DST to PNG", icon="🖼️")
        st.page_link("pages/dst-to-jpg.py", label="DST to JPG", icon="🧵")
        st.page_link("pages/embroidery-to-image.py", label="Any format to image", icon="⚡")
        st.markdown(
            """
            <div style="font-size:.82rem; line-height:1.8; color:#e5edf8;margin-top:1rem;">Clean v4.8 converter · TurboEmb v3</div>
            """,
            unsafe_allow_html=True,
        )


def render_direct_converter_page(
    *,
    page_title: str = "DST to PNG Converter",
    default_format: str = "PNG",
    route_label: str = "/dst-to-png",
    allow_webp: bool = False,
) -> None:
    init_page(page_title=f"{page_title} | {APP_NAME}")
    paths = get_paths()
    render_direct_sidebar()
    top_ad()

    status = engine_status()
    engine_badge = "C++ Turbo ready" if status.get("available") else "Python fallback safe"
    supported_pills = " ".join(f'<span class="emb-pill">{ext.upper().lstrip(".")}</span>' for ext in sorted(SUPPORTED_EXTENSIONS))
    st.markdown(
        f"""
        <div class="emb-hero">
            <h1>{page_title}</h1>
            <div class="emb-badge">Turbo Engine · TurboEmb v3 · 4K image generation · {engine_badge}</div>
            <p>Directly import embroidery files and generate clean, sharp 4K images. This page accepts DST, PES, JEF, EXP, VP3, HUS, XXX, and EMB files, then exports PNG, JPG, or WEBP images without adding files to your library.</p>
            <p class="emb-muted">Direct URL: <code>{route_label}</code></p>
            <div>{supported_pills}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="emb-panel"><h2>Direct Turbo 4K image generation</h2><p class="emb-muted">Upload one embroidery file, many files, or a ZIP. v4.8 keeps 4K output through TurboEmb v3, with single-file downloads and batch ZIP exports.</p></div>', unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "Upload embroidery files or ZIP",
        type=UPLOAD_EXTENSIONS,
        accept_multiple_files=True,
        help="Supported embroidery formats: DST, PES, JEF, EXP, VP3, HUS, XXX, EMB. ZIP batches are also supported.",
        key=f"direct_converter_upload_{route_label}",
    )

    col1, col2 = st.columns([1, 3])
    formats = ["PNG", "JPG"] + (["WEBP"] if allow_webp else [])
    default_format = default_format.upper().replace("JPEG", "JPG")
    with col1:
        selected_format = st.selectbox("Output image format", formats, index=formats.index(default_format) if default_format in formats else 0)
    with col2:
        if image_quality_selector is not None:
            quality = image_quality_selector(key_prefix=f"direct_converter_{route_label.replace('/', '_').replace('-', '_')}", default="4K ultra", max_size=4096)
            image_size = int(quality["size"])
        else:
            image_size = st.number_input("Image size", min_value=512, max_value=4096, value=DEFAULT_GENERATION_SIZE, step=64)

    if uploaded_files:
        total_bytes = sum(uploaded_file_size(file) for file in uploaded_files)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Uploaded files", f"{len(uploaded_files):,}")
        c2.metric("Upload size", human_size(total_bytes))
        c3.metric("Safety limit", f"{DIRECT_CONVERTER_MAX_FILES:,} designs")
        c4.metric("Output", f"{selected_format} {int(image_size)}px")
        if total_bytes > DIRECT_CONVERTER_MAX_BYTES:
            st.error(f"This upload is {human_size(total_bytes)}. Current direct converter limit is {human_size(DIRECT_CONVERTER_MAX_BYTES)}.")

    can_generate = bool(uploaded_files) and sum(uploaded_file_size(file) for file in uploaded_files or []) <= DIRECT_CONVERTER_MAX_BYTES
    if st.button("Generate Turbo 4K image files", type="primary", width="stretch", disabled=not can_generate):
        input_root, sources, warnings = collect_direct_converter_sources(list(uploaded_files or []), paths)
        for warning in warnings[:12]:
            st.warning(warning)
        if not sources:
            st.error("No supported embroidery files were found.")
            return
        fmt = selected_format.upper().replace("JPG", "JPEG")
        results, zip_path = convert_direct_sources(sources, input_root, paths, fmt, int(image_size))
        ok_count = sum(1 for row in results if row.get("ok"))
        st.success(f"Generated {ok_count:,} of {len(results):,} TurboEmb image file{'s' if len(results) != 1 else ''} at {int(image_size)}px.")

        if len(results) == 1:
            first = results[0]
            first_path = Path(first.get("output_path", ""))
            if first_path.exists():
                st.image(str(first_path), caption=first_path.name, width=min(int(image_size), 520))
                st.download_button(
                    f"Download {first_path.suffix.upper().lstrip('.')}",
                    data=first_path.read_bytes(),
                    file_name=first_path.name,
                    mime=_mime_for_format(fmt),
                    width="stretch",
                )

        if zip_path and zip_path.exists():
            st.download_button(
                "Download all generated images ZIP",
                data=zip_path.read_bytes(),
                file_name=zip_path.name,
                mime="application/zip",
                width="stretch",
            )

        with st.expander("Generation details", expanded=False):
            for row in results:
                icon = "✅" if row.get("ok") else "⚠️"
                engine = (row.get("info") or {}).get("engine", "renderer")
                st.write(f"{icon} {row.get('name')} → `{row.get('relative_output')}` · {engine}")

    st.markdown("---")
    if st.button("Clear direct converter session", width="stretch"):
        shutil.rmtree(paths.root, ignore_errors=True)
        st.session_state.pop("session_id", None)
        time.sleep(0.1)
        st.rerun()
