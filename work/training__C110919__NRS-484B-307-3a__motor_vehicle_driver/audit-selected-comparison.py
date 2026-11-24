"""Audit the selected right-arrow pair from independent retained source rows."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXED = ('signal_state_observed', 'right_arrow_state_observed',
         'opposing_signal_state_observed', 'right_arrow_actor_id',
         'opposing_signal_actor_id', 'walker_center_xy_m',
         'walker_conflict_occupied', 'cross_traffic_conflict_occupied',
         'turn_prohibition_present')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(witness):
    path = HERE / 'current-v2-source' / witness / 'native_samples.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines()], sha(path)


def audit_pair(a, b):
    if len(a) != 600 or len(b) != 600:
        raise ValueError('Selected comparison needs both 600-frame sources')
    for left, right in zip(a, b):
        if left['native_frame'] != right['native_frame'] or abs(left['time_s'] - right['time_s']) > 1e-8:
            raise ValueError('Comparison frame/time join differs')
        for key in FIXED:
            if left[key] != right[key]:
                raise ValueError('Comparison fixed condition changed: ' + key)
    turns = [next((row['native_frame'] for row in values if row['ego_turn_entered']), None)
             for values in (a, b)]
    if turns != [281, 245]:
        raise ValueError('Selected turn-entry contrast differs')
    if any(row['right_arrow_glyph_physically_verified'] for row in a + b):
        raise ValueError('Synthetic fixture claims physical arrow glyph')
    return turns


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    comparison = plan['comparisons'][0]
    if comparison['case_ids'] != [case['case_id'] for case in manifest['cases']]:
        raise ValueError('Selected comparison members changed')
    a, ah = rows('witness_1')
    b, bh = rows('witness_2')
    fixed_source_hashes = {}
    for name in ('road_geometry.json', 'video_frames.jsonl', 'road.xodr'):
        sources = [HERE / 'current-v2-source' / witness / name
                   for witness in ('witness_1', 'witness_2')]
        if sha(sources[0]) != sha(sources[1]):
            raise ValueError('Selected map or capture condition changed: ' + name)
        fixed_source_hashes[name] = sha(sources[0])
    turns = audit_pair(a, b)
    altered = [dict(row) for row in b]
    altered[150]['cross_traffic_conflict_occupied'] = not altered[150]['cross_traffic_conflict_occupied']
    try:
        audit_pair(a, altered)
    except ValueError as error:
        if 'fixed condition' not in str(error):
            raise
    else:
        raise ValueError('Altered traffic source was accepted')
    result = {'format': 'c110919-3a-selected-comparison-audit', 'passed': True,
              'comparison_id': comparison['comparison_id'],
              'case_ids': comparison['case_ids'], 'source_sha256': [ah, bh],
              'turn_entry_frames': turns, 'fixed_conditions': list(FIXED),
              'fixed_source_sha256': fixed_source_hashes,
              'negative_altered_traffic_rejected': True,
              'diagnostic_only': True, 'original_native_verified': False,
              'accepted_comparison': False, 'legal_verdict': None}
    path = HERE / 'selected-comparison-audit.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
