# EMBORGANIZER v5.3.1 Clean TurboThinker Code Organization

## Main entry

- `streamlit_app.py` — clean v5.3.1 Streamlit GUI focused only on TurboThinker training, prediction, correction, and brain-part verification.
- `app.py` — local launcher for `streamlit run streamlit_app.py`.

## Recognition brain

- `imgs_training.py` — local image analysis, seed-bank training, correction saving, selector crop reader, and brain blending.
- `turbothinker_student.py` — v4.9 trainable local Student model.
- `turbothinker_ultrabrain.py` — v5.0 ensemble recognition brain.
- `turbothinker_superbrain.py` — v5.3 SuperBrain cortex and teacher-correction priority.
- `turbothinker_model_store.py` — JSON brain-part loader/saver with under-25MB shard support.
- `imagesearch.py` — local fingerprint/similarity features.

## Brain storage

```text
imgs_training/models/turbothinker_superbrain_v5_3_model.json
imgs_training/models/shards/turbothinker_superbrain_v5_3_model/manifest.json
imgs_training/models/shards/turbothinker_superbrain_v5_3_model/brain_part_0000.brainpart
```

Each `.brainpart` must stay below 25 MB.

## Visible UI pages

1. Dashboard
2. TurboThinker GUI
3. Teach / Train
4. Brain Parts
5. Settings

## Hidden/removed from navigation

- Google Drive UI
- Sign-in UI
- Legacy converter UI
- Old image-generation UI
- Duplicate Streamlit native page sidebar
- Old v4/v5 mismatch banners

## Local-only rules

- No API.
- No filename/title label learning.
- Teacher corrections are stronger than auto guesses.
- Raw ZIPs and libraries stay local, not GitHub.
