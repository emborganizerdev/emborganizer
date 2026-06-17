# v5.0 UltraBrain code organization

Important new module:

- `turbothinker_ultrabrain.py` — local ensemble recognition brain. It trains/saves real local weights and memory using visual features only. It contains:
  - feature augmentation
  - one-vs-rest logistic label heads
  - per-tag prototypes
  - nearest-neighbor visual memory
  - tag co-occurrence graph
  - confidence calibration

New model files:

- `imgs_training/models/turbothinker_ultrabrain_v5_model.json`
- `imgs_training/models/last_ultrabrain_training_report.json`

`imgs_training.py` now exposes:

- `train_turbothinker_ultrabrain_model()`
- `load_turbothinker_ultrabrain_summary()`
- `apply_ultrabrain_memory()`
- optional region-bank helpers for future ZIP crop training

`streamlit_app.py` now shows v5.0 UltraBrain status and a training button inside the TurboThinker Training Center.

The main GUI stays clean; the recognition logic is kept in engine files.

---

# IMGS / TurboThinker v4.9 Code Organization

v4.9 keeps the app modular and adds a separate local AI-student model file so the main GUI does not become messy.

## Main rule

Do not put heavy recognition, sync, import, preview rendering, or model training directly inside `streamlit_app.py`.

## Current files

```text
streamlit_app.py          UI only: navigation, buttons, progress, display
imgs_training.py          visual reader, multi-preview logic, corrections, seed bank, model blending
turbothinker_student.py   v4.9 local trained model weights: train + load + predict
sync_engine.py            cache manifests, virtual folders, dedupe/index sync
imagesearch.py            visual fingerprint matching
turboemb_engine.py        preview rendering and 4K image generation helpers
turbo_import_engine.py    folder/ZIP/Drive scanning helpers
```

## v4.9 training flow

```text
TR image ZIP
→ imgs_training.py extracts visual features
→ seed_visual_bank.json stores visual rows, never filename labels
→ turbothinker_student.py trains multi-label logistic weights
→ turbothinker_student_v4_9_weights.json is saved locally
→ imgs_training.py blends student probabilities into prediction/tags
→ user corrections are weighted stronger in next retrain
```

## Why the student model is separate

- `streamlit_app.py` stays clean.
- `imgs_training.py` stays focused on image reasoning and training records.
- `turbothinker_student.py` owns trainable model weights and prediction math.
- The model is dependency-free Python, so the app still runs locally without API.

## v4.9 model files

```text
imgs_training/models/
  turbothinker_student_v4_9_weights.json
  last_student_training_report.json
```

## Experimental warning line

The UI must keep this warning visible:

```text
IMGS BetaV1 / TurboThinker is local and experimental. Auto tags may not be accurate yet; please review, correct, and resync before trusting sorted library folders.
```

## Important behavior rules

- Do not use filename/title as a label.
- For collage/full preview images, keep `multi_design_preview` first.
- Read the full image first; use selector crop as review/training support.
- Use user corrections as stronger supervised labels.
- Search should classify type first, then search smaller cache groups.


## v5.1 TurboThinker SuperBrain GitHub-Safe + GUI

This build adds `turbothinker_superbrain.py`, a larger local recognition layer above v5.0 UltraBrain. It trains a SuperBrain model at `imgs_training/models/turbothinker_superbrain_v5_1_model.json` with multi-cortex features, label capsules, larger KNN memory, teacher-correction priority, and failure diagnosis.

The Training Center now includes a dedicated **TurboThinker GUI** tab for checking model status, testing one image, reading nearest visual memory rows, and seeing why the brain may be failing. Manual corrections are intentionally stronger than auto seed labels, because the program must be taught before it can become reliable.

Honest limitation: v5.1 is a stronger local embroidery recognition engine, not a human-level brain. Correct 20-50 samples per important category and retrain SuperBrain for the best improvement.
