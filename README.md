# EMBORGANIZER v5.4.4 — DST-First Full Site Alive

Local-only embroidery organizer, DST renderer, training center, image/DST searcher, and library manager for Shiva Shanth.

## What changed in v5.4.4

This build fixes the import direction: **DST / embroidery files are now the main library source**, not only images.

Added / restored:

- **DST / embroidery file import** as the first Import Library option.
- **ZIP of DST / embroidery import**.
- **Local DST folder scan/import** for local server/desktop use.
- **Image import kept as legacy fallback**.
- **DST / Image Searcher**: search by uploading a DST/PES/JEF/etc. or an image.
- **Meaningful design summaries** instead of only raw JSON bounds.
- **Teacher-rule TurboThinker identification pipeline** showing how it identified shape/work.
- **DST render → TurboThinker read → fingerprint → cache** pipeline.
- **4K Design Reader** still supports stitch files and images.
- **C++ TurboEmb renderer** support with Python fallback.
- **Maximum Library Manager**, Google Drive, Gmail sign-in, cache/resync, training, and animations kept alive.
- Legacy v0.8.5 helper source files included as `legacy_*` files so older speed/GDrive/C++ logic is not lost.

## Main flow

1. Upload DST/PES/JEF/etc. files, a ZIP, or scan a local folder.
2. EMBORGANIZER renders each stitch file to a clean PNG preview.
3. The stitch reader calculates stitches, bounds, density, colors, jumps, and reader engine.
4. TurboThinker reads the rendered preview visually.
5. It creates tags, a meaningful student label, and an explanation.
6. The search cache stores the preview fingerprint plus original DST metadata.
7. Later, search by DST or image.

## Teacher-rule identification

The redesigned TurboThinker explanation follows this order:

1. **Shape / neck type** — U-shaped, drop/back-drop, boat, pot, etc.
2. **Work type** — cut work, net work, rangoli, normal work.
3. **Motif / part** — floral, full hand, back drop, sleeve, butti, border, etc.

Rules carried forward from training:

- **Cut work**: irregular/scallop inside border; after stitching, the cloth can be cut along the shaped border.
- **Net work**: mainly drop/back-drop with jali or vertical net-line filling.
- **Rangoli work**: kolam/rangoli diamond or geometric motif with loop/dot border.
- **Normal work**: smooth/regular embroidery without cut-work or net-work identity.
- **Neck shape and work type are separate**.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Or:

```bash
python app.py
```

## DST converter / renderer

The converter tries this order:

1. Read stitch file with `pyembroidery` when available.
2. If `pyembroidery` is missing and file is `.dst`, use the built-in DST reader fallback.
3. Render with TurboEmb C++ if `g++`/`clang++` is available.
4. Fall back to Python/Pillow rendering when C++ is unavailable.

Supported upload extensions include DST, PES, JEF, EXP, VP3, XXX, U01, and PEC when `pyembroidery` is installed. The built-in fallback can read DST directly.

## Google Drive / Gmail

Public Drive file download can work without OAuth for shareable links. Private Drive/Gmail needs your local Google OAuth client; secrets/tokens are saved under `local_config/`, which is ignored by git.

## Local-only rule

No external AI/API is needed for recognition or training. File names are stored as record names but are not used as design labels.
