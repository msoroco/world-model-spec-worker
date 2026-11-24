"""Independent six-case original comparison and synthetic CPU mechanics test."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
FEET = (90, 100, 110, 290, 300, 310)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing comparison source: ' + str(path))
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def compare(rows, original):
    plan = read(HERE / 'case-plan.json')
    comparison, = plan['comparisons']
    expected = [f'{HERE.name}__{feet}' for feet in FEET]
    require(comparison['case_ids'] == expected and
            [row['case_id'] for row in rows] == expected,
            'Selected comparison case membership differs')
    reference = None
    measured = {}
    for feet, row in zip(FEET, rows):
        require(row['original_native'] is original and row['passed'] is True,
                'Comparison original provenance or audit failed')
        value = row['measured_signal_distance_ft']
        require(type(value) in (int, float) and abs(value - feet) <= 0.5,
                'Measured comparison distance differs: ' + str(feet))
        measured[feet] = value
        context = row['fixed_context']
        require(isinstance(context, dict) and context.get('area_classification') == 'any_other_area' and
                context.get('weather') == 'clear_noon' and
                context.get('actor') == 'motor_vehicle_driver' and
                context.get('cell_geometry') == 'hill_crest',
                'Fixed comparison context incomplete')
        fixed = (context, row['source_hashes']['road.xodr'])
        if reference is None:
            reference = fixed
        else:
            require(fixed == reference, 'Comparison fixed conditions changed')
    require(all(measured[a] < measured[b] for a, b in zip(FEET, FEET[1:])),
            'Measured comparison order changed')
    return {'format': 'c104393-independent-selected-comparison-audit',
            'comparison_id': comparison['comparison_id'], 'passed': True,
            'case_ids': expected, 'measured_signal_distance_ft': measured,
            'original_native_observed': original, 'legal_verdict': None}


def original(rows_path):
    specification = read(rows_path)
    require(specification.get('format') == 'c104393-original-comparison-input-v1',
            'Original comparison input format differs')
    raw = specification.get('cases', [])
    require(len(raw) == len(FEET), 'Original comparison input incomplete')
    rows = []
    for item in raw:
        attempt = Path(item['attempt']).resolve()
        receipt = read(item['delivery_audit'])
        require(receipt.get('format') == 'worker-delivery-audit' and
                receipt.get('original_native') is True and receipt.get('passed') is True,
                'Independent original delivery audit missing')
        for name, digest in receipt['source_hashes'].items():
            path = (attempt / name).resolve()
            require(attempt in path.parents and path.is_file() and sha(path) == digest,
                    'Original comparison source missing or stale: ' + name)
        rows.append(receipt)
    return compare(rows, True)


def selftest(negative):
    manifest = read(HERE / 'execution-manifest.json')
    entries = {entry['case_id']: entry for entry in manifest['cases']}
    rows = []
    for feet in FEET:
        case = f'{HERE.name}__{feet}'
        entry = entries[case]
        receipt_path = HERE / f'current-active-{feet}-primary-receipt.json'
        receipt = read(receipt_path)
        require(receipt.get('runtime_manifest_sha256') == manifest['runtime_manifest_sha256'] and
                receipt.get('passed') is True and receipt.get('candidate_id') == 'primary',
                'Current selected synthetic receipt missing')
        require(receipt['construction_sha256'] == entry['construction_sha256'],
                'Selected construction changed')
        construction = read(HERE / entry['construction'])
        config = json.loads(next(x['content'] for x in construction['files']
                                 if x['path'] == 'config.json'))
        request = config['native_request']
        rows.append({'case_id': case, 'passed': True, 'original_native': False,
                     'measured_signal_distance_ft': receipt['measurement_examples']['continuous_signal_distance_ft']['value'],
                     'fixed_context': {'area_classification': request['area'],
                                       'weather': request['weather'], 'actor': config['actor'],
                                       'cell_geometry': 'hill_crest',
                                       'other_vehicle_route': 'source-shaped diagnostic route'},
                     'source_hashes': {'road.xodr': request['map_sha256']}})
    if negative:
        rows[2]['fixed_context']['other_vehicle_route'] = 'changed source-shaped route'
    result = compare(rows, False)
    require(not negative, 'Negative comparison mechanics did not reject')
    result['scope'] = 'synthetic source-shaped mechanics only'
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases')
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--negative-selftest', action='store_true')
    args = parser.parse_args()
    if args.selftest or args.negative_selftest:
        print(json.dumps(selftest(args.negative_selftest), indent=2))
    else:
        require(args.cases, 'Original comparison input required')
        print(json.dumps(original(args.cases), indent=2))


if __name__ == '__main__':
    main()
