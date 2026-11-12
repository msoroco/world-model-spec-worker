"""Build 20 Hz synthetic Native samples for the separated-entry comparison.

The 97 frames are a CPU diagnostic, not a full 900-frame recording.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE/'cases/off_ego_left_separated'
CASE = HERE.name+'__off_ego_left_separated'


def lines(rows):
    return ''.join(json.dumps(row, allow_nan=False)+'\n' for row in rows)


def body(x, y):
    return [[x-1, y-1], [x-1, y+1], [x+1, y+1], [x+1, y-1]]


def build():
    spec = json.loads((HERE/'diagnostic.json').read_text())
    files = spec['files']
    frame_rows, crossing, controls, trace = [], [], [], []
    samples = []
    for frame in range(100, 197):
        ego_held, other_held = frame < 120, frame < 160
        samples.append((frame, 1+(frame-100)/20,
                        min(19, max(0, (frame-120)*.25)), 15,
                        min(-3, -12+max(0, frame-160)*.25),
                        ego_held, other_held,
                        0 if ego_held else 5, 0 if other_held else 5))
    for index, (frame, time_s, ego_x, other_x, other_y, ego_held,
                other_held, ego_speed, other_speed) in enumerate(samples):
        ego_body = body(ego_x, 0)
        other_body = body(other_x, other_y)
        frame_rows.append({'video_frame': index, 'carla_frame': frame, 'time_s': time_s})
        crossing.append({
            'frame': frame, 'time_s': time_s,
            'ego': {'body_vertices_xy_m': ego_body, 'intersection_id': 44,
                    'road_id': 1, 'speed_mps': ego_speed,
                    'velocity_mps': [ego_speed, 0, 0]},
            'other': {'body_vertices_xy_m': other_body, 'intersection_id': 44,
                      'road_id': 2, 'speed_mps': other_speed,
                      'velocity_mps': [0, other_speed, 0]},
            'ego_vertices_m': ego_body,
            'governing_signal_state': 'Off',
            'entrance_signal_states': [{'actor_id': 17, 'state': 'Off'},
                                       {'actor_id': 18, 'state': 'Off'}],
        })
        controls.append({'frame': frame, 'time_s': time_s,
                         'ego_held': ego_held, 'other_held': other_held})
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': ego_x, 'y': 0, 'z': 0},
                      'heading_deg': 0, 'speed_mps': ego_speed,
                      'velocity_mps': [ego_speed, 0, 0],
                      'control': {'throttle': 0 if ego_held else .3,
                                  'steer': 0, 'brake': 1 if ego_held else 0,
                                  'hand_brake': False, 'reverse': False}})
    files['video_frames.jsonl'] = lines(frame_rows)
    files['crossing_history.jsonl'] = lines(crossing)
    files['controller_history.jsonl'] = lines(controls)
    files['trace.jsonl'] = lines(trace)
    spec['graphs'] = []
    for video in spec['videos']:
        video['frames'] = len(samples)
    OUT.mkdir(parents=True, exist_ok=True)
    diagnostic = OUT/'diagnostic.json'
    diagnostic.write_text(json.dumps(spec, indent=2, allow_nan=False)+'\n')
    recipe_source = str(diagnostic.relative_to(HERE.parents[1]))
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json',
                           'source': recipe_source, 'sha256': ''}],
              'generator': {'source': recipe_source, 'sha256': ''}}
    (OUT/'diagnostic-recipe.json').write_text(json.dumps(recipe, indent=2)+'\n')
    module_spec = importlib.util.spec_from_file_location('augment_separated', HERE/'augment_diagnostic_capture.py')
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    module.HERE = OUT
    module.CASE = CASE
    generated = module.build()
    plan_path = HERE/'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if not any(CASE in row.get('case_ids', []) for row in plan['requirement_dispositions']):
        for original in plan['requirement_dispositions'][:6]:
            row = copy.deepcopy(original)
            row['case_ids'] = [CASE]
            if row['requirement'].startswith('Both complete bodies'):
                row['evidence_or_gap'] = 'Continuous 20 Hz synthetic original-frame samples measure distinct entry times; no legal approximate-time cutoff is inferred and physical timing remains open.'
            plan['requirement_dispositions'].append(row)
        plan_path.write_text(json.dumps(plan, indent=2, allow_nan=False)+'\n')
    contract = json.loads((HERE/'measurement-contract.json').read_text())
    for index, row in enumerate(contract['requirements']):
        row['disposition_index'] = index+12
    (OUT/'measurement-contract.json').write_text(json.dumps(contract, indent=2, allow_nan=False)+'\n')
    proposal_path = HERE/'proposals/cases.json'
    proposals = json.loads(proposal_path.read_text())
    if not any(row['case_id'] == CASE for row in proposals['cases']):
        proposal = copy.deepcopy(proposals['cases'][0])
        proposal['case_id'] = CASE
        proposal['rationale'] = 'Off-state ego-left separated-entry comparison at the same synthetic crossing; physical site unverified'
        proposal['variable_assignments']['other_release_frame']['value'] = 60
        proposal['paired_probe_id'] = 'c125697-entry-timing'
        proposal['deliberate_differences'] = ['other release timing targets a larger measured complete-body entry gap']
        proposal['probe']['target_value_or_branch'] = 'off_ego_left_separated'
        proposals['cases'].append(proposal)
        proposal_path.write_text(json.dumps(proposals, indent=2, allow_nan=False)+'\n')
    manifest_path = HERE/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    if entry.get('compatibility'):
        raise ValueError('Separated compatibility already bound; retain current proof')
    entry['fixture_recipe'] = str((OUT/'diagnostic-recipe.json').relative_to(HERE.parents[1]))
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    return {'case_id': CASE, **generated}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
