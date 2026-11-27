"""Create five case-specific synthetic compatibility recipes from source shapes.

These fixtures are expressly synthetic and never evidence of original physical
motion, consent, pixels, or a legal finding.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
BASE = REPO / 'work/testing__C145696__NRS-486-351-1__motorcycle_or_moped_operator'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n',
                    encoding='utf8')


def main():
    template = json.loads((BASE / 'diagnostic-left_moving.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    base_capture = [json.loads(line) for line in
                    (BASE / 'diagnostic-left_moving-capture-evidence.jsonl').read_text().splitlines()]
    base_native = (BASE / 'diagnostic-left_moving-capture-native-frames.jsonl').read_text()
    original_trace = [json.loads(line) for line in
                      template['files']['trace.jsonl'].splitlines()]
    mapping = [json.loads(line) for line in
               template['files']['video_frames.jsonl'].splitlines()]
    assert len(original_trace) == len(mapping) == len(base_capture) == 900
    for case in plan['cases']:
        suffix = case['case_id'].removeprefix(AID + '__')
        spec = json.loads(json.dumps(template))
        files = spec['files']
        files.pop('lane-split-scene.json')
        files.pop('lane-split-history.jsonl')
        ego_lane = -1 if case['requested_same_lane'] else -2
        other_class = 'motor_vehicle' if case['requested_two_wheeler_count'] == 1 else 'motorcycle'
        consent = 'consented' if case['requested_driver_consent'] else 'not_consented'
        sources = {key: {'path': key + '.json', 'sha256': 'synthetic-' + key}
                   for key in ('ego_classification', 'other_classification',
                               'driver_identity', 'driver_consent',
                               'subsection_3_review')}
        scene = {
            'format': 'synthetic-diagnostic-same-lane-v1',
            'case_id': case['case_id'], 'diagnostic_fixture': True,
            'ego_vehicle_class': 'motorcycle', 'other_vehicle_class': other_class,
            'consent_status': consent, 'subsection_3_status': 'unresolved',
            'ego_classification_source_sha256': sources['ego_classification']['sha256'],
            'other_classification_source_sha256': sources['other_classification']['sha256'],
            'driver_identity_source_sha256': sources['driver_identity']['sha256'],
            'consent_source_sha256': sources['driver_consent']['sha256'],
            'subsection_3_source_sha256': sources['subsection_3_review']['sha256'],
            'sources': sources,
            'survey': {'map_id': 'synthetic-one-way-multilane',
                       'ego_lane_id': ego_lane, 'other_lane_id': -1,
                       'lane_width_m': 4.7,
                       'physical_lane_truth_unverified': True},
            'participant_readback': {
                'ego': {'actor_id': 1}, 'other': {'actor_id': 2},
                **({'third': {'actor_id': 3}} if case['requested_two_wheeler_count'] == 3 else {}),
            },
        }
        files['same-lane-scene.json'] = json.dumps(scene, allow_nan=False) + '\n'
        history = []
        trace = []
        capture = []
        for i, (base, video) in enumerate(zip(original_trace, mapping)):
            t = video['time_s']
            if case['requested_pass']:
                other_s = 5 + i * 0.02
                ego_s = -12 + i * 0.08
            else:
                other_s = ego_s = 5 + i * 0.05
            actors = {
                'ego': {'actor_id': 1, 'lane_id': ego_lane,
                        'station_m': round(ego_s, 4),
                        'lateral_m': -1.3 if case['requested_same_lane'] else 4.7,
                        'half_length_m': 1.0, 'half_width_m': 0.35,
                        'speed_mps': 1.6 if case['requested_pass'] else 1.0},
                'other': {'actor_id': 2, 'lane_id': -1,
                          'station_m': round(other_s, 4), 'lateral_m': 0.0,
                          'half_length_m': 1.0, 'half_width_m': 0.35,
                          'speed_mps': 0.4 if case['requested_pass'] else 1.0},
            }
            if case['requested_two_wheeler_count'] == 3:
                actors['third'] = {'actor_id': 3, 'lane_id': -1,
                                   'station_m': round(other_s, 4),
                                   'lateral_m': 1.3,
                                   'half_length_m': 1.0,
                                   'half_width_m': 0.35,
                                   'speed_mps': 1.0}
            history.append(json.dumps({'frame': video['carla_frame'],
                                       'time_s': t, 'actors': actors},
                                      separators=(',', ':')))
            row = dict(base)
            row['position'] = {'x': round(ego_s, 4),
                               'y': actors['ego']['lateral_m'], 'z': 0.0}
            row['position_m'] = [row['position']['x'], row['position']['y'], 0.0]
            row['speed_mps'] = actors['ego']['speed_mps']
            row['speed_mph'] = row['speed_mps'] / .44704
            trace.append(json.dumps(row, separators=(',', ':'), allow_nan=False))
            observed = json.loads(json.dumps(base_capture[i]))
            old_x, old_y, _ = observed['ego']['position_m']
            new_x, new_y = row['position_m'][:2]
            observed['ego']['position_m'] = row['position_m']
            observed['ego']['speed_mps'] = row['speed_mps']
            observed['ego']['body_vertices_m'] = [
                [round(vertex[0] + new_x - old_x, 4),
                 round(vertex[1] + new_y - old_y, 4), vertex[2]]
                for vertex in observed['ego']['body_vertices_m']]
            capture.append(json.dumps(observed, separators=(',', ':'), allow_nan=False))
        files['same-lane-history.jsonl'] = '\n'.join(history) + '\n'
        files['trace.jsonl'] = '\n'.join(trace) + '\n'
        files['diagnostic-source-note.json'] = json.dumps({
            'source_kind': 'synthetic_diagnostic_fixture',
            'accepted_original_source': False, 'case_id': case['case_id'],
            'physical_truth_claimed': False,
        }) + '\n'
        manifest = json.loads(files['capture/manifest.json'])
        manifest['case_id'] = case['case_id']
        manifest['source_run'] = 'synthetic-diagnostic-same-lane-900-frames'
        manifest['sources']['trace.jsonl'] = hashlib.sha256(
            files['trace.jsonl'].encode()).hexdigest()
        files['capture/manifest.json'] = json.dumps(manifest, allow_nan=False) + '\n'
        diagnostic = ROOT / ('diagnostic-' + suffix + '.json')
        write(diagnostic, spec)
        capture_path = ROOT / ('diagnostic-' + suffix + '-capture-evidence.jsonl')
        capture_path.write_text('\n'.join(capture) + '\n', encoding='utf8')
        native_path = ROOT / ('diagnostic-' + suffix + '-capture-native-frames.jsonl')
        native_path.write_text(base_native, encoding='utf8')
        recipe = ROOT / ('diagnostic-' + suffix + '-recipe.json')
        sources = [
            {'path': 'diagnostic-input.json',
             'source': str(diagnostic.relative_to(REPO)),
             'sha256': sha(diagnostic)},
            {'path': 'capture/evidence.jsonl',
             'source': str(capture_path.relative_to(REPO)),
             'sha256': sha(capture_path)},
            {'path': 'capture/native/frames.jsonl',
             'source': str(native_path.relative_to(REPO)),
             'sha256': sha(native_path)},
        ]
        write(recipe, {'format': 'worker-fixture-recipe',
                       'sources': sources,
                       'generator': {'source': str(diagnostic.relative_to(REPO)),
                                     'sha256': sha(diagnostic)}})
        print(suffix, diagnostic.stat().st_size)


if __name__ == '__main__':
    main()
