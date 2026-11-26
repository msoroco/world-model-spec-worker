"""Bind tested independent taxi delivery audits to selected cases."""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'lead-current-audits'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_copy(source, target):
    lines = source.read_text().splitlines()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join(line.rstrip() for line in lines).rstrip() + '\n')


def main():
    manifest_path = BASE / 'selected-draft-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for suffix in ('probe_a', 'probe_b'):
        case_id = BASE.name + '__' + suffix
        entry = next(e for e in manifest['cases'] if e['case_id'] == case_id)
        location = BASE / 'native' / 'delivery' / suffix
        positive = location / 'positive.log'
        negative = location / 'missing-source.log'
        clean_copy(SCRATCH / ('c394327-delivery-' + suffix + '-positive.log'), positive)
        clean_copy(SCRATCH / ('c394327-delivery-' + suffix + '-negative.log'), negative)
        outcome = json.loads(positive.read_text())
        if (outcome.get('case_id') != case_id or outcome.get('passed') is not True
                or outcome.get('original_native_accepted') is not False
                or 'Missing source: observed-activity.jsonl' not in negative.read_text()):
            raise ValueError('Taxi delivery proof did not pass source-bound checks')
        command = ('.venv-cpu/bin/python -B work/' + BASE.name +
                   '/delivery_audit.py --case ' + case_id +
                   ' --attempt $ATTEMPT --diagnostic')
        entry['delivery_acceptance'] = {
            'case_id': case_id, 'sets': ['full-train'],
            'checks': outcome['checks'],
            'command': command,
            'negative_command': command +
                                ' --omit-source observed-activity.jsonl',
            'script': 'delivery_audit.py',
            'script_sha256': sha(BASE / 'delivery_audit.py'),
            'test_exit_code': 0, 'negative_exit_code': 1,
            'negative_expected_error': 'Missing source: observed-activity.jsonl',
            'test_log': str(positive.relative_to(BASE)),
            'test_log_sha256': sha(positive),
            'negative_log': str(negative.relative_to(BASE)),
            'negative_log_sha256': sha(negative)}
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
