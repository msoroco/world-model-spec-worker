"""Independent saved-source audit for the directed right-half observation.

CPU fixtures verify joins and source integrity. They do not establish a legal
exception, actual camera visibility, or physical completion.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('video_frames.jsonl', 'trace.jsonl',
           'directed_roadway_footprints.jsonl')
PREFIX = 'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__'
SUFFIXES = ('baseline_right_east', 'baseline_right_west', 'unexcepted_left',
            'passing_same_direction', 'right_half_closed', 'three_lane',
            'posted_one_way', 'insufficient_width')


def _read(root, name):
    path = root / name
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Missing original audit source: ' + name)
    return path


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha(path):
    return sha256(path.read_bytes()).hexdigest()


def audit_attempt(attempt, report, *, decoder=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    config = json.loads(_read(root, 'config.json').read_text())
    case_id = config.get('selected_case_id')
    if (case_id not in {PREFIX + suffix for suffix in SUFFIXES} or
            report.get('case_id') != case_id or
            (config.get('law_id'), config.get('cell_id'), config.get('actor')) !=
            ('NRS-484B-200-1', 'C125714', 'motor_vehicle_driver')):
        raise ValueError('Wrong exact audit case identity')
    paths = {name: _read(root, name) for name in SOURCES}
    hashes = {name: _sha(path) for name, path in paths.items()}
    measurement = report.get('measurements', {}).get('right_half_occupancy', {})
    if measurement.get('sources') != hashes:
        raise ValueError('Analysis source hashes differ from retained originals')
    frames, trace, roadway = (_rows(paths[name]) for name in SOURCES)
    if not frames or len(frames) != len(trace) or len(trace) != len(roadway):
        raise ValueError('Original audit frame count differs')
    for index, (mapping, motion, road) in enumerate(zip(frames, trace, roadway)):
        frame, time_s = mapping.get('carla_frame'), mapping.get('time_s')
        if (mapping.get('video_frame') != index or motion.get('frame') != frame or
                road.get('frame') != frame or motion.get('time_s') != time_s or
                road.get('time_s') != time_s):
            raise ValueError('Original audit frame/time join differs')
    # Recompute independently from the source file, rather than trusting the
    # reported measurement or a derived channel retained by the finalizer.
    from right_half_measurement import measure
    if measurement.get('value') != measure(paths['directed_roadway_footprints.jsonl']):
        raise ValueError('Analysis right-half measurement differs from originals')
    if decoder is None:
        from worker_exchange.media import audit as decoder
    camera_decodes = {}
    for camera in CAMERAS:
        name = camera + '.mkv'
        path = _read(root, name)
        decoded = decoder(path, len(frames), mapping_sha256=hashes['video_frames.jsonl'])
        if decoded.get('frames') != len(frames):
            raise ValueError('Original camera frame count differs: ' + name)
        camera_decodes[name] = {'source_sha256': _sha(path), 'decode': decoded}
    return {'format': 'worker-delivery-audit', 'case_id': case_id,
            'source_sha256': hashes, 'frame_count': len(frames),
            'camera_decodes': camera_decodes, 'measurement_recomputed': True,
            'physical_completion_check': False, 'actual_pixels_check': False,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--analysis', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain previous audit receipt')
    output.write_text(json.dumps(audit_attempt(args.attempt, args.analysis),
                                 indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
