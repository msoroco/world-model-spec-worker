"""Bind exact selected cases to current diagnostic compatibility inputs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    draft = json.loads((ROOT / 'execution-manifest.draft.json').read_text())
    entries = []
    for item in draft['cases']:
        case = item['case_id']
        suffix = case.removeprefix(ROOT.name + '__')
        construction = ROOT / item['construction']
        offline_log = ROOT / ('cpu-measure-final-offline-' + suffix + '.log')
        if sha(construction) != item['construction_sha256']:
            raise ValueError('diagnostic selected construction changed')
        if not offline_log.is_file() or 'offline_passed' not in offline_log.read_text():
            raise ValueError('missing exact offline evidence')
        entries.append({'case_id': case, 'kind': 'delivery',
            'construction': item['construction'], 'construction_sha256': sha(construction),
            'measurement_contract': 'cases/' + suffix + '/measurement-contract.json',
            'measurement_procedure': {'entrypoint': 'analysis.py'},
            'fixture_recipe': str((ROOT / 'cases' / suffix / 'fixture-recipe.json').relative_to(REPO)),
            'candidate_risk': item['candidate_risk'],
            'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
            'offline': {'command': '.venv-cpu/bin/python runtime.py offline --case ' + case,
                        'construction_sha256': sha(construction), 'exit_code': 0,
                        'log': offline_log.name, 'log_sha256': sha(offline_log)},
            'acquisition': {name: {'entrypoint': 'native_acquisition.py',
                                   'method': 'original 20 Hz Native actor/activity observation',
                                   'evidence': 'trace.json and activity.json'}
                            for name in ('activity_history', 'body_footprint_history',
                                         'traffic_conflict_history', 'direction_history')}})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ROOT.name,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'draft_compatibility_pending_original_review', 'cases': entries}
    (ROOT / 'execution-manifest.candidate.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    print('bound', len(entries), 'selected case constructions and exact offline receipts')


if __name__ == '__main__':
    build()
