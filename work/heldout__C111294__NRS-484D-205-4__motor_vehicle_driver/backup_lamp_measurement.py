"""Original-tick forward-motion and backup-lamp state observations.

The Native light-state bit is retained as a command/readback observation.
Illumination requires a separate source-bound decoded-pixel review.
"""

from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path


def _rows(path):
    path = Path(path)
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing original source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure(motion_path, equipment_path, frame_map_path):
    motion = _rows(motion_path)
    frame_map = _rows(frame_map_path)
    equipment_path = Path(equipment_path)
    if not equipment_path.is_file():
        raise ValueError('Missing original equipment inventory')
    equipment = json.loads(equipment_path.read_text())
    if (equipment.get('kind') != 'motor_vehicle'
            or not equipment.get('blueprint_source_sha256')
            or not isinstance(equipment.get('installed_backup_lamps'), list)):
        raise ValueError('Original motor-vehicle equipment inventory incomplete')
    if not motion or len(motion) != len(frame_map):
        raise ValueError('Original motion/frame-map interval incomplete')
    observations = []
    for index, (row, frame) in enumerate(zip(motion, frame_map)):
        if (frame.get('video_frame') != index or frame.get('carla_frame') != row.get('frame')
                or frame.get('time_s') != row.get('time_s')
                or row.get('actor_id') != equipment.get('actor_id')):
            raise ValueError('Original lamp/motion/frame identity differs')
        heading, velocity = row.get('heading_xy'), row.get('velocity_xy_mps')
        if (not isinstance(heading, list) or not isinstance(velocity, list)
                or len(heading) != 2 or len(velocity) != 2):
            raise ValueError('Original heading or velocity missing')
        numbers = [float(v) for v in (*heading, *velocity)]
        if not all(isfinite(v) for v in numbers):
            raise ValueError('Nonfinite original motion')
        norm = hypot(*numbers[:2])
        if norm < 1e-6:
            raise ValueError('Original heading degenerate')
        projected = sum(a * b for a, b in zip(numbers[:2], numbers[2:])) / norm
        lamp_bit = row.get('native_backup_lamp_bit')
        if type(lamp_bit) is not bool:
            raise ValueError('Original Native backup-lamp state missing')
        observations.append({'frame': row['frame'], 'time_s': row['time_s'],
                             'longitudinal_speed_mps': projected,
                             'forward_motion_observed': projected > 0,
                             'native_backup_lamp_bit': lamp_bit})
    return {'format': 'worker-backup-lamp-original-observation',
            'sources': {Path(p).name: sha256(Path(p).read_bytes()).hexdigest()
                        for p in (motion_path, equipment_path, frame_map_path)},
            'installed_backup_lamps': equipment['installed_backup_lamps'],
            'forward_frames': [row['frame'] for row in observations
                               if row['forward_motion_observed']],
            'forward_with_native_lamp_bit_frames': [row['frame'] for row in observations
                                                    if row['forward_motion_observed']
                                                    and row['native_backup_lamp_bit']],
            'observations': observations,
            'actual_lamp_emission': None,
            'pixel_review_required': True,
            'legal_result': None}
