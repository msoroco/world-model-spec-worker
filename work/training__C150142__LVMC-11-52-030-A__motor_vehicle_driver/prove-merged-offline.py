"""Exercise every exact candidate through the integrated draft manifest."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest-draft-all.json'
PYTHON = sys.executable


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', default='v1')
    args = parser.parse_args()
    if not args.tag.replace('-', '').isalnum():
        raise ValueError('Tag must be a simple output label')
    manifest = json.loads(MANIFEST.read_text())
    records = []
    for entry in manifest['cases']:
        case_id = entry['case_id']
        slug = case_id.removeprefix(ROOT.name + '__')
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            output = REPO / '.runtime-work' / (
                'c150142-merged-' + slug + '-' + candidate + '-offline-' + args.tag)
            if not output.exists():
                command = [PYTHON, str(REPO / 'runtime.py'), 'offline',
                           '--manifest', str(MANIFEST), '--case', case_id,
                           '--candidate', candidate, '--output', str(output),
                           '--python', PYTHON]
                process = subprocess.run(command, cwd=REPO,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT,
                                         env=dict(os.environ, PYTHONHASHSEED='0'),
                                         text=True, timeout=300)
                if process.returncode:
                    raise RuntimeError('Integrated offline failed: ' + slug + '/' +
                                       candidate + '\n' + process.stdout[-2000:])
            selection = json.loads((output / 'candidate-selection.json').read_text())
            selected = entry if candidate == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate)
            if selection['case_id'] != case_id or \
               selection['candidate_id'] != candidate or \
               selection['manifest_sha256'] != sha(MANIFEST) or \
               selection['construction_sha256'] != selected['construction_sha256'] or \
               not (output / 'offline.log').is_file():
                raise ValueError('Integrated candidate binding differs: ' + slug + '/' + candidate)
            records.append({'case_id': case_id, 'candidate': candidate,
                            'manifest_sha256': sha(MANIFEST),
                            'construction_sha256': selected['construction_sha256'],
                            'offline_log_sha256': sha(output / 'offline.log'),
                            'offline_passed': True, 'native_executed': False})
        print(slug, 'four offline candidates pass', flush=True)
    target = ROOT / ('merged-offline-matrix-' + args.tag + '.json')
    target.write_text(json.dumps({'kind': 'integrated_draft_offline',
                                  'case_count': len(manifest['cases']),
                                  'candidate_count': len(records),
                                  'records': records,
                                  'selected_delivery_proven': False},
                                 indent=2, allow_nan=False) + '\n')
    print(json.dumps({'cases': len(manifest['cases']),
                      'candidates': len(records),
                      'receipt': str(target.relative_to(REPO))}))


if __name__ == '__main__':
    main()
