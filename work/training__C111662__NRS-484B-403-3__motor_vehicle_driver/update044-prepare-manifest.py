"""Bind current primary CPU receipts to four exact delivery case entries."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ('reference', 'contrast', 'divided_reference', 'divided_opening')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    data = json.loads(path.read_text())
    for case in CASES:
        entry = next(e for e in data['cases'] if e['case_id'].endswith('__' + case))
        proof = HERE / 'update044-current-proof' / case / 'primary'
        mini = json.loads((HERE / f'update043-current-manifest-{case}-primary.json').read_text()) if case != 'reference' else None
        if mini:
            entry['fixture_recipe'] = next(e['fixture_recipe'] for e in mini['cases'] if e['case_id'] == entry['case_id'])
        offline = proof / 'offline.log'
        compat = proof / 'compatibility.json'
        analysis = proof / 'analysis.log'
        negative = proof / 'negative-analysis.log'
        entry['offline'] = {
            'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json '
                       f'--case {entry["case_id"]} --candidate primary '
                       f'--output .runtime-work/update044-c111662/{case}/primary/offline '
                       f'--python {ROOT / ".venv-cpu/bin/python"}',
            'exit_code': 0, 'construction_sha256': entry['construction_sha256'],
            'log': str(offline.relative_to(HERE)), 'log_sha256': sha(offline)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['compatibility'] = {'receipt': str(compat.relative_to(HERE)),
                                  'sha256': sha(compat),
                                  'log': str(analysis.relative_to(HERE)),
                                  'negative_log': str(negative.relative_to(HERE))}
        entry['negative'] = {'log': str(negative.relative_to(HERE))}
        source = 'saved original Native body, frame map, source cameras and authored road geometry'
        entry['acquisition'] = {
            'ego_pose': {'entrypoint': 'runner.py', 'method': 'frame-joined original vehicle body pose', 'evidence': source},
            'ego_speed': {'entrypoint': 'runner.py', 'method': 'frame-joined original vehicle velocity', 'evidence': source},
            'u_turn_at_intersection_or_opening': {
                'entrypoint': 'finalize_current.py',
                'method': 'saved body path spatially joined to authored crossing geometry', 'evidence': source}}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(CASES), 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
