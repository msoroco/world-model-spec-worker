"""Bind passing recorded-only primary CPU checks before final-hash rerun."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE/'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('_', 1)[-1]
        log = HERE/f'update162-{suffix}-primary-saved.log'
        result = json.loads(log.read_text())
        if (result.get('passed') is not True or result.get('recorded_only') is not True
                or result.get('case_id') != entry['case_id']
                or result.get('physical_acceptance_claimed') is not False
                or result.get('legal_acceptance_claimed') is not False):
            raise ValueError('Saved proof is not a passing diagnostic for selected case')
        entry['post_capture'].update(test_log=log.name, test_log_sha256=sha(log),
                                     test_exit_code=0)
    MANIFEST.write_text(json.dumps(manifest, indent=2)+'\n')
    return {'manifest_sha256': sha(MANIFEST), 'cases': len(manifest['cases'])}


if __name__ == '__main__':
    print(json.dumps(bind(), indent=2))
