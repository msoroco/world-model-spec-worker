"""Independent original-source audit for the planned opposing-turn comparisons."""

import argparse
import hashlib
import json
from pathlib import Path

from opposing_turn_measurement import measure


SOURCES = ('subject_original.jsonl', 'opposing_original.jsonl',
           'topology_original.json', 'devices_original.json')
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _originals(root):
    root = Path(root)
    paths = [root / name for name in SOURCES]
    if any(not path.is_file() for path in paths):
        raise ValueError('missing original comparison source')
    for name in CAMERAS:
        if not (root / name).is_file():
            raise ValueError('missing named comparison camera source: ' + name)
    topology = json.loads(paths[2].read_text())
    devices = json.loads(paths[3].read_text())
    geometry = measure(*paths)
    return root, paths, topology, devices, geometry


def audit(left, right, comparison_id):
    if comparison_id not in ('uncontrolled_front_vs_rear',
                             'device_direction_exception', 'directed_front_vs_rear'):
        raise ValueError('unknown frozen comparison')
    a, ap, at, ad, ag = _originals(left)
    b, bp, bt, bd, bg = _originals(right)
    fixed_topology = ('source_map', 'junction_id', 'approach_road_id',
                      'approach_lane_ids', 'exit_road_ids',
                      'both_highways_two_directional', 'same_intersection',
                      'opposing_approaches')
    for key in fixed_topology:
        if key not in at or key not in bt or at[key] != bt[key]:
            raise ValueError('changed or missing fixed original topology: ' + key)
    af = [row['frame'] for row in ag['observations']]
    bf = [row['frame'] for row in bg['observations']]
    if af != bf:
        raise ValueError('changed simultaneous original frame interval')
    if comparison_id == 'device_direction_exception':
        if (ad.get('governing_device'), bd.get('governing_device')) != (
                'none', 'directs_alternate'):
            raise ValueError('missing governing-device direction contrast')
        if ap[0].read_bytes() != bp[0].read_bytes() or ap[1].read_bytes() != bp[1].read_bytes():
            raise ValueError('changed fixed original actor trajectories')
    else:
        expected = 'none' if comparison_id == 'uncontrolled_front_vs_rear' else 'directs_alternate'
        if ad.get('governing_device') != expected or bd.get('governing_device') != expected:
            raise ValueError('changed fixed governing-device state')
        # The trajectory difference is measured, not assigned a front/rear label.
        if ap[0].read_bytes() == bp[0].read_bytes() and ap[1].read_bytes() == bp[1].read_bytes():
            raise ValueError('missing original crossing-geometry contrast')
        if ag['closest']['opposing_ahead_of_subject_m'] == bg['closest']['opposing_ahead_of_subject_m'] and \
                ag['closest']['subject_ahead_of_opposing_m'] == bg['closest']['subject_ahead_of_opposing_m']:
            raise ValueError('missing measured relative-front contrast')
    return {
        'format': 'opposing-turn-comparison-audit-v1',
        'comparison_id': comparison_id,
        'fixed_topology_keys': list(fixed_topology),
        'simultaneous_frames': len(af),
        'left_closest': ag['closest'], 'right_closest': bg['closest'],
        'legal_front_of_each_other': 'unreviewed',
        'physical_completion': 'unreviewed',
        'sources': [{'path': str(path), 'sha256': _sha(path)}
                    for path in ap + bp + [a / name for name in CAMERAS]
                    + [b / name for name in CAMERAS]],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.left, args.right, args.comparison)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
