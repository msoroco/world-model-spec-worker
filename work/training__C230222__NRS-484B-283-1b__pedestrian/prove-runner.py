"""CPU-only Native curb construction preflights and malformed-config negatives."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
RUNNER = HERE / 'native/runner.py'


def invoke(path):
    return subprocess.run([sys.executable, str(RUNNER), '--check', '--config', str(path)],
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)


def main():
    records = []
    for suffix in ('probe_1', 'probe_2'):
        for ident in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            folder = HERE / 'draft-candidates' / suffix / ident
            plan = json.loads((folder / 'construction.json').read_text())
            # The executable's declared camera policy is mirrored as data here, then
            # checked against the executable by its CPU preflight.
            e = plan['engineering']
            cameras = [
                {'name': 'overview', 'width': 1920, 'height': 1080},
                {'name': 'vehicle_approach', 'width': 1280, 'height': 720},
                {'name': 'curb_side', 'width': 1280, 'height': 720},
                {'name': 'curb_close', 'width': e['camera_width'], 'height': e['camera_height']},
            ]
            config = {'case_suffix': suffix, 'candidate_id': ident,
                      'case_id': plan['case_id'], 'selected_case_id': plan['case_id'],
                      'cell_id': plan['cell_id'], 'law_id': plan['law_id'], 'actor': plan['actor'],
                      'duration_s': plan['duration_s'], 'rate_hz': plan['rate_hz'],
                      'cameras': cameras, 'required_atoms': []}
            path = folder / 'cpu-config.json'
            path.write_text(json.dumps(config, indent=2) + '\n')
            positive = invoke(path)
            if positive.returncode:
                raise RuntimeError('Native CPU preflight failed: ' + positive.stdout)
            result = json.loads(positive.stdout)
            if result['native_imported'] or result['accepted_recording_claimed']:
                raise ValueError('CPU preflight falsely claims Native execution')
            with tempfile.TemporaryDirectory(prefix='curb-preflight-') as temporary:
                bad = dict(config)
                bad['case_id'] = bad['case_id'] + '-wrong'
                badpath = Path(temporary) / 'bad.json'
                badpath.write_text(json.dumps(bad))
                negative = invoke(badpath)
                if negative.returncode == 0 or 'Curb case identity differs' not in negative.stdout:
                    raise RuntimeError('Wrong-case Native CPU negative did not reject')
            records.append({'case_id': plan['case_id'], 'candidate_id': ident,
                            'cpu_preflight': 'pass', 'wrong_case_negative': 'pass',
                            'native_attempt_executed': False})
    summary = {'format': 'c230222-curb-runner-cpu-proof-v1', 'records': records,
               'native_attempts': 0, 'accepted_recordings': 0}
    (HERE / 'curb-runner-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'cpu_preflights': len(records), 'wrong_case_negatives': len(records),
                      'native_attempts': 0, 'accepted_recordings': 0}))


if __name__ == '__main__':
    main()
