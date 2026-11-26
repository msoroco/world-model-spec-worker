"""Bind selected cases, source measurements and current-runtime offline proofs."""
import hashlib
import json
from pathlib import Path

from build_selected import CASES

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
SOURCES = ('native-ego-frames.jsonl', 'native-driver-checks.jsonl',
           'driving-context.json', 'video_frames.jsonl')
KEYS = ('lane_activation', 'signal_order', 'independent_check', 'target_lane_gap')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def build():
    plan = json.loads((PACKAGE / 'case-plan.json').read_text())
    draft = json.loads((PACKAGE / 'selected-draft-manifest.json').read_text())
    descriptions = {}
    entries = []
    for suffix, entry in zip(CASES, draft['cases']):
        case = entry['case_id']
        construction = json.loads((PACKAGE / entry['construction']).read_text())
        descriptions[case] = construction['recording_description']
        rows = []
        for i, disposition in enumerate(plan['requirement_dispositions']):
            rows.append({'disposition_index': i,
                         'requirement': disposition['requirement'],
                         'source': disposition['source'],
                         'output_key': KEYS[i], 'method': 'finalize',
                         'value_type': 'object',
                         'kind': 'sourced_context' if i == 2 else 'measured',
                         'inputs': list(SOURCES)})
        measurement = {'format': 'worker-measurement-contract',
                       'case_id': case, 'requirements': rows,
                       'negative': {'remove': ['native-driver-checks.jsonl'],
                                    'error_contains': 'Missing required source: native-driver-checks.jsonl'}}
        measurement_path = PACKAGE / ('measurement-' + suffix + '.json')
        write(measurement_path, measurement)
        item = dict(entry,
                    measurement_contract=measurement_path.name,
                    measurement_procedure={'entrypoint': 'finalize_lane_change.py',
                                           'output_schema': 'c245490-lane-change-analysis-v1'},
                    native_handoff={'python_env_var': 'CARLA_PYTHON',
                                    'host_env_var': 'CARLA_HOST',
                                    'port_env_var': 'CARLA_PORT'},
                    fixture_recipe=str((PACKAGE / ('selected-recipe-' + suffix + '.json')).relative_to(ROOT)))
        entries.append(item)
    proposals = {'status': 'draft', 'assignment_id': PACKAGE.name,
                 'law_id': 'NRS-484B-223-1b', 'cell_id': 'C245490',
                 'actor': 'motor_vehicle_driver', 'sweep_specs': [],
                 'sweeps_expanded': True,
                 'cases': [{'case_id': PACKAGE.name + '__baseline',
                            'target_law_id': None, 'target_type': 'baseline',
                            'rationale': 'Unselected marked-lane context; no delivery recording.',
                            'variable_assignments': {},
                            'recording_description': descriptions[entries[0]['case_id']]}] +
                          [{'case_id': entry['case_id'],
                            'target_law_id': 'NRS-484B-223-1b',
                            'target_type': 'controlled_comparison',
                            'rationale': next(c['physical_target'] for c in plan['cases']
                                              if c['case_id'] == entry['case_id']),
                            'variable_assignments': {
                                'signal_command_frame': {'kind': 'controller',
                                                         'value': 260 if suffix == 'signal_after_safe' else 100},
                                'rear_actor_spawn_distance_m': {'kind': 'world_setup',
                                                                'value': 8 if suffix == 'signal_before_unsafe' else 30},
                                'predeparture_check_action': {'kind': 'controller',
                                                              'value': 'skipped' if suffix == 'signal_before_no_check' else 'evaluated'}},
                            'unresolved_judgment_calls': ['appropriate signal',
                                                          'ascertained that movement can be made with safety'],
                            'recording_description': descriptions[entry['case_id']],
                            'paired_probe_id': next(c['comparison_id'] for c in plan['comparisons']
                                                    if entry['case_id'] in c['case_ids']),
                            'deliberate_differences': next(c['deliberate_differences'] for c in plan['comparisons']
                                                           if entry['case_id'] in c['case_ids'])}
                           for suffix, entry in zip(CASES, entries)]}
    write(PACKAGE / 'proposals' / 'cases.json', proposals)
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': PACKAGE.name,
                'runtime_manifest_sha256': sha(ROOT / 'runtime' / 'SOURCE-MANIFEST.json'),
                'status': 'partial', 'cases': entries}
    write(PACKAGE / 'execution-manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'case_count': len(build()['cases'])}))
