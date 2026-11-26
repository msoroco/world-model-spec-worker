"""Run one exact synthetic motion outcome for the canonical CPU proof gate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'tests'))
from parking import CASES
from physical_outcomes import evaluate
from test_native_history_capture import Adapter
from test_parking import site
from test_physical_outcomes import with_observed_approach


def prove(kind: str, outcome_kind: str) -> dict:
    case = next((item for item in CASES if item.id == kind), None)
    if case is None:
        raise ValueError('unknown exact physical fixture case')
    original_site = site()
    original_site['site_sha256'] = 'synthetic-physical-proof-source'
    if outcome_kind == 'missing_evidence':
        rows = None
        history_sha = None
    else:
        adapter = Adapter(original_site, case)
        rows = with_observed_approach([adapter.tick_and_sample() for _ in range(900)])
        if outcome_kind == 'incomplete_motion':
            rows = [dict(row, activity_observation='moving') for row in rows]
        history_sha = 'synthetic-physical-history-source'
    outcome = evaluate(case, rows, original_site, history_sha,
                       original_site['site_sha256'], diagnostic_fixture=True)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[outcome_kind]
    if outcome['physical_checks']['maneuver']['status'] != expected:
        raise ValueError('synthetic physical outcome differed: ' + kind + '/' + outcome_kind)
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('physical fixture output already exists')
    result = prove(args.case, args.kind)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(args.case, args.kind, result['physical_checks']['maneuver']['status'])


if __name__ == '__main__':
    main()
