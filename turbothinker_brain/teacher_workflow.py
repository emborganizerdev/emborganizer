from __future__ import annotations

from typing import Iterable, List


def recommended_teacher_batches(labels: Iterable[str], samples_per_label: int = 30) -> List[dict]:
    out = []
    for label in labels:
        out.append({
            'label': str(label),
            'recommended_corrected_samples': samples_per_label,
            'why': 'Teacher corrections are weighted higher than automatic seed guesses.',
        })
    return out


def teacher_priority_message() -> str:
    return 'Correct samples first, then retrain. Manual teacher labels override weak auto-seed guesses.'
