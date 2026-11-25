"""Audit selected straight-source detector and device antecedents on CPU.

This is a source diagnostic. A requested, unserviced detector trace cannot by
itself establish why a physical traffic light did not change.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
LABELS = ('probe-1', 'probe-2', 'yield-wait-for-clearance',
          'yield-enter-during-occupancy')
EXPECTED_FACE = 'circular_red_green_left_arrow'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(rows, geometry):
    if len(rows) != 600 or geometry.get('governing_face') != EXPECTED_FACE:
        raise ValueError('Exact 600-frame steady red/green-arrow source absent')
    if geometry.get('other_device_prohibition_survey') is not False:
        raise ValueError('Other-device survey is not negative')
    signal = geometry.get('signal_actor_id')
    cross = geometry.get('cross_signal_actor_id')
    if type(signal) is not int or type(cross) is not int or signal == cross:
        raise ValueError('Two distinct signal identities required')
    entry = next((i for i, row in enumerate(rows)
                  if row.get('entered_intersection') is True), None)
    if entry is None or entry < 10:
        raise ValueError('Straight entry source absent')
    for i, row in enumerate(rows):
        if (row.get('signal_actor_id'), row.get('cross_signal_actor_id')) != (signal, cross):
            raise ValueError('Signal identity changed in original-shaped rows')
        if row.get('ego_face_observed') != EXPECTED_FACE:
            raise ValueError('Steady red/green-arrow readback differs')
        if row.get('other_device_prohibition_observed') is not False:
            raise ValueError('Other-device observation is not negative')
        if i < entry and (row.get('detector_request_present') is not True or
                          row.get('detector_request_serviced') is not False):
            raise ValueError('Detector request/unserviced readback absent before entry')
    if any(row.get('entered_intersection') is True for row in rows[:entry]):
        raise ValueError('Entry history changed')
    return {'entry_frame': entry, 'detector_unserviced_frames': entry,
            'signal_actor_id': signal, 'cross_signal_actor_id': cross,
            'other_device_survey_negative': True,
            'physical_failure_cause_verified': False,
            'lawful_device_status_verified': False}


def reject(rows, geometry, label, mutate):
    changed_rows = [dict(row) for row in rows]
    changed_geometry = dict(geometry)
    mutate(changed_rows, changed_geometry)
    try:
        inspect(changed_rows, changed_geometry)
    except ValueError as exc:
        return {'mutation': label, 'error': str(exc)}
    raise AssertionError('Changed detector/device source accepted: ' + label)


def main():
    assignment = json.loads((Path('inputs') / ASSIGNMENT / 'assignment.json').read_text())
    law = assignment['law']['text']
    if ('signal failed to detect the presence' not in law or
            'No other device at the place prohibits the turn' not in law):
        raise ValueError('Frozen statutory antecedent text changed')
    cases = []
    for label in LABELS:
        folder = HERE / f'current-v2-{label}-fixture'
        native, geometry_path = folder / 'native_samples.jsonl', folder / 'road_geometry.json'
        rows = [json.loads(line) for line in native.read_text().splitlines()]
        geometry = json.loads(geometry_path.read_text())
        measured = inspect(rows, geometry)
        negatives = [
            reject(rows, geometry, 'serviced_detector',
                   lambda r, g: r[20].update(detector_request_serviced=True)),
            reject(rows, geometry, 'missing_detector_request',
                   lambda r, g: r[20].update(detector_request_present=False)),
            reject(rows, geometry, 'other_device_present',
                   lambda r, g: r[20].update(other_device_prohibition_observed=True)),
            reject(rows, geometry, 'wrong_signal_identity',
                   lambda r, g: r[20].update(signal_actor_id=-1)),
            reject(rows, geometry, 'wrong_governing_face',
                   lambda r, g: g.update(governing_face='circular_green')),
            reject(rows, geometry, 'missing_device_survey',
                   lambda r, g: g.pop('other_device_prohibition_survey')),
        ]
        cases.append({'case_id': ASSIGNMENT + '__' + label.replace('-', '_'),
                      'native_samples_sha256': sha(native),
                      'road_geometry_sha256': sha(geometry_path),
                      'source_diagnostic': measured, 'negative_rejections': negatives})
    receipt = {'format': 'c111071-device-antecedents-cpu-proof-v1',
               'assignment_id': ASSIGNMENT, 'input_sha256': sha(Path('inputs') / ASSIGNMENT / 'assignment.json'),
               'cases': cases, 'passed': True, 'original_native_observed': False,
               'physical_detector_causation_verified': False, 'legal_verdict_claimed': False}
    path = HERE / 'device-antecedents-cpu-proof.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(cases),
                      'negative_rejections': sum(len(c['negative_rejections']) for c in cases),
                      'receipt_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
