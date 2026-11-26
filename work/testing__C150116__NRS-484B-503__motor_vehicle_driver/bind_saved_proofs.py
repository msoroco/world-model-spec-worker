"""Bind recorded-only synthetic saved processing replays."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[1] / '.runtime-work' / 'c150116-new'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        name = case.removeprefix(HERE.name + '__')
        source = SCRATCH / ('saved-v4-' + name) / 'v0001' / 'processing.json'
        receipt = json.loads(source.read_text())
        if (receipt.get('passed') is not True or receipt.get('recorded_only') is not True
                or receipt.get('candidate_id') != 'primary' or receipt.get('case_id') != case or
                receipt.get('native_revision', {}).get('construction_sha256') != entry['construction_sha256'] or
                receipt.get('analysis_revision', {}).get('construction_sha256') != entry['construction_sha256']):
            raise ValueError(name + ': saved recorded-only replay failed')
        log = HERE / ('cpu-nov26-saved-' + name + '.log')
        log.write_text(json.dumps({key: receipt[key] for key in
                                   ('format', 'case_id', 'passed', 'recorded_only', 'candidate_id',
                                    'native_revision', 'analysis_revision', 'missing_evidence',
                                    'physical_acceptance_claimed', 'legal_acceptance_claimed', 'events')},
                                  indent=2) + '\n')
        command = ('.venv-cpu/bin/python runtime.py process-saved --manifest work/' + HERE.name +
                   '/execution-manifest.json --case ' + case +
                   ' --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $VALIDATOR')
        entry['post_capture'] = {'recorded_only': True, 'command': command,
                                 'feedback_command': command, 'test_log': log.name,
                                 'test_log_sha256': sha(log), 'test_exit_code': 0,
                                 'scope': 'synthetic recorded-only compatibility replay; no original passenger curb zone or legal acceptance'}
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
