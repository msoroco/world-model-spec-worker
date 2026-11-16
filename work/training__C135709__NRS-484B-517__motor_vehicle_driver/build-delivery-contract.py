"""Bind exact-case CPU delivery-auditor mechanics and rejection proofs."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO/'runtime/pipeline'))
from scenario_pipeline.worker_exchange.delivery_handoff import CHECKS, validate_case


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    script = ROOT/'prove-delivery-contract.py'
    contracts = {}
    for witness in ('reference', 'contrast'):
        case = ROOT.name+'__'+witness
        positive = ROOT/('update053-delivery-'+witness+'-positive.log')
        negative = ROOT/('update053-delivery-'+witness+'-negative.log')
        base = '.venv-cpu/bin/python work/'+ROOT.name+'/prove-delivery-contract.py --case '+case
        receipt = {'case_id': case, 'sets': ['full-train'],
            'checks': sorted(CHECKS), 'command': base,
            'negative_command': base+' --reject-synthetic',
            'script': 'prove-delivery-contract.py', 'script_sha256': sha(script),
            'test_exit_code': 0, 'test_log': positive.name,
            'test_log_sha256': sha(positive), 'negative_exit_code': 1,
            'negative_expected_error':
                'Synthetic or wrong-case result cannot establish original Native delivery',
            'negative_log': negative.name, 'negative_log_sha256': sha(negative)}
        validate_case(ROOT, {'case_id': case, 'delivery_acceptance': receipt},
                      expected_sets={'full-train'})
        contracts[witness] = receipt
    value = {'format': 'c135709-delivery-contract-cpu-v1',
             'contracts': contracts, 'synthetic_mechanics_only': True,
             'original_native_observed': False, 'accepted_recording': False}
    output = ROOT/'update053-delivery-contract.json'
    output.write_text(json.dumps(value, indent=2)+'\n')
    return value


if __name__ == '__main__':
    print(json.dumps({'validated_cases': len(build()['contracts'])}))
