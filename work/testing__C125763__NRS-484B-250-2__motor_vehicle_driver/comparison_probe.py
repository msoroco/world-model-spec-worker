"""CPU diagnostic of the independent three-capture comparison audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'tests'))
from test_compare_saved import ComparisonTest  # noqa: E402
from compare_saved import compare  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', action='store_true',
                        help='Keep three release schedules but make all measured entries equal')
    parser.add_argument('--changed-weather', action='store_true')
    args = parser.parse_args()
    fixture = ComparisonTest('test_source_bound_three_case_comparison_and_fixed_condition_negative')
    fixture.setUp()
    try:
        spec, _ = fixture._spec(changed_weather=args.changed_weather,
                                identical_realized=args.negative)
        report = compare(HERE / 'case-plan.json', spec)
        print(json.dumps({'format': report['format'], 'comparison_id': report['comparison_id'],
            'case_ids': report['case_ids'], 'observed': report['observed'],
            'legal_verdict_claimed': report['legal_verdict_claimed'],
            'physical_acceptance': report['physical_acceptance']}, sort_keys=True))
    finally:
        fixture.doCleanups()


if __name__ == '__main__':
    main()
