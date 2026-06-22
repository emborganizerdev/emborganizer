# EMBORGANIZER v6.0 Code Organization

## GUI layer

- `streamlit_app.py` — v6 dashboard, import GUI, converter GUI, search GUI, training GUI, settings.
- `app.py` — local launcher.

## IMGS engine bridge

- `imgs_engine_v6.py` — v6 bridge imported by the GUI. It re-exports the local engine API and adds lightweight timer/telemetry helpers.
- `imgs_training.py` — existing local IMGS/TurboThinker training and recognition engine.

## Converter / search / library engines

- `dst_converter.py` — DST/PES/JEF/etc. reader and renderer.
- `imagesearch.py` — fingerprint search.
- `library_manager.py` — library management tools.
- `sync_engine.py` — cache/manifest sync.

## v6 cleanup

Visible UI no longer shows typed local folder path scanning, legacy image ZIP/import options, or the old high-res reader page. The converter shows clean cards instead of raw JSON blocks.
