"""Independent saved-source audit for the four C111294 ending-road cases.

The optional decoder injection is for CPU fixture tests. A real audit uses the
pinned full media decoder and never marks physical or legal acceptance.
"""

from hashlib import sha256
import json
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
BASE_SOURCES = ('intersection_topology.json', 'intersection_participants.jsonl',
                'video_frames.jsonl', 'trace.jsonl')
DEVICE_SOURCES = ('official_device_context.json', 'official_device_states.jsonl')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit_attempt(attempt, report, *, decoder=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    case = report.get('case_id', '')
    if not case.startswith('heldout__C111294__NRS-484B-250-3__motor_vehicle_driver__'):
        raise ValueError('Wrong C111294 delivery audit case')
    official = case.endswith(('__official_device_control', '__official_device_green_phase'))
    names = BASE_SOURCES + (DEVICE_SOURCES if official else ('control_inventory.json',))
    for name in (*names, 'config.json'):
        if not (root / name).is_file():
            raise ValueError('Missing audited original ending-road source: ' + name)
    source_hashes = dict(report['measurements']['intersection_observation']['sources'])
    if official:
        device_hashes = report['measurements']['official_device_observation']['sources']
        for name, expected in device_hashes.items():
            if name in source_hashes and source_hashes[name] != expected:
                raise ValueError('Ending-road analysis source hash differs across measurements')
        source_hashes.update(device_hashes)
    if set(source_hashes) != set(names):
        raise ValueError('Ending-road analysis source inventory differs')
    if any(digest(root / name) != expected for name, expected in source_hashes.items()):
        raise ValueError('Ending-road analysis original source hash differs')
    from ending_road_measurement import measure
    observed = measure(root / 'intersection_topology.json', root / 'intersection_participants.jsonl')
    if observed != report['measurements']['intersection_observation']['value']:
        raise ValueError('Ending-road intersection measurement differs from originals')
    if not official:
        inventory = json.loads((root / 'control_inventory.json').read_text())
        if (inventory.get('format') != 'worker-ending-road-original-control-inventory' or
                any(inventory.get(key) for key in ('ending_landmarks', 'through_landmarks', 'junction_lights'))):
            raise ValueError('Original ordinary-route control inventory differs')
    if official:
        from ending_road_official_finalizer import measure_official_device
        device = measure_official_device(root / 'official_device_context.json',
                 root / 'official_device_states.jsonl', root / 'intersection_topology.json',
                 root / 'video_frames.jsonl')
        if device != report['measurements']['official_device_observation']['value']:
            raise ValueError('Official-device measurement differs from originals')
        if case.endswith('__official_device_green_phase'):
            states = [json.loads(line) for line in
                      (root / 'official_device_states.jsonl').read_text().splitlines()
                      if line.strip()]
            if not states or any(row.get('native_state') != 'TrafficLightState.Green'
                                 for row in states):
                raise ValueError('Green-phase original Native readback differs')
    mapping = _rows(root / 'video_frames.jsonl')
    trace = _rows(root / 'trace.jsonl')
    participants = _rows(root / 'intersection_participants.jsonl')
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(participants):
        raise ValueError('Ending-road audited frame sources incomplete')
    for index, (video, motion, participant) in enumerate(zip(mapping, trace, participants)):
        frame = video.get('carla_frame'), video.get('time_s')
        if (video.get('video_frame') != index or
                (motion.get('frame'), motion.get('time_s')) != frame or
                (participant.get('frame'), participant.get('time_s')) != frame):
            raise ValueError('Ending-road audited frame join differs')
    if decoder is None:
        from worker_exchange.media import audit as decoder
    cameras = {}
    for name in CAMERAS:
        source = root / (name + '.mkv')
        if not source.is_file():
            raise ValueError('Missing named ending-road source camera: ' + name)
        decoded = decoder(source, len(mapping), mapping_sha256=digest(root / 'video_frames.jsonl'))
        if decoded.get('frames') != len(mapping):
            raise ValueError('Ending-road source camera frame count differs: ' + name)
        cameras[name] = {'source_sha256': digest(source), 'decode': decoded}
    return {'format': 'worker-ending-road-source-audit', 'case_id': case,
            'source_hashes': source_hashes, 'frame_count': len(mapping),
            'camera_decodes': cameras, 'measurement_recomputed': True,
            'physical_visibility_claimed': False, 'legal_acceptance_claimed': False}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    result = audit_attempt(args.attempt, args.report)
    if result['case_id'] != args.case:
        raise ValueError('Wrong exact delivery audit case argument')
    print(json.dumps({'case_id': args.case, 'frame_count': result['frame_count'],
                      'measurement_recomputed': result['measurement_recomputed'],
                      'camera_sources': sorted(result['camera_decodes']),
                      'physical_visibility_claimed': False}))


if __name__ == '__main__':
    main()
