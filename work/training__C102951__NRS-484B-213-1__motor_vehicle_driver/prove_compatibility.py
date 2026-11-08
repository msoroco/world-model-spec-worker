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


def invoke_preparer(bundle, raw, output):
    return subprocess.run([sys.executable, str(bundle/'prepare_pass.py'),
                           '--raw-folder', str(raw), '--review',
                           str(raw/'sightline-review.json'), '--output', str(output),
                           '--config', str(bundle/'config.json')],
                          text=True, capture_output=True, timeout=30)


def invoke_response(bundle, saved):
    return subprocess.run([sys.executable, str(bundle/'measure_response.py'), str(saved)],
                          text=True, capture_output=True, timeout=30)


def prove():
    manifest = json.loads((CASE/'offline'/'manifest.json').read_text())
    positives, negatives, preparation_positives, preparation_negatives = [], [], [], []
    response_positives, response_negatives = [], []
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
        if entry['candidate_id'] == 'primary':
            raw = CASE/'native'/'raw-fixtures'/str(entry['distance_m'])
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                root = Path(temporary)
                result = invoke_preparer(folder, raw, root/'prepared')
                if result.returncode != 0:
                    raise AssertionError(result.stderr)
                receipt = json.loads(result.stdout)
                if receipt['measurement']['entry_oncoming_body_gap_m'] != entry['distance_m']:
                    raise AssertionError('Copied saved preparer changed entry gap')
                preparation_positives.append({'case_id': entry['case_id'],
                                              'candidate_id': 'primary',
                                              'prepared_saved_hashes': receipt['saved_hashes'],
                                              'passed': True})
                response = invoke_response(folder, root/'prepared')
                if response.returncode != 0:
                    raise AssertionError(response.stderr)
                response_result = json.loads(response.stdout)
                if (response_result['source_hashes'] != receipt['saved_hashes'] or
                        response_result['delivery_ready'] or
                        response_result['response']['oncoming']['five_frame_hard_deceleration_count'] != 0):
                    raise AssertionError('Copied response measurement differs')
                response_positives.append({'case_id': entry['case_id'],
                                           'source_hashes': response_result['source_hashes'],
                                           'passed': True})
                altered_saved = root/'changed-saved'
                shutil.copytree(root/'prepared', altered_saved)
                saved_rows = altered_saved/'native-observed.jsonl'
                saved_rows.write_bytes(saved_rows.read_bytes()+b' ')
                changed = invoke_response(folder, altered_saved)
                if changed.returncode == 0:
                    raise AssertionError('Copied response accepted altered saved rows')
                response_negatives.append({'case_id': entry['case_id'],
                                           'mutation': 'saved_rows_bytes', 'rejected': True})
                changed_raw = root/'changed-raw'
                shutil.copytree(raw, changed_raw)
                (changed_raw/'forward-video-stub.txt').write_text('altered copied video bytes\n')
                changed = invoke_preparer(folder, changed_raw, root/'changed-prepared')
                if changed.returncode == 0:
                    raise AssertionError('Copied preparer accepted altered video')
                preparation_negatives.append({'case_id': entry['case_id'],
                                              'candidate_id': 'primary',
                                              'mutation': 'forward_video_bytes',
                                              'rejected': True})
    proof = {'format': 'c102951-exact-compatibility-proof-v1',
             'assignment_id': CASE.name,
             'offline_manifest_sha256': sha(CASE/'offline'/'manifest.json'),
             'positives': positives, 'negatives': negatives,
             'saved_preparation_positives': preparation_positives,
             'saved_preparation_negatives': preparation_negatives,
             'copied_response_positives': response_positives,
             'copied_response_negatives': response_negatives,
             'original_native_observed': False, 'delivery_ready': False}
    path = CASE/'offline'/'proof-compatibility.json'
    path.write_text(json.dumps(proof, indent=2)+'\n')
    return proof


if __name__ == '__main__':
    result = prove()
    print(json.dumps({'positives': len(result['positives']),
                      'negatives': len(result['negatives']),
                      'saved_preparation_positives': len(result['saved_preparation_positives']),
                      'saved_preparation_negatives': len(result['saved_preparation_negatives'])}))
