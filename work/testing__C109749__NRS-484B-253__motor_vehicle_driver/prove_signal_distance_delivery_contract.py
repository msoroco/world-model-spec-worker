"""Validate exact delivery-audit handoffs for staged 25/36 m signal cases."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.delivery_handoff import validate_case


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    auditor = ROOT / 'signal_distance_delivery_audit.py'
    fixture = ('.venv-cpu/bin/python work/' + ROOT.name +
               '/signal_distance_delivery_fixture_proof.py')
    entries = json.loads((ROOT / 'signal-distance-draft-manifest.json').read_text())['cases']
    contracts = []
    for entry in entries:
        case = entry['case_id']
        label = 'below' if entry['signal_target_m'] == 25.0 else 'above'
        positive_root = f'.runtime-work/c109749-signal-distance-{label}-delivery-v1'
        negative_root = f'.runtime-work/c109749-signal-distance-{label}-delivery-negative-v1'
        positive = f'signal-distance-{label}-delivery-proof.log'
        negative = f'signal-distance-{label}-delivery-negative.log'
        spec = {
            'case_id': case, 'sets': ['demo-test', 'full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion',
                       'signal_advance'],
            'script': auditor.name, 'script_sha256': sha(auditor),
            'command': f'{fixture} --case {case} --output-root {positive_root}',
            'test_exit_code': 0, 'test_log': positive,
            'test_log_sha256': sha(ROOT / positive),
            'negative_command': (f'{fixture} --case {case} --output-root {negative_root} '
                                 f'--negative-source-root {positive_root}'),
            'negative_exit_code': 1,
            'negative_expected_error': 'Sealed original source changed: interaction_history.jsonl',
            'negative_log': negative, 'negative_log_sha256': sha(ROOT / negative)}
        validate_case(ROOT, dict(entry, delivery_acceptance=spec),
                      ('demo-test', 'full-test'))
        contracts.append(spec)
    if len(contracts) != 2:
        raise ValueError('Both exact signal cases need delivery acceptance contracts')
    print(json.dumps({'format': 'worker-staged-signal-distance-delivery-contracts',
                      'contracts': contracts,
                      'source_kind': 'synthetic software diagnostics',
                      'native_or_legal_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
