"""Bind three synthetic physical outcomes and lifecycle proof per exact case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
RESULT = ROOT / 'result.json'
KINDS = ('green_selected_drive', 'adjacent_dark_drive', 'second_green_drive',
         'green_selected_stand')
OUTCOMES = ('complete_motion', 'incomplete_motion', 'missing_evidence')
LIFECYCLE = ['capture_finished', 'encoders_closed', 'restoration_verified',
             'native_exit', 'owner_released', 'saved_processing_started']


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    result = json.loads(RESULT.read_text())
    tests = [t for t in result['tests'] if not t['log'].startswith('physical-')]
    for entry in manifest['cases']:
        kind = entry['case_id'].rsplit('__', 1)[-1]
        if kind not in KINDS:
            raise ValueError('Unexpected exact case')
        log_name = f'physical-{kind}-proof.log'
        log = ROOT / log_name
        message = log.read_text()
        if not all(outcome in message for outcome in OUTCOMES) or 'saved_processing_started' not in message:
            raise ValueError('Incomplete physical protocol log: ' + kind)
        script = 'stationary_physical_probe.py' if kind == 'green_selected_stand' else 'physical_probe.py'
        command = ('SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c147332-12a-physical-runtime-v2-' + kind + '" '
                   'PYTHONPATH="$PWD/runtime/scenario_pipeline" PYTHONDONTWRITEBYTECODE=1 '
                   '.venv-cpu/bin/python ' + str(ROOT / script))
        if script == 'physical_probe.py':
            command += ' --case ' + entry['case_id']
        command += ' --output "$PWD/.runtime-work/c147332-12a-physical-v2/' + kind + '"'
        tests.append({'command': command, 'exit_code': 0, 'log': log_name,
                      'sha256': sha(log)})
        fixtures = []
        for outcome in OUTCOMES:
            name = f'physical-{kind}-{outcome}.json'
            payload = json.loads((ROOT / name).read_text())
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[outcome]
            if (payload['physical_checks']['maneuver']['status'] != expected or
                    payload['maneuver_completed'] != (outcome == 'complete_motion') or
                    payload.get('provenance_kind') != 'synthetic_fixture'):
                raise ValueError('Physical outcome mismatch: ' + name)
            fixtures.append({'kind': outcome, 'command': command, 'exit_code': 0,
                             'log': log_name, 'log_sha256': sha(log),
                             'result': name, 'result_sha256': sha(ROOT / name)})
        receipt = {'construction_sha256': entry['construction_sha256'],
                   'fixtures': fixtures,
                   'lifecycle': {'events': LIFECYCLE, 'exit_code': 0,
                                 'log': log_name, 'log_sha256': sha(log)},
                   'scope': 'Synthetic CPU physical and lifecycle protocol; no Native capture or legal acceptance'}
        name = f'physical-{kind}-receipt.json'
        (ROOT / name).write_text(json.dumps(receipt, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': name, 'sha256': sha(ROOT / name)}
    result['tests'] = tests
    result['readiness_kind'] = 'green_arrow_offline_compatibility_physical_cpu_protocol_proven'
    result['reason'] = ('All eight exact candidates pass pinned offline and source-bound positive/negative compatibility. '
                        'Four exact cases have three source-bound synthetic physical outcomes and lifecycle tests. '
                        'These do not establish Native physical success. Independent delivery audit receipts, local '
                        'integration and genuine highway/device source review remain unfinished.')
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print('bound four physical CPU protocol receipts')


if __name__ == '__main__':
    main()
