"""Materialize eight exact unselected heavy-vehicle CPU capture bundles."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[1]
NATIVE = CASE/'native'
AID = CASE.name
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def build():
    request = json.loads((NATIVE/'drafts/manifest.json').read_text())
    assignment = ROOT/'inputs'/AID/'assignment.json'
    plan = CASE/'case-plan.json'
    road = NATIVE/'road.xodr'
    for path, key in ((assignment,'assignment_sha256'), (plan,'case_plan_sha256'),
                      (road,'road_sha256')):
        if sha(path) != request[key]:
            raise ValueError('Native request source differs before offline packaging: '+key)
    entries = []
    for case in CASES:
        for candidate in CANDIDATES:
            source = NATIVE/'drafts'/case/candidate
            config = json.loads((source/'config.json').read_text())
            if (config['case_suffix'] != case or config['candidate_id'] != candidate or
                    config['assignment_sha256'] != sha(assignment) or
                    config['case_plan_sha256'] != sha(plan) or
                    config['road_sha256'] != sha(road) or
                    config['tracks_sha256'] != sha(source/'requested-tracks.jsonl')):
                raise ValueError('Native exact candidate differs before offline packaging')
            target = CASE/'offline'/case/candidate
            target.mkdir(parents=True, exist_ok=True)
            files = {'assignment-source.json': assignment,
                     'case-plan.json': plan, 'road.xodr': road,
                     'runner.py': NATIVE/'runner.py',
                     'triggers.py': NATIVE/'triggers.py',
                     'measure_saved.py': NATIVE/'measure_saved.py',
                     'measure_camera.py': NATIVE/'measure_camera.py',
                     'measure_context.py': NATIVE/'measure_context.py',
                     'prepare_context.py': NATIVE/'prepare_context.py',
                     'measure_exception.py': NATIVE/'measure_exception.py',
                     'measurement-contract.json': NATIVE/'measurement-contract.json',
                     'config.json': source/'config.json',
                     'requested-tracks.jsonl': source/'requested-tracks.jsonl'}
            for name, original in files.items():
                shutil.copyfile(original, target/name)
            command = [sys.executable, str(target/'runner.py'),
                       '--bundle', str(target), '--case', case,
                       '--candidate', candidate, '--check']
            process = subprocess.run(command, text=True, capture_output=True, check=True)
            result = json.loads(process.stdout)
            if not result['passed'] or result['carla_imported']:
                raise ValueError('Offline CPU entry check failed')
            entries.append({'case_id': AID+'__'+case, 'case_suffix': case,
                            'candidate_id': candidate,
                            'bundle': str(target.relative_to(CASE)),
                            'file_sha256': {name: sha(target/name) for name in files},
                            'cpu_entry_check': result,
                            'status': 'unselected_cpu_bundle'})
    manifest = {'format': 'c422978-heavy-exact-offline-cpu-v1',
                'assignment_id': AID, 'request_manifest_sha256': sha(NATIVE/'drafts/manifest.json'),
                'runtime_manifest_sha256': json.loads((ROOT/'batch.json').read_text())['runtime']['source_manifest_sha256'],
                'runner_sha256': sha(NATIVE/'runner.py'),
                'entries': entries, 'original_native_observed': False,
                'physical_or_legal_acceptance': False, 'delivery_ready': False}
    write(CASE/'offline/manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'bundles': len(build()['entries'])}))
