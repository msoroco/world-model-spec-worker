"""Materialize the representative root bundle and exact four-view capture plan."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASE = ROOT / 'cases/green_selected_drive/construction.json'


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main() -> None:
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 18,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'subject': 'full bus body, both mapped lanes and arrow coverage',
             'view': 'overview', 'interval': 'entire 18 s attempt'},
            {'subject': 'bus approach, selected lane and overhead heads',
             'view': 'approach', 'interval': 'approach through lane-signal encounter'},
            {'subject': 'full bus and bus-facing downward green arrow head',
             'view': 'reference_corner', 'interval': 'approach through lane-signal encounter'},
            {'subject': 'bus control and facing signal context',
             'view': 'driver_reference', 'interval': 'entire 18 s attempt'}],
        'limitation': 'Actual pixels and arrow legibility require later original Native review'}
    plan['source_observation_mapping'] = {}
    for case in plan['cases']:
        case['preparation_status'] = 'offline_compatibility_physical_delivery_cpu_proven_semantic_pending'
    for comparison in plan['comparisons']:
        comparison['status'] = 'source_bound_diagnostic_comparison_cpu_proven_native_pending'
    write(plan_path, plan)
    bundle = json.loads(CASE.read_text())
    bundle['termination_rules'] = [
        'capture 18 seconds at 20 Hz or fail on source, frame, encoder or restoration error']
    bundle['mechanisms'] = [
        'two same-direction 3.6 m right-hand driving lanes',
        'source-reviewed bus-facing downward green-arrow heads',
        'CARLA bus and measured-state feedback control',
        'four synchronized original cameras and source-hashed saved analysis']
    for item in bundle['files']:
        if 'source' in item:
            continue
        target = ROOT / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    write(ROOT / 'construction.json', bundle)
    print('root representative construction and four-view plan materialized')


if __name__ == '__main__':
    main()
