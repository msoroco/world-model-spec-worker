"""Compare exact release-grid controllers on one sealed original-source frame.

This is a counterfactual policy check, not a realized branch trajectory or
physical/legal acceptance. The same 900-frame diagnostic source is retained.
"""
import hashlib
import json
from pathlib import Path

from hazard_sweep_policy import HazardSweepPolicy

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = REPO / '.runtime-work/c109749-far-delivery-v2/attempt'
INDEX = ROOT / 'hazard-release-draft-proof-index.json'
FRAME = 38074


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verified_history_bytes(raw, expected):
    require(hashlib.sha256(raw).hexdigest() == expected,
            'Sealed original source changed: interaction_history.jsonl')
    return [json.loads(line) for line in raw.decode().splitlines() if line]


def sealed_history():
    seal = json.loads((SOURCE / 'capture-seal.json').read_text())
    audit_path = SOURCE / 'far-diagnostic-audit.json'
    audit = json.loads(audit_path.read_text())
    require(seal['format'] == 'worker-sealed-capture' and
            seal['provenance_kind'] == 'synthetic_fixture' and
            seal['diagnostic_fixture'] is True and seal['frames'] == 900,
            'Full diagnostic source seal required')
    for name in ('interaction_history.jsonl', 'intersection_geometry.json',
                 'video_frames.jsonl', 'overview.mkv', 'approach.mkv',
                 'reference_corner.mkv', 'driver_reference.mkv'):
        require(seal['sources'][name] == sha(SOURCE / name),
                'Sealed original source changed: ' + name)
    require(audit['case_id'].endswith('__approaching_far') and
            audit['software_checks_passed'] is True and audit['passed'] is False and
            audit['physical_acceptance_claimed'] is False and audit['frames'] == 900,
            'Far source needs diagnostic delivery audit without physical acceptance')
    raw = (SOURCE / 'interaction_history.jsonl').read_bytes()
    rows = verified_history_bytes(raw, seal['sources']['interaction_history.jsonl'])
    require(audit['original_sources']['history_sha256'] == sha(SOURCE / 'interaction_history.jsonl'),
            'Delivery audit did not bind original history')
    require(len(rows) == 900 and len({row['frame'] for row in rows}) == 900,
            'Full frame-joined history required')
    return seal, audit_path, rows


def source_probe(row):
    geometry = json.loads((SOURCE / 'intersection_geometry.json').read_text())
    direction = geometry['oncoming_direction_xy']
    conflict = geometry['conflict_point_xy_m']
    opponent = row['oncoming']
    remaining = sum((conflict[i] - opponent['position_xy_m'][i]) * direction[i]
                    for i in (0, 1))
    closing = sum(opponent['velocity_xy_mps'][i] * direction[i] for i in (0, 1))
    require(closing > 0.5 and remaining > 0 and
            all(vertex[0] > 5 for vertex in opponent['body_vertices_xy_m']) and
            row['ego_left_indicator'] is True,
            'Fixed source does not show distant closing opponent and left indicator')
    return remaining, closing


def action(release, remaining, closing):
    policy = HazardSweepPolicy(release_ttc_s=release, approach_speed_mps=5.0)
    return policy.step(distance_to_hold_m=0.0, ego_speed_mps=0.0,
                       oncoming_distance_to_conflict_m=remaining,
                       oncoming_closing_speed_mps=closing,
                       oncoming_in_intersection=False, oncoming_cleared=False,
                       turn_complete=False)['state']


