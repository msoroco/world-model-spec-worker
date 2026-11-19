"""Independent original-source CPU delivery audit for the C111294 opposing-left case."""
import argparse
from hashlib import sha256
import json
import sys
from pathlib import Path

ROOT = Path.cwd()
PKG = ROOT / 'work/heldout__C111294__NRS-484B-250-3__motor_vehicle_driver'
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from opposing_left_measurement import measure_opposing_left
from worker_exchange.media import audit as media_audit

CASE = 'heldout__C111294__NRS-484B-250-3__motor_vehicle_driver__opposing_left_travel_subject'
SOURCES = ('opposing_left_context.json', 'opposing_left_participants.jsonl',
           'video_frames.jsonl', 'trace.jsonl')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, report, decoder=media_audit):
    attempt = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    if report.get('case_id') != CASE:
        raise ValueError('Wrong opposing-left delivery case')
    item = report['measurements']['opposing_left_observation']
    if set(item['sources']) != set(SOURCES):
        raise ValueError('Opposing-left analysis source inventory differs')
    for name in SOURCES:
        if not (attempt / name).is_file() or digest(attempt / name) != item['sources'][name]:
            raise ValueError('Opposing-left original source hash differs: ' + name)
    observed = measure_opposing_left(attempt)
    if observed['value'] != item['value'] or any(
            observed['sources'][name] != item['sources'][name] for name in observed['sources']):
        raise ValueError('Opposing-left measurement differs from original sources')
    context = json.loads((attempt / SOURCES[0]).read_text())
    if (context.get('subject_role') != 'opposite' or
            context.get('subject_actor_id') != context.get('opposite_actor_id') or
            observed['value']['observed_opposite_heading_change_rad'] > .25):
        raise ValueError('Opposing-left traveling subject role differs')
    sequences = [[json.loads(line) for line in (attempt / name).read_text().splitlines()
                  if line.strip()] for name in SOURCES[1:]]
    participants, mapping, trace = sequences
    if not participants or len({len(rows) for rows in sequences}) != 1:
        raise ValueError('Opposing-left original frame sources incomplete')
    for index, (body, frame, motion) in enumerate(zip(participants, mapping, trace)):
        identity = frame.get('carla_frame'), frame.get('time_s')
        if (frame.get('video_frame') != index or
                (body.get('frame'), body.get('time_s')) != identity or
                (motion.get('frame'), motion.get('time_s')) != identity):
            raise ValueError('Opposing-left original frame join differs')
    cameras = {}
    for name in CAMERAS:
        source = attempt / (name + '.mkv')
        if not source.is_file():
            raise ValueError('Missing opposing-left source camera: ' + name)
        decoded = decoder(source, len(mapping), mapping_sha256=digest(attempt / 'video_frames.jsonl'))
        if decoded.get('frames') != len(mapping):
            raise ValueError('Opposing-left source camera frame count differs: ' + name)
        cameras[name] = {'source_sha256': digest(source), 'decode': decoded}
    return {'case_id': CASE, 'frame_count': len(mapping),
            'original_sources': {name: digest(attempt / name) for name in SOURCES},
            'camera_decodes': cameras, 'measurement_recomputed': True,
            'physical_visibility_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.report)
    if result['case_id'] != args.case:
        raise ValueError('Wrong opposing-left exact case argument')
    print(json.dumps({'case_id': CASE, 'frame_count': result['frame_count'],
                      'camera_sources': sorted(result['camera_decodes']),
                      'measurement_recomputed': True}))
