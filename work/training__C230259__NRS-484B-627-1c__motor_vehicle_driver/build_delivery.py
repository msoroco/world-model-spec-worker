"""Freeze exact case handoff and independent delivery gate selftests."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
SCRIPT = HERE / 'delivery_audit.py'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = json.loads((HERE / 'draft-route-manifest.json').read_text())
    proofs = HERE / 'delivery-proofs'
    proofs.mkdir(exist_ok=True)
    for entry in source['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        receipt = {'case_id': entry['case_id'], 'sets': ['full-train'],
                   'checks': CHECKS, 'script': SCRIPT.name,
                   'script_sha256': sha(SCRIPT),
                   'negative_expected_error': 'Missing original source: exact original Native result'}
        for negative in (False, True):
            label = 'negative' if negative else 'positive'
            command = [sys.executable, '-B', str(SCRIPT), '--case', entry['case_id'], '--self-test']
            if negative:
                command.append('--negative')
            log = proofs / (suffix + '-' + label + '.log')
            with log.open('w') as output:
                completed = subprocess.run(command, cwd=ROOT, stdout=output,
                                           stderr=subprocess.STDOUT)
            text = log.read_text().rstrip() + '\n'
            log.write_text(text)
            if (negative and (completed.returncode == 0 or
                              receipt['negative_expected_error'] not in text)) or (
                              not negative and completed.returncode != 0):
                raise RuntimeError('Delivery selftest failed: ' + str(log))
            receipt['negative_command' if negative else 'command'] = ' '.join(command)
            receipt['negative_exit_code' if negative else 'test_exit_code'] = completed.returncode
            receipt['negative_log' if negative else 'test_log'] = str(log.relative_to(HERE))
            receipt['negative_log_sha256' if negative else 'test_log_sha256'] = sha(log)
        entry['delivery_acceptance'] = receipt
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['acquisition'] = {
            name: {'entrypoint': 'runner.py',
                   'method': 'same-tick original Native actor, road and four-camera frame recording',
                   'evidence': 'route-trace.jsonl, route-context.json, road.xodr and video_frames.jsonl'}
            for name in ('participant_motion', 'route_occupancy')}
        entry['post_capture'] = {'recorded_only': True,
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + AID +
                       '/execution-manifest.json --case ' + entry['case_id'] +
                       ' --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $DECODER --owner-release-receipt $OWNER_RELEASE_RECEIPT',
            'feedback_command': 'cat $OUTPUT/versions/*/feedback.json # ' + entry['case_id']}
    execution = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                 'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                 'status': 'selected_delivery_prepared', 'cases': source['cases']}
    (HERE / 'execution-manifest.json').write_text(json.dumps(execution, indent=2) + '\n')
    primary = json.loads((HERE / source['cases'][0]['construction']).read_text())
    (HERE / 'construction.json').write_text(json.dumps(primary, indent=2) + '\n')
    config = next(f['content'] for f in primary['files'] if f['path'] == 'config.json')
    (HERE / 'config.json').write_text(config)
    print(json.dumps({'cases': len(source['cases']),
                      'execution_manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