def compare():
    seal, audit_path, rows = sealed_history()
    sample = next(row for row in rows if row['frame'] == FRAME)
    remaining, closing = source_probe(sample)
    ttc = remaining / closing
    require(4.9 < ttc < 5.0, 'Source does not sit between 4 s and 5 s settings')
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    selected = next(row for row in manifest['cases'] if row['case_id'].endswith('__approaching_far'))
    require(sha(ROOT / selected['construction']) == selected['construction_sha256'],
            'Selected 4 s construction changed')
    selected_bundle = json.loads((ROOT / selected['construction']).read_text())
    selected_config = json.loads(next(row['content'] for row in selected_bundle['files']
                                      if row['path'] == 'config.json'))
    require(selected_config['controller_release_ttc_s'] == 4.0 and
            action(4.0, remaining, closing) == 'turn',
            'Selected 4 s controller or fixed-frame behavior changed')
    index = json.loads(INDEX.read_text())
    observations = []
    for proof in index['cases']:
        path = ROOT / 'cases' / proof['case_id'].split('__')[-1] / (
            'construction.json' if proof['candidate'] == 'primary'
            else proof['candidate'] + '-construction.json')
        require(sha(path) == proof['construction_sha256'],
                'Release-grid construction differs from exact proof')
        bundle = json.loads(path.read_text())
        config = json.loads(next(row['content'] for row in bundle['files']
                                 if row['path'] == 'config.json'))
        policy_source = next(row['content'] for row in bundle['files']
                             if row['path'] == 'hazard_sweep_policy.py')
        require(policy_source == (ROOT / 'hazard_sweep_policy.py').read_text() and
                config['hazard_legal_threshold'] is None and
                config['selected_case_id'] == proof['case_id'],
                'Exact bundle policy or legal uncertainty changed')
        release = config['controller_release_ttc_s']
        observations.append({'case_id': proof['case_id'], 'candidate': proof['candidate'],
                             'construction_sha256': proof['construction_sha256'],
                             'engineering_release_ttc_s': release,
                             'counterfactual_action': action(release, remaining, closing)})
    primary = {row['case_id'].split('__')[-1]: row['counterfactual_action']
               for row in observations if row['candidate'] == 'primary'}
    require(primary == {'approaching_release_3s': 'turn',
                        'approaching_release_5s': 'yield'},
            'Fixed-source engineering grid lost distinct actions')
    cleared = next((row for row in rows if row['frame'] > FRAME and
                    max(vertex[0] for vertex in row['oncoming']['body_vertices_xy_m']) < -5), None)
    require(cleared is not None, 'Later original complete-body clearance absent')
    geometry = json.loads((SOURCE / 'intersection_geometry.json').read_text())
    clearance_remaining = sum(
        (geometry['conflict_point_xy_m'][i] - cleared['oncoming']['position_xy_m'][i]) *
        geometry['oncoming_direction_xy'][i] for i in (0, 1))
    require(clearance_remaining < 0, 'Complete-body clearance did not pass conflict')
    long_policy = HazardSweepPolicy(release_ttc_s=5.0, approach_speed_mps=5.0)
    first = long_policy.step(distance_to_hold_m=0.0, ego_speed_mps=0.0,
                             oncoming_distance_to_conflict_m=remaining,
                             oncoming_closing_speed_mps=closing,
                             oncoming_in_intersection=False, oncoming_cleared=False,
                             turn_complete=False)
    later = long_policy.step(distance_to_hold_m=0.0, ego_speed_mps=0.0,
                             oncoming_distance_to_conflict_m=clearance_remaining,
                             oncoming_closing_speed_mps=closing,
                             oncoming_in_intersection=False, oncoming_cleared=True,
                             turn_complete=False)
    require(first['state'] == 'yield' and later['state'] == 'turn',
            'Five-second controller did not wait for sourced complete-body clearance')
    # A modified opposing position must fail the same source seal path.
    altered = [dict(row) for row in rows]
    altered[0]['oncoming'] = dict(altered[0]['oncoming'])
    altered[0]['oncoming']['position_xy_m'] = list(altered[0]['oncoming']['position_xy_m'])
    altered[0]['oncoming']['position_xy_m'][0] += 1.0
    changed_bytes = ('\n'.join(json.dumps(row) for row in altered) + '\n').encode()
    try:
        verified_history_bytes(changed_bytes, seal['sources']['interaction_history.jsonl'])
    except ValueError as exc:
        require('Sealed original source changed' in str(exc),
                'Changed-source negative failed for another reason')
    else:
        raise ValueError('Changed opposing source passed seal check')
    comparison = {'format': 'worker-hazard-release-fixed-original-source-probe',
                  'source_kind': 'sealed synthetic diagnostic; counterfactual one-step policy probe',
                  'source_case': selected['case_id'],
                  'selected_construction_sha256': selected['construction_sha256'],
                  'source_history_sha256': sha(SOURCE / 'interaction_history.jsonl'),
                  'source_geometry_sha256': sha(SOURCE / 'intersection_geometry.json'),
                  'source_audit_sha256': sha(audit_path), 'source_frames': len(rows),
                  'sample_frame': FRAME, 'measured_remaining_m': remaining,
                  'measured_closing_mps': closing,
                  'measured_time_to_conflict_s': ttc,
                  'complete_body_clearance_frame': cleared['frame'],
                  'five_second_after_clearance_action': later['state'],
                  'observations': observations, 'changed_source_rejected': True,
                  'native_or_legal_acceptance_claimed': False}
    index['source_policy_comparison'] = comparison
    INDEX.write_text(json.dumps(index, indent=2) + '\n')
    return comparison


if __name__ == '__main__':
    print(json.dumps(compare(), indent=2))
