"""Synthetic saved packet positives and source-corruption negatives."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path

from measure_saved import AID, FRAME, HERE, ROOT, measure, sha


def save(folder, scope, rows):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'source-scope.json').write_text(json.dumps(scope, sort_keys=True) + '\n')
    (folder / 'actor-frames.jsonl').write_text(''.join(
        json.dumps(row, sort_keys=True) + '\n' for row in rows))


def packet(case, candidate):
    path = HERE / 'drafts' / case / candidate / 'requested-tracks.jsonl'
    requested = [json.loads(line) for line in path.read_text().splitlines()]
    scope = {'assignment_sha256': sha(ROOT / 'inputs' / AID / 'assignment.json'),
             'case_suffix': case, 'coordinate_frame': FRAME,
             'source_kind': 'synthetic_cpu', 'original_camera_decode_verified': False}
    rows = []
    for item in requested:
        i = item['frame']
        s = item['subject_request']
        a = item['approach_request']
        body = [[round(s['x_m'] + dx, 4), round(s['y_m'] + dy, 4)]
                for dx, dy in ((-2.25, -.9), (-2.25, .9), (2.25, -.9), (2.25, .9))]
        rows.append({'frame': i, 'native_frame': 1000 + i,
                     'video_frame': i, 'time_s': item['time_s'],
                     'coordinate_frame': FRAME, 'source_kind': 'synthetic_cpu',
                     'subject': {'center_xy_m': [s['x_m'], s['y_m']],
                                 'body_xy_m': body, 'speed_mps': s['speed_mps'],
                                 'heading_deg': s['heading_deg']},
                     'approach': {'center_xy_m': [a['x_m'], a['y_m']]}})
    return scope, rows


def prove():
    positives = []
    negatives = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for case in ('reference', 'contrast'):
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                scope, rows = packet(case, candidate)
                folder = base / case / candidate
                save(folder, scope, rows)
                receipt = measure(folder)
                if (receipt['frames'] != 480 or receipt['source_kind'] != 'synthetic_cpu' or
                    receipt['legal_immediacy_or_edge_verdict'] is not None or
                    receipt['vehicle_authority_or_lamps_qualified'] or
                    (receipt['edge_before_catchup'] != (case == 'reference'))):
                    raise ValueError('Saved positive failed scope or comparison')
                positives.append({'case': case, 'candidate': candidate,
                                  'edge_frame': receipt['first_edge_target_frame'],
                                  'catchup_frame': receipt['approach_catchup_frame'],
                                  'scope_sha256': receipt['scope_sha256'],
                                  'actor_frames_sha256': receipt['actor_frames_sha256']})
        scope, rows = packet('reference', 'primary')
        mutations = (
            ('law_source', lambda s, r: s.update(assignment_sha256='0' * 64), 'frozen assignment source differs'),
            ('frame_join', lambda s, r: r[4].update(video_frame=5), 'saved frame/time/provenance join differs'),
            ('native_frame', lambda s, r: r[4].update(native_frame=1005), 'Native frame identity differs'),
            ('coordinate_frame', lambda s, r: r[4].update(coordinate_frame='native_xy'), 'saved frame/time/provenance join differs'),
            ('body', lambda s, r: r[4]['subject']['body_xy_m'][0].__setitem__(1, -20), 'saved subject footprint/center differs'),
            ('original_decode', lambda s, r: (s.update(source_kind='original_native'),
                                              [row.update(source_kind='original_native') for row in r]),
             'original cameras need decoded frame proof'),
        )
        for name, mutation, expected in mutations:
            s, r = copy.deepcopy(scope), copy.deepcopy(rows)
            mutation(s, r)
            folder = base / 'negative' / name
            save(folder, s, r)
            try:
                measure(folder)
            except ValueError as exc:
                if str(exc) != expected:
                    raise
                negatives.append({'name': name, 'error': expected})
            else:
                raise ValueError('Negative saved packet accepted: ' + name)
    result = {'format': 'c405647-1b-synthetic-saved-proof-v1',
              'processor_sha256': sha(HERE / 'measure_saved.py'),
              'manifest_sha256': sha(HERE / 'drafts' / 'manifest.json'),
              'positives': positives, 'negatives': negatives,
              'original_native_processed': False, 'legal_verdict': None}
    (HERE / 'synthetic-saved-proof.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
