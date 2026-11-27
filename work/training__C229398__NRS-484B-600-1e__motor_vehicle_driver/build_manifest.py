"""Bind three exact source-reviewed speed constructions to pinned runtime."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    source = REPO / 'runtime/SOURCE-MANIFEST.json'
    cases = []
    for index in range(1, 4):
        suffix = f'probe_0{index}'
        case = AID + '__' + suffix
        construction = f'cases/{suffix}/construction.json'
        cases.append({'case_id': case, 'kind': 'delivery',
            'construction': construction,
            'construction_sha256': sha(HERE / construction),
            'candidate_risk': {'status': 'none',
                'reason': 'The same frozen road, curb, actor, camera and phase sources must be reviewed; no source-preserving alternative can establish absent original Native velocity or same-cell review. Native curb completion remains an explicit delivery risk.'},
            'candidates': [],
            'delivery_readiness': 'cpu_construction_original_capture_pending',
            'measurement_contract': f'cases/{suffix}/measurement-contract.json',
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'fixture_recipe': f'work/{AID}/cases/{suffix}/fixture-recipe.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
            'acquisition': {
                'kin.speed': {'entrypoint': 'runner.py',
                    'method': 'Original three-axis Native velocity converted to mph only in reviewed driving-approach frames.',
                    'evidence': ['native-speed.jsonl', 'video_frames.jsonl',
                                 'approach-review.json']},
                'kin.velocity': {'entrypoint': 'runner.py',
                    'method': 'Original post-tick Native vehicle velocity with actor/frame identity.',
                    'evidence': ['native-speed.jsonl', 'trace.jsonl']},
                'ru.subject': {'entrypoint': 'runner.py',
                    'method': 'Original Native actor, blueprint, road and lane readback in the same source recording.',
                    'evidence': ['native-speed.jsonl', 'road.xodr',
                                 'source_context/vehicle_identity.txt']}},
            'offline': {}, 'compatibility': {}, 'negative': {},
            'post_capture': {}, 'physical_preparation': {},
            'delivery_acceptance': {}})
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': AID, 'runtime_manifest_sha256': sha(source),
                'status': 'partial', 'cases': cases}
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Three exact constructions bound to current runtime')


if __name__ == '__main__':
    main()
