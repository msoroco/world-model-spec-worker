"""Independent saved-source comparison for the two C228133 draft cases.

This checks the controlled CPU contrast and source bindings. It does not decide
whether a Native signal is official or whether a pedestrian violated the law.
"""

import argparse
import hashlib
import json
from pathlib import Path


BASE = 'training__C228133__NRS-484B-307-9c__pedestrian'
FIXED_SOURCES = ('road-boundary.json', 'native-signal-frames.jsonl',
                 'native-pedestrian-device-frames.jsonl', 'video_frames.jsonl',
                 'governing-device-authority.json', 'highway-authority.json')
PEDESTRIAN_SOURCE = 'native-pedestrian-frames.jsonl'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def side(folder, suffix):
    folder = Path(folder)
    case_id = BASE + '__' + suffix
    config = read(folder / 'config.json')
    construction = read(folder / 'construction.json')
    result = read(folder / 'result.json')
    measurement = read(folder / 'reviewed-source/measurement.json')
    analysis = read(folder / 'analysis-report.json')
    if any(item.get('case_id') != case_id for item in
           (config, construction, result, analysis)):
        raise ValueError('Comparison case identity differs: ' + suffix)
    if config.get('case_suffix') != suffix or config.get('duration_s') != 30 or \
            config.get('rate_hz') != 20:
        raise ValueError('Comparison capture contract differs: ' + suffix)
    if config.get('pedestrian_enters_highway_requested') is not (suffix == 'contrast'):
        raise ValueError('Comparison requested variable differs: ' + suffix)
    if result.get('recording_description') != construction.get('recording_description'):
        raise ValueError('Comparison recording description differs: ' + suffix)
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Comparison result overclaims acceptance: ' + suffix)
    if result.get('provenance_kind') != 'synthetic_local_diagnostic' or \
            measurement.get('diagnostic_fixture') is not True:
        raise ValueError('Comparison requires labeled synthetic diagnostic: ' + suffix)
    measured = measurement.get('measurement', {})
    if measured.get('frame_count') != 600 or measured.get('rate_hz') != 20:
        raise ValueError('Comparison interval incomplete: ' + suffix)
    if result.get('measured_values', {}).get('potential_9c_entry_frames') != \
            measured.get('potential_9c_entry_frames'):
        raise ValueError('Comparison result/measurement differs: ' + suffix)
    if result['measured_values'].get('pedestrian_enters_highway') is not \
            bool(measured.get('entry_events')):
        raise ValueError('Comparison entry result differs: ' + suffix)
    bound = dict(measurement.get('original_source_sha256', {}))
    review = read(folder / 'independent-review.json')
    for name in ('governing-device-authority.json', 'highway-authority.json'):
        bound[name] = review.get('source_sha256', {}).get(name)
    for name in (*FIXED_SOURCES, PEDESTRIAN_SOURCE, 'independent-review.json'):
        if bound.get(name) != digest(folder / name):
            raise ValueError('Comparison source hash differs: ' + suffix + '/' + name)
    pedestrian = rows(folder / PEDESTRIAN_SOURCE)
    if len(pedestrian) != 600:
        raise ValueError('Comparison pedestrian source incomplete: ' + suffix)
    return config, construction, result, measured, bound, pedestrian


def audit(reference, contrast):
    ref = side(reference, 'reference')
    alt = side(contrast, 'contrast')
    rc, ac = ref[0], alt[0]
    fixed_config = ('assignment_id', 'law_id', 'cell_id', 'actor', 'duration_s',
                    'rate_hz', 'required_atoms', 'cameras', 'recording_description')
    for key in fixed_config:
        if rc.get(key) != ac.get(key):
            raise ValueError('Comparison fixed configuration differs: ' + key)
    for name in FIXED_SOURCES:
        if ref[4][name] != alt[4][name]:
            raise ValueError('Comparison fixed source differs: ' + name)
    a, b = ref[5], alt[5]
    changed = []
    for index, (left, right) in enumerate(zip(a, b)):
        for key in ('frame', 'native_frame', 'time_s', 'actor_id', 'source_kind'):
            if left.get(key) != right.get(key):
                raise ValueError('Comparison pedestrian identity differs: ' + key)
        if left.get('footprint_roadward_y_m') != right.get('footprint_roadward_y_m'):
            changed.append(index)
    if not changed:
        raise ValueError('Comparison has no pedestrian-footprint contrast')
    if ref[2]['measured_values']['pedestrian_enters_highway'] is not False or \
            alt[2]['measured_values']['pedestrian_enters_highway'] is not True:
        raise ValueError('Comparison observed entry contrast absent')
    if ref[3]['potential_9c_entry_frames'] or \
            not alt[3]['potential_9c_entry_frames']:
        raise ValueError('Comparison source-grounded entry contrast absent')
    return {'format': 'c228133-independent-comparison-audit-v1',
            'passed': True, 'comparison_id': BASE + '__comparison_main',
            'case_ids': [BASE + '__reference', BASE + '__contrast'],
            'fixed_source_sha256': {name: ref[4][name] for name in FIXED_SOURCES},
            'pedestrian_source_sha256': {'reference': ref[4][PEDESTRIAN_SOURCE],
                                         'contrast': alt[4][PEDESTRIAN_SOURCE]},
            'changed_footprint_frames': len(changed),
            'reference_entry_frames': ref[3]['potential_9c_entry_frames'],
            'contrast_entry_frames': alt[3]['potential_9c_entry_frames'],
            'synthetic_diagnostic': True, 'original_native_observed': False,
            'physical_acceptance_claimed': False, 'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--contrast', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.reference, args.contrast)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))
