"""Independent C101303 comparison audit of construction and retained sources.

Diagnostic specifications exercise this code, but do not establish physical acceptance.
On Native output pass each case's original vehicle_history.jsonl to audit_pair.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

DIMENSIONS = {
    'body_gap': ({'requested_engineering_gap_m'}, 'gap'),
    'ego_speed': ({'ego_target_speed_mps'}, 'ego_speed'),
    'lead_speed': ({'lead_target_speed_mps'}, 'lead_speed'),
    'lead_braking': ({'lead_brake_start_fraction'}, 'braking'),
    'wet_surface': ({'requested_precipitation_pct', 'requested_wetness_pct'}, 'surface'),
    'following_end': ({'lane_change_start_fraction', 'lane_change_end_fraction'}, 'following_end'),
    'queued_traffic': ({'queued_traffic_required'}, 'traffic'),
}
IDENTITY = {'selected_case_id', 'supported_case_ids'}


def _construction_config(folder, entry, candidate=None):
    row = entry if candidate is None else next(
        c for c in entry['candidates'] if c['id'] == candidate)
    path = folder / row['construction']
    if hashlib.sha256(path.read_bytes()).hexdigest() != row['construction_sha256']:
        raise ValueError('comparison construction hash changed')
    construction = json.loads(path.read_text())
    config = next((f for f in construction['files'] if f['path'] == 'config.json'), None)
    if config is None:
        raise ValueError('missing embedded config.json')
    return json.loads(config['content'])


def _history(path):
    if path is None or not Path(path).is_file():
        raise ValueError('missing original vehicle_history.jsonl')
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line]
    if not rows:
        raise ValueError('empty original vehicle_history.jsonl')
    frames = [r['frame'] for r in rows]
    if len(frames) != len(set(frames)) or frames != sorted(frames):
        raise ValueError('unaligned or repeated source frames')
    for row in rows:
        for actor in ('ego', 'lead'):
            vertices = row[actor]['body_vertices_xy_m']
            velocity = row[actor]['velocity_mps']
            if len(vertices) < 4 or len(velocity) != 3 or not all(
                    math.isfinite(float(v)) for xy in vertices for v in xy):
                raise ValueError('missing complete-body source evidence')
            if not all(math.isfinite(float(v)) for v in velocity):
                raise ValueError('missing velocity source evidence')
        if not {'surface_condition', 'traffic_actor_ids', 'lane_change_started'} <= row.keys():
            raise ValueError('missing condition or traffic source evidence')
    return rows


def _metric(rows, kind):
    if kind == 'gap':
        return sum(min(v[0] for v in r['lead']['body_vertices_xy_m']) -
                   max(v[0] for v in r['ego']['body_vertices_xy_m']) for r in rows) / len(rows)
    if kind in ('ego_speed', 'lead_speed'):
        actor = kind.split('_')[0]
        return sum(math.sqrt(sum(v*v for v in r[actor]['velocity_mps'])) for r in rows) / len(rows)
    if kind == 'braking':
        return tuple(bool(r['lead'].get('brake_applied')) for r in rows)
    if kind == 'surface':
        return tuple(r['surface_condition'] for r in rows)
    if kind == 'following_end':
        return tuple((r['lane_change_started'], r['ego']['lane_id']) for r in rows)
    if kind == 'traffic':
        return tuple(tuple(r['traffic_actor_ids']) for r in rows)
    raise ValueError(kind)


def audit_pair(folder, comparison_id, left_source, right_source, candidate=None,
               left_candidate=None, right_candidate=None):
    folder = Path(folder)
    plan = json.loads((folder / 'case-plan.json').read_text())
    manifest = json.loads((folder / 'execution-manifest.json').read_text())
    pair = next(c for c in plan['comparisons'] if c['comparison_id'] == comparison_id)
    if len(pair['case_ids']) != 2 or comparison_id not in DIMENSIONS:
        raise ValueError('unsupported comparison')
    entries = [next(e for e in manifest['cases'] if e['case_id'] == case_id)
               for case_id in pair['case_ids']]
    if candidate and (left_candidate or right_candidate):
        raise ValueError('select shared candidate or explicit side candidates')
    left_candidate = left_candidate or candidate
    right_candidate = right_candidate or candidate
    configs = [_construction_config(folder, entries[0], left_candidate),
               _construction_config(folder, entries[1], right_candidate)]
    allowed, kind = DIMENSIONS[comparison_id]
    changed = {k for k in configs[0].keys() | configs[1].keys()
               if configs[0].get(k) != configs[1].get(k)} - IDENTITY
    if not changed or not changed <= allowed:
        raise ValueError('comparison construction changes undeclared or no dimension: '
                         + comparison_id + ': ' + ', '.join(sorted(changed)))
    for config in configs:
        if config['rate_hz'] != 20 or config['duration_s'] != 45 or len(config['cameras']) != 4:
            raise ValueError('comparison capture contract changed')
    left, right = _history(left_source), _history(right_source)
    if [r['frame'] for r in left] != [r['frame'] for r in right]:
        raise ValueError('comparison source time join differs')
    for a, b in zip(left, right):
        if a['road_id'] != b['road_id'] or a['ego']['actor_id'] != b['ego']['actor_id'] or a['lead']['actor_id'] != b['lead']['actor_id']:
            raise ValueError('comparison route or participant source differs')
        if kind != 'surface' and a['surface_condition'] != b['surface_condition']:
            raise ValueError('comparison surface differs unexpectedly')
        if kind != 'traffic' and a['traffic_actor_ids'] != b['traffic_actor_ids']:
            raise ValueError('comparison traffic differs unexpectedly')
    values = (_metric(left, kind), _metric(right, kind))
    if values[0] == values[1] or (isinstance(values[0], float) and
                                 math.isclose(values[0], values[1], abs_tol=1e-6)):
        raise ValueError('declared comparison difference absent in original source')
    return {'comparison_id': comparison_id, 'case_ids': pair['case_ids'],
            'left_candidate': left_candidate or 'primary',
            'right_candidate': right_candidate or 'primary', 'frames': len(left),
            'left_source_sha256': hashlib.sha256(Path(left_source).read_bytes()).hexdigest(),
            'right_source_sha256': hashlib.sha256(Path(right_source).read_bytes()).hexdigest(),
            'changed_config_keys': sorted(changed), 'observed_values': values}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--comparison', required=True, choices=sorted(DIMENSIONS))
    parser.add_argument('--left-source', type=Path, required=True)
    parser.add_argument('--right-source', type=Path, required=True)
    parser.add_argument('--candidate', choices=('fallback1', 'fallback2', 'fallback3'))
    parser.add_argument('--left-candidate', choices=('fallback1', 'fallback2', 'fallback3'))
    parser.add_argument('--right-candidate', choices=('fallback1', 'fallback2', 'fallback3'))
    args = parser.parse_args()
    print(json.dumps(audit_pair(args.folder, args.comparison, args.left_source,
                                args.right_source, args.candidate,
                                args.left_candidate, args.right_candidate), sort_keys=True))


if __name__ == '__main__':
    main()
