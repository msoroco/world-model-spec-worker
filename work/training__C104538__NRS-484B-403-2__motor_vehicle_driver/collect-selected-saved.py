"""Bind current recorded-only selected primary processing tests."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        digit = suffix[-1]
        source = ROOT / f'.runtime-work/c104538-v4-saved-w{digit}-command.log'
        processing = ROOT / f'.runtime-work/c104538-v4-saved-w{digit}-output/v0001/processing.json'
        info = json.loads(processing.read_text())
        if not info['originals_preserved'] or info['missing_evidence'] or info['physical_acceptance_claimed'] or info['legal_acceptance_claimed']:
            raise ValueError('Selected saved processing did not preserve original source or claimed acceptance')
        target = HERE / 'selected-proof' / suffix / 'primary'
        log = target / 'saved-command.log'
        receipt = target / 'saved-processing.json'
        for a, b in ((source, log), (processing, receipt)):
            if not a.is_file() or a.stat().st_size > 2 * 1024 * 1024:
                raise ValueError('Saved proof missing or oversized')
            shutil.copyfile(a, b)
        command = (f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json '
                   f'--case {entry["case_id"]} --attempt .runtime-work/c104538-v4-saved-w{digit}-attempt '
                   f'--output .runtime-work/c104538-v4-saved-w{digit}-output '
                   f'--library runtime/library --validator .runtime-work/c104538-decoder/.lake/build/bin/adapterCheck')
        entry['post_capture'] = {'recorded_only': True, 'command': command, 'feedback_command': command,
                                 'test_log': str(log.relative_to(HERE)), 'test_log_sha256': sha(log),
                                 'test_exit_code': 0, 'scope': 'Synthetic CPU saved-processing; original Native feedback unverified'}
        entry['saved_processing'] = {'receipt': str(receipt.relative_to(HERE)), 'sha256': sha(receipt)}
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
