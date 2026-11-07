"""CPU preflight of all eight proposed Native construction policies."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / 'native/runner.py'


def prove():
    rows = []
    for case in ('witness_1', 'witness_2'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            result = subprocess.run([sys.executable, str(RUNNER), '--check',
                                     '--case', case, '--candidate', candidate],
                                    text=True, capture_output=True, check=True)
            packet = json.loads(result.stdout)
            assert packet['passed'] and packet['native_track_rows'] == 480
            assert packet['camera_count'] == 4 and packet['carla_imported'] is False
            assert packet['physical_success_claimed'] is False
            rows.append({'case_suffix': case, 'candidate_id': candidate,
                         'candidate_sha256': packet['candidate_sha256']})
    assert len({row['candidate_sha256'] for row in rows}) == 8
    bad = subprocess.run([sys.executable, str(RUNNER), '--check',
                          '--case', 'witness_1', '--candidate', 'unsupported'],
                         text=True, capture_output=True)
    assert bad.returncode != 0 and 'invalid choice' in bad.stderr
    with tempfile.TemporaryDirectory(prefix='c405647-native-preflight-') as temporary:
        bundle = Path(temporary)
        for name in ('runner.py', 'candidates.py', 'geometry.py', 'source-scope.json'):
            shutil.copyfile(ROOT / 'native' / name, bundle / name)
        (bundle / 'config.json').write_text(json.dumps({
            'case_suffix': 'witness_1', 'candidate_id': 'primary'}) + '\n')
        materialized = subprocess.run([sys.executable, str(bundle / 'runner.py'), '--check'],
                                      cwd=bundle, text=True, capture_output=True, check=True)
        assert json.loads(materialized.stdout)['candidate_sha256'] == rows[0]['candidate_sha256']
    return {'passed': True, 'runner_sha256': hashlib.sha256(RUNNER.read_bytes()).hexdigest(),
            'candidate_checks': rows, 'unknown_candidate_rejected': True,
            'materialized_no_argument_check_passed': True,
            'carla_started': False, 'original_pixels_seen': False,
            'scope': 'CPU construction preflight only'}


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2))
