"""Bind the midpoint's own full-duration positive and negative CPU receipts."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
CASE='testing__C101303__NRS-484B-127-1__motor_vehicle_driver__source_verified_midpoint'
POS=REPO/'.runtime-work/c101303-full-duration/midpoint-positive-v1'
NEG=REPO/'.runtime-work/c101303-full-duration/midpoint-negative-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path=ROOT/'execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    case=next(c for c in manifest['cases'] if c['case_id']==CASE)
    audit=json.loads((POS/'attempt/diagnostic-audit.json').read_text())
    if (audit['case_id']!=CASE or audit['frames']!=900 or audit['passed'] is not False
            or audit['software_checks_passed'] is not True
            or audit['physical_acceptance_claimed'] is not False):
        raise ValueError('Midpoint full-duration diagnostic audit differs')
    negative=(ROOT/'midpoint-delivery-negative.log').read_text()
    if 'ValueError: Sealed original source changed: vehicle_history.jsonl' not in negative:
        raise ValueError('Missing-source negative proof differs')
    target=ROOT/'delivery-proofs/midpoint'
    target.mkdir(parents=True,exist_ok=True)
    for source,name in ((POS/'attempt/diagnostic-audit.json','diagnostic-audit.json'),
                        (POS/'source-decode.json','source-decode.json'),
                        (ROOT/'midpoint-delivery-positive.log','positive.log'),
                        (ROOT/'midpoint-delivery-negative.log','negative.log')):
        shutil.copyfile(source,target/name)
    spec=case['delivery_acceptance']
    py=str(REPO/'.venv-cpu/bin/python')
    script=str(ROOT/'delivery_fixture_proof.py')
    spec.update({
        'command':f'{py} {script} --case {CASE} --output-root .runtime-work/c101303-full-duration/midpoint-positive-v1',
        'test_exit_code':0,'test_log':'delivery-proofs/midpoint/positive.log',
        'test_log_sha256':sha(target/'positive.log'),
        'negative_command':f'{py} {script} --case {CASE} --output-root .runtime-work/c101303-full-duration/midpoint-negative-v1 --negative-missing-source --negative-source-root .runtime-work/c101303-full-duration/midpoint-positive-v1',
        'negative_exit_code':1,'negative_expected_error':'Sealed original source changed: vehicle_history.jsonl',
        'negative_log':'delivery-proofs/midpoint/negative.log',
        'negative_log_sha256':sha(target/'negative.log'),
        'diagnostic_audit':'delivery-proofs/midpoint/diagnostic-audit.json',
        'diagnostic_audit_sha256':sha(target/'diagnostic-audit.json'),
        'diagnostic_decode_receipt':'delivery-proofs/midpoint/source-decode.json',
        'diagnostic_decode_receipt_sha256':sha(target/'source-decode.json')})
    value=json.dumps(manifest,indent=2)+'\n'
    manifest_path.write_text(value)
    (ROOT/'midpoint-promotion-ready.json').write_text(value)
    print('midpoint own 900-frame diagnostic delivery proof bound')


if __name__=='__main__':
    main()
