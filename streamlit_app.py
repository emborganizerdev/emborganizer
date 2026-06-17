"""
EMBORGANIZER v5.3.1 Clean TurboThinker GUI

Clean local UI for the v5.3 24MB brain-part build.
Removed old/clutter pages from the visible app: Google Drive, external sign-in,
legacy converters, and extra marketing panels. This file focuses only on the
workflow Shiva needs now:

1. Check SuperBrain status.
2. Test one image visually.
3. Save teacher corrections.
4. Train/retrain local brain from ZIP + corrections.
5. Verify GitHub-safe 24MB brain parts.

Local-only. No API. File names are never used as labels.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import streamlit as st
from PIL import Image, ImageOps

try:
    from imgs_training import (
        IMGS_LABELS,
        IMGS_TRAINING_WARNING,
        IMGS_TRAINING_VERSION,
        TURBOTHINKER_ENGINE_VERSION,
        analyze_image_for_training,
        analyze_selector_area,
        apply_seed_training_memory,
        apply_student_model_memory,
        apply_ultrabrain_memory,
        apply_superbrain_memory,
        build_seed_training_corpus_from_zip_bytes,
        build_ultrabrain_region_corpus_from_zip_bytes,
        ensure_training_dirs,
        load_corrections,
        load_seed_training_bank,
        load_turbothinker_student_summary,
        load_turbothinker_ultrabrain_summary,
        load_turbothinker_superbrain_summary,
        record_training_correction,
        record_selector_area_training,
        save_uploaded_training_image,
        train_turbothinker_student_model,
        train_turbothinker_ultrabrain_model,
        train_turbothinker_superbrain_model,
    )
except Exception as exc:  # pragma: no cover - Streamlit will display the issue.
    IMGS_LABELS = ["unknown_review"]
    IMGS_TRAINING_WARNING = "TurboThinker modules could not be imported."
    IMGS_TRAINING_VERSION = f"Unavailable: {exc}"
    TURBOTHINKER_ENGINE_VERSION = "Unavailable"
    analyze_image_for_training = None
    analyze_selector_area = None
    apply_seed_training_memory = None
    apply_student_model_memory = None
    apply_ultrabrain_memory = None
    apply_superbrain_memory = None
    build_seed_training_corpus_from_zip_bytes = None
    build_ultrabrain_region_corpus_from_zip_bytes = None
    ensure_training_dirs = None
    load_corrections = None
    load_seed_training_bank = None
    load_turbothinker_student_summary = None
    load_turbothinker_ultrabrain_summary = None
    load_turbothinker_superbrain_summary = None
    record_training_correction = None
    record_selector_area_training = None
    save_uploaded_training_image = None
    train_turbothinker_student_model = None
    train_turbothinker_ultrabrain_model = None
    train_turbothinker_superbrain_model = None

try:
    from turbothinker_superbrain import SUPERBRAIN_VERSION
except Exception:
    SUPERBRAIN_VERSION = "TurboThinker SuperBrain unavailable"

try:
    from turbothinker_model_store import storage_summary
except Exception:
    storage_summary = None


APP_NAME = "EMBORGANIZER"
APP_VERSION = "v5.3.1"
APP_RELEASE = "TurboThinker 24MB Brain-Parts Clean GUI"
APP_ROOT = Path(__file__).resolve().parent
SUPPORTED_IMAGE_TYPES = ["png", "jpg", "jpeg", "webp", "bmp"]


# -----------------------------
# Small safe helpers
# -----------------------------

def _json_read(path: Path, default: Any) -> Any:
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _json_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _safe_percent(value: Any) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except Exception:
        return 0


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _short_path(path: Path) -> str:
    try:
        return str(path.relative_to(APP_ROOT))
    except Exception:
        return str(path)


def _image_from_upload(uploaded: Any) -> Image.Image:
    raw = uploaded.getvalue()
    with Image.open(io.BytesIO(raw)) as img:
        return ImageOps.exif_transpose(img).convert("RGB")


def _sample_id_for_image(img: Image.Image, source_name: str) -> str:
    small = img.copy()
    small.thumbnail((128, 128))
    buf = io.BytesIO()
    small.save(buf, format="PNG")
    return hashlib.sha256(buf.getvalue() + source_name.encode("utf-8", "ignore")).hexdigest()[:16]


def _run_full_analysis(img: Image.Image, source_name: str) -> Dict[str, Any]:
    if analyze_image_for_training is None:
        raise RuntimeError("TurboThinker image analysis is unavailable.")
    analysis = analyze_image_for_training(img, source_name)
    # Blend brains from old to strongest. Each function safely returns unchanged if missing.
    for fn in (apply_seed_training_memory, apply_student_model_memory, apply_ultrabrain_memory, apply_superbrain_memory):
        if fn is not None:
            analysis = fn(APP_ROOT, analysis)
    return analysis


def _score_table(scores: Dict[str, Any], limit: int = 12) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for label, score in sorted((scores or {}).items(), key=lambda kv: float(kv[1] or 0), reverse=True)[:limit]:
        try:
            pct = round(float(score) * 100, 1)
        except Exception:
            pct = 0.0
        rows.append({"label": label, "score": pct})
    return rows


def _brain_manifest_path() -> Path:
    return APP_ROOT / "imgs_training" / "models" / "shards" / "turbothinker_superbrain_v5_3_model" / "manifest.json"


def brain_part_status() -> Dict[str, Any]:
    manifest_path = _brain_manifest_path()
    manifest = _json_read(manifest_path, {})
    parts = []
    total = 0
    ok = True
    for row in _as_list(manifest.get("parts")):
        name = str(row.get("file") or "")
        part_path = manifest_path.parent / name
        size = part_path.stat().st_size if part_path.exists() else 0
        total += size
        part_ok = part_path.exists() and size < 25_000_000
        ok = ok and part_ok
        parts.append({
            "file": name,
            "size_mb": round(size / (1024 * 1024), 2),
            "under_25mb": part_ok,
        })
    return {
        "manifest_exists": manifest_path.exists(),
        "model": manifest.get("model_name") or "turbothinker_superbrain_v5_3_model",
        "parts": parts,
        "parts_count": len(parts),
        "total_mb": round(total / (1024 * 1024), 2),
        "ok": bool(parts and ok),
        "manifest_path": _short_path(manifest_path),
    }


def load_all_summaries() -> Dict[str, Any]:
    summaries: Dict[str, Any] = {}
    for name, fn in [
        ("seed", load_seed_training_bank),
        ("student", load_turbothinker_student_summary),
        ("ultrabrain", load_turbothinker_ultrabrain_summary),
        ("superbrain", load_turbothinker_superbrain_summary),
    ]:
        try:
            summaries[name] = fn(APP_ROOT) if fn is not None else {"exists": False}
        except Exception as exc:
            summaries[name] = {"exists": False, "error": str(exc)}
    try:
        corrections = load_corrections(APP_ROOT) if load_corrections is not None else {}
        summaries["corrections"] = {"count": len(_as_list(corrections.get("samples")))}
    except Exception as exc:
        summaries["corrections"] = {"count": 0, "error": str(exc)}
    summaries["brain_parts"] = brain_part_status()
    return summaries


def _show_prediction_card(analysis: Dict[str, Any]) -> None:
    pred = analysis.get("prediction") or {}
    thinker = analysis.get("turbothinker") or {}
    label = str(pred.get("predicted_type") or "unknown_review")
    confidence = _safe_percent(pred.get("confidence"))
    tags = _as_list(pred.get("tags"))
    secondary = _as_list(pred.get("secondary_types"))
    reasons = _as_list(pred.get("reason"))
    failure_notes = _as_list(pred.get("superbrain_failure_notes"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Primary type", label)
    c2.metric("Confidence", f"{confidence}%")
    c3.metric("Image mode", str(pred.get("image_mode") or thinker.get("image_mode") or "single_design"))
    c4.metric("Estimated parts", str(thinker.get("estimated_region_count") or thinker.get("unique_design_file_count", {}).get("min") or "1"))

    if tags:
        st.markdown("**Tags**")
        st.write(" · ".join(f"`{tag}`" for tag in tags[:24]))
    if secondary:
        st.markdown("**Secondary candidates**")
        st.write(" · ".join(f"`{tag}`" for tag in secondary[:12]))
    if failure_notes:
        st.warning(" | ".join(str(x) for x in failure_notes[:4]))
    if reasons:
        with st.expander("Why TurboThinker guessed this"):
            for reason in reasons[:10]:
                st.write("• " + str(reason))
    scores = _score_table(pred.get("scores") or {}, limit=16)
    if scores:
        with st.expander("Score table"):
            st.dataframe(scores, use_container_width=True, hide_index=True)
    if pred.get("superbrain_neighbors"):
        with st.expander("Nearest visual memory"):
            rows = []
            for n in _as_list(pred.get("superbrain_neighbors"))[:12]:
                rows.append({
                    "label": n.get("label") or n.get("primary") or "",
                    "score": round(float(n.get("score") or n.get("similarity") or 0) * 100, 1),
                    "tags": ", ".join(_as_list(n.get("tags"))[:6]),
                })
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)


# -----------------------------
# Page setup + styling
# -----------------------------

def init_page() -> None:
    st.set_page_config(
        page_title=f"{APP_NAME} {APP_VERSION}",
        page_icon="🧵",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"], section[data-testid="stSidebar"] nav {display:none !important;}
        .block-container {padding-top: 1.35rem; max-width: 1320px;}
        [data-testid="stSidebar"] {background: linear-gradient(180deg,#0f172a,#111827);}
        [data-testid="stSidebar"] * {color:#e5edf8;}
        [data-testid="stSidebar"] label[data-baseweb="radio"] {
          border:1px solid rgba(255,255,255,.10); border-radius:14px; padding:.5rem .65rem; margin:.12rem 0;
          background:rgba(255,255,255,.04);
        }
        [data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {
          background:linear-gradient(135deg,#f59e0b,#f97316); color:#111827 !important; font-weight:900;
        }
        .emb-hero {border:1px solid #e2e8f0; border-radius:24px; padding:1.25rem 1.35rem; background:linear-gradient(135deg,#fff7ed,#eef2ff 55%,#ecfeff); box-shadow:0 20px 50px rgba(15,23,42,.08);}
        .emb-hero h1 {margin:0; font-size:2.1rem; letter-spacing:-.05em; color:#0f172a;}
        .emb-muted {color:#64748b;}
        .emb-card {border:1px solid #e2e8f0; border-radius:20px; padding:1rem; background:#fff; box-shadow:0 12px 30px rgba(15,23,42,.05);}
        .emb-pill {display:inline-block; padding:.25rem .6rem; border-radius:999px; background:#0f172a; color:white; font-size:.78rem; font-weight:800; margin:.15rem .2rem .15rem 0;}
        .emb-good {background:#dcfce7; color:#166534;}
        .emb-warn {background:#fef3c7; color:#92400e;}
        .emb-bad {background:#fee2e2; color:#991b1b;}
        .stButton>button {border-radius:999px; font-weight:800;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_nav() -> str:
    with st.sidebar:
        logo = APP_ROOT / "static" / "logo.png"
        if logo.exists():
            st.image(str(logo), use_container_width=True)
        st.markdown(f"### {APP_NAME}")
        st.caption(f"{APP_VERSION} · Clean TurboThinker GUI")
        nav = st.radio(
            "Navigation",
            ["Dashboard", "TurboThinker GUI", "Teach / Train", "Brain Parts", "Settings"],
            label_visibility="collapsed",
        )
        st.divider()
        st.caption("Local-only · no API · no filename-label learning")
    return nav


def hero(title: str, text: str = "") -> None:
    st.markdown(
        f"""
        <div class="emb-hero">
          <h1>{title}</h1>
          <p class="emb-muted">{text}</p>
          <span class="emb-pill">{APP_VERSION}</span>
          <span class="emb-pill">24MB brain parts</span>
          <span class="emb-pill">TurboThinker SuperBrain</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")


