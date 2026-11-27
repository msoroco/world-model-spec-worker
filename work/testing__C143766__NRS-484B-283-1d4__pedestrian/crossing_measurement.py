"""Measure original pedestrian entry, signal phase, and destination timing.

These are observations. Whether earlier entry was lawful and whether statutory
exceptions apply require independent source and legal review.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ASSIGNMENT = 'testing__C143766__NRS-484B-283-1d4__pedestrian'
PHASES = ('walk', 'flashing', 'steady')


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if packet.get('assignment_id') != ASSIGNMENT or not packet.get('original_trace_id'):
        raise ValueError('original crossing assignment and trace identity required')
    for field in ('pedestrian_actor_id', 'crossing_id', 'signal_actor_id',
                  'site_source_sha256', 'signal_source_sha256', 'destination_source_sha256'):
        if not packet.get(field):
            raise ValueError('original crossing identity/source missing: ' + field)
    frames = packet.get('frames')
    if not isinstance(frames, list) or len(frames) < 4:
        raise ValueError('original crossing frame history incomplete')
    previous_phase = None
    entry = arrival = steady = None
    for index, frame in enumerate(frames):
        if type(frame.get('frame')) is not int or type(frame.get('time_s')) not in (int, float):
            raise ValueError('original frame/time missing')
        if index and (frame['frame'] != frames[index - 1]['frame'] + 1 or
                      abs(frame['time_s'] - frames[index - 1]['time_s'] - .05) > .005):
            raise ValueError('original 20 Hz frame/time join differs')
        phase = frame.get('signal_phase')
        if phase not in PHASES:
            raise ValueError('original pedestrian signal phase missing')
        if previous_phase is not None and PHASES.index(phase) - PHASES.index(previous_phase) not in (0, 1):
            raise ValueError('original signal transition differs')
        previous_phase = phase
        if type(frame.get('countdown_visible')) is not bool:
            raise ValueError('original countdown readback missing')
        if type(frame.get('in_highway')) is not bool or type(frame.get('at_destination')) is not bool:
            raise ValueError('original pedestrian route readback missing')
        if not frame.get('pedestrian_pose_source_sha256') or not frame.get('signal_readback_source_sha256'):
            raise ValueError('original synchronized source missing')
        if entry is None and frame['in_highway']:
            entry = (frame['frame'], phase)
        if arrival is None and frame['at_destination']:
            arrival = (frame['frame'], phase)
        if steady is None and phase == 'steady':
            steady = frame['frame']
    if (entry is None or arrival is None or steady is None or
            entry[0] >= arrival[0] or PHASES.index(frames[0]['signal_phase']) != 0):
        raise ValueError('original Walk-entry, arrival or steady history incomplete')
    flashing = [f for f in frames if f['signal_phase'] == 'flashing']
    if not flashing or len({f['countdown_visible'] for f in flashing}) != 1:
        raise ValueError('flashing interval or countdown source inconsistent')
    return {'assignment_id': ASSIGNMENT, 'case_id': packet.get('case_id'),
            'source': {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()},
            'original_trace_id': packet['original_trace_id'],
            'first_original_frame': frames[0]['frame'], 'last_original_frame': frames[-1]['frame'],
            'frame_count': len(frames), 'entry_original_frame': entry[0],
            'entry_phase': entry[1], 'arrival_original_frame': arrival[0],
            'arrival_phase': arrival[1], 'steady_original_frame': steady,
            'destination': packet.get('destination'),
            'countdown_during_flashing': flashing[0]['countdown_visible'],
            'prior_entry_lawfulness': 'unresolved', 'exception_applicability': 'unresolved',
            'legal_judgment': None}
