"""Compare exact selected stop controls using retained source rows and receipts."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(negative=False):
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    cases = {entry['case_id']: entry for entry in manifest['cases']}
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    comparison = next(row for row in plan['comparisons'] if row['comparison_id'] == ROOT.name + '__comparison')
    names = ('probe_a', 'probe_b')
    ids = [ROOT.name + '__' + name for name in names]
    if comparison['case_ids'] != ids or not set(ids) <= set(cases):
        raise ValueError('Selected stop comparison identity changed')
    observations = []
    source_rows = []
    for name, case in zip(names, ids):
        here = ROOT / ('selected-stop-' + name)
        receipt_path = here / 'compatibility.json'
        receipt = json.loads(receipt_path.read_text())
        entry = cases[case]
        if (receipt.get('passed') is not True or receipt.get('case_id') != case or
                receipt.get('construction_sha256') != entry['construction_sha256'] or
                receipt.get('runtime_manifest_sha256') != manifest['runtime_manifest_sha256']):
            raise ValueError('Selected stop receipt changed')
        source = here / 'source/native_samples.jsonl'
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if len(rows) != 600:
            raise ValueError('Selected stop source incomplete')
        reported = receipt['measurement_examples']['facility_stop_observation']['value']
        observed = {'case_id': case, 'source_sha256': sha(source),
                    'receipt_sha256': sha(receipt_path),
                    'max_stopped_overlap_m2': reported['max_stopped_overlap_m2'],
                    'stop_duration_s': reported['stop_duration_s']}
        observations.append(observed)
        source_rows.append(rows)
    for a, b in zip(*source_rows):
        if a['native_frame'] != b['native_frame'] or a['time_s'] != b['time_s']:
            raise ValueError('Fixed stop frame/time condition changed')
    first, second = observations
    if negative:
        second['max_stopped_overlap_m2'] = 0
    if (first['max_stopped_overlap_m2'] != 0 or
            abs(second['max_stopped_overlap_m2'] - 9.36) > .01 or
            first['stop_duration_s'] < 2 or second['stop_duration_s'] < 2):
        raise ValueError('Selected stop contrast absent')
    result = {'format': 'c10052-selected-stop-comparison-cpu-v1',
              'comparison_id': comparison['comparison_id'], 'cases': observations,
              'fixed_frame_time_verified': True,
              'deliberate_difference': 'synthetic stopped ego body lateral placement',
              'source_bound_cpu_passed': True, 'diagnostic_only': True,
              'original_native_observed': False, 'legal_verdict_claimed': False}
    if not negative:
        (ROOT / 'selected-stop-pair-comparison.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.negative), indent=2))
