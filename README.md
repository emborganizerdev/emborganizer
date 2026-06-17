# EMBORGANIZER v5.4 — TurboThinker Interactive Searcher GUI

This build recreates the clean **v5.3.1 TurboThinker GUI** as **v5.4** and adds a new local **Interactive Searcher** page.

## What is new in v5.4

- **Interactive Searcher** page added to the sidebar.
- Search by design number, neck type, work type, dress type, or features.
- Uses Shiva teacher-memory rules for:
  - cut work
  - normal work
  - net work
  - rangoli work
  - U-shaped neck
  - drop/back-drop neck
  - pot neck
  - boat neck
  - kurta/front-slit neck
  - full hand and matching hand border
- Searches saved teacher corrections and local training index rows.
- Optional local folder scan for image files.
- Teacher-confirmed examples are kept separate from lower-confidence draft records.

## Teacher rules now built in

### Cut work

Cut work is identified by an **irregular/scallop/step inside border**. After stitching, cloth is cut along that shaped edge and it gives the cut-work finish.

### Net work

Net work is mainly used when a **drop/back-drop area** has vertical, hanging, or jali line filling. Do not call every line pattern net work.

### Rangoli work

Rangoli work has **kolam/rangoli-style diamond or geometric motifs** with loop/dot borders.

### Normal work

Normal work has smooth/regular embroidery borders and floral/motif filling without cut-work edge, net/drop filling, or rangoli geometry.

### Neck shape and work type are separate

Example: **U-shaped neck + cut work**, **pot neck + net work**, **drop neck + normal work**.

## Visible pages

- **Dashboard** — current engine/model status.
- **TurboThinker GUI** — upload one image, predict tags/type, inspect reasons, save teacher correction.
- **Interactive Searcher** — search teacher memory, corrections, training index, and optional local image folders.
- **Teach / Train** — build seed + region rows from local ZIPs and retrain Student, UltraBrain, and SuperBrain.
- **Brain Parts** — verify every `.brainpart` file is below 25 MB before GitHub upload.
- **Settings** — version/path/model summary.

## Current versions

- App: `v5.4`
- UI: `TurboThinker Interactive Searcher GUI`
- Brain compatibility: `TurboThinker SuperBrain v5.3` 24MB brain parts
- Searcher: `TurboThinker Interactive Searcher v5.4`

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

or:

```bash
python app.py
```

## Important local rules

The app stays local-only:

- No external API.
- No filename/title used as labels.
- Teacher corrections are stronger than auto guesses.
- Search can use filenames/design numbers only to find records, not to train labels.
- Multi-design previews keep `multi_design_preview` as the first/primary mode when detected.

Keep these local only. Do **not** push them to GitHub:

```text
training ZIPs
library/
cache/
uploads/
imgs_training/samples/
imgs_training/crops/
imgs_training/design_json/
large seed banks if they grow too big
```

## GitHub-safe brain parts

The trained SuperBrain is stored as small brain parts:

```text
imgs_training/models/turbothinker_superbrain_v5_3_model.json
imgs_training/models/shards/turbothinker_superbrain_v5_3_model/brain_part_0000.brainpart
imgs_training/models/shards/turbothinker_superbrain_v5_3_model/manifest.json
```

Verify before GitHub push:

```bash
python scripts/verify_model_shards.py
python scripts/check_github_safety.py
```
