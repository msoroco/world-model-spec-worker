"""Materialize the first selected exact case as the package root preview."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent


def main():
    manifest = json.loads((FOLDER / 'execution-manifest.json').read_text())
    construction = json.loads((FOLDER / manifest['cases'][0]['construction']).read_text())
    for item in construction['files']:
        path = FOLDER / item['path']
        path.parent.mkdir(exist_ok=True)
        path.write_text(item['content'])
    (FOLDER / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    plan['selected_branch'] = plan['scope_branches'][0]['branch']
    for case in plan['cases']:
        case['selected'] = True
        case['planning_status'] = 'selected_cpu_preparation_original_native_pending'
    for term, mapping in plan['source_observation_mapping'].items():
        mapping['channels'] = [term]
        mapping['evidence'] = 'Selected saved original Native channel and source context; actual activity, authority and legal applicability require independent original review.'
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'entire roadway edge, vehicle body and surrounding traffic context', 'interval': 'all 600 frames'},
            {'view': 'approach', 'subject': 'vehicle yaw and edge relation', 'interval': 'all 600 frames'},
            {'view': 'reference_corner', 'subject': 'edge tangent and body footprint', 'interval': 'all 600 frames'},
            {'view': 'driver_reference', 'subject': 'driver and roadside activity context', 'interval': 'all 600 frames'}]}
    (FOLDER / 'case-plan.json').write_text(json.dumps(plan, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
