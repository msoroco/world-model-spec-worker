"""Independently audit the three exact same-lane contrasts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit, require, rows, sha


ROOT = Path(__file__).resolve().parent
FIELDS = ('requested_same_lane', 'requested_pass',
          'requested_driver_consent', 'requested_two_wheeler_count')
CHANGED = {
    'same_lane_scope': {'requested_same_lane'},
    'consent_for_abreast': {'requested_driver_consent'},
    'no_more_than_two': {'requested_two_wheeler_count'},
}


def compare(comparison_id, left, right):
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    selected = [item for item in plan['comparisons']
                if item['comparison_id'] == comparison_id]
    require(len(selected) == 1 and comparison_id in CHANGED,
            'Unknown exact comparison')
    pair = selected[0]['case_ids']
    roots = (Path(left).resolve(), Path(right).resolve())
    audited = [audit(path, case) for path, case in zip(roots, pair)]
    require(audited[0]['native_source'] == audited[1]['native_source'],
            'Comparison mixes original and diagnostic source')
    configs = [json.loads((path / 'config.json').read_text()) for path in roots]
    scenes = [json.loads((path / 'same-lane-scene.json').read_text()) for path in roots]
    histories = [rows(path / 'same-lane-history.jsonl') for path in roots]
    require(configs[0]['cameras'] == configs[1]['cameras'] and
            configs[0]['rate_hz'] == configs[1]['rate_hz'] == 20 and
            configs[0]['duration_s'] == configs[1]['duration_s'] == 45 and
            configs[0]['engineering'] == configs[1]['engineering'],
            'Fixed camera, duration or engineering setup differs')
    surveys = [scene.get('survey', {}) for scene in scenes]
    require(surveys[0].get('map_id') == surveys[1].get('map_id') and
            surveys[0].get('lane_width_m') == surveys[1].get('lane_width_m'),
            'Fixed roadway or surveyed lane width differs')
    parameters = [config['case'] for config in configs]
    for field in FIELDS:
        if field in CHANGED[comparison_id]:
            require(parameters[0][field] != parameters[1][field],
                    'Declared contrast was not constructed: ' + field)
        else:
            require(parameters[0][field] == parameters[1][field],
                    'Fixed case parameter differs: ' + field)
    if comparison_id == 'same_lane_scope':
        lanes = [set(row['actors'][role]['lane_id'] ==
                     row['actors']['other']['lane_id'] for row in history
                     for role in ('ego',)) for history in histories]
        require(lanes == [{True}, {False}],
                'Same-lane versus other-lane contrast not observed')
    elif comparison_id == 'consent_for_abreast':
        require(scenes[0]['consent_status'] == 'consented' and
                scenes[1]['consent_status'] == 'not_consented',
                'Consent context contrast not observed')
        if all(item['native_source'] for item in audited):
            require(scenes[0]['consent_source_sha256'] !=
                    scenes[1]['consent_source_sha256'],
                    'Independent original driver consent sources not contrasted')
    else:
        counts = [len(history[0]['actors']) for history in histories]
        require(counts == [2, 3], 'Two versus three participant contrast not observed')
    return {'comparison_id': comparison_id, 'case_ids': pair,
            'source_sha256': [item['source_sha256'] for item in audited],
            'construction_sha256': [sha(path / 'construction.json') for path in roots],
            'declared_differences': sorted(CHANGED[comparison_id]),
            'fixed_conditions_checked': True,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.comparison, args.left, args.right), sort_keys=True))


if __name__ == '__main__':
    main()
