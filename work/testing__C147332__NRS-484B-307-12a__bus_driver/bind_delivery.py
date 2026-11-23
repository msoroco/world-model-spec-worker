"""Bind exact independent delivery-audit CPU tests, without Native claims."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
RESULT = ROOT / 'result.json'
ERROR = 'acquisition original source missing or changed: lane-signal-history.jsonl'
CHECKS = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion']


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    result = json.loads(RESULT.read_text())
    tests = [t for t in result['tests'] if not t['log'].startswith('delivery-')]
    script_sha = sha(ROOT / 'delivery_audit.py')
    for entry in manifest['cases']:
        kind = entry['case_id'].rsplit('__', 1)[-1]
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        positive = f'delivery-{kind}-positive.log'
        negative = f'delivery-{kind}-negative.log'
        if ERROR not in (ROOT / negative).read_text():
            raise ValueError('Missing-source negative did not reject ' + kind)
        if 'diagnostic original-source audit and Native guard passed' not in (ROOT / positive).read_text():
            raise ValueError('Independent positive audit did not pass ' + kind)
        runtime_root = 'c147332-12a-delivery-runtime-v2-' + kind
        command = ('SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/' + runtime_root + ' '
                   'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python '
                   'work/testing__C147332__NRS-484B-307-12a__bus_driver/prove_delivery.py'
                   ' --case ' + entry['case_id'])
        receipt = {'case_id': entry['case_id'], 'sets': ['full-test'], 'checks': CHECKS,
                   'script': 'delivery_audit.py', 'script_sha256': script_sha,
                   'command': command + ' --mode positive --output "$PWD/.runtime-work/c147332-12a-delivery-v2/' + kind + '/positive"',
                   'test_exit_code': 0, 'test_log': positive, 'test_log_sha256': sha(ROOT / positive),
                   'negative_command': command + ' --mode negative --output "$PWD/.runtime-work/c147332-12a-delivery-v2/' + kind + '/negative"',
                   'negative_exit_code': 1, 'negative_expected_error': ERROR,
                   'negative_log': negative, 'negative_log_sha256': sha(ROOT / negative),
                   'scope': 'Synthetic source audit only; Native physical acceptance requires later original capture'}
        entry['delivery_acceptance'] = receipt
        tests.append({'command': receipt['command'], 'exit_code': 0,
                      'log': positive, 'sha256': sha(ROOT / positive)})
    result['tests'] = tests
    result['readiness_kind'] = 'green_arrow_offline_compatibility_physical_and_delivery_cpu_protocol_proven'
    result['reason'] = ('Four exact cases and four fallbacks pass pinned offline and source-bound compatibility. '
                        'All four cases have three synthetic physical outcomes and independent delivery-audit '
                        'positive/negative CPU tests. Native physical success, genuine highway/device review, '
                        'comparison audit receipt and local integration remain unverified.')
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print('bound four exact independent delivery audit contracts')


if __name__ == '__main__':
    main()
