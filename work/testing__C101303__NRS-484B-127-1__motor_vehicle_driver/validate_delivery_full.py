"""Validate all nine exact diagnostic delivery receipts and their 900-frame scope."""
import json
import hashlib
import sys
from pathlib import Path

folder=Path(__file__).resolve().parent
repo=folder.parent.parent
sys.path.insert(0,str(repo/'runtime/scenario_pipeline'))
from worker_exchange.delivery_handoff import validate_case

manifest=json.loads((folder/'execution-manifest.json').read_text())
if len(manifest['cases'])!=9:
    raise ValueError('Expected nine selected C101303 cases')
for entry in manifest['cases']:
    validate_case(folder,entry,{'demo-test','full-test'})
    spec=entry['delivery_acceptance']
    for key,digest_key in [('diagnostic_audit','diagnostic_audit_sha256'),
                           ('diagnostic_decode_receipt','diagnostic_decode_receipt_sha256')]:
        path=folder/spec[key]
        if hashlib.sha256(path.read_bytes()).hexdigest()!=spec[digest_key]:
            raise ValueError('Diagnostic artifact hash changed: '+entry['case_id']+' '+key)
    audit=json.loads((folder/spec['diagnostic_audit']).read_text())
    if (audit.get('case_id')!=entry['case_id'] or audit.get('frames')!=900 or
            audit.get('passed') is not False or audit.get('software_checks_passed') is not True or
            audit.get('diagnostic_fixture') is not True or
            audit.get('physical_acceptance_claimed') is not False or
            set(audit.get('checks',{}))!=set(spec['checks'])):
        raise ValueError('Diagnostic receipt scope or case differs: '+entry['case_id'])
    print('validated',entry['case_id'],audit['frames'],'diagnostic frames')
