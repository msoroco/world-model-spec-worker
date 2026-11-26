"""Bind exact case CPU receipts while preserving the pending full-law branch."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
AID = ROOT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    manifest_path = ROOT / 'probe-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    saved = json.loads((HERE / 'saved-only-cpu-proof.json').read_text())
    cases = {entry['case_id']: entry for entry in saved['cases']}
    manifest['status'] = 'partial'
    manifest['delivery_ready'] = False
    manifest['readiness_gap'] = (
        'Separate roadway-entry yield clause has no actor-eligible frozen '
        'candidate cell; original physical and pixel acceptance remain pending.')
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        base = HERE / suffix
        physical = base / 'physical-proof/receipt.json'
        audit = base / 'saved-proof/delivery-audit.json'
        positive_log = base / 'saved-proof/delivery-audit.log'
        negative_log = base / 'saved-proof/delivery-negative.log'
        if 'Missing original sidewalk source' not in negative_log.read_text():
            raise ValueError('Missing-source delivery audit negative absent')
        if json.loads(audit.read_text())['delivery_accepted'] is not False:
            raise ValueError('Diagnostic audit claimed delivery acceptance')
        entry['physical_preparation'] = {
            'receipt': physical.relative_to(ROOT).as_posix(),
            'sha256': sha(physical)}
        entry['post_capture'] = {
            'command': '.venv-cpu/bin/python -B runtime.py process-saved '
                       '--manifest work/' + AID + '/probe-manifest.json '
                       '--case ' + case + ' --attempt "$SAVED_ATTEMPT" '
                       '--output "$PROCESSED_OUT" --library runtime/library '
                       '--validator "$VALIDATOR"',
            'proof': cases[case]['positive']['receipt'],
            'proof_sha256': cases[case]['positive']['sha256'],
            'missing_source_negative': cases[case]['negative']['receipt'],
            'missing_source_negative_sha256': cases[case]['negative']['sha256'],
            'recorded_only': True,
            'test_exit_code': 0,
            'test_log': cases[case]['positive']['log'],
            'test_log_sha256': cases[case]['positive']['log_sha256']}
        entry['diagnostic_delivery_audit'] = {
            'script': 'native/audit_delivery.py',
            'script_sha256': sha(HERE / 'audit_delivery.py'),
            'result': audit.relative_to(ROOT).as_posix(),
            'result_sha256': sha(audit),
            'positive_log': positive_log.relative_to(ROOT).as_posix(),
            'positive_log_sha256': sha(positive_log),
            'negative_log': negative_log.relative_to(ROOT).as_posix(),
            'negative_log_sha256': sha(negative_log),
            'missing_source_rejected': True,
            'actual_native_pixels_reviewed': False,
            'delivery_accepted': False}
        entry['delivery_readiness'] = 'incomplete'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    return {'manifest_sha256': sha(manifest_path),
            'case_count': len(manifest['cases']), 'status': manifest['status']}


if __name__ == '__main__':
    print(json.dumps(bind()))
