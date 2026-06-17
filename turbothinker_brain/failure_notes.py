from __future__ import annotations

from typing import Dict, List


def explain_failure(probabilities: Dict[str, float], confidence_floor: float = 0.42) -> List[str]:
    if not probabilities:
        return ['No label probabilities were produced; train or reload SuperBrain.']
    ranked = sorted(probabilities.items(), key=lambda kv: float(kv[1]), reverse=True)
    notes: List[str] = []
    if ranked[0][1] < confidence_floor:
        notes.append('Low confidence: add teacher corrections for this visual type and retrain.')
    if len(ranked) > 1 and (ranked[0][1] - ranked[1][1]) < 0.08:
        notes.append('Label conflict: top labels are too close; teach more clear examples.')
    return notes or ['Prediction is usable, but still review before trusting sorting.']
