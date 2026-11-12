"""Bind tested exact constructions and saved-processing sources for eight cases."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time

from rebind_primary_compatibility import HERE, ROOT, AID, MANIFESTS


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    index = json.loads((HERE / 'canonical-primary-compatibility-index.json').read_text())
    entries = []
    runtime_sha = None
    for suffix, manifest_name in MANIFESTS.items():
        source = json.loads((HERE / manifest_name).read_text())
        if runtime_sha is None:
            runtime_sha = source['runtime_manifest_sha256']
        elif runtime_sha != source['runtime_manifest_sha256']:
            raise ValueError('Exact cases bind different pinned runtimes')
        entry = dict(source['cases'][0])
        case = AID + '__' + suffix
        if entry['case_id'] != case:
            raise ValueError('Exact manifest case changed')
        construction = json.loads((HERE / entry['construction']).read_text())
        finalizer = entry['measurement_procedure']['entrypoint']
        output = ROOT / '.runtime-work' / ('c125714-delivery-offline-' + suffix + '-' + str(time.time_ns()))
        command = [sys.executable, str(ROOT / 'runtime.py'), 'offline', '--manifest',
                   str(HERE / manifest_name), '--case', case, '--candidate', 'primary',
                   '--output', str(output), '--python', sys.executable]
        log = HERE / ('canonical-' + suffix + '-offline.log')
        with log.open('w') as stream:
            subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)
        bound = index[suffix]['copied']
        entry['kind'] = 'delivery'
        entry['offline'] = {'command': ' '.join(command), 'exit_code': 0,
                            'construction_sha256': entry['construction_sha256'],
                            'log': log.name, 'log_sha256': digest(log)}
        entry['compatibility'] = {'receipt': bound['receipt']['path'],
                                  'sha256': bound['receipt']['sha256'],
                                  'log': bound['analysis']['path'],
                                  'negative_log': bound['negative']['path']}
        entry['negative'] = {'log': bound['negative']['path']}
        entry['acquisition'] = {channel['name']: {
            'entrypoint': finalizer, 'method': channel['method'],
            'evidence': 'Original Native roadway, participant, frame-map and trace sources; derived only after saved acquisition'}
            for channel in construction['recording_description']['channels']}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entries.append(entry)
        print(suffix, 'exact offline proof bound', flush=True)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'runtime_manifest_sha256': runtime_sha, 'cases': entries}
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
