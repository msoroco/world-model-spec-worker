"""Independent comparison audit of source-only saved diagnostics."""
from __future__ import annotations

import json

from request import CASES, HERE, sha
from saved import CAMERAS


def audit():
    proof_path = HERE / 'saved-proof.json'
    proof = json.loads(proof_path.read_text())
    if (proof.get('format') != 'c109166-source-only-saved-proof-v1' or
            len(proof.get('positive_cases', [])) != 2 or
            len(proof.get('negative_controls', [])) != 5 or
            proof.get('original_native_observed') is not False or
            proof.get('delivery_ready') is not False):
        raise ValueError('Saved diagnostic proof incomplete')
    pair = {item['case_id'].split('__')[-1]: item
            for item in proof['positive_cases']}
    if set(pair) != set(CASES):
        raise ValueError('Saved comparison cases differ')
    a, b = pair['marked_crosswalk'], pair['unmarked_midblock']
    fixed = ('frame-map.jsonl', 'devices.jsonl', 'map-readback.json')
    if any(a['source_sha256'][name] != b['source_sha256'][name] for name in fixed):
        raise ValueError('Saved comparison context differs')
    if any(a['decoded_pixel_sha256'][name] != b['decoded_pixel_sha256'][name]
           for name in CAMERAS):
        raise ValueError('Decoded camera pixels differ')
    if (a['source_sha256']['pedestrian.jsonl'] == b['source_sha256']['pedestrian.jsonl'] or
            a['roadway_entry_frame'] != b['roadway_entry_frame'] or
            a['roadway_entry_frame'] != 259 or
            a['marked_crosswalk_at_entry_in_diagnostic_source'] is not True or
            b['marked_crosswalk_at_entry_in_diagnostic_source'] is not False):
        raise ValueError('Saved crossing contrast differs')
    expected = {'unbound pedestrian bytes', 'wrong frame join',
                'disabled device at entry', 'intermediate intersection',
                'missing fourth camera'}
    if {item['mutation'] for item in proof['negative_controls']} != expected:
        raise ValueError('Saved rejection controls differ')
    result = {'format': 'c109166-saved-comparison-audit-v1',
              'proof_sha256': sha(proof_path), 'compared_frames': 600,
              'fixed_source_files': list(fixed),
              'equal_decoded_camera_pixels': list(CAMERAS),
              'deliberate_difference': 'pedestrian footprint x at roadway entry',
              'shared_entry_frame': 259, 'positive_cases': 2,
              'material_rejections': len(expected),
              'original_native_observed': False, 'legal_verdict': None,
              'delivery_ready': False}
    (HERE / 'saved-comparison-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(audit()))
