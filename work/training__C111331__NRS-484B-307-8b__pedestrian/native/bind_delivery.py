"""Bind exact current public, saved, physical and audit proofs to delivery."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

folder = Path(__file__).resolve().parent.parent
repo = folder.parents[1]
manifest_path = folder / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
base = f'work/{folder.name}'
validator = '.runtime-work/c229398-pinned-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return str(target.relative_to(folder))


def command(args, log):
    with log.open('w') as output:
        done = subprocess.run(args, cwd=repo, stdout=output, stderr=subprocess.STDOUT)
    return done.returncode


def main():
    if os.environ.get('PYTHONDONTWRITEBYTECODE') != '1':
        raise ValueError('Disable Python bytecode in the work tree')
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        cid = entry['case_id']
        for candidate in ('primary', 'fallback1'):
            selected = entry if candidate == 'primary' else entry['candidates'][0]
            compat = (repo / '.runtime-work/c111331-compat-a-primary-v5' if
                      condition == 'condition_a' and candidate == 'primary' else
                      repo / f'.runtime-work/c111331-compat-{condition}-{candidate}-v5')
            saved = (repo / '.runtime-work/c111331-saved-a-primary-v2' if
                     condition == 'condition_a' and candidate == 'primary' else
                     repo / f'.runtime-work/c111331-saved-{condition}-{candidate}-v2')
            receipt = json.loads((compat / 'compatibility.json').read_text())
            processing = json.loads((saved / 'v0001/processing.json').read_text())
            if not receipt['passed'] or not processing['passed'] or processing['missing_evidence']:
                raise ValueError('Incomplete positive public/saved proof: ' + condition + ' ' + candidate)
            proof_dir = folder / 'proofs' / condition / candidate
            proof = {'receipt': copy(compat / 'compatibility.json', proof_dir / 'compatibility.json'),
                     'sha256': sha(compat / 'compatibility.json'),
                     'log': copy(compat / 'compatibility-analysis.log', proof_dir / 'analysis.log'),
                     'negative_log': copy(compat / 'negative-analysis.log', proof_dir / 'negative-analysis.log')}
            selected['compatibility'] = proof
            selected['saved_processing'] = {
                'receipt': copy(saved / 'v0001/processing.json', proof_dir / 'processing.json'),
                'sha256': sha(saved / 'v0001/processing.json')}
            offline_log = folder / f'native-red-offline-{condition}-{candidate}.log'
            selected['offline'] = {'command': f'.venv-cpu/bin/python runtime.py offline --manifest {base}/execution-manifest.json --case {cid} --candidate {candidate} --output .runtime-work/c111331-offline-v7-{condition}-{candidate}',
                                   'exit_code': 0,
                                   'construction_sha256': selected['construction_sha256'],
                                   'log': offline_log.name, 'log_sha256': sha(offline_log)}
            if candidate == 'primary':
                entry['negative'] = {'log': proof['negative_log']}
                saved_log = folder / f'saved-{condition}-{candidate}.log'
                entry['post_capture'] = {'recorded_only': True,
                    'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest {base}/execution-manifest.json --case {cid} --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator {validator}',
                    'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
                    'test_exit_code': 0, 'test_log': saved_log.name,
                    'test_log_sha256': sha(saved_log)}
                physical = folder / f'physical-{condition}-preparation.json'
                entry['physical_preparation'] = {'receipt': physical.name, 'sha256': sha(physical)}
                positive_log = folder / f'delivery-{condition}-positive.log'
                negative_log = folder / f'delivery-{condition}-negative.log'
                positive = ['.venv-cpu/bin/python', f'{base}/delivery_acceptance.py',
                            '--attempt', str(compat.relative_to(repo)), '--case', cid,
                            '--diagnostic', '--output', f'{base}/delivery-{condition}-positive.json']
                negative = ['.venv-cpu/bin/python', f'{base}/delivery_acceptance.py',
                            '--attempt', str(compat.relative_to(repo)), '--case', cid,
                            '--output', f'{base}/delivery-{condition}-negative.json']
                if command(positive, positive_log) != 0 or command(negative, negative_log) == 0:
                    raise ValueError('Delivery audit positive/negative failed: ' + condition)
                expected = 'Missing delivery source: capture-seal.json'
                if expected not in negative_log.read_text():
                    raise ValueError('Missing source rejection absent')
                entry['delivery_acceptance'] = {'case_id': cid, 'sets': ['full-train'],
                    'checks': ['native_source', 'all_participants', 'time_join',
                               'full_video_decode', 'actual_pixels', 'physical_completion'],
                    'script': 'delivery_acceptance.py', 'script_sha256': sha(folder / 'delivery_acceptance.py'),
                    'command': ' '.join(positive), 'test_exit_code': 0,
                    'test_log': positive_log.name, 'test_log_sha256': sha(positive_log),
                    'negative_command': ' '.join(negative), 'negative_exit_code': 1,
                    'negative_expected_error': expected, 'negative_log': negative_log.name,
                    'negative_log_sha256': sha(negative_log),
                    'proof_scope': 'Synthetic diagnostic source join and synthetic-as-Native rejection only'}
        print(json.dumps({'case': condition, 'public_saved_candidates': 2}))
    manifest['status'] = 'delivery_prepared_cpu'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
