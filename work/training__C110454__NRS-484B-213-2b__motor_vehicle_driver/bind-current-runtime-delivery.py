"""Rerun and bind nine diagnostic delivery checks after current manifest binding."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
output_root = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
if not output_root or ROOT / '.runtime-work' not in Path(output_root).resolve().parents:
    raise RuntimeError('Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first')
sys.path.insert(0, str(ROOT / 'runtime/pipeline'))
from scenario_pipeline.worker_exchange.delivery_handoff import CHECKS, validate_case


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if len(manifest['cases']) != 9:
        raise ValueError('Nine selected cases required')
    script = HERE / 'prove-current-runtime-delivery-case.py'
    rows = []
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        folder = HERE / 'current-runtime-selected-delivery' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        commands = {}
        for negative in (False, True):
            kind = 'negative' if negative else 'positive'
            command = [sys.executable, str(script), '--case', case]
            if negative:
                command.append('--negative')
            run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            log = folder / (kind + '.log')
            log.write_text(run.stdout + run.stderr)
            commands[kind] = (command, run.returncode, log)
        positive, negative = commands['positive'], commands['negative']
        proof = json.loads(positive[2].read_text()) if positive[1] == 0 else {}
        if (positive[1] != 0 or negative[1] == 0 or
                proof.get('case_id') != case or
                proof.get('delivery_accepted') is not False or
                'Delivery construction differs from selected manifest' not in negative[2].read_text()):
            raise ValueError('Current delivery check failed: ' + suffix)
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'], 'checks': sorted(CHECKS),
            'script': script.name, 'script_sha256': sha(script),
            'command': ' '.join(positive[0]), 'test_exit_code': 0,
            'test_log': str(positive[2].relative_to(HERE)),
            'test_log_sha256': sha(positive[2]),
            'negative_command': ' '.join(negative[0]),
            'negative_exit_code': negative[1],
            'negative_expected_error': 'Delivery construction differs from selected manifest',
            'negative_log': str(negative[2].relative_to(HERE)),
            'negative_log_sha256': sha(negative[2]),
            'scope': 'Diagnostic CPU source chain only; original Native and pixel acceptance unverified'}
        validate_case(HERE, entry, ['full-train'])
        rows.append({'case_id': case, 'positive_log_sha256': sha(positive[2]),
                     'negative_log_sha256': sha(negative[2])})
        print(suffix, 'diagnostic delivery passed', flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    output = HERE / 'current-runtime-selected-delivery-proof.json'
    output.write_text(json.dumps({'format': 'c110454-current-delivery-cpu-v1',
        'manifest_sha256': sha(manifest_path), 'selected_cases': 9,
        'positive_diagnostic_audits': 9, 'negative_construction_rejections': 9,
        'rows': rows, 'original_native_or_delivery_acceptance_claimed': False}, indent=2) + '\n')


if __name__ == '__main__':
    main()
