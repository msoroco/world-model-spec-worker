"""Retain synchronized original Native readbacks for backup-lamp analysis."""

import json
from math import isfinite
from pathlib import Path


class LampSourceRecorder:
    def __init__(self, directory, ego, equipment, reverse_light_mask):
        if equipment.get('actor_id') != ego.id or equipment.get('kind') != 'motor_vehicle':
            raise ValueError('Motor-vehicle equipment identity differs')
        if not equipment.get('blueprint_source_sha256') or not isinstance(equipment.get('installed_backup_lamps'), list):
            raise ValueError('Installed backup-lamp source inventory required')
        if type(reverse_light_mask) is not int or reverse_light_mask <= 0:
            raise ValueError('Native reverse-light mask required')
        self.ego = ego
        self.mask = reverse_light_mask
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        (root / 'equipment.json').write_text(json.dumps(equipment, allow_nan=False) + '\n')
        self.path = root / 'motion.jsonl'
        self.output = self.path.open('x')
        self.previous = None

    def append(self, frame, time_s):
        if type(frame) is not int or type(time_s) not in (int, float) or not isfinite(time_s):
            raise ValueError('Original frame/time invalid')
        if self.previous is not None and (frame != self.previous[0] + 1 or time_s <= self.previous[1]):
            raise ValueError('Original frames missing or unordered')
        transform = self.ego.get_transform()
        forward = transform.get_forward_vector()
        velocity = self.ego.get_velocity()
        heading = [float(forward.x), float(forward.y)]
        speed = [float(velocity.x), float(velocity.y)]
        if not all(isfinite(x) for x in heading + speed):
            raise ValueError('Original Native motion nonfinite')
        native_state = int(self.ego.get_light_state())
        row = {'frame': frame, 'time_s': time_s, 'actor_id': self.ego.id,
               'heading_xy': heading, 'velocity_xy_mps': speed,
               'native_light_state_bits': native_state,
               'native_backup_lamp_bit': bool(native_state & self.mask)}
        self.output.write(json.dumps(row, allow_nan=False) + '\n')
        self.output.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        self.output.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
