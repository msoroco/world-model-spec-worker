"""Bind exact C146314 cases for offline and compatibility CPU proofs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
PLAN = json.loads((ROOT / 'case-plan.json').read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


cases = []
entries = []
for suffix in ('probe_a', 'probe_b'):
    case_id = ROOT.name + '__' + suffix
    construction_path = ROOT / 'native' / (suffix + '-construction.json')
    construction = json.loads(construction_path.read_text())
    proposal = next(item for item in PLAN['cases'] if item['case_id'] == case_id)
    cases.append({'case_id': case_id, 'target_law_id': PLAN['law_id'],
                  'target_type': proposal['target_type'], 'kind': 'delivery',
                  'rationale': proposal['physical_target'],
                  'variable_assignments': {
                      'lead_lateral_plan_m': {'kind': 'world_setup', 'value': -2.0 if suffix == 'probe_a' else -6.0,
                                              'unit': 'm', 'source': 'author engineering plan'},
                      'ego_lateral_plan_m': {'kind': 'subject_behavior', 'value': -6.0 if suffix == 'probe_a' else -8.7,
                                             'unit': 'm', 'source': 'author engineering plan'}},
                  'recording_description': construction['recording_description'],
                  'unresolved_judgment_calls': ['physical off-pavement necessity pending original Native review']})
    contract = {'format': 'worker-measurement-contract', 'case_id': case_id, 'status': 'draft',
                'requirements': [{'disposition_index': 0, 'requirement': 'NRS-484B-210-3',
                                  'source': 'NRS 484B.210(3)',
                                  'output_key': 'right_pass_paved_surface',
                                  'method': 'measure_original_body_and_paved_corridor',
                                  'value_type': 'object', 'kind': 'measured',
                                  'inputs': ['native_motion.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                                             'capture/evidence.jsonl', 'road.xodr']}],
                'negative': {'remove': ['native_motion.jsonl'],
                             'error_contains': 'Missing required source: native_motion.jsonl'}}
    write(ROOT / 'native' / (suffix + '-measurement-contract.json'), contract)
    entries.append({'case_id': case_id, 'kind': 'delivery',
                    'construction': 'native/' + suffix + '-construction.json',
                    'construction_sha256': digest(construction_path),
                    'measurement_contract': 'native/' + suffix + '-measurement-contract.json',
                    'measurement_procedure': {'entrypoint': 'finalize.py'},
                    'fixture_recipe': 'work/' + ROOT.name + '/native/diagnostic/' + suffix + '/fixture-recipe.json',
                    'candidate_risk': {'status': 'none', 'reason': 'The currently authored two routes have no separate validated engineering fallback before original Native material and body review; physical review remains mandatory.'},
                    'candidates': [],
                    'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                                       'port_env_var': 'CARLA_PORT'}})
write(ROOT / 'proposals' / 'cases.json', {'cell_id': PLAN['cell_id'], 'actor': PLAN['actor'],
                                          'status': 'draft', 'cases': cases,
                                          'sweep_specs': [], 'sweeps_expanded': True})
write(ROOT / 'execution-manifest.json', {'format': 'worker-execution-manifest',
                                         'assignment_id': ROOT.name, 'status': 'draft',
                                         'runtime_manifest_sha256': digest(REPO / 'runtime/SOURCE-MANIFEST.json'),
                                         'cases': entries})
print(json.dumps({'cases': [x['case_id'] for x in entries], 'runtime_sha': digest(REPO / 'runtime/SOURCE-MANIFEST.json')}))
