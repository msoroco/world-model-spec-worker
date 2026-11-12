"""Pinned positive/negative compatibility for all staged sweep constructions."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'
TAG = 'update028'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def copy(relative, folder):
    target = folder / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / relative, target)


def main():
    source_manifest = HERE / 'sweep-execution-candidate.json'
    source = json.loads(source_manifest.read_text())
    validator = REPO / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
    if not validator.is_file():
        raise ValueError('Pinned diagnostic validator missing')
    matrix_path = HERE / f'{TAG}-sweep-staged-compat-matrix.json'
    if matrix_path.exists():
        raise ValueError('Retain prior staged compatibility matrix')
    rows = []
    with tempfile.TemporaryDirectory(prefix='c111256-sweep-compat-all-', dir=REPO / '.runtime-work') as scratch:
        mini = Path(scratch)
        folder = mini / 'work' / HERE.name
        folder.mkdir(parents=True)
        write(folder / 'proposals/cases.json',
              json.loads((HERE / 'proposals/sweep-stage-candidate.json').read_text()))
        plan = json.loads((HERE / 'case-plan.json').read_text())
        sweep_ids = {case['case_id'] for case in source['cases']}
        for disposition in plan['requirement_dispositions']:
            if disposition['status'] == 'selected_required':
                disposition['case_ids'] = sorted(set(disposition.get('case_ids', [])) | sweep_ids)
        write(folder / 'case-plan.json', plan)
        for relative in ('update028-sweep-diagnostic.json', 'update028-sweep-recipe.json'):
            copy(relative, folder)
        for case in source['cases']:
            copy(case['measurement_contract'], folder)
            copy(case['construction'], folder)
            for fallback in case['candidates']:
                copy(fallback['construction'], folder)
        manifest = folder / 'execution-manifest.json'
        write(manifest, source)
        for case in source['cases']:
            suffix = case['case_id'].rsplit('__', 1)[-1]
            for candidate in ('primary', *(row['id'] for row in case['candidates'])):
                output = mini / '.runtime-work' / suffix / candidate
                command = [str(PYTHON), str(REPO / 'runtime.py'), 'compatibility',
                           '--manifest', str(manifest), '--case', case['case_id'],
                           '--candidate', candidate, '--output', str(output),
                           '--library', str(REPO / 'runtime/pipeline/library'),
                           '--validator', str(validator)]
                run = subprocess.run(command, cwd=REPO, capture_output=True,
                                     text=True, timeout=600)
                dest = HERE / f'{TAG}-sweep-staged-compat' / suffix / candidate
                dest.mkdir(parents=True, exist_ok=True)
                (dest / 'runtime-command.log').write_text(run.stdout + run.stderr)
                if run.returncode:
                    raise ValueError(f'Pinned compatibility failed {suffix} {candidate}: {(run.stdout + run.stderr)[-1100:]}')
                receipt = output / 'compatibility.json'
                if not receipt.is_file():
                    raise ValueError('Pinned compatibility receipt missing')
                value = json.loads(receipt.read_text())
                required = {'selected_measurements', 'negative_case_source',
                            'lean_decoder', 'final_decode'}
                if (value['passed'] is not True or value['case_id'] != case['case_id'] or
                        value['candidate_id'] != candidate or not required <= set(value['checks'])):
                    raise ValueError('Pinned compatibility checks incomplete')
                for name in ('compatibility.json', 'compatibility-analysis.log',
                             'negative-analysis.log'):
                    shutil.copy2(output / name, dest / name)
                rows.append({'case_id': case['case_id'], 'candidate_id': candidate,
                             'construction_sha256': value['construction_sha256'],
                             'receipt': (dest / 'compatibility.json').relative_to(HERE).as_posix(),
                             'receipt_sha256': sha(dest / 'compatibility.json'),
                             'positive_log_sha256': sha(dest / 'compatibility-analysis.log'),
                             'negative_log_sha256': sha(dest / 'negative-analysis.log'),
                             'runtime_command_log_sha256': sha(dest / 'runtime-command.log')})
                write(matrix_path, {'format': 'c111256-staged-sweep-compat-matrix-v1',
                      'status': 'complete_diagnostic' if len(rows) == 16 else 'partial',
                      'staged_manifest_sha256': sha(source_manifest),
                      'rows': rows, 'original_recordings_accepted': 0})
                print(suffix, candidate, 'passed', flush=True)
    print(json.dumps({'staged_compatibility_passed': len(rows),
                      'matrix_sha256': sha(matrix_path), 'selected': False}, sort_keys=True))


if __name__ == '__main__':
    main()
