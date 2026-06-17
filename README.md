# EMBORGANIZER v5.4.3 — Full Site Alive

Local-only embroidery organizer, training, converter, and image search site for Shiva Shanth.

## What is restored in v5.4.3

- Full polished Streamlit site navigation, not the broken default pages sidebar.
- **DST to PNG Converter** restored as a main page.
- **4K Design Reader** for stitch files and image analysis.
- **Import Library** for image files, ZIPs, and local folders.
- **Image Searcher** with divide-and-rule type filtering.
- **TurboThinker GUI** for one-image visual reading.
- **Interactive Searcher** using teacher naming rules.
- **IMGS Training BETA** with corrections, weak-tag cleanup, and selector/crop training.
- **Teach / Train** for local ZIP training and brain refresh.
- **Maximum Library Manager** for filtering, previewing, relabeling, dedupe checks, exports, backups, and missing-file cleanup.
- **Library Cache** for resync and fingerprint maintenance.
- **Google Drive** page restored with local OAuth bridge and public Drive download support.
- **Gmail Sign In** page restored for local Google/Gmail connection status and recent header preview.
- **Brain Parts** page for under-25MB GitHub-safe model checks.
- Loading animations across converter, searcher, reader, import, training, and cache tools.

## Important local-only rules

- No external AI/API is needed for image recognition or training.
- File names are kept as record names, but the engine should not learn labels from file names.
- Teacher corrections are stronger than auto guesses.
- `local_config/`, `downloads/`, `library/`, `cache/`, and raw embroidery files stay local and are ignored by git.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Or:

```bash
python app.py
```

## DST to PNG converter

The converter tries this order:

1. Read stitch file with `pyembroidery` when available.
2. If `pyembroidery` is missing and file is `.dst`, use the built-in DST reader fallback.
3. Render with TurboEmb C++ if `g++`/`clang++` is available.
4. Fall back to Python/Pillow rendering when C++ is unavailable.

Supported upload extensions include DST, PES, JEF, EXP, VP3, XXX, U01, and PEC when `pyembroidery` is installed. The built-in fallback can read DST directly.

## Google Drive / Gmail

Public Drive file download can work without OAuth for shareable file links.

Private Drive/Gmail needs your own local Google OAuth client. Save it inside the app UI; tokens and secrets are written to:

```text
local_config/google_connections.json
```

This folder is gitignored and must stay private.

## Teacher naming rules carried forward

Examples from the corrected training conversation are included in the search memory:

- Cut work: irregular inside border stitched, then cloth is cut along that border.
- Net work: drop/back-drop style with jali or vertical net-line filling.
- Rangoli work: kolam/rangoli-style diamond or geometric motifs with loop/dot border.
- Normal work: smooth/regular embroidery without cut-work edge or net/drop identity.
- Neck shape and work type are separate labels.

## GitHub-safe note

Before pushing, use **Brain Parts** and keep all large generated data local. The repository is designed to keep source code and under-25MB brain parts only.
