"""Source-shaped CPU completion check for the two-actor crossing request."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(source, road, case, output):
    source, road, output = Path(source), Path(road), Path(output)
    rows = [json.loads(line) for line in source.read_text().splitlines()] if source.is_file() else []
    road_present = road.is_file() and '<OpenDRIVE' in road.read_text()
    joined = (len(rows) == 600 and all(
        r.get('video_frame') == i and r.get('native_frame') == 100 + i
        and abs(r.get('time_s', -1) - i / 20) < 1e-6
        and r.get('source_kind') == 'synthetic_native_sample'
        and r.get('through', {}).get('lane_id') == 1
        and r.get('entrant', {}).get('lane_id') == -1
        for i, r in enumerate(rows)))
    traversed = (joined and road_present and rows[0]['through']['y_m'] > 30
                 and rows[-1]['through']['y_m'] < -30
                 and rows[0]['entrant']['x_m'] < -10
                 and rows[-1]['entrant']['x_m'] > 30
                 and any(r['entrant']['speed_mps'] == 0 for r in rows[:140]))
    status = 'unverified' if not source.is_file() or not road.is_file() else ('met' if traversed else 'not_met')
    sources = {p.name: sha(p) for p in (source, road) if p.is_file()} or {'missing': source.name}
    check = {'status': status,
             'method': '600 joined source-shaped frames; both actor centers traverse the authored conflict area and entrant starts stopped; original full-body and lawful first yield await Native review',
             'sources': sources, 'observed_frames': len(rows),
             'original_native_observed': False,
             'physical_highway_verified': False}
    result = {'case_id': case, 'physical_checks': {'maneuver': check},
              'maneuver_completed': status == 'met',
              'realized_observables': {'both_actor_centers_traversed': True} if status == 'met' else {},
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': case, 'status': status, 'frames': len(rows)}))


def main():
    p = argparse.ArgumentParser()
    for name in ('source', 'road', 'case', 'output'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    assess(a.source, a.road, a.case, a.output)


if __name__ == '__main__':
    main()
