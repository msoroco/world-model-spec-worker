"""Bind three exact unselected 300 ft CPU delivery audit contracts."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.delivery_handoff import validate_case

SUFFIXES = ('below_86', 'at', 'above_97')
LABELS = ('86', 'at', '97')
TARGETS = (86.0, 91.44, 97.0)
PREFIX = ROOT.name + '__signal_advance_300_'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    script = ROOT / 'signal_300_delivery_audit.py'
    fixture = '.venv-cpu/bin/python work/' + ROOT.name + '/signal_300_delivery_fixture_proof.py'
    manifests = (ROOT / 'signal-300-sides-draft-manifest.json',
                 ROOT / 'signal-300-at-draft-manifest.json')
    entries = {e['case_id']: e for path in manifests for e in json.loads(path.read_text())['cases']}
    contracts = []
    for suffix, label, target in zip(SUFFIXES, LABELS, TARGETS):
        case = PREFIX + suffix
        entry = entries[case]
        manifest = manifests[1] if suffix == 'at' else manifests[0]
        root = REPO / f'.runtime-work/c109749-signal-300-{label}-delivery-v1'
        negative_root = REPO / f'.runtime-work/c109749-signal-300-{label}-delivery-negative-v1'
        audit_file = root / 'attempt/diagnostic-audit.json'
        audit = json.loads(audit_file.read_text())
        measured = audit['signal_advance']['observed_continuous_approach_distance_m']
        if (audit['case_id'] != case or audit['passed'] is not False or
                audit['software_checks_passed'] is not True or
                audit['diagnostic_fixture'] is not True or audit['frames'] != 900 or
                abs(measured - target) >= .001 or
                audit['signal_advance']['observable_91_44_m_met'] is not (target >= 91.44) or
                audit['physical_acceptance_claimed'] is not False):
            raise ValueError('Exact diagnostic delivery audit differs: ' + case)
        positive_log = f'signal-300-{label}-delivery-positive.log'
        negative_log = f'signal-300-{label}-delivery-negative.log'
        spec = {
            'case_id': case, 'sets': ['demo-test', 'full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion',
                       'signal_advance'],
            'script': script.name, 'script_sha256': sha(script),
            'command': (f'{fixture} --case {case} --manifest {manifest.relative_to(REPO)} '
                        f'--output-root {root.relative_to(REPO)}'),
            'test_exit_code': 0, 'test_log': positive_log,
            'test_log_sha256': sha(ROOT / positive_log),
            'negative_command': (f'{fixture} --case {case} --manifest {manifest.relative_to(REPO)} '
                                 f'--output-root {negative_root.relative_to(REPO)} '
                                 f'--negative-source-root {root.relative_to(REPO)}'),
            'negative_exit_code': 1,
            'negative_expected_error': 'Sealed original source changed: interaction_history.jsonl',
            'negative_log': negative_log,
            'negative_log_sha256': sha(ROOT / negative_log),
        }
        validate_case(ROOT, dict(entry, delivery_acceptance=spec), ('demo-test', 'full-test'))
        contracts.append({'case_id': case, 'target_m': target,
                          'audit_sha256': sha(audit_file),
                          'diagnostic_fixture': True,
                          'physical_acceptance_claimed': False,
                          'delivery_acceptance': spec})
    if len(contracts) != 3:
        raise ValueError('Three exact 300 ft delivery contracts required')
    print(json.dumps({'format': 'worker-signal-300-draft-delivery-contracts',
                      'contracts': contracts,
                      'native_or_legal_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
