"""Bind current construction hash recorded-only replay evidence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c405341-2e'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    for entry in manifest['cases']:
        case = entry['case_id']
        name = case.removeprefix(HERE.name + '__')
        receipt = SCRATCH / ('saved-emergency-v3-' + name) / 'v0001/processing.json'
        data = json.loads(receipt.read_text(encoding='utf-8'))
        if not (data.get('passed') is True and data.get('recorded_only') is True and
                data.get('native_revision', {}).get('construction_sha256') == entry['construction_sha256']):
            raise ValueError('current recorded-only replay missing: ' + name)
        source_log = SCRATCH / ('saved-command-' + name + '.log')
        log = HERE / ('cpu-saved-' + name + '.log')
        log.write_text(source_log.read_text(encoding='utf-8').rstrip() + '\n', encoding='utf-8')
        command = ('.venv-cpu/bin/python runtime.py process-saved --manifest work/' + HERE.name +
                   '/execution-manifest.json --case ' + case +
                   ' --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $VALIDATOR')
        entry['post_capture'] = {
            'recorded_only': True, 'command': command, 'feedback_command': command,
            'test_log': log.name, 'test_log_sha256': sha(log), 'test_exit_code': 0,
            'scope': 'synthetic recorded-only replay; original emergency-lane source and physical/legal judgment pending'}
        print(name + ': saved replay passed', flush=True)
    path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
