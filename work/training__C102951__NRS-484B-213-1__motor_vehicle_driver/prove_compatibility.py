"""Execute copied CPU runner checks and reject altered exact offline bundles."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(bundle, distance, candidate):
    env = os.environ.copy()
    env['SCENARIO_REPO_ROOT'] = str(ROOT)
    return subprocess.run([sys.executable, str(bundle/'runner.py'), '--check',
                           '--bundle', str(bundle), '--distance', str(distance),
                           '--candidate', candidate], text=True, capture_output=True,
                          timeout=30, env=env)


def prove():
    manifest = json.loads((CASE/'offline'/'manifest.json').read_text())
    positives, negatives = [], []
    for entry in manifest['entries']:
        folder = CASE/entry['bundle']
        actual = {name: sha(folder/name) for name in entry['sha256']}
        if actual != entry['sha256']:
            raise ValueError('Copied bundle manifest hash differs')
        result = invoke(folder, entry['distance_m'], entry['candidate_id'])
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        outcome = json.loads(result.stdout)
        if not outcome['passed'] or outcome['carla_imported'] or outcome['original_native_observed']:
            raise AssertionError('Copied runner claimed original Native evidence')
        positives.append({'case_id': entry['case_id'],
                          'candidate_id': entry['candidate_id'],
                          'bundle_sha256': sha(folder/'config.json'), 'passed': True})
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            altered = Path(temporary)/'bundle'
            shutil.copytree(folder, altered)
            track = altered/'requested-tracks.jsonl'
            track.write_text(track.read_text().replace('"frame": 0', '"frame": 99', 1))
            changed = invoke(altered, entry['distance_m'], entry['candidate_id'])
            if changed.returncode == 0:
                raise AssertionError('Changed copied track accepted')
            negatives.append({'case_id': entry['case_id'],
                              'candidate_id': entry['candidate_id'],
                              'mutation': 'requested_track_bytes', 'rejected': True})
            shutil.copy2(folder/'requested-tracks.jsonl', track)
            source = altered/'assignment-source.json'
            source.write_text(source.read_text()+' ')
            changed = invoke(altered, entry['distance_m'], entry['candidate_id'])
            if changed.returncode == 0:
                raise AssertionError('Changed copied assignment source accepted')
            negatives.append({'case_id': entry['case_id'],
                              'candidate_id': entry['candidate_id'],
                              'mutation': 'frozen_assignment_bytes', 'rejected': True})
    proof = {'format': 'c102951-exact-compatibility-proof-v1',
             'assignment_id': CASE.name,
             'offline_manifest_sha256': sha(CASE/'offline'/'manifest.json'),
             'positives': positives, 'negatives': negatives,
             'original_native_observed': False, 'delivery_ready': False}
    path = CASE/'offline'/'proof-compatibility.json'
    path.write_text(json.dumps(proof, indent=2)+'\n')
    return proof


if __name__ == '__main__':
    result = prove()
    print(json.dumps({'positives': len(result['positives']),
                      'negatives': len(result['negatives'])}))