# -----------------------------
# Pages
# -----------------------------

def dashboard_page() -> None:
    hero("TurboThinker SuperBrain", "Clean v5.3.1 GUI matched to the v5.3 24MB brain-part model.")
    st.info(IMGS_TRAINING_WARNING)
    s = load_all_summaries()
    seed_summary = (s.get("seed") or {}).get("summary") or {}
    student = s.get("student") or {}
    ultra = s.get("ultrabrain") or {}
    super_s = s.get("superbrain") or {}
    parts = s.get("brain_parts") or {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Seed images", f"{int(seed_summary.get('images_indexed') or 0):,}")
    c2.metric("Corrections", f"{int((s.get('corrections') or {}).get('count') or 0):,}")
    c3.metric("SuperBrain memory", f"{int(super_s.get('memory_rows') or super_s.get('knn_memory_rows') or 0):,}")
    c4.metric("Brain parts", f"{int(parts.get('parts_count') or 0)}")

    left, right = st.columns([1.15, .85])
    with left:
        st.markdown("#### Current engine")
        st.markdown(f"**IMGS:** `{IMGS_TRAINING_VERSION}`")
        st.markdown(f"**TurboThinker:** `{TURBOTHINKER_ENGINE_VERSION}`")
        st.markdown(f"**SuperBrain:** `{SUPERBRAIN_VERSION}`")
        if parts.get("ok"):
            st.success(f"Brain-part model is GitHub-safe. Largest/part checked under 25 MB. Total: {parts.get('total_mb')} MB")
        else:
            st.warning("Brain-part manifest is missing or a part failed the under-25MB check.")
    with right:
        st.markdown("#### Model summaries")
        st.json({
            "student": {k: student.get(k) for k in ("exists", "labels", "rows", "epochs") if k in student},
            "ultrabrain": {k: ultra.get(k) for k in ("exists", "labels_with_weights", "knn_memory_rows", "rows") if k in ultra},
            "superbrain": {k: super_s.get(k) for k in ("exists", "labels", "memory_rows", "cortex_features", "training_rows") if k in super_s},
            "brain_parts": parts,
        })

    st.markdown("#### Clean UI kept")
    st.write("Dashboard · TurboThinker GUI · Teach/Train · Brain Parts · Settings")
    st.markdown("#### Removed from visible UI")
    st.write("Google Drive sign-in/import · legacy converter pages · old marketing/animation panels · duplicate Streamlit page sidebar")


def turbothinker_gui_page() -> None:
    hero("TurboThinker GUI", "Upload one embroidery preview/image, see the local prediction, then save a correction if needed.")
    uploaded = st.file_uploader("Upload image for visual recognition", type=SUPPORTED_IMAGE_TYPES)
    if not uploaded:
        st.caption("Use this page to test one image after every training round.")
        return

    img = _image_from_upload(uploaded)
    c_img, c_result = st.columns([.85, 1.15])
    with c_img:
        st.image(img, caption=uploaded.name, use_container_width=True)
    with c_result:
        with st.spinner("TurboThinker is reading the image visually…"):
            analysis = _run_full_analysis(img, uploaded.name)
        st.session_state["last_analysis"] = analysis
        st.session_state["last_image"] = img
        st.session_state["last_source_name"] = uploaded.name
        _show_prediction_card(analysis)

    st.divider()
    st.markdown("### Teacher correction")
    pred = (analysis.get("prediction") or {})
    default_label = str(pred.get("predicted_type") or "unknown_review")
    if default_label not in IMGS_LABELS:
        default_label = "unknown_review"
    col1, col2 = st.columns([.8, 1.2])
    with col1:
        final_label = st.selectbox("Correct primary label", IMGS_LABELS, index=IMGS_LABELS.index(default_label))
        auto_remove = st.checkbox("Auto-remove weak leftover tags", value=True)
        min_score = st.slider("Weak tag cutoff", 0.05, 0.75, 0.24, 0.01)
    with col2:
        manual_tags_raw = st.text_input("Extra correct tags", placeholder="flower_border, back_neck, net_work")
        notes = st.text_area("Teacher notes", placeholder="Why this label is correct…", height=80)
    if st.button("Save teacher correction", type="primary"):
        sample_id, sample_path = save_uploaded_training_image(APP_ROOT, img, uploaded.name)
        manual_tags = [x.strip() for x in manual_tags_raw.split(",") if x.strip()]
        saved = record_training_correction(
            APP_ROOT,
            sample_id=sample_id,
            source_name=uploaded.name,
            analysis=analysis,
            final_label=final_label,
            notes=notes,
            sample_image_path=str(sample_path),
            manual_tags=manual_tags,
            auto_remove_low_tags=auto_remove,
            tag_min_score=float(min_score),
        )
        st.success(f"Saved correction: {saved.get('final_label')} · sample {saved.get('sample_id')}")

    with st.expander("Fixed crop / selector reader"):
        st.caption("Enter crop coordinates to test only one area of the image. This is useful for sleeves, borders, neck curves, butti, flowers, or net-work.")
        w, h = img.size
        c1, c2, c3, c4 = st.columns(4)
        x0 = c1.number_input("x0", min_value=0, max_value=max(0, w - 1), value=0)
        y0 = c2.number_input("y0", min_value=0, max_value=max(0, h - 1), value=0)
        x1 = c3.number_input("x1", min_value=1, max_value=w, value=w)
        y1 = c4.number_input("y1", min_value=1, max_value=h, value=h)
        if st.button("Analyze selected area"):
            box = (int(x0), int(y0), int(x1), int(y1))
            result = analyze_selector_area(img, source_name=f"{uploaded.name}::selector", box=box)
            st.image(img.crop(box), caption=f"Selected area {box}", use_container_width=True)
            st.write("Tags: " + " · ".join(f"`{x}`" for x in _as_list(result.get("selector_tags"))))
            for r in _as_list(result.get("selector_reasons")):
                st.write("• " + str(r))
            st.session_state["last_selector_result"] = result
        if st.button("Save selected area training"):
            result = st.session_state.get("last_selector_result")
            if not result:
                st.warning("Analyze a selected area first.")
            else:
                parent_id = _sample_id_for_image(img, uploaded.name)
                saved = record_selector_area_training(APP_ROOT, parent_id, uploaded.name, result)
                st.success(f"Saved selector training area: {saved.get('area_id')}")


def teach_train_page() -> None:
    hero("Teach / Train", "Build visual seed data from ZIPs and retrain the local brain. Corrections are stronger than auto guesses.")
    st.warning("For GitHub, do not commit raw ZIPs. Train locally, keep only under-25MB brain parts in the repo.")

    st.markdown("### 1) Build visual training rows from ZIP")
    zip_file = st.file_uploader("Upload image ZIP for local training", type=["zip"])
    c1, c2, c3 = st.columns(3)
    limit = c1.number_input("Image limit", min_value=1, max_value=100000, value=500, step=100)
    crops_per_image = c2.slider("Region crops per image", 1, 12, 8)
    tag_min = c3.slider("Weak tag cutoff", 0.05, 0.75, 0.24, 0.01)

    if zip_file and st.button("Build seed + region training bank", type="primary"):
        if build_seed_training_corpus_from_zip_bytes is None:
            st.error("Seed-bank builder is unavailable.")
        else:
            payload = zip_file.getvalue()
            with st.spinner("Building full-image seed bank…"):
                seed = build_seed_training_corpus_from_zip_bytes(APP_ROOT, payload, corpus_name=zip_file.name, limit=int(limit), tag_min_score=float(tag_min))
            st.success(f"Seed bank indexed {seed.get('summary', {}).get('images_indexed', 0):,} images")
            if build_ultrabrain_region_corpus_from_zip_bytes is not None:
                with st.spinner("Building crop/region training bank…"):
                    regions = build_ultrabrain_region_corpus_from_zip_bytes(APP_ROOT, payload, corpus_name=f"{zip_file.name}_regions", limit=int(limit), crops_per_image=int(crops_per_image), tag_min_score=float(tag_min))
                st.success(f"Region bank indexed {regions.get('summary', {}).get('region_rows_indexed', 0):,} crop rows")

    st.markdown("### 2) Train local brain weights")
    c1, c2, c3 = st.columns(3)
    train_student = c1.checkbox("Train v4.9 Student", value=True)
    train_ultra = c2.checkbox("Train v5.0 UltraBrain", value=True)
    train_super = c3.checkbox("Train v5.3 SuperBrain", value=True)
    if st.button("Train / refresh selected models", type="primary"):
        if train_student and train_turbothinker_student_model is not None:
            with st.spinner("Training Student weights…"):
                report = train_turbothinker_student_model(APP_ROOT)
            st.success(f"Student trained: {report.get('training_rows', report.get('rows', 'done'))}")
        if train_ultra and train_turbothinker_ultrabrain_model is not None:
            with st.spinner("Training UltraBrain…"):
                report = train_turbothinker_ultrabrain_model(APP_ROOT)
            st.success(f"UltraBrain trained: {report.get('training_rows', report.get('rows', 'done'))}")
        if train_super and train_turbothinker_superbrain_model is not None:
            with st.spinner("Training SuperBrain 24MB brain-part model…"):
                report = train_turbothinker_superbrain_model(APP_ROOT)
            st.success(f"SuperBrain trained: {report.get('training_rows', report.get('raw_training_rows', 'done'))}")
            st.info("Run Brain Parts page check before pushing to GitHub.")

    st.markdown("### 3) Local teacher corrections")
    corrections = load_corrections(APP_ROOT) if load_corrections is not None else {"samples": []}
    rows = _as_list(corrections.get("samples"))
    st.metric("Saved corrections", len(rows))
    if rows:
        compact = [{
            "sample_id": r.get("sample_id"),
            "final_label": r.get("final_label"),
            "predicted_type": r.get("predicted_type"),
            "tags": ", ".join(_as_list(r.get("tags"))[:8]),
            "created_at": r.get("created_at"),
        } for r in rows[-100:]]
        st.dataframe(compact, use_container_width=True, hide_index=True)


def brain_parts_page() -> None:
    hero("Brain Parts", "Check that every brain file is below 25 MB before GitHub upload.")
    status = brain_part_status()
    if status.get("ok"):
        st.success("Brain parts are OK for your under-25MB rule.")
    else:
        st.error("Brain parts need attention before GitHub upload.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Parts", status.get("parts_count", 0))
    c2.metric("Total brain size", f"{status.get('total_mb', 0)} MB")
    c3.metric("Manifest", "found" if status.get("manifest_exists") else "missing")
    if status.get("parts"):
        st.dataframe(status["parts"], use_container_width=True, hide_index=True)
    st.markdown("#### GitHub-safe commands")
    st.code("""git add streamlit_app.py imgs_training.py turbothinker_*.py imgs_training/models/shards/ imgs_training/models/turbothinker_superbrain_v5_3_model.json .gitignore .gitattributes README.md docs scripts\ngit commit -m \"Update clean v5.3 TurboThinker GUI and 24MB brain parts\"\ngit push""", language="bash")
    st.markdown("#### Keep these local only")
    st.code("""training ZIPs\nlibrary/\ncache/\nuploads/\nimgs_training/samples/\nimgs_training/crops/\nimgs_training/design_json/\nimgs_training/seed_training/ if it grows large""", language="text")


def settings_page() -> None:
    hero("Settings", "Clean local setup details.")
    st.markdown("### Visible UI version")
    st.write(f"`{APP_VERSION} — {APP_RELEASE}`")
    st.markdown("### Runtime paths")
    st.json({
        "app_root": str(APP_ROOT),
        "brain_manifest": brain_part_status().get("manifest_path"),
        "training_root": str(APP_ROOT / "imgs_training"),
    })
    st.markdown("### Cleaned out of the navigation")
    st.write("Google Drive, sign-in controls, legacy direct converter pages, old image-generation panels, duplicate page sidebar, old v4/v5 mismatch banners.")
    st.markdown("### Raw engine access")
    if st.checkbox("Show full local model summaries"):
        st.json(load_all_summaries())


# -----------------------------
# Main
# -----------------------------

def main() -> None:
    init_page()
    if ensure_training_dirs is not None:
        ensure_training_dirs(APP_ROOT)
    nav = sidebar_nav()
    if nav == "Dashboard":
        dashboard_page()
    elif nav == "TurboThinker GUI":
        turbothinker_gui_page()
    elif nav == "Teach / Train":
        teach_train_page()
    elif nav == "Brain Parts":
        brain_parts_page()
    else:
        settings_page()


if __name__ == "__main__":
    main()
