"""Source-bound CPU diagnostic of distant and close opposing approaches.

The time-to-conflict setting is an engineering control, not a legal cutoff.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from approaching_no_yield_observation import observe as observe_near
from far_approach_observation import observe as observe_far

SOURCES = ('intersection_geometry.json', 'interaction_history.jsonl', 'video_frames.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def checked(root):
    root = Path(root)
    seal = read(root / 'capture-seal.json')
    if seal.get('diagnostic_fixture') is not True:
        raise ValueError('Diagnostic source seal required')
    for name in SOURCES:
        if seal.get('sources', {}).get(name) != sha(root / name):
            raise ValueError('Paired original source differs from capture seal: ' + name)
    return rows(root / 'interaction_history.jsonl')


def compare(far_root, near_root):
    far_root, near_root = Path(far_root), Path(near_root)
    far, near = checked(far_root), checked(near_root)
    if len(far) != len(near) or len(far) != 900:
        raise ValueError('Paired full-duration sample count differs')
    for name in ('intersection_geometry.json', 'video_frames.jsonl'):
        if sha(far_root / name) != sha(near_root / name):
            raise ValueError('Fixed geometry or frame map differs: ' + name)
    fc, nc = read(far_root / 'config.json'), read(near_root / 'config.json')
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras',
                'approach_speed_mps', 'reciprocal_approach_speed_mps',
                'controller_release_ttc_s'):
        if fc[key] != nc[key]:
            raise ValueError('Fixed configuration differs: ' + key)
    if not (fc['selected_case_id'].endswith('__approaching_far') and
            nc['selected_case_id'].endswith('__approaching_no_yield')):
        raise ValueError('Exact far/near case pair required')
    displacement = None
    for f, n in zip(far, near):
        for key in ('frame', 'time_s', 'ego', 'reciprocal', 'ego_heading_deg',
                    'ego_left_indicator'):
            if f[key] != n[key]:
                raise ValueError('Fixed original source differs: ' + key)
        fo, no = f['oncoming'], n['oncoming']
        if (fo['actor_id'] != no['actor_id'] or
                fo['velocity_xy_mps'] != no['velocity_xy_mps']):
            raise ValueError('Fixed opposing identity or velocity differs')
        delta = [no['position_xy_m'][i] - fo['position_xy_m'][i] for i in (0, 1)]
        if displacement is None:
            displacement = delta
        if any(not math.isclose(delta[i], displacement[i], abs_tol=1e-8) for i in (0, 1)):
            raise ValueError('Opposing displacement is not constant')
        for fv, nv in zip(fo['body_vertices_xy_m'], no['body_vertices_xy_m']):
            if any(not math.isclose(nv[i]-fv[i], displacement[i], abs_tol=1e-8)
                   for i in (0, 1)):
                raise ValueError('Opposing body changed beyond approach distance')
    if displacement is None or displacement[0] >= 0 or not math.isclose(displacement[1], 0, abs_tol=1e-8):
        raise ValueError('Near opposing body is not closer on same approach')
    fobs, nobs = observe_far(far_root), observe_near(near_root)
    fturn, nturn = fobs['ego_turn_start_frame'], nobs['ego_turn_start_frame']
    if (fturn != nturn or not fturn < fobs['opposing_entry_frame'] or
            not nturn < nobs['opposing_entry_frame']):
        raise ValueError('Both branches must turn before opposing entry')
    direction = read(far_root / 'intersection_geometry.json')['oncoming_direction_xy']
    conflict = read(far_root / 'intersection_geometry.json')['conflict_point_xy_m']
    nrow = next(row for row in near if row['frame'] == nturn)['oncoming']
    remaining = sum((conflict[i]-nrow['position_xy_m'][i])*direction[i] for i in (0, 1))
    closing = sum(nrow['velocity_xy_mps'][i]*direction[i] for i in (0, 1))
    near_ttc = remaining / closing
    release = fc['controller_release_ttc_s']
    far_ttc = fobs['turn_sample']['kinematic_time_to_conflict_s']
    if not 0 < near_ttc < release <= far_ttc:
        raise ValueError('Measured engineering distance contrast absent')
    return {'format': 'c109749-far-near-comparison-diagnostic',
            'software_checks_passed': True, 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False, 'legal_verdict_asserted': False,
            'frames': len(far), 'turn_frame': fturn,
            'far_entry_frame': fobs['opposing_entry_frame'],
            'near_entry_frame': nobs['opposing_entry_frame'],
            'far_time_to_conflict_s': far_ttc,
            'near_time_to_conflict_s': near_ttc,
            'engineering_release_s': release,
            'opposing_displacement_xy_m': displacement,
            'far_history_sha256': sha(far_root / 'interaction_history.jsonl'),
            'near_history_sha256': sha(near_root / 'interaction_history.jsonl')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--far-root', required=True, type=Path)
    parser.add_argument('--near-root', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(args.far_root, args.near_root), sort_keys=True))


if __name__ == '__main__':
    main()
