# Local TurboThinker training workflow

1. Run the app locally.
2. Open TurboThinker GUI / Training Center.
3. Test an image.
4. If prediction fails, save a teacher correction.
5. Retrain SuperBrain.
6. The model is saved as GitHub-safe shards.

Teacher corrections are stronger than automatic seed guesses. This is the safest way to make the brain wiser without learning bad labels from the first auto-pass.
