"""Independent saved-source audit for the linked opposing-left cases."""

from hashlib import sha256
import json
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('opposing_left_context.json', 'opposing_left_participants.jsonl',
           'video_frames.jsonl', 'trace.jsonl')
HEADING_SOURCE = 'turn_heading_last_rad.jsonl'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit_attempt(attempt, report, *, decoder=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    case = report.get('case_id', '')
    if not case.startswith('heldout__C293604__NRS-484B-250-3__motor_vehicle_driver__'):
        raise ValueError('Wrong C293604 delivery audit case')
    sources = report['measurements']['opposing_left_observation']['sources']
    sweep = '__turn_release_delay-' in case
    expected = set(SOURCES) | ({HEADING_SOURCE} if sweep else set())
    if set(sources) != expected:
        raise ValueError('Opposing-left audited source inventory differs')
    for name, expected in sources.items():
        if not (root / name).is_file() or digest(root / name) != expected:
            raise ValueError('Opposing-left analysis original source hash differs: ' + name)
    from opposing_left_measurement import measure_opposing_left
    measured = measure_opposing_left(root)
    if measured['value'] != report['measurements']['opposing_left_observation']['value']:
        raise ValueError('Opposing-left measurement differs from originals')
    mapping, trace, participants = (rows(root / name) for name in
                                    ('video_frames.jsonl', 'trace.jsonl',
                                     'opposing_left_participants.jsonl'))
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(participants):
        raise ValueError('Opposing-left audited frame sources incomplete')
    for index, (video, motion, participant) in enumerate(zip(mapping, trace, participants)):
        identity = video.get('carla_frame'), video.get('time_s')
        if (video.get('video_frame') != index or
                (motion.get('frame'), motion.get('time_s')) != identity or
                (participant.get('frame'), participant.get('time_s')) != identity):
            raise ValueError('Opposing-left audited original frame join differs')
    if sweep:
        heading = rows(root / HEADING_SOURCE)
        if len(heading) != len(participants) or any(
                (scalar.get('time_s'), scalar.get('value')) !=
                (participant['time_s'], participant['turning_heading_rad'])
                for scalar, participant in zip(heading, participants)):
            raise ValueError('Opposing-left audited scalar heading join differs')
    if decoder is None:
        from worker_exchange.media import audit as decoder
    cameras = {}
    for name in CAMERAS:
        source = root / (name + '.mkv')
        if not source.is_file():
            raise ValueError('Missing named opposing-left camera: ' + name)
        decoded = decoder(source, len(mapping), mapping_sha256=digest(root / 'video_frames.jsonl'))
        if decoded.get('frames') != len(mapping):
            raise ValueError('Opposing-left source camera frame count differs: ' + name)
        cameras[name] = {'source_sha256': digest(source), 'decode': decoded}
    return {'format': 'worker-opposing-left-source-audit', 'case_id': case,
            'source_hashes': sources, 'frame_count': len(mapping),
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
                      'measurement_recomputed': True,
                      'camera_sources': sorted(result['camera_decodes']),
                      'physical_visibility_claimed': False}))


if __name__ == '__main__':
    main()
