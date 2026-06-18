# EMBORGANIZER v5.4.4 Code Organization

## Main GUI

- `streamlit_app.py` — full-site Streamlit shell with custom sidebar navigation, DST-first import, searcher, training, converter, Drive/Gmail pages, and animations.
- `app.py` — local Streamlit launcher.

## Recognition / training

- `imgs_training.py` — IMGS/TurboThinker local visual analysis, teacher-rule pipeline, corrections, selector training, and local model training helpers.
- `turbothinker_student.py` — student memory layer.
- `turbothinker_ultrabrain.py` — region/feature memory layer.
- `turbothinker_superbrain.py` — stronger local memory layer.
- `turbothinker_interactive_searcher.py` — teacher-rule text searcher.
- `teacher_search_memory_v5_4.json` — corrected design naming memory.

## DST / renderer / reader

- `dst_converter.py` — DST/PES/JEF/etc. reader, converter, 4K preview generator, metadata/statistics collector.
- `turboemb_engine.py` — TurboEmb Python bridge to optional C++ renderer.
- `turboemb_cpp_renderer.cpp` — optional native renderer.
- `legacy_fast_preview_renderer.cpp` — old v0.8.5 C++ renderer source kept for recovery/merge.
- `legacy_imgs_engine.cpp` — old v0.8.5 image search/native helper source kept for recovery/merge.

## Search / import / cache

- `imagesearch.py` — local fingerprint similarity engine.
- `sync_engine.py` — local cache and manifest resync.
- `sync_native.cpp` — optional C++ dedupe/helper.
- `library_manager.py` — maximum library manager: filters, relabeling, exports, backup, dedupe, missing-file cleanup.

## Google / Gmail

- `drive_gmail_bridge.py` — current local Google OAuth, public Drive download, Drive browser, Gmail profile/recent header helpers.
- `legacy_gdrive_sync_engine.py` — old v0.8.5 sync helper kept for merge/reference.
- `local_config/` — private local Google secrets/tokens, ignored by git.

## Speed / UI legacy assets

- `legacy_speed_quality.py` — old speed/quality helper kept for merge/reference.
- `static/legacy/` — old UI JS/CSS helpers kept for recovery.

## Data folders

- `library/` — local imported stitch previews/originals; ignored by git.
- `cache/` — local search index/fingerprints; ignored by git.
- `exports/` — converter outputs, backups, CSV/JSON exports; ignored by git.
- `downloads/` — Drive downloads; ignored by git.
- `imgs_training/design_json/`, `crops/`, `samples/`, `corrections.json` — local training data; ignored by git.

## GitHub-safe model files

- `imgs_training/models/` and `imgs_training/models/shards/` keep under-25MB brain parts.
- Use `scripts/check_github_safety.py` before push.
