"""Copy exact C102951 Native request bundles with frozen and authored sources."""
import hashlib
import json
from pathlib import Path
import shutil

CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[1]
NATIVE = CASE/'native'
OUT = CASE/'offline'/'bundles'
AID = CASE.name
FILES = ('config.json', 'requested-tracks.jsonl', 'road.xodr',
         'assignment-source.json', 'case-plan.json', 'runner.py',
         'measure_pass.py', 'prepare_pass.py', 'triggers.py',
         'measurement-contract.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries = []
    for distance in (70, 120, 170):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            source = NATIVE/'drafts'/str(distance)/candidate
            dest = OUT/str(distance)/candidate
            dest.mkdir(parents=True, exist_ok=True)
            inputs = {'config.json': source/'config.json',
                      'requested-tracks.jsonl': source/'requested-tracks.jsonl',
                      'road.xodr': NATIVE/'road.xodr',
                      'assignment-source.json': ROOT/'inputs'/AID/'assignment.json',
                      'case-plan.json': CASE/'case-plan.json',
                      'runner.py': NATIVE/'runner.py',
                      'measure_pass.py': NATIVE/'measure_pass.py',
                      'prepare_pass.py': NATIVE/'prepare_pass.py',
                      'triggers.py': NATIVE/'triggers.py',
                      'measurement-contract.json': NATIVE/'measurement-contract.json'}
            for name, path in inputs.items():
                shutil.copy2(path, dest/name)
            hashes = {name: sha(dest/name) for name in FILES}
            entries.append({'case_id': AID+'__'+str(distance),
                            'distance_m': distance, 'candidate_id': candidate,
                            'bundle': str(dest.relative_to(CASE)), 'sha256': hashes,
                            'status': 'unselected_native_request'})
    manifest = {'format': 'c102951-exact-offline-bundles-v1',
                'assignment_id': AID,
                'construction_manifest_sha256': sha(NATIVE/'drafts/manifest.json'),
                'entries': entries, 'original_native_observed': False,
                'delivery_ready': False}
    path = CASE/'offline'/'manifest.json'
    path.write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    print(json.dumps({'bundles': len(build()['entries'])}))
