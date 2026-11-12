"""Retain original Native actor readback for the proposed passing exception.

This records motion only. Governing passing-law conditions need separate review.
"""

import json
from pathlib import Path


def _actor_state(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    return {
        'actor_id': str(actor.id),
        'blueprint_id': actor.type_id,
        'position_m': [float(transform.location.x), float(transform.location.y),
                       float(transform.location.z)],
        'velocity_mps': [float(velocity.x), float(velocity.y), float(velocity.z)],
    }


class PassingSourceRecorder:
    def __init__(self, output, subject, lead):
        if subject.id == lead.id:
            raise ValueError('Passing source needs two distinct actors')
        self.subject, self.lead = subject, lead
        self.path = Path(output) / 'passing_actors.jsonl'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open('x', encoding='utf-8')
        self.previous = None

    def append(self, frame, time_s):
        if self.previous is not None:
            old_frame, old_time = self.previous
            if frame != old_frame + 1 or abs(time_s - old_time - .05) > 1e-4:
                raise ValueError('Passing source not continuous at 20 Hz')
        row = {'frame': int(frame), 'time_s': float(time_s),
               'subject': _actor_state(self.subject), 'lead': _actor_state(self.lead),
               'passing_law_verified': False}
        self.file.write(json.dumps(row, sort_keys=True) + '\n')
        self.file.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        self.file.close()
