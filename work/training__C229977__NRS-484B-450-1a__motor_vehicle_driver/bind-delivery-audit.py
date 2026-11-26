"""Run and bind exact-case independent delivery audit selftests."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    script = HERE / 'delivery_audit.py'
    folder = HERE / 'delivery-proofs'
    folder.mkdir(exist_ok=True)
    for index, entry in enumerate(manifest['cases'], 1):
        case = entry['case_id']
        base = [sys.executable, '-B', str(script), '--case', case, '--self-test']
        logs = []
        for negative in (False, True):
            argv = base + (['--negative'] if negative else [])
            log = folder / (f'probe_{index}-negative.log' if negative else f'probe_{index}-positive.log')
            with log.open('w') as stream:
                status = subprocess.run(argv, cwd=REPO, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=30,
                                        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            log.write_text(log.read_text().rstrip() + '\n')
            if (status.returncode == 0) == negative:
                raise ValueError('Delivery audit selftest did not distinguish source status')
            logs.append((argv, log, status.returncode))
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'], 'checks': CHECKS,
            'script': str(script.relative_to(HERE)), 'script_sha256': sha(script),
            'command': ' '.join(logs[0][0]),
            'negative_command': ' '.join(logs[1][0]),
            'test_exit_code': 0, 'negative_exit_code': logs[1][2],
            'negative_expected_error': 'Missing original sidewalk source',
            'test_log': str(logs[0][1].relative_to(HERE)),
            'test_log_sha256': sha(logs[0][1]),
            'negative_log': str(logs[1][1].relative_to(HERE)),
            'negative_log_sha256': sha(logs[1][1])}
        evidence = ['vehicle-trace.jsonl', 'camera-frames.jsonl',
                    'video_frames.jsonl', 'map-packet.json',
                    'authority-context.json', 'native-road.xodr']
        channels = json.loads((HERE / entry['construction']).read_text())['recording_description']['channels']
        names = {row['name'] for row in channels}
        names.update(('sidewalk_map_context', 'exception_authority_context'))
        entry['acquisition'] = {name: {
            'entrypoint': 'runner.py',
            'method': 'same-tick original Native body, map and authority source capture; independent review required',
            'evidence': ', '.join(evidence)} for name in sorted(names)}
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(sha(path))


if __name__ == '__main__':
    main()
