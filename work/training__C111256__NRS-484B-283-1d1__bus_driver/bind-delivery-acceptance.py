"""Bind independent positive shape and negative original delivery CPU proofs."""
import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / 'delivery_audit.py'
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(tag, source_tag):
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(HERE.name + '__')
        base = ROOT / '.runtime-work' / f'c111256-{source_tag}-selected' / suffix / 'primary'
        common = [sys.executable, str(SCRIPT), '--case', case,
                  '--candidate', 'primary', '--attempt', str(base / 'selected-attempt'),
                  '--processing', str(base / 'processed/v0001/processing.json')]
        positive = common + ['--output', str(HERE / f'{tag}-{suffix}-delivery-diagnostic.json'),
                             '--diagnostic']
        negative = common + ['--output', str(HERE / f'{tag}-{suffix}-delivery-negative.json')]
        logs = []
        for kind, command in (('positive', positive), ('negative', negative)):
            run = subprocess.run(command, cwd=ROOT, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 timeout=180)
            log = HERE / f'{tag}-{suffix}-delivery-{kind}.log'
            log.write_text(run.stdout)
            logs.append((run.returncode, log))
        (positive_rc, positive_log), (negative_rc, negative_log) = logs
        receipt = json.loads((HERE / f'{tag}-{suffix}-delivery-diagnostic.json').read_text())
        if (positive_rc or receipt.get('passed') is not False or
                receipt.get('source_shaped_unit_test') is not True or
                negative_rc == 0 or
                'Original Native Walk source required' not in negative_log.read_text()):
            raise ValueError('Independent Walk delivery CPU proof did not separate diagnostics')
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'], 'checks': list(CHECKS),
            'script': SCRIPT.name, 'script_sha256': sha(SCRIPT),
            'command': shlex.join(positive), 'test_exit_code': 0,
            'test_log': positive_log.name, 'test_log_sha256': sha(positive_log),
            'negative_command': shlex.join(negative),
            'negative_exit_code': negative_rc,
            'negative_expected_error': 'Original Native Walk source required',
            'negative_log': negative_log.name,
            'negative_log_sha256': sha(negative_log)}
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'selected_cases': len(manifest['cases']),
                      'manifest_sha256': sha(manifest_path),
                      'original_deliveries_accepted': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', default='update023')
    parser.add_argument('--source-tag', default='update022')
    args = parser.parse_args()
    main(args.tag, args.source_tag)
