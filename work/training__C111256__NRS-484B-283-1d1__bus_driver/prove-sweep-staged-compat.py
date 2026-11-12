"""Run pinned compatibility for first sweep primary in an isolated staging repo."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def copy_to_folder(relative, folder):
    target = folder / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / relative, target)


def main():
    source_manifest = HERE / 'sweep-execution-candidate.json'
    source = json.loads(source_manifest.read_text())
    case = source['cases'][0]
    validator = REPO / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
    if not validator.is_file():
        raise ValueError('Pinned diagnostic validator missing')
    with tempfile.TemporaryDirectory(prefix='c111256-sweep-compat-', dir=REPO / '.runtime-work') as scratch:
        mini = Path(scratch)
        folder = mini / 'work' / HERE.name
        folder.mkdir(parents=True)
        staged = json.loads((HERE / 'proposals/sweep-stage-candidate.json').read_text())
        write(folder / 'proposals/cases.json', staged)
        plan = json.loads((HERE / 'case-plan.json').read_text())
        for disposition in plan['requirement_dispositions']:
            if disposition['status'] == 'selected_required':
                disposition['case_ids'] = sorted(set(disposition.get('case_ids', [])) | {case['case_id']})
        write(folder / 'case-plan.json', plan)
        for relative in ('update028-sweep-diagnostic.json', 'update028-sweep-recipe.json',
                         case['measurement_contract'], case['construction']):
            copy_to_folder(relative, folder)
        manifest = folder / 'execution-manifest.json'
        write(manifest, source)
        output = mini / '.runtime-work/first-primary'
        command = [str(PYTHON), str(REPO / 'runtime.py'), 'compatibility',
                   '--manifest', str(manifest), '--case', case['case_id'],
                   '--candidate', 'primary', '--output', str(output),
                   '--library', str(REPO / 'runtime/pipeline/library'),
                   '--validator', str(validator)]
        run = subprocess.run(command, cwd=REPO, capture_output=True,
                             text=True, timeout=600)
        if run.returncode:
            failure = HERE / 'update028-sweep-staged-compat-failure.log'
            failure.write_text(run.stdout + run.stderr)
            raise ValueError('Pinned sweep compatibility failed; see ' + failure.name + ': ' + (run.stdout + run.stderr)[-900:])
        receipt = output / 'compatibility.json'
        if not receipt.is_file():
            raise ValueError('Pinned compatibility receipt missing')
        value = json.loads(receipt.read_text())
        if (value['passed'] is not True or value['case_id'] != case['case_id'] or
                value['candidate_id'] != 'primary' or
                not {'selected_measurements', 'negative_case_source', 'lean_decoder', 'final_decode'} <= set(value['checks'])):
            raise ValueError('Pinned compatibility checks incomplete')
        for name in ('compatibility.json', 'compatibility-analysis.log', 'negative-analysis.log'):
            shutil.copy2(output / name, HERE / ('update028-sweep-staged-' + name))
        result = {'format': 'c111256-staged-sweep-compatibility-proof-v1',
                  'case_id': case['case_id'], 'candidate_id': 'primary',
                  'staged_manifest_sha256': sha(source_manifest),
                  'staging_copy_only': True,
                  'positive_receipt_sha256': sha(HERE / 'update028-sweep-staged-compatibility.json'),
                  'positive_log_sha256': sha(HERE / 'update028-sweep-staged-compatibility-analysis.log'),
                  'negative_log_sha256': sha(HERE / 'update028-sweep-staged-negative-analysis.log'),
                  'original_recordings_accepted': 0}
    proof = HERE / 'update028-sweep-staged-compat-proof.json'
    write(proof, result)
    print(json.dumps({'proof': proof.name, 'sha256': sha(proof),
                      'positive_and_negative_passed': True, 'staging_copy_only': True},
                     sort_keys=True))


if __name__ == '__main__':
    main()
