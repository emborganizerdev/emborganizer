# EMBORGANIZER v5.0 — TurboThinker UltraBrain

This build adds the new **TurboThinker UltraBrain** local recognition engine. It keeps the v4.9 AI-student model, then adds a bigger local ensemble brain trained from the uploaded TR image corpus.

## What is new in v5.0

- New file: `turbothinker_ultrabrain.py`
- New saved model: `imgs_training/models/turbothinker_ultrabrain_v5_model.json`
- UltraBrain training report: `imgs_training/models/last_ultrabrain_training_report.json`
- Trained from the visual seed bank created from the user's TR files ZIP.
- Uses **1,940 visual training rows**: 336 full-image visual rows plus image-derived part/zone augmentation rows.
- Trains **19 local label heads** with **89 augmented visual features**.
- Stores **1,600 nearest-neighbor visual memory rows**.
- Adds prototype matching, KNN memory, tag co-occurrence reasoning, and confidence blending.
- Stays local-only: no API, no internet model, no filename/title labels.

## Recognition order

1. Rule/feature reader reads the image visually.
2. v4.9 AI-student weight model gives learned probabilities.
3. v5.0 UltraBrain adds local ensemble recognition:
   - logistic label heads
   - tag prototypes
   - nearest-neighbor visual memory
   - embroidery tag graph / co-occurrence brain
4. User corrections remain strongest and can retrain the local models.

## Run

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Open **TurboThinker Training** to review seed bank, train/refresh the v4.9 student, train/refresh v5.0 UltraBrain, correct tags, and save selector/crop training.

---

# EMBORGANIZER v4.9 Streamlit

## v4.9 focus: TurboThinker AI Student with real local model weights

This build keeps the clean EMBORGANIZER GUI and adds the requested next step: **image-trained local model weights**, not only a visual JSON seed bank.

- App version updated to `v4.9`.
- TurboThinker engine updated to v1.4 / v4.9.
- Adds `turbothinker_student.py`, a dependency-free local AI-student trainer.
- Trains a real multi-label logistic model from image visual features.
- Saves model weights to `imgs_training/models/turbothinker_student_v4_9_weights.json`.
- Uses your uploaded TR files visually: 336 images indexed in the seed bank, then 336 visual rows trained into the v4.9 student model.
- No external API.
- No filename/title learning. Filenames are kept only as source IDs for review.
- User corrections are treated as stronger supervised labels when the model is retrained.
- `multi_design_preview` remains first when the full image is a collage/multi-preview.
- IMGS Search and library cache can blend rule reading + seed memory + v4.9 trained student weights.

## What “trained” means in v4.9

v4.8.2 created a local visual seed bank. v4.9 adds real model-weight training:

```text
TR image ZIP
→ visual feature extraction
→ pseudo-labels / user corrections
→ multi-label logistic training
→ saved local weights JSON
→ prediction blends trained probabilities with TurboThinker reasons
```

The current included model was trained from the available TR corpus:

- Visual rows trained: 336
- Feature count: 19
- Output labels: 29
- Trusted user-correction rows at build time: 0
- Pseudo seed rows at build time: 336

Because the initial labels are auto/pseudo labels, this is a real local model but still needs user correction for best production accuracy.

## Main local training flow

1. Upload image/ZIP in TurboThinker Training Center.
2. TurboThinker reads the full image visually.
3. It saves a visual seed bank from ZIP images.
4. Click **Train / refresh v4.9 AI-student model weights**.
5. Correct wrong tags or labels.
6. Retrain the student model so corrections become stronger supervised rows.
7. Resync cache for faster divided search.

## Key files

- `streamlit_app.py` — clean Streamlit GUI and routing.
- `imgs_training.py` — local image recognition, multi-part hints, correction memory, seed bank, model integration.
- `turbothinker_student.py` — v4.9 local AI-student model training and prediction weights.
- `imgs_training/models/turbothinker_student_v4_9_weights.json` — trained local model weights included in this build.
- `imgs_training/seed_training/seed_visual_bank.json` — visual seed bank from TR files.
- `sync_engine.py` — TurboSync manifest/cache builder.
- `turboemb_engine.py` / `turboemb_cpp_renderer.cpp` — preview rendering helpers.
- `imagesearch.py` — visual fingerprint matching.
- `.streamlit/config.toml` — disables Streamlit native page navigation.

## Run locally

```bash
pip install -r requirements-streamlit.txt
streamlit run streamlit_app.py
```

## Cache/model files created during use

```text
imgs_training/
  samples/
  crops/
  design_json/
  fingerprints/
  seed_training/seed_visual_bank.json
  models/turbothinker_student_v4_9_weights.json
  models/last_student_training_report.json
  prototypes/seed_tag_prototypes.json
  indexes/
    type_folders.json
    fast_search_manifest.json
  imgs_index.json
  corrections.json
```

## Important warning

TurboThinker v4.9 is local and more trainable than v4.8.2, but auto/pseudo labels can still be wrong. Review and correct tags before trusting production sorting.


## v5.1/v5.3 TurboThinker SuperBrain + GUI

This build adds `turbothinker_superbrain.py`, a larger local recognition layer above v5.0 UltraBrain. v5.3 stores the SuperBrain model at `imgs_training/models/turbothinker_superbrain_v5_3_model.json`, which is a small redirect to GitHub-safe shards. The brain keeps multi-cortex features, label capsules, larger KNN memory, teacher-correction priority, and failure diagnosis.

The Training Center now includes a dedicated **TurboThinker GUI** tab for checking model status, testing one image, reading nearest visual memory rows, and seeing why the brain may be failing. Manual corrections are intentionally stronger than auto seed labels, because the program must be taught before it can become reliable.

Honest limitation: v5.3 is a stronger local embroidery recognition engine, not a human-level brain. Correct 20-50 samples per important category and retrain SuperBrain for the best improvement.

---

## v5.3 GitHub-safe SuperBrain rebuild

This build stores the SuperBrain model as under-25MB local brain parts instead of one large monolithic model file. The app loads the shards automatically through `turbothinker_model_store.py`.

Useful commands:

```bash
python scripts/check_github_safety.py .
python scripts/verify_model_shards.py
python scripts/train_superbrain_local.py
```

Keep raw training ZIPs, embroidery libraries, generated previews, and cache folders local. Commit code, docs, catalog files, and the under-25MB brain-part model files only.
