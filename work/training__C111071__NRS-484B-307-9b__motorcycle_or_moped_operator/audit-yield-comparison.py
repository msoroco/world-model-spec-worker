"""Audit a source-shaped straight yield intervention without a legal verdict."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STABLE = (
    'native_frame', 'time_s', 'signal_actor_id', 'cross_signal_actor_id',
    'ego_face_observed', 'cross_phase_observed', 'controller_cycle_count',
    'actor_class_observed', 'detector_request_present',
    'detector_request_serviced', 'other_device_prohibition_observed',
    'pedestrians_in_crosswalk', 'lawful_traffic_conflict',
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(wait_path, enter_path):
    series = [[json.loads(line) for line in path.read_text().splitlines()]
              for path in (wait_path, enter_path)]
    if any(len(rows) != 600 for rows in series):
        raise ValueError('Both original-source requests need 600 frames')
    for index, (wait, enter) in enumerate(zip(*series)):
        for key in STABLE:
            if wait.get(key) != enter.get(key):
                raise ValueError(f'Fixed source differs at frame {index}: {key}')
        occupied = 240 <= index < 320
        if wait['pedestrians_in_crosswalk'] != occupied or wait['lawful_traffic_conflict'] != occupied:
            raise ValueError('Common source occupation window differs')
    entries = [next((i for i, row in enumerate(rows) if row['entered_intersection']), None)
               for rows in series]
    if entries != [340, 260]:
        raise ValueError('Yield timing intervention differs')
    if series[0][entries[0]]['pedestrians_in_crosswalk'] or not series[1][entries[1]]['pedestrians_in_crosswalk']:
        raise ValueError('Entry conflict distinction differs')
    return {'format': 'c111071-yield-source-comparison-v1', 'passed': True,
            'source_sha256': {'wait_for_clearance': sha(wait_path),
                              'enter_during_occupancy': sha(enter_path)},
            'fixed_fields': list(STABLE), 'entry_frames': entries,
            'occupation_window_frames': [240, 320],
            'controlled_variable': 'yield_after_two_cycles',
            'original_native_observed': False,
            'lawful_status_verified': False,
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    paths = [HERE / f'current-v2-yield-{label}-fixture/native_samples.jsonl'
             for label in ('wait-for-clearance', 'enter-during-occupancy')]
    print(json.dumps(audit(*paths), indent=2, sort_keys=True))
