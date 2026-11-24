"""Run current-runtime Native offline checks for all 56 short constructions."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
MANIFEST = WORK / 'current-runtime-refresh-short-draft-manifest.json'
SCRATCH = REPO / '.runtime-work/owner150142/runtime-refresh-short-offline'
PORTABLE = WORK / 'current-runtime-refresh-short-offline'
INDEX = WORK / 'current-runtime-refresh-short-offline-index.json'
SHORTS = {'reference', 'contrast', 'ordinary_red_signed',
          'armored_car_signed_business', 'armored_car_signed_no_business',
          'armored_car_unsigned_business', 'armored_car_unsigned_no_business',
          'emergency_vehicle_signed_business',
          'emergency_vehicle_signed_no_business',
          'emergency_vehicle_unsigned_business',
          'emergency_vehicle_unsigned_no_business',
          'mail_adjacent_deposit', 'mail_adjacent_no_deposit',
          'mail_no_box_deposit'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='wb', dir=SCRATCH, delete=False) as stream:
        stream.write(value)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def one(item):
    case_id, candidate, field = item
    slug = case_id.removeprefix(WORK.name + '__')
    target = PORTABLE / slug / (candidate + '.log')
    if target.is_file():
        proof = json.loads(target.read_text())
    else:
        bundle = SCRATCH / slug / candidate
        if bundle.exists():
            raise ValueError('Inspect incomplete offline scratch before rerun: ' + str(bundle))
        bundle.parent.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, str(REPO / 'runtime.py'), 'offline',
                   '--manifest', str(MANIFEST), '--case', case_id,
                   '--candidate', candidate, '--output', str(bundle)]
        env = os.environ.copy()
        env.update(PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(SCRATCH),
                   SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'output'))
        run = subprocess.run(command, cwd=REPO, env=env,
                             capture_output=True, text=True)
        if run.returncode:
            (bundle.parent / (candidate + '.failed.log')).write_text(
                (run.stdout + run.stderr).rstrip() + '\n')
            raise ValueError('Current-runtime offline failed: ' + slug + '/' + candidate)
        proof = json.loads(run.stdout)
        atomic_write(target, (json.dumps(proof, sort_keys=True) + '\n').encode())
    if (proof['case_id'] != case_id or proof['candidate_id'] != candidate or
            proof['offline_passed'] is not True or
            proof['simulation_started'] is not False or
            field['construction_sha256'] != sha(WORK / field['construction'])):
        raise ValueError('Offline receipt or construction changed: ' + slug + '/' + candidate)
    return {'case_id': case_id, 'candidate_id': candidate,
            'construction_sha256': field['construction_sha256'],
            'log': str(target.relative_to(WORK)), 'log_sha256': sha(target)}


def run():
    manifest = json.loads(MANIFEST.read_text())
    current = sha(REPO / 'runtime/SOURCE-MANIFEST.json')
    if manifest['runtime_manifest_sha256'] != current:
        raise ValueError('Offline draft binds another runtime')
    jobs = []
    for entry in manifest['cases']:
        if entry['case_id'].removeprefix(WORK.name + '__') not in SHORTS:
            continue
        jobs.append((entry['case_id'], 'primary', entry))
        jobs.extend((entry['case_id'], item['id'], item)
                    for item in entry['candidates'])
    if len(jobs) != 56:
        raise ValueError('Expected 14 short cases with four candidates each')
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(one, item) for item in jobs]):
            rows.append(future.result())
            index = {'format': 'c150142-current-runtime-refresh-short-offline-v1',
                     'manifest_sha256': sha(MANIFEST),
                     'runtime_manifest_sha256': current,
                     'completed': len(rows), 'expected': 56,
                     'rows': sorted(rows, key=lambda x: (x['case_id'], x['candidate_id'])),
                     'delivery_ready': False}
            atomic_write(INDEX, (json.dumps(index, sort_keys=True, indent=2) + '\n').encode())
    return {'completed': len(rows), 'expected': 56, 'index_sha256': sha(INDEX),
            'runtime_manifest_sha256': current}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
