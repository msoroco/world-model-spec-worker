"""Bind successful current-runtime primary CPU receipts to the selected manifest."""
import hashlib
import json
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
SUFFIXES = ('outside', 'all_present', 'no_designation', 'no_dedication',
            'no_posting', 'emergency', 'maintenance')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return sha(target)


def main():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    manifest['status'] = 'partial'
    for entry, suffix in zip(manifest['cases'], SUFFIXES):
        case_id = ASSIGNMENT + '__' + suffix
        assert entry['case_id'] == case_id
        proof = ROOT / '.runtime-work' / ('c143691-compat-' +
                                             ('all-present' if suffix == 'all_present' else suffix) + '-v5')
        offline_log = ROOT / '.runtime-work' / ('c143691-offline-' +
                                                  ('all-present' if suffix == 'all_present' else suffix) + '-v5.log')
        receipt = json.loads((proof / 'compatibility.json').read_text())
        if (receipt['passed'] is not True or receipt['case_id'] != case_id or
                receipt['construction_sha256'] != entry['construction_sha256']):
            raise ValueError('Public compatibility proof differs: ' + suffix)
        if not offline_log.is_file():
            raise ValueError('Exact offline log absent: ' + suffix)
        offline_target = HERE / 'offline' / (suffix + '-primary.log')
        copy(offline_log, offline_target)
        receipt_target = HERE / 'compatibility' / (suffix + '-primary.json')
        analysis_target = HERE / 'compatibility' / (suffix + '-primary-analysis.log')
        negative_target = HERE / 'compatibility' / (suffix + '-primary-negative.log')
        copy(proof / 'compatibility.json', receipt_target)
        copy(proof / 'compatibility-analysis.log', analysis_target)
        copy(proof / 'negative-analysis.log', negative_target)
        if (sha(analysis_target) != receipt['log_sha256'] or
                sha(negative_target) != receipt['negative_log_sha256']):
            raise ValueError('Public log differs: ' + suffix)
        entry['offline'] = {
            'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' +
                       ASSIGNMENT + '/draft-execution-manifest.json --case ' + case_id +
                       ' --output .runtime-work/c143691-offline-' +
                       ('all-present' if suffix == 'all_present' else suffix) + '-v5',
            'exit_code': 0,
            'construction_sha256': entry['construction_sha256'],
            'log': str(offline_target.relative_to(HERE)),
            'log_sha256': sha(offline_target),
        }
        entry['compatibility'] = {
            'receipt': str(receipt_target.relative_to(HERE)),
            'sha256': sha(receipt_target),
            'log': str(analysis_target.relative_to(HERE)),
            'negative_log': str(negative_target.relative_to(HERE)),
        }
        entry['negative'] = {'log': str(negative_target.relative_to(HERE))}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        entry['candidate_risk'] = {'status': 'none',
            'reason': 'No original Native physical failure has been measured; retain primary until first capture and preserve explicit barrier/clearance readbacks'}
        entry['preparation_status'] = 'incomplete'
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    chosen = json.loads((HERE / manifest['cases'][1]['construction']).read_text())
    (HERE / 'construction.json').write_text(json.dumps(chosen, indent=2) + '\n')
    for item in chosen['files']:
        if item['path'] in ('runner.py', 'config.json'):
            (HERE / item['path']).write_text(item['content'])
    print(json.dumps({'selected': len(manifest['cases']), 'manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
