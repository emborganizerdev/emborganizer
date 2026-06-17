from __future__ import annotations

from typing import Any, Dict


def superbrain_model_card(model: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'name': 'TurboThinker SuperBrain',
        'version': model.get('version'),
        'local_only': True,
        'uses_api': False,
        'filenames_used_as_labels': bool(model.get('source_name_used_for_label')),
        'trained_from_filename': bool(model.get('trained_from_filename')),
        'labels': len(model.get('output_labels') or []),
        'memory_rows': len(model.get('memory_rows') or []),
        'feature_count': model.get('feature_count'),
        'cortex_feature_count': model.get('cortex_feature_count'),
        'teacher_policy': model.get('teacher_policy') or {},
    }
