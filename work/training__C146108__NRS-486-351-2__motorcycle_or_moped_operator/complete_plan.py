"""Bind the exact current-runtime observation and camera plans to selected cases."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = ROOT / 'case-plan.json'


def main():
    plan = json.loads(PLAN.read_text())
    channels = json.loads((ROOT / 'construction.json').read_text())['recording_description']['channels']
    names = {row['name'] for row in channels}
    input_ref = plan['sources'][0]
    for term, mapping in plan['source_observation_mapping'].items():
        mapping['evidence'] = mapping.pop('measurement', '') or (
            'Original Native source and separately reviewable statutory alternative')
        mapping['channels'] = [term] if term in names else []
        mapping['source_refs'] = [input_ref] if term not in names else []
    plan['camera_plan'] = {'profile': 'overview1080-capability',
        'duration_s': 30, 'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'both same-lane vehicles and complete pass corridor',
             'interval': 'all 600 frames'},
            {'view': 'approach', 'subject': 'initial motorcycle following gap and approach',
             'interval': 'approach through overlap'},
            {'view': 'reference_corner', 'subject': 'side-by-side body and same traffic lane',
             'interval': 'overlap interval'},
            {'view': 'driver_reference', 'subject': 'motorcycle and other vehicle relative order',
             'interval': 'all 600 frames'}]}
    for case in plan['cases']:
        case['kind'] = 'selected_delivery'
        case['requested_not_measured'] = True
    plan['runtime_uncertainties'] = [
        'Original Native motion, pixels, class identities and same-lane full-body history require independent acceptance.',
        'CPU source-shaped fixture proves the analysis path only; no legal or physical acceptance is claimed.']
    PLAN.write_text(json.dumps(plan, indent=2).rstrip() + '\n')


if __name__ == '__main__':
    main()
