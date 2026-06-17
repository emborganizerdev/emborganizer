# EMBORGANIZER v5.4.3 Code Organization

## Main GUI

- `streamlit_app.py` — polished full-site Streamlit shell with custom sidebar navigation and pages.
- `app.py` — local Streamlit launcher.

## Recognition / training

- `imgs_training.py` — IMGS/TurboThinker local image analysis, corrections, selector training, and model training helpers.
- `turbothinker_student.py` — student memory layer.
- `turbothinker_ultrabrain.py` — region/feature memory layer.
- `turbothinker_superbrain.py` — stronger KNN-like local memory.
- `turbothinker_interactive_searcher.py` — teacher-rule searcher.
- `teacher_search_memory_v5_4.json` — corrected design naming memory.

## Search / import / cache

- `imagesearch.py` — local fingerprint similarity engine.
- `sync_engine.py` — local cache and manifest resync.
- `sync_native.cpp` — optional C++ dedupe helper.
- `library_manager.py` — maximum library manager helpers for filtering, relabeling, exports, backup, dedupe, and cleanup.

## Converter / renderer

- `dst_converter.py` — restored DST/image converter and design reader helpers.
- `turboemb_engine.py` — TurboEmb v3 C++/Python renderer bridge.
- `turboemb_cpp_renderer.cpp` — native renderer for fast high-quality stitch previews.

## Google / Gmail

- `drive_gmail_bridge.py` — local OAuth config, public Drive download, authenticated Drive browser helpers, Gmail profile/recent-header helpers.
- `local_config/` — private local Google secrets/tokens, ignored by git.

## Data folders

- `library/` — local imported images; ignored by git.
- `cache/` — local search index/fingerprints; ignored by git.
- `exports/` — converter outputs, backups, CSV/JSON exports; ignored by git.
- `downloads/` — Drive downloads; ignored by git.
- `imgs_training/design_json/`, `crops/`, `samples/`, `corrections.json` — local training data; ignored by git.

## GitHub-safe model files

- `imgs_training/models/` and `imgs_training/models/shards/` keep under-25MB brain parts.
- Use `scripts/check_github_safety.py` before push.
