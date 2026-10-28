"""Measure native travel direction and sign inventory; no legal acceptance."""
import argparse
import json
from pathlib import Path
from source_audit import audit_sources


def assess(attempt):
    attempt = Path(attempt)
    cfg = json.loads((attempt / 'config.json').read_text())
    rows = [json.loads(x) for x in (attempt / 'physical_samples.jsonl').read_text().splitlines()]
    sources = audit_sources(attempt, cfg, rows)
    setup = json.loads((attempt / 'native-setup.json').read_text())
    direction = None if len(rows) < 2 else rows[-1]['position_m'][0] - rows[0]['position_m'][0]
    branch = cfg['case']['variable_assignments']['test_branch']['value']
    expected_sign = 1 if branch == 'designated_direction' else -1
    aligned = direction is not None and expected_sign*direction > 30
    right_roadway_footprints = all(all(-7 <= v[1] <= 0 for v in row['body_vertices_m']) for row in rows)
    complete = bool(rows and rows[-1]['route_index'] >= 229)
    sign_present = bool(setup['native_signs'])
    decision = 'inspect_native_sign_pixels_and_governance' if aligned and right_roadway_footprints and complete and sign_present else 'repair_same_frozen_case'
    return {'format': 'one-way-direction-capability-v1', 'case_id': cfg['selected_case_id'],
            'original_source_validation': sources,
            'measured_longitudinal_displacement_m': direction,
            'requested_branch': branch, 'travel_direction_realized': aligned,
            'full_body_on_right_roadway': right_roadway_footprints,
            'route_completed': complete, 'native_landmark_count': len(setup['native_signs']),
            'sign_rendering_verified': False, 'sign_governance_verified': False,
            'decision': decision, 'follow_up_configuration': {'source': 'config.json',
                'case_id': cfg['selected_case_id'], 'preserve_direction_and_map': True,
                'new_attempt_required': decision == 'repair_same_frozen_case'},
            'physical_acceptance': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    Path(a.output).write_text(json.dumps(assess(a.attempt), indent=2) + '\n')
