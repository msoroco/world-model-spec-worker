"""Independent original-source audit for the C295149 delivery cases.

CPU fixture invocations test rejection and joins. A local delivery run must
independently inspect the retained Native sources and decode every camera.
"""

import argparse
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path


PREFIX = 'heldout__C295149__NRS-484B-250-3__motor_vehicle_driver__'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def module(path, name):
    spec = spec_from_file_location(name, path)
    loaded = module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def audit_attempt(attempt, report, *, decoder=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    case = report.get('case_id', '')
    if not case.startswith(PREFIX):
        raise ValueError('Wrong C295149 delivery case')
    measurements = report.get('measurements', {})
    if not measurements:
        raise ValueError('Missing independent measurements')
    source_hashes = {}
    for name, measurement in measurements.items():
        if not isinstance(measurement, dict):
            continue
        for source, expected in measurement.get('sources', {}).items():
            if source in source_hashes and source_hashes[source] != expected:
                raise ValueError('Original source hash differs across measurements')
            source_hashes[source] = expected
    required = {'video_frames.jsonl', 'trace.jsonl'}
    opposing = case.endswith('__opposing_left_exception')
    required.update(('opposing_left_context.json', 'opposing_left_participants.jsonl') if opposing
                    else ('intersection_topology.json', 'intersection_participants.jsonl'))
    if not required <= set(source_hashes):
        raise ValueError('Original source inventory omits a required join')
    for source, expected in source_hashes.items():
        path = root / source
        if not path.is_file() or digest(path) != expected:
            raise ValueError('Original source hash differs: ' + source)
    mapping = rows(root / 'video_frames.jsonl')
    trace = rows(root / 'trace.jsonl')
    participants = rows(root / ('opposing_left_participants.jsonl' if opposing
                                else 'intersection_participants.jsonl'))
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(participants):
        raise ValueError('Original frame sources incomplete')
    for index, (video, motion, participant) in enumerate(zip(mapping, trace, participants)):
        frame = video.get('carla_frame'), video.get('time_s')
        if (video.get('video_frame') != index or
                (motion.get('frame'), motion.get('time_s')) != frame or
                (participant.get('frame'), participant.get('time_s')) != frame):
            raise ValueError('Original frame/time join differs')
    if opposing:
        observed = module(root / 'opposing_left_measurement.py', 'c295_opposing').measure_opposing_left(root)
        value = observed.get('value', observed)
        if value != measurements['opposing_left_observation']['value']:
            raise ValueError('Opposing-left measurement differs from originals')
    else:
        from ending_road_measurement import measure
        observed = measure(root / 'intersection_topology.json', root / 'intersection_participants.jsonl')
        if observed != measurements['intersection_observation']['value']:
            raise ValueError('Ending-road measurement differs from originals')
    if decoder is None:
        from worker_exchange.media import audit as decoder
    cameras = {}
    for name in CAMERAS:
        source = root / (name + '.mkv')
        if not source.is_file():
            raise ValueError('Missing original camera: ' + name)
        decoded = decoder(source, len(mapping), mapping_sha256=digest(root / 'video_frames.jsonl'))
        if decoded.get('frames') != len(mapping):
            raise ValueError('Original camera frame count differs: ' + name)
        cameras[name] = {'source_sha256': digest(source), 'decode': decoded}
    return {'format': 'worker-ending-road-source-audit', 'case_id': case,
            'source_hashes': source_hashes, 'frame_count': len(mapping),
            'camera_decodes': cameras, 'measurement_recomputed': True,
            'physical_visibility_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    result = audit_attempt(args.attempt, args.report)
    if result['case_id'] != args.case:
        raise ValueError('Wrong exact delivery case argument')
    print(json.dumps({'case_id': args.case, 'frame_count': result['frame_count'],
                      'measurement_recomputed': True,
                      'camera_sources': sorted(result['camera_decodes'])}))


if __name__ == '__main__':
    main()
