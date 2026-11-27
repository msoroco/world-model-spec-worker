"""Saved-only source-shape finalizer positive and missing-source negative."""

import json
import tempfile
from pathlib import Path

from prove_rail_source import CASE, SCRATCH, fixture
from rail_finalize import run


def main():
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='rail-finalize-') as temp:
        root = Path(temp)
        fixture(root)
        (root / 'config.json').write_text(json.dumps({
            'case_id': CASE, 'selected_case_id': CASE,
            'law_id': 'NRS-484B-450-1i', 'cell_id': 'C229398',
            'actor': 'motor_vehicle_driver', 'target_footprint_gap_m': 12.5,
            'behavior_variant': 'park',
            'recording_description': {'channels': [{'name': 'rail_footprint',
                'method': 'original pose, extent and rail survey'}]}}) + '\n')
        report = run(root, root / 'analysis-report.json')
        assert report['source_complete'] is True
        assert report['measurements']['rail_footprint']['value']['frame_count'] == 600
        assert json.loads((root / 'result.json').read_text())['physical_acceptance_claimed'] is False
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='rail-finalize-negative-') as temp:
        root = Path(temp)
        fixture(root)
        (root / 'config.json').write_text(json.dumps({
            'case_id': CASE, 'selected_case_id': CASE,
            'law_id': 'NRS-484B-450-1i', 'cell_id': 'C229398',
            'actor': 'motor_vehicle_driver', 'target_footprint_gap_m': 12.5,
            'behavior_variant': 'park',
            'recording_description': {'channels': [{'name': 'rail_footprint'}]}}) + '\n')
        (root / 'original-rail-survey.json').unlink()
        try:
            run(root, root / 'analysis-report.json')
        except (ValueError, FileNotFoundError):
            pass
        else:
            raise AssertionError('Missing original physical rail survey accepted')
    print(json.dumps({'synthetic_source_shape': True, 'positive_count': 1,
                      'missing_original_rail_negative_count': 1,
                      'physical_or_legal_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
