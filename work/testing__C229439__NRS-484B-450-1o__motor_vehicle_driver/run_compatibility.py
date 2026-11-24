"""Run and bind exact pinned Core/video positives and missing-device negatives."""
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    manifest_path = folder / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    scratch = next(repo / '.runtime-work' / f'c229439-compat-v{index}'
                   for index in range(3, 100)
                   if not (repo / '.runtime-work' / f'c229439-compat-v{index}').exists())
    scratch.mkdir()
    validator = repo / '.runtime-work/c229439-validator/.lake/build/bin/adapterCheck'
    if not validator.is_file():
        raise ValueError('pinned CPU decoder missing')

    def run(entry):
        short = entry['case_id'].rsplit('__', 1)[-1]
        output = scratch / short
        if output.exists():
            raise ValueError('fresh compatibility output required: ' + short)
        command = [sys.executable, str(repo / 'runtime.py'), 'compatibility',
                   '--manifest', str(manifest_path), '--case', entry['case_id'],
                   '--output', str(output), '--library', str(repo / 'runtime/library'),
                   '--validator', str(validator)]
        driver_log = scratch / (short + '-driver.log')
        with driver_log.open('x') as log:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                       env=os.environ.copy(), timeout=1200)
        if completed.returncode:
            raise ValueError(short + ': compatibility failed: ' + driver_log.read_text()[-1800:])
        receipt = json.loads((output / 'compatibility.json').read_text())
        if (receipt['case_id'] != entry['case_id'] or
                receipt['construction_sha256'] != entry['construction_sha256'] or
                receipt['passed'] is not True):
            raise ValueError(short + ': stale or incomplete exact compatibility receipt')
        return short, output

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        outputs = dict(pool.map(run, manifest['cases']))

    for entry in manifest['cases']:
        short = entry['case_id'].rsplit('__', 1)[-1]
        output = outputs[short]
        case_dir = folder / 'cases' / short
        for name in ('compatibility.json', 'compatibility-analysis.log', 'negative-analysis.log'):
            shutil.copyfile(output / name, case_dir / name)
        entry['compatibility'] = {'receipt': f'cases/{short}/compatibility.json',
                                  'sha256': sha(case_dir / 'compatibility.json'),
                                  'log': f'cases/{short}/compatibility-analysis.log'}
        entry['negative'] = {'log': f'cases/{short}/negative-analysis.log'}
        entry['acquisition'] = {
            'actual_halt_activity': {'entrypoint': 'native_capture.py',
                                     'method': 'independent per-tick context observer',
                                     'evidence': 'actor_rows.json'},
            'body_footprint_history': {'entrypoint': 'native_capture.py',
                                       'method': 'original CARLA actor bounding vertices',
                                       'evidence': 'actor_rows.json'},
            'official_device_instruction': {'entrypoint': 'native_capture.py',
                                            'method': 'reviewed sign packet and per-tick identity join',
                                            'evidence': 'device-source.json and actor_rows.json'},
            'effective_conditions': {'entrypoint': 'native_capture.py',
                                     'method': 'independent per-tick device observer',
                                     'evidence': 'actor_rows.json'},
            'exception_circumstances': {'entrypoint': 'native_capture.py',
                                        'method': 'independent per-tick exception observer',
                                        'evidence': 'actor_rows.json'},
            'capture_quality': {'entrypoint': 'native_camera_writer.py',
                                'method': 'four synchronized original RGB callbacks with pixel hash',
                                'evidence': 'four PNG archives and frame map'}}
        print(short + ': Core/video, native validation, selected analyzer and negative passed', flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
