"""Exercise all exact heavy-vehicle bundles and altered-source rejections."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CASE = Path(__file__).resolve().parent
OFFLINE = CASE/'offline'
SOURCES = ('assignment-source.json', 'case-plan.json', 'road.xodr',
           'requested-tracks.jsonl')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(bundle, case, candidate):
    return subprocess.run([sys.executable, str(bundle/'runner.py'),
                           '--bundle', str(bundle), '--case', case,
                           '--candidate', candidate, '--check'],
                          text=True, capture_output=True)


def prove():
    manifest = json.loads((OFFLINE/'manifest.json').read_text())
    positives, negatives = [], []
    for entry in manifest['entries']:
        case, candidate = entry['case_suffix'], entry['candidate_id']
        bundle = CASE/entry['bundle']
        result = run(bundle, case, candidate)
        if result.returncode or not json.loads(result.stdout)['passed']:
            raise AssertionError('Exact offline positive failed: '+case+'/'+candidate)
        saved_fixture = CASE/'native/saved-fixtures'/case/candidate
        saved_run = subprocess.run([sys.executable, str(bundle/'measure_saved.py'),
                                    str(saved_fixture)], text=True, capture_output=True, check=True)
        saved_measure = json.loads(saved_run.stdout)
        if saved_measure['frames'] != 480 or saved_measure['source_kind'] != 'synthetic_cpu':
            raise AssertionError('Packaged saved processor positive failed')
        context_run = subprocess.run([sys.executable, str(bundle/'measure_context.py'),
                                      '--attempt', str(saved_fixture), '--context',
                                      str(saved_fixture/'city-context.json')],
                                     text=True, capture_output=True, check=True)
        context_measure = json.loads(context_run.stdout)
        if context_measure['frames'] != 480 or context_measure['authority_kind'] != 'synthetic_cpu':
            raise AssertionError('Packaged spatial processor positive failed')
        camera_visible = None
        if candidate == 'fallback3':
            camera = CASE/'native/camera-fixtures'/case/'clear'
            camera_run = subprocess.run([sys.executable, str(bundle/'measure_camera.py'),
                                         str(saved_fixture), str(camera/'camera-review.jsonl'),
                                         str(camera/'sidewalk-video-stub.txt')],
                                        text=True, capture_output=True, check=True)
            camera_visible = json.loads(camera_run.stdout)['visible_frames']
            if camera_visible != 420:
                raise AssertionError('Packaged camera processor positive failed')
        positives.append({'case': case, 'candidate': candidate,
                          'bundle_sha256': {name: sha(bundle/name) for name in entry['file_sha256']},
                          'packaged_saved_frames':saved_measure['frames'],
                          'packaged_spatial_outside_entrance_frames':context_measure['moving_city_sidewalk_outside_entrance_frames'],
                          'packaged_clear_camera_visible_frames':camera_visible})
        for name in SOURCES:
            with tempfile.TemporaryDirectory(dir=OFFLINE) as temporary:
                altered = Path(temporary)/'candidate'
                shutil.copytree(bundle, altered)
                with (altered/name).open('ab') as stream:
                    stream.write(b' ')
                result = run(altered, case, candidate)
                if result.returncode == 0 or 'Exact frozen or authored source hash differs' not in result.stderr:
                    raise AssertionError('Altered source accepted: '+case+'/'+candidate+'/'+name)
                negatives.append({'case': case, 'candidate': candidate,
                                  'altered_file': name, 'rejected': True})
    proof = {'format': 'c422978-heavy-offline-compatibility-proof-v1',
             'manifest_sha256': sha(OFFLINE/'manifest.json'),
             'positives': positives, 'negatives': negatives,
             'synthetic_or_cpu_scope_only': True,
             'original_native_observed': False, 'delivery_ready': False}
    (OFFLINE/'proof-compatibility.json').write_text(json.dumps(proof, indent=2)+'\n')
    return proof


if __name__ == '__main__':
    result = prove()
    print(json.dumps({'positives': len(result['positives']),
                      'negatives': len(result['negatives'])}))
