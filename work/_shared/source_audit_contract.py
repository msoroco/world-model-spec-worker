"""Verify an independent local Native audit before canonical acceptance."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

REQUIRED = {'native_source', 'all_participants', 'time_join',
            'full_video_decode', 'actual_pixels', 'physical_completion'}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def check(root, batch, case, attempt, audit_path):
    root, attempt, audit_path = (Path(p).resolve() for p in (root, attempt, audit_path))
    audit = json.loads(audit_path.read_text())
    if (audit.get('format') != 'worker-delivery-audit' or audit.get('passed') is not True
            or audit.get('case_id') != case or
            not REQUIRED <= {k for k, v in audit.get('checks', {}).items() if v is True}):
        raise ValueError('Independent exact-case source audit incomplete')
    if root / 'recordings' not in attempt.parents or attempt not in audit_path.parents:
        raise ValueError('Attempt/audit are outside one canonical recording')
    for name, expected in (('result.json', audit['source_result_sha256']),
                           (audit['video'], audit['video_sha256']),
                           (audit['trace'], audit['trace_sha256'])):
        path = (attempt / name).resolve()
        if attempt not in path.parents or sha(path) != expected:
            raise ValueError('Source changed or escaped attempt: ' + name)
    operations = root / 'state/operations/worker_exchange' / batch
    auditor = Path(audit['auditor_path']).resolve()
    decode_path = Path(audit['source_decode_receipt_path']).resolve()
    if (operations not in auditor.parents or auditor.name != 'delivery_audit.py'
            or operations not in decode_path.parents
            or sha(auditor) != audit['auditor_sha256']
            or sha(decode_path) != audit['source_decode_receipt_sha256']):
        raise ValueError('Independent auditor or full-decode receipt changed')
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime/scenario_pipeline'))
    from worker_exchange.media import verify_receipt
    decoded = verify_receipt(attempt / audit['video'], decode_path, audit['frames'],
                             mapping_sha256=sha(attempt / 'video_frames.jsonl'))
    if decoded['auditor_sha256'] != audit['source_decode_auditor_sha256']:
        raise ValueError('Full-decode auditor revision changed')
    return {'case_id': case, 'frames': audit['frames'], 'source_bound': True, 'passed': True}

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for flag in ('root', 'batch', 'case', 'attempt', 'audit'):
        p.add_argument('--' + flag, required=True)
    args = p.parse_args()
    print(json.dumps(check(args.root, args.batch, args.case, args.attempt, args.audit), indent=2))
