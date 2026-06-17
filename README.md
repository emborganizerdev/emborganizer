# EMBORGANIZER v5.3.1 — TurboThinker 24MB Brain-Parts Clean GUI

This build matches the latest **v5.3 brain-part SuperBrain** and removes the old/clutter UI from the visible Streamlit app.

## What is visible now

- **Dashboard** — current engine/model status.
- **TurboThinker GUI** — upload one image, predict tags/type, inspect reasons, save teacher correction.
- **Teach / Train** — build seed + region rows from local ZIPs and retrain Student, UltraBrain, and SuperBrain.
- **Brain Parts** — verify every `.brainpart` file is below 25 MB before GitHub upload.
- **Settings** — version/path/model summary.

## Removed from the visible UI

- Google Drive sign-in/import screens.
- Legacy converter pages.
- Old image-generation/marketing panels.
- Duplicate Streamlit native page sidebar.
- Old v4/v5 mismatch banners.

The supporting engine files remain local and modular, but the main app is now focused on training and using TurboThinker.

## Current versions

- App: `v5.3.1`
- UI: `TurboThinker 24MB Brain-Parts Clean GUI`
- Brain: `TurboThinker SuperBrain v5.3`
- Storage: 24MB brain parts under `imgs_training/models/shards/`

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

or:

```bash
python app.py
```

## GitHub-safe brain parts

The trained SuperBrain is stored as small brain parts:

```text
imgs_training/models/turbothinker_superbrain_v5_3_model.json
imgs_training/models/shards/turbothinker_superbrain_v5_3_model/brain_part_0000.brainpart
imgs_training/models/shards/turbothinker_superbrain_v5_3_model/manifest.json
```

Current check:

```text
brain_part_0000.brainpart = 23,063,127 bytes
under 25 MB rule = PASSED
GitHub normal 100 MB file rule = PASSED
```

If the brain grows later, the model store can split it into:

```text
brain_part_0000.brainpart
brain_part_0001.brainpart
brain_part_0002.brainpart
```

Every part should remain under 25 MB.

## Local training rule

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

The app stays local-only:

- No external API.
- No filename/title used as labels.
- Teacher corrections are stronger than auto guesses.
- Multi-design previews keep `multi_design_preview` as the first/primary mode when detected.

## Verify before GitHub push

```bash
python scripts/verify_model_shards.py
python scripts/check_github_safety.py
```

Expected result:

```text
Brain-part size check: OK
GitHub safety: OK
```
