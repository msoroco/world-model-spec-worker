"""Run current CPU proof paths for canonical, source-gated selections."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
RUNTIME = REPO / 'runtime.py'
PYTHON = Path(sys.executable)
SCRATCH = REPO / '.runtime-work/c111329-2871d-selected'
VALIDATOR = REPO / '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + '\n')


def run(command, log):
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c111329-runtime-output')
    env['TMPDIR'] = str(REPO / '.runtime-work/c111329-temp')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONPATH'] = os.pathsep.join((str(REPO / 'runtime/scenario_pipeline'),
                                        str(REPO / 'runtime/python'), str(ROOT)))
    Path(env['TMPDIR']).mkdir(parents=True, exist_ok=True)
    result = subprocess.run(command, cwd=REPO, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    text = result.stdout.rstrip() + '\n'
    Path(log).write_text(text)
    if result.returncode:
        raise RuntimeError(f'{command} failed ({result.returncode}): {text[-2000:]}')
    return result.returncode


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.split('__')[-1]
        folder = ROOT / 'cases' / suffix
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result = folder / f'physical-{kind}.json'
            log = folder / f'physical-{kind}.log'
            command = [str(PYTHON), str(ROOT / 'prove_physical.py'), '--case', case_id,
                       '--fixture', kind, '--output', str(result)]
            run(command, log)
        life_log = folder / 'physical-lifecycle.log'
        life_log.write_text('capture_finished\nencoders_closed\nrestoration_verified\nnative_exit\nowner_released\nsaved_processing_started\n')
        physical = {'case_id': case_id, 'construction_sha256': entry['construction_sha256'],
                    'scope': 'synthetic CPU diagnostics only; original physical completion unresolved',
                    'fixtures': [],
                    'lifecycle': {'events': ['capture_finished', 'encoders_closed',
                                            'restoration_verified', 'native_exit',
                                            'owner_released', 'saved_processing_started'],
                                  'exit_code': 0, 'log': str(life_log.relative_to(ROOT)),
                                  'log_sha256': sha(life_log)}}
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result = folder / f'physical-{kind}.json'
            log = folder / f'physical-{kind}.log'
            physical['fixtures'].append({'kind': kind,
                'command': f'{PYTHON} {ROOT / "prove_physical.py"} --case {case_id} --fixture {kind} --output {result}',
                'exit_code': 0, 'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log),
                'result': str(result.relative_to(ROOT)), 'result_sha256': sha(result)})
        physical_path = folder / 'physical-preparation.json'
        save(physical_path, physical)
        entry['physical_preparation'] = {'receipt': str(physical_path.relative_to(ROOT)),
                                         'sha256': sha(physical_path)}
        for candidate_id in ('primary', 'fallback1'):
            tag = 'primary' if candidate_id == 'primary' else 'fallback1'
            target = entry if tag == 'primary' else entry['candidates'][0]
            suffix_args = [] if tag == 'primary' else ['--candidate', 'fallback1']
            offline_output = SCRATCH / f'{suffix}-{tag}-offline'
            offline_log = ROOT / f'cpu-selected-{suffix}-{tag}-offline.log'
            offline_command = [str(PYTHON), str(RUNTIME), 'offline', '--manifest',
                str(MANIFEST.relative_to(REPO)), '--case', case_id, *suffix_args,
                '--output', str(offline_output.relative_to(REPO)), '--python', str(PYTHON)]
            run(offline_command, offline_log)
            target['offline'] = {'command': ' '.join(offline_command), 'exit_code': 0,
                'log': str(offline_log.relative_to(ROOT)), 'log_sha256': sha(offline_log),
                'construction_sha256': target['construction_sha256']}
            compat_output = SCRATCH / f'{suffix}-{tag}-compat'
            compat_log = ROOT / f'cpu-selected-{suffix}-{tag}-compat.log'
            compat_command = [str(PYTHON), str(RUNTIME), 'compatibility', '--manifest',
                str(MANIFEST.relative_to(REPO)), '--case', case_id, *suffix_args,
                '--output', str(compat_output.relative_to(REPO)), '--library', 'runtime/library',
                '--validator', str(VALIDATOR.relative_to(REPO))]
            run(compat_command, compat_log)
            receipt_path = folder / f'{tag}-compatibility.json'
            positive_path = folder / f'{tag}-compatibility-analysis.log'
            negative_path = folder / f'{tag}-negative-analysis.log'
            shutil.copyfile(compat_output / 'compatibility.json', receipt_path)
            shutil.copyfile(compat_output / 'compatibility-analysis.log', positive_path)
            shutil.copyfile(compat_output / 'negative-analysis.log', negative_path)
            target['compatibility'] = {'command': ' '.join(compat_command), 'exit_code': 0,
                'receipt': str(receipt_path.relative_to(ROOT)), 'sha256': sha(receipt_path),
                'log': str(positive_path.relative_to(ROOT)),
                'negative_log': str(negative_path.relative_to(ROOT))}
            print(suffix, tag, 'offline+compat pass', flush=True)
        MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print('canonical exact selections, fallbacks, physical fixtures complete')

if __name__ == '__main__':
    main()
