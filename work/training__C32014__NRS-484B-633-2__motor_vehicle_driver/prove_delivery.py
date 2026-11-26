"""CPU positive/negative independent audit tests for both exact bridge cases."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNTIME_WORK = ROOT / '.runtime-work'
assert Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve().is_relative_to(RUNTIME_WORK)
from delivery_audit import check_authority


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    result = subprocess.run(command, cwd=ROOT, env=os.environ.copy(),
                            capture_output=True, text=True)
    message = (result.stdout + result.stderr).rstrip()
    Path(log).write_text((message if message else 'Audit command completed with exit code ' + str(result.returncode)) + '\n')
    return result.returncode


def main():
    for suffix in ('probe_01', 'probe_02'):
        case = HERE.name + '__' + suffix
        receipt = RUNTIME_WORK / ('c32014-final-output-' + suffix[-2:]) / 'v0001/processing.json'
        output = RUNTIME_WORK / ('c32014-delivery-' + suffix[-2:] + '.json')
        proof = HERE / 'proof' / suffix
        common = [str(ROOT / '.venv-cpu/bin/python'), '-B', str(HERE / 'delivery_audit.py'),
                  '--case', case, '--processing', str(receipt), '--output', str(output), '--diagnostic']
        positive_log = proof / 'delivery-positive.log'
        negative_log = proof / 'delivery-negative.log'
        if run(common, positive_log):
            raise ValueError('Diagnostic delivery positive failed: ' + positive_log.read_text()[-1200:])
        result = json.loads(output.read_text())
        if (result.get('case_id') != case or result.get('diagnostic_only') is not True
                or result.get('authority_verified') is not False):
            raise ValueError('Diagnostic delivery proof claimed original authority')
        negative = common + ['--omit-source', 'bridge-speed-history.jsonl']
        if run(negative, negative_log) == 0 or 'Missing original delivery source: bridge-speed-history.jsonl' not in negative_log.read_text():
            raise ValueError('Delivery audit accepted missing original bridge speed history')
        print(json.dumps({'case_id': case, 'positive_log_sha256': sha(positive_log),
                          'negative_log_sha256': sha(negative_log),
                          'audit_sha256': sha(output)}), flush=True)
    invalid = RUNTIME_WORK / 'c32014-invalid-department.json'
    invalid.write_text(json.dumps({'issuing_body': 'Nevada Department of Transportation',
                                   'review_status': 'authored_scenario_only',
                                   'declared_maximum_mph': 25,
                                   'bridge_identifier': 'C32014 authored bridge',
                                   'department_source': {'path': str(invalid), 'sha256': '0'*64,
                                                         'record_id': 'synthetic',
                                                         'verification_method': 'none'}}) + '\n')
    authority_log = HERE / 'proof' / 'authority-negative.log'
    try:
        check_authority(invalid, {'sign_limit_mph': 25, 'bridge_identifier': 'C32014 authored bridge'})
    except ValueError as error:
        authority_log.write_text(str(error) + '\n')
    else:
        raise ValueError('Audit accepted unverified Department declaration')
    value = json.loads(invalid.read_text())
    value['review_status'] = 'independently_verified'
    invalid.write_text(json.dumps(value) + '\n')
    try:
        check_authority(invalid, {'sign_limit_mph': 25, 'bridge_identifier': 'C32014 authored bridge'})
    except ValueError as error:
        with authority_log.open('a') as stream:
            stream.write(str(error) + '\n')
    else:
        raise ValueError('Audit accepted stale Department document hash')
    print(json.dumps({'authority_negative_log_sha256': sha(authority_log)}))


if __name__ == '__main__':
    main()
