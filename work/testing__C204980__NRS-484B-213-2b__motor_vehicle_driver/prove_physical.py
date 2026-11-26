"""Diagnostic physical outcomes from sealed synthetic railroad body rows."""
import argparse
import json
from pathlib import Path

from rail_left import CASES, measure_original

ROOT = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'), required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    suffix = a.case.removeprefix(ROOT.name + '__')
    case = next((item for item in CASES if item.case_id == suffix), None)
    if case is None or a.case != ROOT.name + '__' + suffix:
        raise ValueError('unknown exact rail case')
    fixture = ROOT / 'diagnostics' / suffix
    rows = [json.loads(line) for line in (fixture/'rail-frames.jsonl').read_text().splitlines()]
    context = json.loads((fixture/'rail-context.json').read_text())
    if a.kind == 'missing_evidence':
        rows = []
    elif a.kind == 'incomplete_motion':
        for row in rows:
            row['leading_body_station_m'] -= 20
            row['trailing_body_station_m'] -= 20
    try:
        measured = measure_original(rows, context['scene'], case)
    except ValueError as error:
        measured = {}
        failure = str(error)
    else:
        failure = None
    status = 'unverified' if not rows else 'met' if measured else 'not_met'
    result = {
        'case_id': a.case, 'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
        'maneuver_completed': status == 'met',
        'physical_checks': {'maneuver': {
            'status': status,
            'method': '900 original-index diagnostic body/crossing station, side and traversal probe',
            'sources': ['diagnostics/'+suffix+'/rail-frames.jsonl',
                        'diagnostics/'+suffix+'/rail-context.json'],
            'failure': failure}},
        'realized_observables': measured}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, sort_keys=True) + '\n')
    print(json.dumps({'case_id': a.case, 'kind': a.kind, 'status': status,
                      'diagnostic_fixture': True}, sort_keys=True))


if __name__ == '__main__':
    main()
