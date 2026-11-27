"""Independent CPU checks of the eight source-fact contrasts."""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIFFERENCE = {
    'route_comparison': ('truck_route', 'truck_route.source.json', [True, False]),
    'weight_comparison': ('unladen_weight_lb', 'weight.source.json', [7999, 8000, 8001]),
    'district_comparison': ('district', 'district.source.json', ['other', 'residence']),
    'night_entry_comparison': ('civil_timestamp', 'civil_clock.source.json',
                               ['2026-11-27T18:59:00-08:00', '2026-11-27T19:01:00-08:00']),
    'night_exit_comparison': ('civil_timestamp', 'civil_clock.source.json',
                              ['2026-11-27T05:59:00-08:00', '2026-11-27T06:01:00-08:00']),
    'permit_comparison': ('written_permit_status', 'permit.source.json', ['absent', 'present']),
    'permit_scope_comparison': ('permit_scope_claim', 'permit.source.json', ['matched', 'mismatched']),
    'motion_comparison': ('movement', 'original-route-rows.jsonl', ['stationary', 'moving'])}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def rows(spec):
    return [json.loads(line) for line in spec['files']['original-route-rows.jsonl'].splitlines()]


def inspect(comparison, source_root=HERE):
    suffix = comparison['comparison_id'].split('__')[-1]
    if suffix not in DIFFERENCE:
        raise ValueError('Unexpected comparison: ' + suffix)
    key, source_file, expected_values = DIFFERENCE[suffix]
    names = [case.removeprefix(HERE.name + '__') for case in comparison['case_ids']]
    paths = [source_root / ('diagnostic-' + name + '.json') for name in names]
    specimens = [load(path) for path in paths]
    if len(specimens) != len(expected_values):
        raise ValueError('Comparison omits exact boundary members')
    contexts = [json.loads(spec['files']['authority-context.json']) for spec in specimens]
    measured = [context['facts'].get(key) if key != 'movement' else name for context, name in zip(contexts, names)]
    if measured != expected_values:
        raise ValueError('Deliberate source contrast differs: ' + suffix)
    fixed_keys = {'unladen_weight_lb', 'district', 'truck_route', 'civil_timestamp',
                  'written_permit_status', 'permit_scope_claim'} - {key}
    for other in contexts[1:]:
        if any(other['facts'].get(field) != contexts[0]['facts'].get(field) for field in fixed_keys):
            raise ValueError('Uncontrolled source fact differs: ' + suffix)
    if any(spec['files']['road.xodr'] != specimens[0]['files']['road.xodr'] or
           spec['files']['video_frames.jsonl'] != specimens[0]['files']['video_frames.jsonl']
           for spec in specimens[1:]):
        raise ValueError('Fixed road or synchronized camera source differs')
    observations = [rows(spec) for spec in specimens]
    if any(len(item) != 600 for item in observations):
        raise ValueError('600 original diagnostic route rows required')
    for index in range(600):
        fixed = {k: v for k, v in observations[0][index].items()
                 if k not in ('case_id', 'ego_x_m', 'ego_y_m', 'ego_speed_mps')}
        for item in observations[1:]:
            other = {k: v for k, v in item[index].items()
                     if k not in ('case_id', 'ego_x_m', 'ego_y_m', 'ego_speed_mps')}
            if other != fixed:
                raise ValueError('Original route frame join or vehicle identity differs')
            if key != 'movement' and any(item[index][field] != observations[0][index][field]
                                         for field in ('ego_x_m', 'ego_y_m', 'ego_speed_mps')):
                raise ValueError('Untargeted original vehicle path differs')
    if key == 'movement':
        speeds = [max(abs(row['ego_speed_mps']) for row in item) for item in observations]
        if not (speeds[0] < 0.1 and speeds[1] > 0.5):
            raise ValueError('Measured movement contrast absent')
    else:
        if any(spec['files'][source_file] == specimens[0]['files'][source_file]
               for spec in specimens[1:]):
            raise ValueError('Target authority source did not change')
    return {'format': 'c394566-comparison-cpu-v1',
            'comparison_id': comparison['comparison_id'], 'case_ids': comparison['case_ids'],
            'passed': True, 'fixed_conditions_checked': ['road_source', 'vehicle_identity',
                '600_original_route_rows', 'synchronized_four_camera_map', 'non_target_authority_context'],
            'deliberate_difference_observed': key, 'observed_values': measured,
            'source_sha256': {name: sha(path) for name, path in zip(names, paths)},
            'diagnostic_only': True, 'original_native_observed': False, 'legal_verdict': None}


def build():
    for comparison in load(HERE / 'case-plan.json')['comparisons']:
        proof = inspect(comparison)
        path = HERE / 'comparison-proof' / (comparison['comparison_id'].split('__')[-1] + '.json')
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(proof, indent=2) + '\n')
        print(comparison['comparison_id'].split('__')[-1])


def negative():
    temporary_root = Path(os.environ['TMPDIR']).resolve()
    if '.runtime-work' not in temporary_root.parts:
        raise ValueError('Comparison scratch must stay under .runtime-work')
    with tempfile.TemporaryDirectory(dir=temporary_root, prefix='c394566-comparison-negative-') as temporary:
        root = Path(temporary)
        for comparison in load(HERE / 'case-plan.json')['comparisons']:
            names = [case.removeprefix(HERE.name + '__') for case in comparison['case_ids']]
            for name in names:
                shutil.copyfile(HERE / ('diagnostic-' + name + '.json'),
                                root / ('diagnostic-' + name + '.json'))
            (root / ('diagnostic-' + names[0] + '.json')).unlink()
            try:
                inspect(comparison, root)
            except (ValueError, FileNotFoundError):
                pass
            else:
                raise AssertionError('Comparison accepted missing original diagnostic source')
            for name in names[1:]:
                (root / ('diagnostic-' + name + '.json')).unlink()
            print(comparison['comparison_id'].split('__')[-1] + ': missing source rejected')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--negative', action='store_true')
    options = parser.parse_args()
    if options.build:
        build()
    elif options.negative:
        negative()
    else:
        parser.error('Use --build or --negative')
