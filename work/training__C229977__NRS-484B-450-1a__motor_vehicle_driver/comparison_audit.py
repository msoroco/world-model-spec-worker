"""Audit the selected diagnostic contrast and list unproved law comparisons."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / 'case-plan.json').read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check_pair(first, second, map_same=True):
    if len(first) != 600 or len(second) != 600:
        raise ValueError('Missing fixed original comparison frames')
    for index, (a, b) in enumerate(zip(first, second)):
        for key in ('frame', 'native_frame', 'time_s', 'actor_id',
                    'blueprint_id', 'speed_mps'):
            if a.get(key) != b.get(key):
                raise ValueError('Uncontrolled sidewalk comparison difference: ' + key)
        if a['frame'] != index or b['frame'] != index:
            raise ValueError('Missing fixed comparison frame identity')
    if not any(a.get('sidewalk_overlap_area_m2') != b.get('sidewalk_overlap_area_m2')
               for a, b in zip(first, second)):
        raise ValueError('Sidewalk occupancy contrast absent')
    if not map_same:
        raise ValueError('Uncontrolled sidewalk map difference')


def main():
    pair = PLAN['comparisons'][0]
    roots = [HERE / 'diagnostic-source' / f'probe_{i}' for i in (1, 2)]
    sources = [rows(root / 'vehicle-trace.jsonl') for root in roots]
    maps = [root / 'map-packet.json' for root in roots]
    authorities = [root / 'authority-context.json' for root in roots]
    frames = [root / 'video_frames.jsonl' for root in roots]
    if len(pair['case_ids']) != 2 or pair['deliberate_differences'] != ['sidewalk_vehicle_occupancy']:
        raise ValueError('Selected comparison changed')
    if sha(authorities[0]) != sha(authorities[1]) or sha(frames[0]) != sha(frames[1]):
        raise ValueError('Uncontrolled authority or camera-frame condition')
    check_pair(*sources, map_same=sha(maps[0]) == sha(maps[1]))
    for mutation in ('short', 'speed', 'no_contrast', 'map'):
        left, right = [list(map(dict, source)) for source in sources]
        same = True
        if mutation == 'short':
            right.pop()
        elif mutation == 'speed':
            right[240]['speed_mps'] += 1
        elif mutation == 'no_contrast':
            right = [dict(row) for row in left]
        else:
            same = False
        try:
            check_pair(left, right, map_same=same)
        except ValueError:
            pass
        else:
            raise AssertionError('Uncontrolled comparison accepted: ' + mutation)
    selected = {'comparison_id': pair['comparison_id'],
                'case_ids': pair['case_ids'],
                'changed_request_keys': ['sidewalk_vehicle_occupancy'],
                'fixed_map_sha256': sha(maps[0]),
                'fixed_authority_sha256': sha(authorities[0]),
                'fixed_frame_map_sha256': sha(frames[0]),
                'diagnostic_trace_sha256': [sha(root / 'vehicle-trace.jsonl') for root in roots],
                'source_originality': 'diagnostic_only',
                'original_native_outcome_reviewed': False,
                'negative_mutations_rejected': ['short', 'speed', 'no_contrast', 'map']}
    pending = [{'comparison_id': row['comparison_id'],
                'case_ids': row['case_ids'],
                'status': 'selected_native_and_source_proof_pending',
                'deliberate_differences': row['deliberate_differences']}
               for row in PLAN['comparisons'][1:]]
    target = HERE / 'comparison-audit-specs.json'
    target.write_text(json.dumps({'format': 'c229977-comparison-audit-v1',
                                  'selected_diagnostic_comparison': selected,
                                  'pending_comparisons': pending,
                                  'all_original_reviews_pending': True}, indent=2) + '\n')
    print(json.dumps({'selected_comparison': pair['comparison_id'],
                      'pending_comparisons': len(pending), 'spec_sha256': sha(target)}))


if __name__ == '__main__':
    main()
