"""Bind four passing exact offline tests for device-candidate cases."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def bind():
    source = json.loads((FOLDER / 'device-construction-manifest.json').read_text())
    for entry in source['cases']:
        suffix = entry['case_id'].split('__')[-1]
        folder = FOLDER / ('selected-' + suffix.replace('_', '-'))
        for variant, obj in [('primary', entry)] + [
                (candidate['id'], candidate) for candidate in entry['candidates']]:
            scratch = REPO / '.runtime-work' / f'c229977-device-{suffix.rsplit("_", 1)[-1]}-{variant}'
            raw = (scratch / 'offline.log').read_text()
            if '\nOK\n' not in raw:
                raise ValueError('Exact offline proof did not pass')
            log = folder / f'proof-{variant}.log'
            content = '\n'.join(line.rstrip() for line in (
                scratch / 'offline.log').read_text().splitlines()).rstrip() + '\n'
            log.write_text(content)
            obj['offline'] = {
                'command': '.venv-cpu/bin/python -B runtime.py offline '
                           '--manifest work/' + FOLDER.name + '/device-construction-manifest.json '
                           '--case ' + entry['case_id'] + ' --candidate ' + variant +
                           ' --output ' + str(scratch.relative_to(REPO)),
                'construction_sha256': obj['construction_sha256'],
                'exit_code': 0, 'log': str(log.relative_to(FOLDER)),
                'log_sha256': sha(log)}
        entry['measurement_contract'] = 'measurement-contract-device.json'
        entry['measurement_procedure'] = {'entrypoint': 'finalize_sidewalk.py'}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        entry['acquisition'] = {name: {'entrypoint': 'runner.py', 'evidence': 'vehicle-trace.jsonl, device-trace.jsonl, camera-frames.jsonl, video_frames.jsonl, map-packet.json, authority-context.json, native-road.xodr', 'method': 'frame-aligned original Native subject and device-candidate capture; official status and direction require independent review'} for name in ('vehicle_body_pose', 'vehicle_speed', 'sidewalk_overlap', 'sidewalk_map_context', 'exception_authority_context', 'device_candidate_trajectory')}
    source['status'] = 'public_compatibility_pending'
    dump(FOLDER / 'device-execution-manifest.json', dict(
        source, format='worker-execution-manifest'))
    return sha(FOLDER / 'device-execution-manifest.json')


if __name__ == '__main__':
    print(bind())
