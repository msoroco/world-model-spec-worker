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


def run_preparer(bundle, raw, output):
    return subprocess.run([sys.executable, str(bundle/'prepare_pass.py'),
                           '--raw-folder', str(raw), '--review',
                           str(raw/'sightline-review.json'), '--output', str(output),
                           '--config', str(bundle/'config.json')],
                          text=True, capture_output=True, timeout=30)


def run_response(bundle, saved):
    return subprocess.run([sys.executable, str(bundle/'measure_response.py'), str(saved)],
                          text=True, capture_output=True, timeout=30)


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
    if (len(proof.get('saved_preparation_positives', [])) != 3 or
            len(proof.get('saved_preparation_negatives', [])) != 3 or
            not all(item['rejected'] is True for item in proof['saved_preparation_negatives'])):
        raise ValueError('Copied saved-preparation coverage differs')
    if (len(proof.get('copied_response_positives', [])) != 3 or
            len(proof.get('copied_response_negatives', [])) != 3 or
            not all(item['rejected'] is True for item in proof['copied_response_negatives'])):
        raise ValueError('Copied response coverage differs')
    checks, rejections, preparation_checks, preparation_rejections = 0, 0, 0, 0
    response_checks, response_rejections = 0, 0
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
            'measure_response.py': CASE/'native'/'measure_response.py',
            'prepare_pass.py': CASE/'native'/'prepare_pass.py',
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
        if candidate == 'primary':
            raw = CASE/'native'/'raw-fixtures'/str(distance)
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                root = Path(temporary)
                result = run_preparer(folder, raw, root/'prepared')
                if result.returncode != 0:
                    raise ValueError('Copied raw-to-saved preparer failed: '+result.stderr)
                receipt = json.loads(result.stdout)
                if (receipt['measurement']['entry_oncoming_body_gap_m'] != distance or
                        receipt['saved_hashes'] != {name: sha(root/'prepared'/name)
                                                     for name in ('native-observed.jsonl',
                                                                  'road-readback.json')}):
                    raise ValueError('Copied saved processor result differs')
                expected_receipt = next(item for item in proof['saved_preparation_positives']
                                        if item['case_id'] == entry['case_id'])
                if expected_receipt['prepared_saved_hashes'] != receipt['saved_hashes']:
                    raise ValueError('Copied saved preparation hash differs from proof')
                preparation_checks += 1
                response = run_response(folder, root/'prepared')
                if response.returncode != 0:
                    raise ValueError('Copied response failed: '+response.stderr)
                measured = json.loads(response.stdout)
                expected_response = next(item for item in proof['copied_response_positives']
                                         if item['case_id'] == entry['case_id'])
                if (measured['source_hashes'] != receipt['saved_hashes'] or
                        measured['source_hashes'] != expected_response['source_hashes'] or
                        measured['delivery_ready']):
                    raise ValueError('Copied response source or status differs')
                response_checks += 1
                changed_saved = root/'changed-saved'
                shutil.copytree(root/'prepared', changed_saved)
                rows = changed_saved/'native-observed.jsonl'
                rows.write_bytes(rows.read_bytes()+b' ')
                if run_response(folder, changed_saved).returncode == 0:
                    raise ValueError('Copied response accepted altered saved rows')
                response_rejections += 1
                changed_raw = root/'changed-raw'
                shutil.copytree(raw, changed_raw)
                (changed_raw/'forward-video-stub.txt').write_text('independent altered video\n')
                if run_preparer(folder, changed_raw, root/'changed-prepared').returncode == 0:
                    raise ValueError('Copied preparer accepted altered video')
                preparation_rejections += 1
    receipt = {'format': 'c102951-independent-package-audit-v1',
               'assignment_id': AID,
               'manifest_sha256': sha(manifest_path), 'proof_sha256': sha(proof_path),
               'copied_bundles_checked': checks,
               'altered_source_rejections_replayed': rejections,
               'copied_saved_preparations_checked': preparation_checks,
               'copied_video_rejections_replayed': preparation_rejections,
               'copied_responses_checked': response_checks,
               'copied_response_rejections_replayed': response_rejections,
               'original_native_observed': False, 'delivery_ready': False}
    (CASE/'offline'/'package-audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(audit()))
