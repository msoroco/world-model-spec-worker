"""Diagnostic body-passage proof without legal or Native acceptance claims."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    if '.runtime-work' not in str(args.fixture.resolve()):
        raise ValueError('diagnostic fixture must remain under .runtime-work')
    data = json.loads(args.fixture.read_text())
    if data.get('case_id') != args.case or data.get('diagnostic_fixture') is not True:
        raise ValueError('wrong exact physical fixture')
    rows = data.get('body_history')
    if rows is None:
        status = 'unverified'
    elif not isinstance(rows, list) or len(rows) < 3:
        raise ValueError('incomplete diagnostic body history')
    else:
        if [row.get('frame') for row in rows] != list(range(len(rows))):
            raise ValueError('diagnostic body frames not contiguous')
        if any(type(row.get('ego_leading_station_m')) not in (int, float) or
               type(row.get('ego_full_body_clear')) is not bool for row in rows):
            raise ValueError('body geometry sample missing')
        entry = data['entry_station_m']
        status = 'met' if rows[0]['ego_leading_station_m'] < entry and any(
            row['ego_leading_station_m'] >= entry and row['ego_full_body_clear']
            for row in rows[1:]) else 'not_met'
    source = {'path': str(args.fixture),
              'sha256': hashlib.sha256(args.fixture.read_bytes()).hexdigest()}
    result = {'case_id': args.case, 'diagnostic_fixture': True,
              'provenance_kind': 'synthetic_fixture', 'physical_acceptance_claimed': False,
              'physical_checks': {'maneuver': {'status': status,
                                               'method': 'original-format body station and full clearance',
                                               'sources': [source]}},
              'maneuver_completed': status == 'met',
              'realized_observables': {'ego_clearance_station_m':
                  rows[-1]['ego_leading_station_m']} if status == 'met' else {},
              'legal_judgment': 'unresolved'}
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': args.case, 'status': status,
                      'diagnostic_fixture': True}, sort_keys=True))


if __name__ == '__main__':
    main()
