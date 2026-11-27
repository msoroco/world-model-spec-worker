"""Bind exact C158142 Native and CPU proof files without changing frozen inputs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parents[1]
AID = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    entries = []
    for number, condition in ((1, 'halt'), (2, 'roll')):
        suffix = f'witness_{number}'
        case = AID + '__' + suffix
        construction = ('construction.json' if number == 1
                        else 'cases/witness_2/construction.json')
        candidate = f'candidates/{suffix}/fallback1/construction.json'
        entries.append({
            'case_id': case, 'kind': 'delivery',
            'construction': construction,
            'construction_sha256': sha(HERE / construction),
            'measurement_contract': ('measurement-contract.json' if number == 1
                                     else 'cases/witness_2/measurement-contract.json'),
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'fixture_recipe': f'work/{AID}/diagnostic-{condition}-recipe.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
            'candidate_risk': {'status': 'physical',
                'reason': 'Native OpenDRIVE signal actor and two-vehicle clearance may differ from authored geometry; surveyed lane/state and original motion determine the trigger.'},
            'candidates': [{'id': 'fallback1', 'construction': candidate,
                'construction_sha256': sha(HERE / candidate),
                'trigger': {'source': 'interaction_history.jsonl',
                            'metric': 'ego/priority vehicle entry and clearance within 600 joined frames',
                            'failure_condition': 'one vehicle fails the planned junction passage or clearance despite correct signal/lane survey'},
                'changed_knobs': ['ego rolling throttle', 'priority vehicle entry and clear speed']}],
            'delivery_readiness': 'incomplete'})
    put(HERE / 'execution-manifest.json', {
        'format': 'worker-execution-manifest', 'assignment_id': AID,
        'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
        'status': 'partial', 'cases': entries})
    print(sha(HERE / 'execution-manifest.json'))


if __name__ == '__main__':
    build()
