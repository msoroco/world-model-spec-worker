"""Audit the source-shaped traffic-device prop contrast, without legal inference."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREFIX = HERE.name + '__official_device_'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(state):
    path = HERE / 'compatibility' / f'official_device_{state}-primary.json'
    return json.loads(path.read_text()), path


def check(absent, present):
    for state, receipt in (('absent', absent), ('present', present)):
        if (receipt.get('case_id') != PREFIX + state or
                receipt.get('candidate_id') != 'primary' or
                receipt.get('passed') is not True or
                receipt.get('scope') != 'diagnostic software compatibility only' or
                'negative_case_source' not in receipt.get('checks', [])):
            raise ValueError('Exact device source-shaped receipt missing: ' + state)
        values = receipt['measurement_examples']
        sidewalk = values['sidewalk_stop_occupancy']['value']
        device = values['official_device_context']['value']
        if (sidewalk.get('legal_conclusion') is not None or
                device.get('legal_conclusion') is not None or
                device.get('official_status_verified') is not False or
                device.get('direction_observed') is not None or
                device.get('compliance_independently_verified') is not False):
            raise ValueError('Unreviewed device comparison preclaims authority or law')
        if (device.get('device_presence_requested') is not (state == 'present') or
                device.get('device_candidate_actor_count') != int(state == 'present') or
                device.get('device_candidate_trace_complete') is not True):
            raise ValueError('Device candidate contrast differs from exact case')
        if sidewalk.get('rest_and_overlap_frames', 0) <= 0:
            raise ValueError('Common synthetic sidewalk stop was not measured')
    a = absent['measurement_examples']
    b = present['measurement_examples']
    common = ('vehicle-trace.jsonl', 'video_frames.jsonl', 'camera-frames.jsonl',
              'map-packet.json', 'native-road.xodr')
    for name in common:
        key = 'sidewalk_stop_occupancy'
        if a[key]['sources'].get(name) != b[key]['sources'].get(name):
            raise ValueError('Controlled subject/map/camera source differs: ' + name)
    if (a['official_device_context']['sources']['device-trace.jsonl'] ==
            b['official_device_context']['sources']['device-trace.jsonl']):
        raise ValueError('Device trace did not change between source-shaped cases')
    return {'source_shaped_contrast_checked': True,
            'subject_map_camera_sources_fixed': list(common),
            'candidate_actor_counts': {'absent': 0, 'present': 1},
            'official_status_verified': False, 'legal_conclusion': None,
            'scope': 'synthetic CPU comparison only'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    absent, path_a = read('absent')
    present, path_b = read('present')
    report = check(absent, present)
    if args.self_test:
        variants = []
        bad = json.loads(json.dumps(present))
        bad['measurement_examples']['official_device_context']['value']['official_status_verified'] = True
        variants.append(('false_official_status', bad))
        bad = json.loads(json.dumps(present))
        bad['measurement_examples']['official_device_context']['value']['device_candidate_actor_count'] = 0
        variants.append(('missing_candidate', bad))
        bad = json.loads(json.dumps(present))
        bad['measurement_examples']['sidewalk_stop_occupancy']['sources']['vehicle-trace.jsonl'] = '0' * 64
        variants.append(('changed_subject_source', bad))
        for label, changed in variants:
            try:
                check(absent, changed)
            except ValueError:
                pass
            else:
                raise AssertionError('Corrupted device comparison accepted: ' + label)
        report['negative_mutations_rejected'] = [label for label, _ in variants]
    report['receipt_sha256'] = {'absent': sha(path_a), 'present': sha(path_b)}
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
