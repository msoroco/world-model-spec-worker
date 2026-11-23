"""Independent controlled-request audit; no Native or legal conclusion."""
import json
from pathlib import Path

from request import CASES, HERE, PLAN, SOURCE, sha


def audit():
    source = json.loads(SOURCE.read_text())
    plan = json.loads(PLAN.read_text())
    if source['law']['text'] != plan['source_law_text'] or len(plan['comparisons']) != 1:
        raise ValueError('Law or comparison changed')
    comparison = plan['comparisons'][0]
    if comparison['deliberate_differences'] != ['first intersection turn direction']:
        raise ValueError('Controlled variable changed')
    routes = {}
    for suffix in CASES:
        bundle = HERE / 'drafts' / suffix
        cfg = json.loads((bundle / 'config.json').read_text())
        rows = [json.loads(line) for line in (bundle / 'requested-tracks.jsonl').read_text().splitlines()]
        if (cfg['assignment_sha256'] != sha(SOURCE) or
                cfg['case_plan_sha256'] != sha(PLAN) or
                cfg['tracks_sha256'] != sha(bundle / 'requested-tracks.jsonl') or
                len(rows) != 600 or cfg['duration_s'] != 30 or
                any(row['frame'] != i or row['time_s'] != (i+1)/20 or
                    row['cab_stand_departure_station_m'] != 5 or
                    row['first_intersection_station_m'] != 80 or
                    row['next_intersection_station_m'] != 130 or
                    row['stand_designation_verified'] is not False or
                    row['posted_notice_verified'] is not False or
                    row['original_native_observed'] is not False or
                    row['legal_verdict'] is not None for i, row in enumerate(rows))):
            raise ValueError('Source, duration or unverified request changed')
        routes[suffix] = rows
    right, straight = (routes[suffix] for suffix in ('probe_01', 'probe_02'))
    pre = [i for i, row in enumerate(right) if row['requested_x_m'] < 80]
    if not pre or any((right[i]['requested_x_m'], right[i]['requested_y_m']) !=
                      (straight[i]['requested_x_m'], straight[i]['requested_y_m']) for i in pre):
        raise ValueError('Pre-intersection path is not controlled')
    if not (any(row['requested_y_m'] < 0 for row in right) and
            all(row['requested_x_m'] <= 80 for row in right) and
            any(row['requested_x_m'] > 80 for row in straight) and
            all(row['requested_y_m'] == 0 for row in straight)):
        raise ValueError('First-turn contrast absent')
    result = {'format': 'c110875-taxi-request-comparison-audit-v1',
              'assignment_id': source['assignment_id'],
              'frames_audited': 1200, 'identical_pre_intersection_frames': len(pre),
              'first_intersection_station_m': 80, 'later_intersection_station_m': 130,
              'authored_request_only': True, 'original_native_observed': False,
              'stand_designation_verified': False, 'posted_notice_verified': False,
              'delivery_ready': False}
    (HERE / 'comparison-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(audit()))
