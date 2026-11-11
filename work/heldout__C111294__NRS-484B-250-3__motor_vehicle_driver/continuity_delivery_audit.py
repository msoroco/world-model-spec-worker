"""Independent original-source audit of the continuing-highway CPU package."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from highway_continuity_source import measure_originals

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('highway_pair_topology.json', 'intersection_participants.jsonl',
           'video_frames.jsonl', 'trace.jsonl', 'control_inventory.json')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, report, decoder=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    case = report.get('case_id')
    if case != 'heldout__C111294__NRS-484B-250-3__motor_vehicle_driver__continuing_highway':
        raise ValueError('Wrong continuing-highway audit case')
    item = report['measurements']['highway_continuity_observation']
    if set(item['sources']) != set(SOURCES):
        raise ValueError('Continuing-highway analysis source inventory differs')
    for name in SOURCES:
        if not (root / name).is_file() or digest(root / name) != item['sources'][name]:
            raise ValueError('Continuing-highway original source hash differs: ' + name)
    observed = measure_originals(root / SOURCES[0], root / SOURCES[1])
    if observed != item['value']:
        raise ValueError('Continuing-highway measurement differs from originals')
    topology = json.loads((root / SOURCES[0]).read_text())
    inventory = json.loads((root / 'control_inventory.json').read_text())
    if (inventory.get('format') != 'worker-ending-road-original-control-inventory'
            or str(inventory.get('junction_id')) != str(topology['junction_id'])
            or any(inventory.get(name) for name in
                   ('ending_landmarks', 'through_landmarks', 'junction_lights'))):
        raise ValueError('Continuing-highway original control inventory differs')
    sequences = [[json.loads(line) for line in (root / name).read_text().splitlines()
                  if line.strip()] for name in
                 ('video_frames.jsonl', 'trace.jsonl', 'intersection_participants.jsonl')]
    if not sequences[0] or len({len(rows) for rows in sequences}) != 1:
        raise ValueError('Continuing-highway original frame sources incomplete')
    for index, (mapping, trace, body) in enumerate(zip(*sequences)):
        identity = mapping.get('carla_frame'), mapping.get('time_s')
        if (mapping.get('video_frame') != index or
                (trace.get('frame'), trace.get('time_s')) != identity or
                (body.get('frame'), body.get('time_s')) != identity):
            raise ValueError('Continuing-highway original frame join differs')
    if decoder is None:
        from worker_exchange.media import audit as decoder
    cameras = {}
    for name in CAMERAS:
        source = root / (name + '.mkv')
        if not source.is_file():
            raise ValueError('Missing continuing-highway source camera: ' + name)
        decoded = decoder(source, len(sequences[0]),
                          mapping_sha256=digest(root / 'video_frames.jsonl'))
        if decoded.get('frames') != len(sequences[0]):
            raise ValueError('Continuing-highway source camera frame count differs: ' + name)
        cameras[name] = {'source_sha256': digest(source), 'decode': decoded}
    return {'case_id': case, 'frame_count': len(sequences[0]),
            'original_sources': {name: digest(root / name) for name in SOURCES},
            'camera_decodes': cameras, 'measurement_recomputed': True,
            'physical_visibility_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.report)
    if result['case_id'] != args.case:
        raise ValueError('Wrong exact continuing-highway case argument')
    print(json.dumps({'case_id': args.case, 'frame_count': result['frame_count'],
                      'camera_sources': sorted(result['camera_decodes']),
                      'measurement_recomputed': True}))


if __name__ == '__main__':
    main()
