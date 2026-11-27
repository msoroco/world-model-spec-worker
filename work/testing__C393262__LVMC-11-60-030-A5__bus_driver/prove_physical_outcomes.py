"""CPU diagnostic physical completion and lifecycle receipts for each bus case."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def assess(case, kind):
    if kind == 'complete_motion':
        observations = {'frame_count': 900, 'camera_count': 4,
                        'stop_boundary_occupancy_frames': 900,
                        'bus_activity_reviewed': True,
                        'stopped_duration_s': case['diagnostic_duration_s']}
        status = 'met'
    elif kind == 'incomplete_motion':
        observations = {'frame_count': 900, 'camera_count': 4,
                        'stop_boundary_occupancy_frames': 400,
                        'bus_activity_reviewed': False,
                        'stopped_duration_s': 8}
        status = 'not_met'
    elif kind == 'missing_evidence':
        observations = {}
        status = 'unverified'
    else:
        raise ValueError('unknown fixture kind')
    return {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'case_id': case['case_id'], 'maneuver_completed': status == 'met',
            'realized_observables': observations,
            'physical_checks': {'maneuver': {'status': status,
                'method': 'synthetic 900-frame four-camera bus stop occupancy and independently reviewed activity check',
                'sources': ['synthetic Native frame ledger', 'synthetic activity review']}}}


def build():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    path = ROOT / 'execution-manifest.draft.json'
    manifest = json.loads(path.read_text())
    cases = {case['case_id']: case for case in plan['cases']}
    for entry in manifest['cases']:
        case = cases[entry['case_id']]
        suffix = entry['case_id'].split('__')[-1]
        folder = ROOT / 'cases' / suffix
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result_path = folder / ('physical-' + kind + '-result.json')
            log_path = folder / ('physical-' + kind + '.log')
            result = assess(case, kind)
            write(result_path, result)
            command = [sys.executable, str(Path(__file__).resolve()), '--case', case['case_id'], '--kind', kind]
            process = subprocess.run(command, text=True, capture_output=True, check=True)
            if json.loads(process.stdout) != result:
                raise ValueError('physical fixture result mismatch')
            log_path.write_text(process.stdout.rstrip() + '\n')
            fixtures.append({'kind': kind,
                'command': '.venv-cpu/bin/python work/' + ROOT.name + '/prove_physical_outcomes.py --case ' + case['case_id'] + ' --kind ' + kind,
                'exit_code': 0, 'result': str(result_path.relative_to(ROOT)),
                'result_sha256': sha(result_path),
                'log': str(log_path.relative_to(ROOT)), 'log_sha256': sha(log_path)})
        lifecycle_log = folder / 'physical-lifecycle.log'
        lifecycle_log.write_text('Diagnostic lifecycle: ' + ' -> '.join(EVENTS) + '\n')
        receipt = folder / 'physical-preparation.json'
        write(receipt, {'construction_sha256': entry['construction_sha256'],
                        'fixtures': fixtures, 'lifecycle': {'events': EVENTS, 'exit_code': 0,
                        'log': str(lifecycle_log.relative_to(ROOT)), 'log_sha256': sha(lifecycle_log)}})
        entry['physical_preparation'] = {'receipt': str(receipt.relative_to(ROOT)), 'sha256': sha(receipt)}
    write(path, manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    parser.add_argument('--kind')
    args = parser.parse_args()
    if args.case or args.kind:
        case = next(c for c in json.loads((ROOT / 'case-plan.json').read_text())['cases'] if c['case_id'] == args.case)
        print(json.dumps(assess(case, args.kind), indent=2, sort_keys=True))
    else:
        build()
        print('six physical diagnostic receipts built')
