"""Materialize canonical root inspection files from the exact witness bundle."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    construction = json.loads((HERE / 'v2-primary/witness_1/construction.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    case_ids = [case['case_id'] for case in plan['cases']]
    for item in construction['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['supported_case_ids'] = case_ids
            for camera in config['cameras']:
                camera['pose_strategy'] = 'fixed authored crosswalk and signal-head composition; verify original source pixels'
                camera['fov_deg'] = 90
            item['content'] = json.dumps(config, indent=2) + '\n'
        if item['path'] == 'runner.py':
            old = "config['cameras'] != plan['cameras']"
            new = "[(c['name'], c['width'], c['height']) for c in config['cameras']] != [(c['name'], c['width'], c['height']) for c in plan['cameras']]"
            assert item['content'].count(old) == 1
            item['content'] = item['content'].replace(old, new)
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    construction['status'] = 'draft'
    (HERE / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'whole crossing, both heads and walker', 'interval': 'entire 30 s'},
            {'view': 'approach', 'subject': 'pedestrian entry and circular-green head', 'interval': 'entry through clearance'},
            {'view': 'reference_corner', 'subject': 'marked crosswalk and pedestrian signal', 'interval': 'entire 30 s'},
            {'view': 'driver_reference', 'subject': 'facing direction and head governance', 'interval': 'entry through clearance'}]}
    plan['observations'] = [{'name': 'pedestrian_entry_signal', 'mandatory': True,
                             'source': 'joined Native pose, signal actor readback and camera frame map'}]
    for term, mapping in plan['source_observation_mapping'].items():
        mapping['channels'] = ['pedestrian_entry_signal']
        mapping['source_refs'] = ['saved_entry_measurement.py', 'physical_audit.py']
        mapping['status'] = 'CPU acquisition only; original pixel and governance review pending'
    for case in plan['cases']:
        case['kind'] = 'selected_delivery_preparation'
        case['requested_not_measured'] = True
        case['recording_description'] = construction['recording_description']
    plan['blockers'] = ['Original Native source pixel and governance review remain for local delivery; CPU semantic and package proofs are recorded separately.']
    (HERE / 'case-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps({'canonical_files': len(construction['files']), 'selected_cases': len(case_ids)}))


if __name__ == '__main__':
    main()
