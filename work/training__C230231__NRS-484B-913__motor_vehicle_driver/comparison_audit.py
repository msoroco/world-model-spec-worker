"""Independent fixed-condition and measured hose/consent contrast audit."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def audit(comparison_id, processing_specs, omit_case=None):
    plan = read(HERE / 'case-plan.json')
    comparison = next((x for x in plan['comparisons'] if x['comparison_id'] == comparison_id), None)
    if comparison is None:
        raise ValueError('Unknown comparison')
    paths = dict(item.split('=', 1) for item in processing_specs)
    if set(paths) != set(comparison['case_ids']) or omit_case:
        raise ValueError('Missing comparison case: ' + str(omit_case or sorted(set(comparison['case_ids']) - set(paths))))
    manifest = read(HERE / 'execution-manifest.json')
    observations = []
    for case in comparison['case_ids']:
        selected = next(row for row in manifest['cases'] if row['case_id'] == case)
        saved = read(paths[case])
        if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
                saved.get('case_id') != case or saved.get('candidate_id') != 'primary' or
                saved.get('native_revision', {}).get('construction_sha256') != selected['construction_sha256'] or
                saved.get('timestamp_joins', {}).get('frames') != 600):
            raise ValueError('Selected comparison source differs')
        stage = Path(saved['analysis_directory'])
        config = read(stage / 'config.json')
        report = read(stage / 'analysis-report.json')
        measured = report.get('measurements', {}).get('source_bound_hose_passage', {})
        if measured.get('method') != 'measured':
            raise ValueError('Comparison lacks source-bound hose measurement')
        for name, digest in measured.get('sources', {}).items():
            if digest != sha(stage / name):
                raise ValueError('Comparison source changed: ' + name)
        observations.append((case, config, measured['value'], stage, sha(stage / 'analysis-report.json')))
    configs = [row[1] for row in observations]
    for field in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras',
                  'required_atoms', 'source_packets', 'physical_completion'):
        if any(config[field] != configs[0][field] for config in configs[1:]):
            raise ValueError('Comparison fixed condition changed: ' + field)
    suffixes = [config['case_suffix'] for config in configs]
    counts = [row[2]['driven_hose_overlap_frames'] for row in observations]
    if comparison_id.endswith('witness_comparison'):
        if suffixes != ['witness_1', 'witness_2'] or counts[0] != 0 or counts[1] <= 0:
            raise ValueError('Route-around/across source measurement differs')
        if any(config['consent_record_requested'] for config in configs):
            raise ValueError('Witness comparison command condition changed')
    else:
        if suffixes != ['exception_1_1', 'exception_1_2'] or min(counts) <= 0:
            raise ValueError('Consent comparison passage condition differs')
        if [config['consent_record_requested'] for config in configs] != [False, True]:
            raise ValueError('Consent contrast changed')
    for name in ('road.xodr', 'reference_corner.mkv'):
        if len({sha(row[3] / name) for row in observations}) != 1:
            raise ValueError('Fixed way or pixels changed: ' + name)
    reviews = [(read(row[3] / 'way-review.json'), read(row[3] / 'hose-review.json'),
                read(row[3] / 'command-review.json')) for row in observations]
    for key in ('way_kind', 'road_access_basis', 'hose_on_actual_route'):
        if reviews[0][0].get(key) != reviews[1][0].get(key):
            raise ValueError('Fixed way context changed: ' + key)
    for key in ('department_affiliation', 'fire_use_purpose', 'protection_arrangements', 'unprotected'):
        if reviews[0][1].get(key) != reviews[1][1].get(key):
            raise ValueError('Fixed hose context changed: ' + key)
    if comparison_id.endswith('witness_comparison'):
        if [r[2].get('communication_status') for r in reviews] != ['explicit_none', 'explicit_none']:
            raise ValueError('Fixed command communication changed')
    else:
        if [r[2].get('communication_status') for r in reviews] != ['explicit_none', 'documented_consent']:
            raise ValueError('Command communication contrast changed')
    return {'format': 'c230231-independent-comparison-audit-v1',
            'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
            'fixed_conditions_checked': True, 'differences_checked': True,
            'driven_hose_overlap_frames': counts,
            'analysis_sha256': {row[0]: row[4] for row in observations},
            'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--processing', action='append', required=True)
    parser.add_argument('--omit-case')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = audit(args.comparison, args.processing, args.omit_case)
    if args.output.exists():
        raise ValueError('Retain previous comparison audit result')
    args.output.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'passed': True, 'comparison_id': args.comparison}))


if __name__ == '__main__':
    main()
