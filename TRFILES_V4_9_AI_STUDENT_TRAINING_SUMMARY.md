# TR Files v4.9 AI Student Training Summary

- Source ZIP inspected in this workspace: `trfiles zip.zip`
- Images visually indexed into seed bank: **336**
- Seed-bank errors: **0**
- Filename/title used as label: **No**
- Seed bank written to: `imgs_training/seed_training/seed_visual_bank.json`
- Prototype file written to: `imgs_training/prototypes/seed_tag_prototypes.json`
- v4.9 trained model weights written to: `imgs_training/models/turbothinker_student_v4_9_weights.json`
- Model report written to: `imgs_training/models/last_student_training_report.json`

## v4.9 model training

- Model type: **multi-label logistic student**
- Visual rows trained: **336**
- Feature count: **19**
- Output labels: **29**
- Pseudo seed rows: **336**
- Trusted user correction rows at build time: **0**
- External API used: **No**

This is now a real local model-weight training layer. The initial labels are auto/pseudo labels from visual reading, so user review/corrections are still important. When the user corrects samples and retrains, those corrected examples are weighted stronger than pseudo seed rows.
