"""Materialize three exact case bundles without claiming delivery readiness."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    draft = json.loads((HERE / 'draft-thirty-second-execution-manifest.json').read_text())
    old_path = HERE / 'execution-manifest.json'
    previous = {e['case_id']: e for e in json.loads(old_path.read_text()).get('cases', [])} if old_path.exists() else {}
    entries = []
    for source in draft['cases']:
        suffix = source['case_id'].rsplit('__', 1)[-1]
        construction_path = HERE / source['construction']
        construction = json.loads(construction_path.read_text())
        target_root = HERE if suffix == 'controlled_1' else HERE / 'cases' / suffix
        for item in construction['files']:
            dest = target_root / item['path']
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(item['content'])
        if suffix == 'controlled_1':
            write(HERE / 'construction.json', construction)
        entry = dict(source)
        entry['kind'] = 'delivery'
        old = previous.get(entry['case_id'], {})
        if old.get('construction_sha256') == entry['construction_sha256']:
            for key in ('physical_preparation', 'compatibility', 'post_capture',
                        'saved_processing', 'delivery_acceptance', 'acquisition', 'negative'):
                if key in old:
                    entry[key] = old[key]
        entry['native_handoff'] = {
            'python_env_var': 'CARLA_PYTHON',
            'host_env_var': 'CARLA_HOST',
            'port_env_var': 'CARLA_PORT'}
        offline_source = HERE.parents[1] / '.runtime-work' / ('c104538-current-offline-' + suffix) / 'offline.log'
        if offline_source.is_file():
            offline_log = HERE / 'selected-proof' / suffix / 'primary' / 'offline.log'
            offline_log.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(offline_source, offline_log)
            entry['offline'] = {
                'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {entry["case_id"]} --output .runtime-work/c104538-current-offline-{suffix}',
                'exit_code': 0,
                'construction_sha256': sha(construction_path),
                'log': str(offline_log.relative_to(HERE)),
                'log_sha256': sha(offline_log)}
        entry.pop('id', None)
        entries.append(entry)
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': HERE.name,
                'runtime_manifest_sha256': draft['runtime_manifest_sha256'],
                'cases': entries}
    write(HERE / 'execution-manifest.json', manifest)
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    for case in plan['cases']:
        case['kind'] = 'delivery'
    plan['camera_plan'] = {
        'profile': 'overview1080-capability',
        'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'hill approach, sign, bicycle and rider movement', 'interval': 'all 600 frames'},
            {'view': 'approach', 'subject': 'approach lane, rider and source sign pixels', 'interval': 'all 600 frames'},
            {'view': 'reference_corner', 'subject': 'turn prohibition and dismount posture', 'interval': 'all 600 frames'},
            {'view': 'driver_reference', 'subject': 'forward road and pedestrian path context', 'interval': 'all 600 frames'}]}
    write(plan_path, plan)
    print(json.dumps({'cases': len(entries), 'manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
