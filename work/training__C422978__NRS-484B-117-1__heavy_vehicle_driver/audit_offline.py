"""Independently verify copied heavy-vehicle CPU bundles and source negatives."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OFFLINE = HERE/'offline'
AID = HERE.name
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
SOURCE_FILES = ('assignment-source.json', 'case-plan.json', 'road.xodr',
                'requested-tracks.jsonl')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(bundle, case, candidate):
    return subprocess.run((sys.executable, str(bundle/'runner.py'), '--bundle', str(bundle),
                           '--case', case, '--candidate', candidate, '--check'),
                          capture_output=True, text=True)


def audit():
    manifest_path = OFFLINE/'manifest.json'
    proof_path = OFFLINE/'proof-compatibility.json'
    manifest = json.loads(manifest_path.read_text())
    proof = json.loads(proof_path.read_text())
    if (manifest['format'] != 'c422978-heavy-exact-offline-cpu-v1' or
            manifest['assignment_id'] != AID or
            proof['manifest_sha256'] != digest(manifest_path) or
            len(manifest['entries']) != 8 or len(proof['positives']) != 8 or
            len(proof['negatives']) != 32):
        raise ValueError('Offline manifest/proof scope differs')
    if any(manifest[key] for key in ('original_native_observed',
                                    'physical_or_legal_acceptance', 'delivery_ready')):
        raise ValueError('Offline bundle overclaims acceptance')
    if (manifest['request_manifest_sha256'] != digest(HERE/'native/drafts/manifest.json') or
            manifest['runner_sha256'] != digest(HERE/'native/runner.py')):
        raise ValueError('Offline bundle current code or request differs')
    if manifest['runtime_manifest_sha256'] != json.loads((ROOT/'batch.json').read_text())['runtime']['source_manifest_sha256']:
        raise ValueError('Offline bundle runtime source manifest differs')
    seen, rejection_count = set(), 0
    for entry in manifest['entries']:
        case, candidate = entry['case_suffix'], entry['candidate_id']
        if case not in CASES or candidate not in CANDIDATES or (case,candidate) in seen:
            raise ValueError('Offline candidate identity differs')
        seen.add((case,candidate))
        expected_bundle = OFFLINE/case/candidate
        if (HERE/entry['bundle']).resolve() != expected_bundle.resolve():
            raise ValueError('Offline bundle path differs')
        expected = {'assignment-source.json': ROOT/'inputs'/AID/'assignment.json',
                    'case-plan.json': HERE/'case-plan.json',
                    'road.xodr': HERE/'native/road.xodr',
                    'runner.py': HERE/'native/runner.py',
                    'triggers.py': HERE/'native/triggers.py',
                    'config.json': HERE/'native/drafts'/case/candidate/'config.json',
                    'requested-tracks.jsonl': HERE/'native/drafts'/case/candidate/'requested-tracks.jsonl'}
        if set(entry['file_sha256']) != set(expected):
            raise ValueError('Offline file set differs')
        for name, original in expected.items():
            if digest(expected_bundle/name) != digest(original) or digest(original) != entry['file_sha256'][name]:
                raise ValueError('Offline source bytes differ: '+name)
        rows = [json.loads(line) for line in (expected_bundle/'requested-tracks.jsonl').read_text().splitlines()]
        config = json.loads((expected_bundle/'config.json').read_text())
        if (len(rows) != 480 or config['case_suffix'] != case or
                config['candidate_id'] != candidate or
                any(row['frame'] != i or row['subject_blueprint_request'] != 'vehicle.carlamotors.carlacola'
                    for i,row in enumerate(rows))):
            raise ValueError('Offline requested actor frames differ')
        positive = command(expected_bundle, case, candidate)
        if positive.returncode or not json.loads(positive.stdout)['passed']:
            raise ValueError('Offline positive recheck failed')
        for name in SOURCE_FILES:
            with tempfile.TemporaryDirectory(dir=OFFLINE) as temporary:
                altered = Path(temporary)/'copy'
                shutil.copytree(expected_bundle, altered)
                (altered/name).write_bytes((altered/name).read_bytes()+b'\n')
                negative = command(altered, case, candidate)
                if negative.returncode == 0:
                    raise ValueError('Offline altered source accepted: '+name)
                rejection_count += 1
    if seen != {(case,candidate) for case in CASES for candidate in CANDIDATES}:
        raise ValueError('Offline candidate coverage differs')
    if {(n['case'],n['candidate'],n['altered_file']) for n in proof['negatives']} != {
            (case,candidate,name) for case,candidate in seen for name in SOURCE_FILES}:
        raise ValueError('Offline recorded negative coverage differs')
    result = {'format': 'c422978-heavy-independent-offline-audit-v1',
              'manifest_sha256': digest(manifest_path), 'proof_sha256': digest(proof_path),
              'exact_positive_bundles': len(seen), 'altered_source_rejections': rejection_count,
              'original_native_observed': False, 'delivery_ready': False}
    (OFFLINE/'independent-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    result = audit()
    print(json.dumps({'positives': result['exact_positive_bundles'],
                      'negatives': result['altered_source_rejections']}))
