"""Independent selected 9(a) movement comparison over source-bound CPU diagnostics.

This checks physical signal/other-actor fixture isolation, not arrow direction or lawfulness.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def check(first, second, first_report, second_report):
    reports = [read(first_report), read(second_report)]
    sources = [Path(first), Path(second)]
    expected = ('witness_1', 'witness_2')
    datasets = []
    for suffix, source, report in zip(expected, sources, reports):
        if not report['case_id'].endswith('__' + suffix):
            raise ValueError('Comparison case identity mismatch')
        if report.get('physical_acceptance_claimed') or report.get('legal_acceptance_claimed'):
            raise ValueError('Diagnostic claims acceptance')
        measure = report['measurements']['arrow_movement']
        for name, digest in measure['sources'].items():
            if sha(source / name) != digest:
                raise ValueError('Comparison source hash changed: ' + name)
        value = measure['value']
        if any(value.get(key) is not False for key in ('arrow_pixels_verified',
                'governing_direction_verified', 'other_traffic_lawfulness_verified',
                'native_provenance')):
            raise ValueError('Unreviewed legal or physical fact asserted')
        if value.get('frames') != 600 or value.get('observed_steady_red_frames') != 600 or value.get('observed_green_head_frames') != 600:
            raise ValueError('Incomplete comparison observation window')
        native = rows(source / 'native-raw-actors.jsonl')
        frame_map = rows(source / 'video_frames.jsonl')
        if len(native) != len(frame_map) or len(native) != 600:
            raise ValueError('Incomplete comparison source rows')
        datasets.append((native, frame_map, value))
    (native_a, map_a, value_a), (native_b, map_b, value_b) = datasets
    if map_a != map_b:
        raise ValueError('Comparison camera/frame policy changed')
    for index, (a, b) in enumerate(zip(native_a, native_b)):
        for key in ('frame', 'native_frame', 'time_s', 'red_actor_id', 'arrow_actor_id',
                    'red_state', 'arrow_state', 'other_vehicle'):
            if a.get(key) != b.get(key):
                raise ValueError('Comparison fixed source differs at frame %d: %s' % (index, key))
        if a['ego']['actor_id'] != b['ego']['actor_id']:
            raise ValueError('Comparison ego identity changed')
    if not (value_a['observed_heading_change_deg'] >= 60 and value_b['observed_heading_change_deg'] <= 10):
        raise ValueError('Requested contrast absent in diagnostic heading samples')
    return {'format': 'c111603-selected-cpu-comparison',
        'case_ids': [r['case_id'] for r in reports],
        'comparison_variable': 'arrow_only_movement',
        'fixed_source_frames': 600,
        'measured_heading_change_deg': [value_a['observed_heading_change_deg'], value_b['observed_heading_change_deg']],
        'other_vehicle_id': value_a['other_vehicle_actor_id'],
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
        'unverified': ['directional arrow pixels', 'governing direction',
                       'lawful other traffic', 'pedestrian and yielding status']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for flag in ('first', 'second', 'first-report', 'second-report', 'output'):
        parser.add_argument('--' + flag, required=True)
    args = parser.parse_args()
    result = check(args.first, args.second, args.first_report, args.second_report)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
