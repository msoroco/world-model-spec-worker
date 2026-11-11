"""Independent saved-source audit for the one-way to two-directional left turn."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from turn_geometry import measure

ORIGINALS = ('road_geometry.json', 'body_footprints.json', 'body_footprints.jsonl',
             'video_frames.jsonl', 'trace.jsonl')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(attempt, report, decoder=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    case = report.get('case_id', '')
    if not case.startswith('heldout__C109705__NRS-484B-400-4__motor_vehicle_driver__'):
        raise ValueError('Wrong C109705 turn delivery audit case')
    item = report['measurements']['turn_geometry']
    if set(item['sources']) != set(ORIGINALS):
        raise ValueError('Turn analysis source inventory differs')
    for name in ORIGINALS:
        if not (root / name).is_file() or digest(root / name) != item['sources'][name]:
            raise ValueError('Turn original source hash differs: ' + name)
    observed = measure(root / 'road_geometry.json', root / 'body_footprints.json')
    if observed != item['value']:
        raise ValueError('Turn geometry measurement differs from originals')
    body_json = json.loads((root / 'body_footprints.json').read_text())['frames']
    body_rows = rows(root / 'body_footprints.jsonl')
    frame_rows = rows(root / 'video_frames.jsonl')
    trace_rows = rows(root / 'trace.jsonl')
    if (body_json != body_rows or not body_rows or
            len({len(body_rows), len(frame_rows), len(trace_rows)}) != 1):
        raise ValueError('Turn original body/frame source length differs')
    for index, (body, frame, trace) in enumerate(zip(body_rows, frame_rows, trace_rows)):
        if (frame.get('video_frame') != index or
                (body.get('frame'), body.get('time_s')) !=
                (frame.get('carla_frame'), frame.get('time_s')) or
                (trace.get('frame'), trace.get('time_s')) !=
                (frame.get('carla_frame'), frame.get('time_s')) or
                body.get('subject_id') != observed['subject_id']):
            raise ValueError('Turn original frame/body join differs')
    if decoder is None:
        from worker_exchange.media import audit as decoder
    cameras = {}
    for name in CAMERAS:
        path = root / (name + '.mkv')
        if not path.is_file():
            raise ValueError('Missing named turn camera: ' + name)
        decoded = decoder(path, len(frame_rows),
                          mapping_sha256=digest(root / 'video_frames.jsonl'))
        if decoded.get('frames') != len(frame_rows):
            raise ValueError('Turn camera frame count differs: ' + name)
        cameras[name] = {'sha256': digest(path), 'decode': decoded}
    return {'format': 'worker-turn-source-audit', 'case_id': case,
            'original_source_hashes': {name: digest(root / name) for name in ORIGINALS},
            'frame_count': len(frame_rows), 'camera_decodes': cameras,
            'measurement_recomputed': True, 'physical_visibility_claimed': False,
            'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.report)
    if result['case_id'] != args.case:
        raise ValueError('Wrong exact turn case argument')
    print(json.dumps({'case_id': args.case, 'frame_count': result['frame_count'],
                      'camera_sources': sorted(result['camera_decodes']),
                      'measurement_recomputed': True}))


if __name__ == '__main__':
    main()
