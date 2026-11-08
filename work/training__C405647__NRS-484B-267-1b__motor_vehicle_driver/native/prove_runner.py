"""CPU proof for every exact C405647 1(b) Native runner preflight."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runner  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove():
    positives = []
    for case in ('reference', 'contrast'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            command = [sys.executable, str(HERE / 'runner.py'), '--check',
                       '--case', case, '--candidate', candidate]
            result = subprocess.run(command, text=True, capture_output=True, check=False)
            if result.returncode:
                raise ValueError('Runner preflight failed: ' + result.stderr)
            receipt = json.loads(result.stdout)
            if (not receipt['passed'] or receipt['native_track_rows'] != 480 or
                receipt['camera_count'] != 4 or receipt['carla_imported'] or
                receipt['physical_success_claimed'] or receipt['original_pixels_seen']):
                raise ValueError('Runner preflight claims physical evidence or lacks capture')
            positives.append({'case': case, 'candidate': candidate,
                              'candidate_sha256': receipt['candidate_sha256']})
    negatives = []
    for case, candidate in (('missing', 'primary'), ('reference', 'missing')):
        try:
            runner.check(case, candidate)
        except ValueError as exc:
            if str(exc) != 'Unknown case or candidate':
                raise
            negatives.append(str(exc))
        else:
            raise ValueError('Unknown variant accepted')
    # Rebind the runner to an isolated copy of one exact bundle, corrupting
    # its Native request hash. The live drafts are never modified.
    original = runner.OUT
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        shutil.copy2(original / 'road.xodr', folder / 'road.xodr')
        sample = folder / 'reference' / 'primary'
        sample.mkdir(parents=True)
        for name in ('config.json', 'requested-tracks.jsonl', 'native-requests.jsonl'):
            shutil.copy2(original / 'reference' / 'primary' / name, sample / name)
        config = json.loads((sample / 'config.json').read_text())
        config['native_requests_sha256'] = '0' * 64
        (sample / 'config.json').write_text(json.dumps(config))
        runner.OUT = folder
        try:
            runner.check('reference', 'primary')
        except ValueError as exc:
            if str(exc) != 'Exact CPU construction hash or identity differs':
                raise
            negatives.append(str(exc))
        else:
            raise ValueError('Corrupted bundle accepted')
        finally:
            runner.OUT = original
    result = {'format': 'c405647-1b-native-runner-cpu-proof-v1',
              'runner_sha256': sha(HERE / 'runner.py'),
              'manifest_sha256': sha(original / 'manifest.json'),
              'positive_preflights': positives, 'negative_preflights': negatives,
              'carla_imported': False, 'original_capture_executed': False,
              'accepted_delivery': False}
    (HERE / 'native-runner-proof.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
