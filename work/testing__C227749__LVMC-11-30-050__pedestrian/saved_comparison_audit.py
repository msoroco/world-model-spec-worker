"""Independent comparison of five saved software diagnostics and exact scenes.

This compares controlled engineering inputs and retained diagnostic measurements;
it makes no physical or legal acceptance claim.
"""
import json
from pathlib import Path

from saved_delivery_gate import audit as audit_saved, sha


def read(path):
    return json.loads(Path(path).read_text())


def compare(root, scratch, compat_prefix='compat-v4-'):
    root, scratch = Path(root), Path(scratch)
    plan = read(root / 'case-plan.json')
    assignment = root.name
    outputs = []
    for row in plan['comparisons']:
        ids = row['case_ids']
        if len(ids) != 2 or any(not name.startswith(assignment + '__') for name in ids):
            raise ValueError('comparison case identity invalid')
        names = [case_id.removeprefix(assignment + '__') for case_id in ids]
        scenes, configs, observed, receipts = [], [], [], []
        for name, case_id in zip(names, ids):
            case = root / 'cases' / name
            construction = case / 'construction.json'
            attempt = scratch / (compat_prefix + name)
            version = scratch / ('process-' + name) / 'v0001'
            receipts.append(audit_saved(version, attempt, case_id, sha(construction)))
            scenes.append(read(case / 'scene.json'))
            configs.append(read(case / 'config.json'))
            observed.append(read(version / 'analysis' / 'result.json'))
            if sha(case / 'scene.json') != sha(attempt / 'scene.json'):
                raise ValueError('saved attempt differs from exact case scene')
            if sha(case / 'config.json') != sha(attempt / 'config.json'):
                raise ValueError('saved attempt differs from exact case config')
        fixed_scene = ['starting_curb_xy_m', 'opposite_curb_xy_m', 'map_source_sha256']
        fixed_config = ['law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras']
        if any(scenes[0][key] != scenes[1][key] for key in fixed_scene):
            raise ValueError('comparison fixed curb/map changed')
        if any(configs[0][key] != configs[1][key] for key in fixed_config):
            raise ValueError('comparison fixed capture condition changed')
        if any(r['status'] != 'software_diagnostic_complete' for r in receipts):
            raise ValueError('comparison requires exact saved software diagnostics')
        if any(o.get('provenance_kind') != 'synthetic_fixture' for o in observed):
            raise ValueError('comparison diagnostic provenance changed')
        cid = row['comparison_id']
        routes = [s['route_xy_m'] for s in scenes]
        polygons = [s['crosswalk_boundaries_xy_m'] for s in scenes]
        if cid == 'right_angle_vs_neither':
            condition = routes[0] != routes[1] and polygons[0] == polygons[1]
        elif cid == 'shortest_vs_neither':
            condition = routes[0] != routes[1] and routes[0][0] == routes[1][0] and polygons[0] == polygons[1]
        elif cid == 'outside_vs_crosswalk_exception':
            condition = routes[0] == routes[1] and polygons[0] != polygons[1]
        else:
            raise ValueError('unreviewed comparison ID')
        if not condition:
            raise ValueError('declared comparison variable not isolated')
        outputs.append({'comparison_id': cid, 'case_ids': ids,
                        'case_construction_sha256': [sha(root / 'cases' / n / 'construction.json') for n in names],
                        'saved_processing_sha256': [r['processing_sha256'] for r in receipts],
                        'saved_result_sha256': [r['result_sha256'] for r in receipts],
                        'fixed_curbs_map_capture': True, 'declared_difference_isolated': True,
                        'provenance': 'synthetic_fixture', 'physical_acceptance': False,
                        'legal_verdict': 'unresolved'})
    if len(outputs) != 3:
        raise ValueError('three planned comparisons required')
    return {'format': 'saved-comparison-diagnostic', 'assignment_id': assignment,
            'plan_sha256': sha(root / 'case-plan.json'),
            'auditor_sha256': sha(root / 'saved_comparison_audit.py'),
            'status': 'software_diagnostic_complete', 'physical_acceptance': False,
            'comparisons': outputs}


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    scratch = root.parents[1] / '.runtime-work' / 'p08-c227749-nov23'
    result = compare(root, scratch)
    output = root / 'saved-comparison-diagnostic.json'
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(f'checked {len(result["comparisons"])} saved diagnostic comparisons; output SHA256 {sha(output)}')
