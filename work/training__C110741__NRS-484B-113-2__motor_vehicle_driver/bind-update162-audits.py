"""Rebind current selected delivery, comparison and trigger CPU audit logs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE/'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind():
    manifest = json.loads(MANIFEST.read_text())
    script_hash = sha(HERE/'audit-selected.py')
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('_', 1)[-1]
        acceptance = entry['delivery_acceptance']
        positive = HERE/f'update162-delivery-{suffix}-positive.log'
        negative = HERE/f'update162-delivery-{suffix}-negative.log'
        result = json.loads(positive.read_text())
        if (result.get('passed') is not True or result['case_id'] != entry['case_id']
                or result.get('accepted') is not False
                or acceptance['negative_expected_error'] not in negative.read_text()):
            raise ValueError('Delivery diagnostic positive/negative differs')
        acceptance.update(script_sha256=script_hash, test_log=positive.name,
                          test_log_sha256=sha(positive), negative_log=negative.name,
                          negative_log_sha256=sha(negative))
        comparison = entry['comparison_audit']
        positive = HERE/'update162-comparison.log'
        negative = HERE/'update162-comparison-negative.log'
        if (json.loads(positive.read_text()).get('passed') is not True
                or comparison['negative_expected_error'] not in negative.read_text()):
            raise ValueError('Controlled comparison diagnostic differs')
        comparison.update(script_sha256=script_hash, test_log=positive.name,
                          test_log_sha256=sha(positive), negative_log=negative.name,
                          negative_log_sha256=sha(negative))
        trigger = entry['candidate_trigger_test']
        log = HERE/'update162-triggers.log'
        if json.loads(log.read_text()).get('tested_trigger_boundaries') != 6:
            raise ValueError('Candidate trigger boundaries not checked')
        trigger.update(test_log=log.name, test_log_sha256=sha(log))
    MANIFEST.write_text(json.dumps(manifest, indent=2)+'\n')
    return {'cases': len(manifest['cases']), 'manifest_sha256': sha(MANIFEST)}


if __name__ == '__main__':
    print(json.dumps(bind(), indent=2))
