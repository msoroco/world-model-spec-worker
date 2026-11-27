"""Promote two source-bound motorcycle constructions to the exact delivery manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('road.xodr', 'pass-context.json', 'participant-poses.jsonl',
           'video_frames.jsonl', 'trace.jsonl', 'capture/manifest.json',
           *(view + '.mkv' for view in VIEWS), 'pass-review.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2).rstrip() + '\n')


def main():
    draft = json.loads((ROOT / 'draft-two-case-manifest.json').read_text())
    cases = []
    for number, entry in enumerate(draft['cases'], 1):
        case_id = entry['case_id']
        suffix = f'controlled_{number}'
        construction = ROOT / entry['construction']
        proposal = json.loads(construction.read_text())
        assert proposal['case_id'] == case_id
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'requirements': [
                        {'disposition_index': 0, 'requirement': 'NRS-486-351-2',
                         'source': 'NRS 486.351(2); with 486.351(3)', 'kind': 'measured',
                         'method': 'measure_same_lane_episode',
                         'output_key': 'same_lane_episode', 'value_type': 'object',
                         'inputs': list(SOURCES)},
                        {'disposition_index': 1, 'requirement': 'NRS-486-351-2',
                         'source': 'NRS 486.351(2); with 486.351(3)', 'kind': 'measured',
                         'method': 'measure_statutory_alternatives',
                         'output_key': 'statutory_alternatives', 'value_type': 'object',
                         'inputs': ['pass-context.json', 'participant-poses.jsonl',
                                    'pass-review.json']}],
                    'negative': {'remove': ['pass-context.json'],
                                 'error_contains': 'Missing required source: pass-context.json'}}
        put(ROOT / 'cases' / suffix / 'measurement-contract.json', contract)
        case = dict(entry)
        case.update(measurement_contract=f'cases/{suffix}/measurement-contract.json',
                    fixture_recipe=f'work/{ROOT.name}/cases/{suffix}/recipe.json',
                    native_handoff={'python_env_var': 'CARLA_PYTHON',
                                    'host_env_var': 'CARLA_HOST',
                                    'port_env_var': 'CARLA_PORT'},
                    acquisition={name: {'entrypoint': 'runner.py',
                           'method': 'Original Native actor bodies, lane source and synchronized four-camera capture',
                           'evidence': list(SOURCES)} for name in
                           ('ru.motorcycle', 'ru.moped', 'st.lane', 'rel.occupies',
                            'rel.longitudinal_overlap', 'drv.overtaking',
                            'rel.bearing', 'ru.motor_vehicle', 'rel.surface_gap')},
                    offline={}, compatibility={}, negative={}, post_capture={},
                    physical_preparation={}, delivery_acceptance={})
        cases.append(case)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ROOT.name,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'partial', 'cases': cases}
    put(ROOT / 'execution-manifest.json', manifest)
    (ROOT / 'construction.json').write_text((ROOT / cases[0]['construction']).read_text())
    print(json.dumps({'cases': [c['case_id'] for c in cases],
                      'construction_sha256': [sha(ROOT / c['construction']) for c in cases]}))


if __name__ == '__main__':
    main()
