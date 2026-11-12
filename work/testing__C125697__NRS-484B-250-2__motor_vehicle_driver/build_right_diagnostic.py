"""Create the ego-right diagnostic from exchanged original actor roles.

This is synthetic CPU evidence only. It carries distinct geometry and entry order.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE/'cases/off_ego_right_near_time'
LEFT = HERE.name+'__off_ego_left_near_time'
RIGHT = HERE.name+'__off_ego_right_near_time'


def lines(rows):
    return ''.join(json.dumps(row, allow_nan=False)+'\n' for row in rows)


def build():
    spec = json.loads((HERE/'diagnostic.json').read_text())
    files = spec['files']
    crossing = [json.loads(row) for row in files['crossing_history.jsonl'].splitlines()]
    trace = [json.loads(row) for row in files['trace.jsonl'].splitlines()]
    for row, point in zip(crossing, trace):
        row['ego'], row['other'] = row['other'], row['ego']
        row['ego']['road_id'], row['other']['road_id'] = 2, 1
        # Place the ego on the sourced north-south route rather than merely
        # relabeling the old east-west synthetic actor.
        dx, dy = (15, 0) if row['frame'] == 100 else (3, -3)
        row['ego']['body_vertices_xy_m'] = [
            [x+dx, y+dy] for x, y in row['ego']['body_vertices_xy_m']]
        row['ego_vertices_m'] = row['ego']['body_vertices_xy_m']
        body = row['ego']['body_vertices_xy_m']
        x = sum(p[0] for p in body)/len(body)
        y = sum(p[1] for p in body)/len(body)
        point['position'] = {'x': x, 'y': y, 'z': 0}
        point['heading_deg'] = 90
    files['crossing_history.jsonl'] = lines(crossing)
    files['trace.jsonl'] = lines(trace)
    context = json.loads(files['junction_context.json'])
    context['ego_highway_id'], context['other_highway_id'] = context['other_highway_id'], context['ego_highway_id']
    context['ego_road_id'], context['other_road_id'] = context['other_road_id'], context['ego_road_id']
    context['ego_approach_forward_xy'] = [0, 1]
    files['junction_context.json'] = json.dumps(context, allow_nan=False)+'\n'
    spec['graphs'] = []
    OUT.mkdir(parents=True, exist_ok=True)
    diagnostic = OUT/'diagnostic.json'
    diagnostic.write_text(json.dumps(spec, indent=2, allow_nan=False)+'\n')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json',
                           'source': str(diagnostic.relative_to(HERE.parents[1])),
                           'sha256': ''}],
              'generator': {'source': str(diagnostic.relative_to(HERE.parents[1])),
                            'sha256': ''}}
    (OUT/'diagnostic-recipe.json').write_text(json.dumps(recipe, indent=2)+'\n')
    module_path = HERE/'augment_diagnostic_capture.py'
    module_spec = importlib.util.spec_from_file_location('augment_right', module_path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    module.HERE = OUT
    module.CASE = RIGHT
    module.HEADINGS = ((101, 'ego', 90), (102, 'other', 0))
    module.RECORDER_START = (15, -12, 0)
    module.EGO_ROAD_S_AXIS = 1
    module.EGO_ROAD_S_OFFSET = 15
    generated = module.build()
    plan_path = HERE/'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if not any(RIGHT in row.get('case_ids', []) for row in plan['requirement_dispositions']):
        for index, original in enumerate(plan['requirement_dispositions'][:6]):
            row = copy.deepcopy(original)
            row['case_ids'] = [RIGHT]
            if index == 2:
                row['requirement'] = 'The other vehicle is spatially left of ego on the selected approaches'
                row['evidence_or_gap'] = 'The exchanged synthetic approach geometry is measured from original-frame crossing history; physical left-side geometry remains open.'
            else:
                row['evidence_or_gap'] = row['evidence_or_gap'].replace('right-side', 'left-side')
            plan['requirement_dispositions'].append(row)
        plan_path.write_text(json.dumps(plan, indent=2, allow_nan=False)+'\n')
    contract = json.loads((HERE/'measurement-contract.json').read_text())
    for index, row in enumerate(contract['requirements']):
        row['disposition_index'] = index+6
        if index == 2:
            row['requirement'] = 'The other vehicle is spatially left of ego on the selected approaches'
    (OUT/'measurement-contract.json').write_text(json.dumps(contract, indent=2, allow_nan=False)+'\n')
    proposal_path = HERE/'proposals/cases.json'
    proposals = json.loads(proposal_path.read_text())
    if not any(row['case_id'] == RIGHT for row in proposals['cases']):
        proposal = copy.deepcopy(proposals['cases'][0])
        proposal['case_id'] = RIGHT
        proposal['rationale'] = 'Off-state ego-right comparison at the same synthetic crossing; physical site unverified'
        proposal['paired_probe_id'] = 'c125697-relative-left-side'
        proposal['probe']['target_value_or_branch'] = 'off_ego_right_near_time'
        proposal['deliberate_differences'] = ['exchange ego and other approach orientation while retaining the crossing and Off state']
        proposals['cases'].append(proposal)
        proposal_path.write_text(json.dumps(proposals, indent=2, allow_nan=False)+'\n')
    manifest_path = HERE/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == RIGHT)
    if entry.get('compatibility'):
        raise ValueError('Right compatibility proof already bound; retain existing receipt')
    entry['fixture_recipe'] = str((OUT/'diagnostic-recipe.json').relative_to(HERE.parents[1]))
    entry['measurement_contract'] = str((OUT/'measurement-contract.json').relative_to(HERE))
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    return {'case_id': RIGHT, **generated}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
