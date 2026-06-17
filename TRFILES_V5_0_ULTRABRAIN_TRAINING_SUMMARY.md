# TRFILES v5.0 UltraBrain Training Summary

Build: **EMBORGANIZER v5.0 TurboThinker UltraBrain**

User request: add more brain / ultra recognition engine and make the program behave more like a local GPT-style student for embroidery images.

## What was trained

The new v5.0 model was trained from the visual seed bank created from the uploaded TR files ZIP. The source image names were kept only as review IDs and were **not** used as labels.

Training result included in this package:

- Full visual seed images: **336**
- Total UltraBrain training rows: **1,940**
- Augmented feature count: **89**
- Trained label heads: **19**
- Output labels tracked: **34**
- Nearest-neighbor visual memory rows: **1,600**
- Model file: `imgs_training/models/turbothinker_ultrabrain_v5_model.json`
- Report file: `imgs_training/models/last_ultrabrain_training_report.json`

## UltraBrain engine layers

1. Rule/feature reader
2. v4.9 local AI-student weights
3. v5.0 UltraBrain ensemble
   - logistic label heads
   - tag prototypes
   - nearest-neighbor visual memory
   - tag co-occurrence graph
   - multi-design first-tag lock
4. User correction memory

## Honest note

This is now beyond simple JSON seed-bank training. It contains a real saved local model with trained weights and visual memory. It is still not a giant GPT/vision foundation model; it is a local embroidery-recognition brain designed to improve through user corrections and retraining.
