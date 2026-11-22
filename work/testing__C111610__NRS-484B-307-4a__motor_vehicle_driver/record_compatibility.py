"""Attach passing pinned compatibility receipts for both exact cases and candidates."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
OUTPUTS = {
    ('crosswalk_clear_turn', 'primary'): 'c111610-compat-clear-v3',
    ('crosswalk_clear_turn', 'fallback1'): 'c111610-compat-clear-fallback1-v1',
    ('crosswalk_occupied_yield', 'primary'): 'c111610-compat-occupied-primary-v1',
    ('crosswalk_occupied_yield', 'fallback1'): 'c111610-compat-occupied-fallback1-v1',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate, holder in [('primary', entry),
                                  ('fallback1', entry['candidates'][0])]:
            output = REPO / '.runtime-work' / OUTPUTS[suffix, candidate]
            receipt = json.loads((output / 'compatibility.json').read_text())
            assert receipt['passed'] and receipt['case_id'] == entry['case_id']
            assert receipt['candidate_id'] == candidate
            assert receipt['construction_sha256'] == holder['construction_sha256']
            tag = suffix + '-' + candidate
            copied = {}
            for key, source, ending in (
                ('receipt', 'compatibility.json', '-receipt.json'),
                ('log', 'compatibility-analysis.log', '-analysis.log'),
                ('negative_log', 'negative-analysis.log', '-negative.log'),
            ):
                target = ROOT / ('compat-' + tag + ending)
                shutil.copyfile(output / source, target)
                copied[key] = target.name
                if key == 'receipt':
                    copied['sha256'] = sha(target)
            command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                       'compatibility', '--manifest', str(MANIFEST), '--case',
                       entry['case_id'], '--output', str(output), '--library',
                       str(REPO / 'runtime/library'), '--validator',
                       str(REPO / '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'),
                       '--candidate', candidate]
            copied['command'] = ' '.join(command)
            holder['compatibility'] = copied
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print('Recorded four passing pinned compatibility receipts.')


if __name__ == '__main__':
    main()
