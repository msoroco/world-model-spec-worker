"""Independent exact-source and subprocess audit of copied C102951 bundles."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[1]
AID = CASE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(folder, distance, candidate):
    env = os.environ.copy()
    env['SCENARIO_REPO_ROOT'] = str(ROOT)
    return subprocess.run([sys.executable, str(folder/'runner.py'), '--check',
                           '--bundle', str(folder), '--distance', str(distance),
                           '--candidate', candidate], env=env, text=True,
                          capture_output=True, timeout=30)


def audit():
    manifest_path = CASE/'offline'/'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    proof_path = CASE/'offline'/'proof-compatibility.json'
    proof = json.loads(proof_path.read_text())
    expected_pairs = {(d, c) for d in (70, 120, 170)
                      for c in ('primary', 'fallback1', 'fallback2', 'fallback3')}
    if (manifest['format'] != 'c102951-exact-offline-bundles-v1' or
            manifest['assignment_id'] != AID or manifest['original_native_observed'] or
            manifest['delivery_ready'] or
            manifest['construction_manifest_sha256'] != sha(CASE/'native'/'drafts'/'manifest.json') or
            proof['format'] != 'c102951-exact-compatibility-proof-v1' or
            proof['offline_manifest_sha256'] != sha(manifest_path) or
            proof['original_native_observed'] or proof['delivery_ready']):
        raise ValueError('Exact package provenance or status differs')
    if {(r['distance_m'], r['candidate_id']) for r in manifest['entries']} != expected_pairs:
        raise ValueError('Package coverage differs')
    if len(proof['positives']) != 12 or len(proof['negatives']) != 24 or not all(
            item['rejected'] is True for item in proof['negatives']):
        raise ValueError('Compatibility proof coverage differs')
    checks, rejections = 0, 0
    for entry in manifest['entries']:
        distance, candidate = entry['distance_m'], entry['candidate_id']
        folder = CASE/entry['bundle']
        if (entry['case_id'] != AID+'__'+str(distance) or
                entry['status'] != 'unselected_native_request'):
            raise ValueError('Exact package case or status differs')
        actual = {name: sha(folder/name) for name in entry['sha256']}
        if actual != entry['sha256']:
            raise ValueError('Copied package bytes differ')
        source_pairs = {
            'config.json': CASE/'native'/'drafts'/str(distance)/candidate/'config.json',
            'requested-tracks.jsonl': CASE/'native'/'drafts'/str(distance)/candidate/'requested-tracks.jsonl',
            'road.xodr': CASE/'native'/'road.xodr',
            'assignment-source.json': ROOT/'inputs'/AID/'assignment.json',
            'case-plan.json': CASE/'case-plan.json',
            'runner.py': CASE/'native'/'runner.py',
            'measure_pass.py': CASE/'native'/'measure_pass.py',
            'triggers.py': CASE/'native'/'triggers.py',
            'measurement-contract.json': CASE/'native'/'measurement-contract.json'}
        if actual != {name: sha(path) for name, path in source_pairs.items()}:
            raise ValueError('Copied package differs from current exact source')
        lanes = {int(l.attrib['id']): l.attrib['type'] for l in
                 ET.parse(folder/'road.xodr').findall('.//lane')}
        if lanes != {-1: 'driving', 0: 'none', 1: 'driving'}:
            raise ValueError('Copied road lane geometry differs')
        result = run(folder, distance, candidate)
        if result.returncode != 0 or json.loads(result.stdout)['requested_frames'] != 480:
            raise ValueError('Copied runner CPU check failed')
        checks += 1
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            changed = Path(temporary)/'bundle'
            shutil.copytree(folder, changed)
            track = changed/'requested-tracks.jsonl'
            track.write_bytes(track.read_bytes()+b' ')
            if run(changed, distance, candidate).returncode == 0:
                raise ValueError('Altered track accepted by copied runner')
            rejections += 1
            shutil.copy2(folder/'requested-tracks.jsonl', track)
            source = changed/'assignment-source.json'
            source.write_bytes(source.read_bytes()+b' ')
            if run(changed, distance, candidate).returncode == 0:
                raise ValueError('Altered frozen assignment accepted by copied runner')
            rejections += 1
    receipt = {'format': 'c102951-independent-package-audit-v1',
               'assignment_id': AID,
               'manifest_sha256': sha(manifest_path), 'proof_sha256': sha(proof_path),
               'copied_bundles_checked': checks,
               'altered_source_rejections_replayed': rejections,
               'original_native_observed': False, 'delivery_ready': False}
    (CASE/'offline'/'package-audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(audit()))
