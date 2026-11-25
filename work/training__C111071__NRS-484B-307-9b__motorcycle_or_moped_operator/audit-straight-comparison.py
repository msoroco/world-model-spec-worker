"""Audit the two synthetic straight-movement source requests, without legal inference."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STABLE_FIELDS = (
    'native_frame', 'time_s', 'signal_actor_id', 'cross_signal_actor_id',
    'ego_face_observed', 'cross_phase_observed', 'controller_cycle_count',
    'actor_class_observed', 'detector_request_present',
    'detector_request_serviced', 'other_device_prohibition_observed',
    'pedestrians_in_crosswalk', 'lawful_traffic_conflict',
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    result = [json.loads(line) for line in path.read_text().splitlines()]
    if len(result) != 600:
        raise ValueError('Comparison needs two complete 600-frame sources')
    return result


def audit(first, second):
    a, b = rows(first), rows(second)
    for index, (left, right) in enumerate(zip(a, b)):
        for field in STABLE_FIELDS:
            if left.get(field) != right.get(field):
                raise ValueError(f'Fixed source differs at frame {index}: {field}')
    entries = []
    for series in (a, b):
        entry = next((i for i, row in enumerate(series)
                      if row.get('entered_intersection') is True), None)
        if entry is None or any(row.get('entered_intersection') is True
                                for row in series[:entry]):
            raise ValueError('Intersection entry source absent or nonmonotone')
        entries.append(entry)
    if entries != [250, 150]:
        raise ValueError('One-cycle versus two-cycle intervention differs')
    return {
        'format': 'c111071-straight-diagnostic-comparison-v1',
        'passed': True,
        'source_sha256': {'probe_1': digest(first), 'probe_2': digest(second)},
        'fixed_fields': list(STABLE_FIELDS),
        'entry_frames': entries,
        'controlled_variable': 'red_arrow_cycle_wait',
        'original_native_observed': False,
        'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False,
    }


if __name__ == '__main__':
    paths = [HERE / f'current-v2-probe-{i}-fixture/native_samples.jsonl'
             for i in (1, 2)]
    print(json.dumps(audit(*paths), indent=2, sort_keys=True))
