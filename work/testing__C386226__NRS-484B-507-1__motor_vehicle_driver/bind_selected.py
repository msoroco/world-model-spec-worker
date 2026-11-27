"""Bind exact selected diagnostic proofs to the source-gated Native case packages."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREFIX = HERE.name + '__'
SCRATCH = ROOT / '.runtime-work'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    diagnostic = json.loads((HERE / 'execution-manifest.compatibility-diagnostic.json').read_text())
    by_case = {entry['case_id']: entry for entry in diagnostic['cases']}
    manifest['runtime_manifest_sha256'] = sha(ROOT / 'runtime/SOURCE-MANIFEST.json')
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(PREFIX)
        selected = by_case[case]
        for key in ('construction', 'construction_sha256', 'fixture_recipe',
                    'measurement_contract', 'measurement_procedure'):
            entry[key] = selected[key]
        construction = json.loads((HERE / entry['construction']).read_text())
        channels = construction['recording_description']['channels']
        entry['acquisition'] = {item['name']: {
            'entrypoint': 'analysis.py',
            'method': item['method'],
            'evidence': 'channel-' + item['name'] + '.jsonl',
        } for item in channels}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        source = (SCRATCH / 'c386226-5071-compat-stop-v7' if suffix == 'stop_no_material'
                  else SCRATCH / 'c386226-5071-batch-compat' / suffix)
        target = HERE / 'proofs' / ('selected-' + suffix)
        target.mkdir(parents=True, exist_ok=True)
        for name, copied in (('compatibility.json', 'receipt.json'),
                             ('compatibility-analysis.log', 'analysis.log'),
                             ('negative-analysis.log', 'negative.log')):
            (target / copied).write_bytes((source / name).read_bytes())
        entry['compatibility'] = {'receipt': str((target / 'receipt.json').relative_to(HERE)),
                                  'sha256': sha(target / 'receipt.json'),
                                  'log': str((target / 'analysis.log').relative_to(HERE))}
        entry['negative'] = {'log': str((target / 'negative.log').relative_to(HERE))}
        entry['offline'] = {'construction_sha256': entry['construction_sha256'],
                            'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' +
                                       HERE.name + '/execution-manifest.json --case ' + case +
                                       ' --output .runtime-work/c386226-5071-selected-offline-' + suffix,
                            'exit_code': None, 'log': 'proof-selected-offline-' + suffix + '.log',
                            'log_sha256': None}
        entry.pop('physical_preparation', None)
    manifest['status'] = 'selected_compatibility_bound_pending_proofs'
    write(manifest_path, manifest)


if __name__ == '__main__':
    main()
