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
        positives.append({'case': case, 'candidate': candidate,
                          'bundle_sha256': {name: sha(bundle/name) for name in entry['file_sha256']}})
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
