"""Bind corrected physical constructions and rerun exact CPU candidate proofs."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = '.venv-cpu/bin/python'
VALIDATOR = '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'
CASES = {
    'primary': 'yield_ego_left_near_time',
    'right': 'yield_ego_right_near_time',
    'separated': 'yield_ego_left_separated',
    'opposite': 'yield_opposite_left_turn',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def run(command, log):
    with (HERE / log).open('w') as output:
        outcome = subprocess.run(command, cwd=REPO, stdout=output, stderr=subprocess.STDOUT)
    if outcome.returncode:
        raise RuntimeError(f'{log} failed with exit {outcome.returncode}')


def main():
    for prefix, suffix in CASES.items():
        path = HERE / f'{prefix}-candidate-manifest.json'
        manifest = json.loads(path.read_text())
        entry = manifest['cases'][0]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            name = 'physical-construction.json' if candidate == 'primary' else f'{candidate}-physical-construction.json'
            construction = HERE / 'cases' / suffix / name
            selected['construction'] = str(construction.relative_to(HERE))
            selected['construction_sha256'] = sha(construction)
        write(path, manifest)
        case = entry['case_id']
        manifest_arg = str(path.relative_to(REPO))
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            stem = f'promoted-{prefix}-{candidate}'
            out = f'.runtime-work/c125763-{stem}'
            candidate_args = [] if candidate == 'primary' else ['--candidate', candidate]
            offline_command = [PYTHON, 'runtime.py', 'offline', '--manifest', manifest_arg,
                               '--case', case, *candidate_args, '--output', out + '-offline']
            offline_log = stem + '-offline.log'
            run(offline_command, offline_log)
            selected['offline'] = {'command': ' '.join(offline_command), 'exit_code': 0,
                                   'construction_sha256': selected['construction_sha256'],
                                   'log': offline_log, 'log_sha256': sha(HERE / offline_log)}
            compatibility_command = [PYTHON, 'runtime.py', 'compatibility', '--manifest', manifest_arg,
                                     '--case', case, *candidate_args, '--output', out + '-compat',
                                     '--library', 'runtime/library', '--validator', VALIDATOR]
            compatibility_log = stem + '-compat.log'
            run(compatibility_command, compatibility_log)
            output = REPO / (out + '-compat')
            receipt = json.loads((output / 'compatibility.json').read_text())
            if not receipt.get('passed') or receipt['construction_sha256'] != selected['construction_sha256']:
                raise RuntimeError('Incompatible receipt: ' + stem)
            receipt_file = stem + '-compatibility-receipt.json'
            analysis_file = stem + '-analysis.log'
            negative_file = stem + '-negative-analysis.log'
            (HERE / receipt_file).write_bytes((output / 'compatibility.json').read_bytes())
            (HERE / analysis_file).write_bytes((output / 'compatibility-analysis.log').read_bytes())
            (HERE / negative_file).write_bytes((output / 'negative-analysis.log').read_bytes())
            selected['compatibility'] = {'receipt': receipt_file, 'sha256': sha(HERE / receipt_file),
                                         'log': analysis_file, 'negative_log': negative_file}
            if candidate == 'primary':
                entry['negative'] = {'log': negative_file}
            saved_command = [PYTHON, 'runtime.py', 'process-saved', '--manifest', manifest_arg,
                             '--case', case, '--attempt', out + '-compat', '--output', out + '-saved',
                             '--library', 'runtime/library', '--validator', VALIDATOR]
            saved_log = stem + '-saved.log'
            run(saved_command, saved_log)
            saved = json.loads((HERE / saved_log).read_text())
            if not saved.get('passed') or not saved.get('recorded_only'):
                raise RuntimeError('Saved processing incomplete: ' + stem)
            saved_file = stem + '-saved-receipt.json'
            write(HERE / saved_file, saved)
            if candidate != 'primary':
                selected['saved_processing'] = {'receipt': saved_file, 'sha256': sha(HERE / saved_file),
                                                'log': saved_log, 'log_sha256': sha(HERE / saved_log)}
            write(path, manifest)
            print(json.dumps({'case_id': case, 'candidate': candidate, 'offline': 'passed',
                              'compatibility': 'passed', 'saved': 'passed'}), flush=True)


if __name__ == '__main__':
    main()
