"""Rerun exact C125697 offline, compatibility and saved CPU proofs.

All generated media stays under ignored .runtime-work; only small logs and
source-bound receipts are retained in this assignment directory.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
PYTHON = REPO / '.venv-cpu/bin/python'
VALIDATOR = REPO / '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(manifest):
    MANIFEST.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')


def run(command, log):
    with log.open('w') as stream:
        finished = subprocess.run(command, cwd=REPO, stdout=stream,
                                  stderr=subprocess.STDOUT, check=False)
    if finished.returncode:
        raise RuntimeError(f'{log}: command exited {finished.returncode}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', help='Exact case suffix to refresh')
    parser.add_argument('--candidate', help='Only one of primary/fallback1/fallback2/fallback3')
    parser.add_argument('--revision', default='v2', help='Unique ignored diagnostic run revision')
    args = parser.parse_args()
    if not VALIDATOR.is_file():
        raise FileNotFoundError('Pinned Lean decoder executable is absent')
    manifest = json.loads(MANIFEST.read_text())
    completed = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        if args.only and args.only != suffix:
            continue
        for selected in [entry, *entry['candidates']]:
            candidate = selected.get('id', 'primary')
            if args.candidate and args.candidate != candidate:
                continue
            tag = f'completion-{suffix}-{candidate}-{args.revision}'
            case = entry['case_id']
            selector = [] if candidate == 'primary' else ['--candidate', candidate]
            construction = HERE / selected['construction']
            if sha(construction) != selected['construction_sha256']:
                raise ValueError('Construction hash changed: ' + tag)
            offline_dir = REPO / '.runtime-work' / (tag + '-offline')
            offline_log = HERE / (tag + '-offline.log')
            offline_command = [str(PYTHON), 'runtime.py', 'offline',
                               '--manifest', str(MANIFEST.relative_to(REPO)),
                               '--case', case, *selector, '--output',
                               str(offline_dir.relative_to(REPO))]
            run(offline_command, offline_log)
            if '"offline_passed": true' not in offline_log.read_text():
                raise ValueError('Offline success receipt missing: ' + tag)
            selected['offline'] = {
                'command': ' '.join(offline_command), 'exit_code': 0,
                'construction_sha256': selected['construction_sha256'],
                'log': offline_log.name, 'log_sha256': sha(offline_log),
            }
            save(manifest)
            compatibility_dir = REPO / '.runtime-work' / (tag + '-compatibility')
            compatibility_log = HERE / (tag + '-compatibility.log')
            compatibility_command = [str(PYTHON), 'runtime.py', 'compatibility',
                                     '--manifest', str(MANIFEST.relative_to(REPO)),
                                     '--case', case, *selector, '--output',
                                     str(compatibility_dir.relative_to(REPO)),
                                     '--library', 'runtime/library',
                                     '--validator', str(VALIDATOR.relative_to(REPO))]
            run(compatibility_command, compatibility_log)
            names = {
                'receipt': ('compatibility.json', tag + '-compatibility-receipt.json'),
                'log': ('compatibility-analysis.log', tag + '-analysis.log'),
                'negative_log': ('negative-analysis.log', tag + '-negative.log'),
            }
            for source, destination in names.values():
                shutil.copyfile(compatibility_dir / source, HERE / destination)
            receipt_path = HERE / names['receipt'][1]
            receipt = json.loads(receipt_path.read_text())
            if (receipt.get('passed') is not True or receipt['case_id'] != case
                    or receipt['candidate_id'] != candidate
                    or receipt['construction_sha256'] != selected['construction_sha256']
                    or receipt['log_sha256'] != sha(HERE / names['log'][1])
                    or receipt['negative_log_sha256'] != sha(HERE / names['negative_log'][1])):
                raise ValueError('Compatibility source receipt changed: ' + tag)
            selected['compatibility'] = {
                'receipt': receipt_path.name, 'sha256': sha(receipt_path),
                'log': names['log'][1],
            }
            if candidate == 'primary':
                entry['negative'] = {'log': names['negative_log'][1]}
            else:
                selected['compatibility']['negative_log'] = names['negative_log'][1]
            saved_dir = REPO / '.runtime-work' / (tag + '-saved')
            saved_log = HERE / (tag + '-saved.log')
            saved_command = [str(PYTHON), 'runtime.py', 'process-saved',
                             '--manifest', str(MANIFEST.relative_to(REPO)),
                             '--case', case, '--attempt',
                             str(compatibility_dir.relative_to(REPO)),
                             '--output', str(saved_dir.relative_to(REPO)),
                             '--library', 'runtime/library',
                             '--validator', str(VALIDATOR.relative_to(REPO))]
            run(saved_command, saved_log)
            processing = json.loads((saved_dir / 'v0001/processing.json').read_text())
            if (processing.get('passed') is not True or
                    processing.get('recorded_only') is not True or
                    processing.get('case_id') != case):
                raise ValueError('Recorded-only saved proof changed: ' + tag)
            if candidate == 'primary':
                entry['post_capture'] = {
                    'recorded_only': True,
                    'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck',
                    'feedback_command': 'cat $OUTPUT/feedback.json',
                    'test_log': saved_log.name,
                    'test_log_sha256': sha(saved_log),
                    'test_exit_code': 0,
                    'proof_scope': 'synthetic source-bound recorded-only processing; physical acceptance unclaimed',
                }
            save(manifest)
            completed.append(tag)
            print(tag, flush=True)
    print(json.dumps({'completed': completed}, indent=2))


if __name__ == '__main__':
    main()
