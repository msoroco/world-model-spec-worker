"""CPU positive and damaging-source checks for the proposed entry branch."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent / 'native'))
from entry_boundary import audit


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def main():
    scratch = Path(os.environ['TMPDIR']).resolve()
    with tempfile.TemporaryDirectory(prefix='c227853-entry-', dir=scratch) as name:
        root = Path(name)
        sources = {}
        for label in ('private_origin', 'public_highway', 'boundary', 'pre_movement_review'):
            path = root / (label + '.txt')
            path.write_text('Synthetic CPU-only ' + label + ' source; not physical authority.\n')
            sources[label] = {'path': path.name, 'citation': 'software fixture ' + label,
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest = {'format': 'nrs-484b-410-entry-boundary-v1', 'state': 'Nevada',
                    'boundary_coordinate_system': 'local_xy_m', 'sources': sources,
                    'review_conclusion': 'undetermined', 'review_completed_before_movement': True}
        trace = [{'frame': 0, 'native_frame': 101, 'time_s': 0.0,
                  'ego_origin_side': True, 'ego_highway_side': False, 'ego_moving': False,
                  'ego_boundary_signed_distance_m': -4.0,
                  'approaching_traffic_native_frame': 101},
                 {'frame': 1, 'native_frame': 102, 'time_s': 0.05,
                  'ego_origin_side': True, 'ego_highway_side': False, 'ego_moving': True,
                  'ego_boundary_signed_distance_m': -0.5,
                  'approaching_traffic_native_frame': 102},
                 {'frame': 2, 'native_frame': 103, 'time_s': 0.1,
                  'ego_origin_side': False, 'ego_highway_side': True, 'ego_moving': True,
                  'ego_boundary_signed_distance_m': 0.5,
                  'approaching_traffic_native_frame': 103}]
        mp, tp = root / 'manifest.json', root / 'trace.jsonl'
        write(mp, manifest)
        tp.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in trace))
        positive = audit(mp, tp)
        failures = {}
        variants = {
            'missing_origin': ('manifest', lambda x: x['sources'].pop('private_origin')),
            'stale_boundary': ('manifest', lambda x: x['sources']['boundary'].update(sha256='0' * 64)),
            'late_review': ('manifest', lambda x: x.update(review_completed_before_movement=False)),
            'starts_highway': ('trace', lambda x: x[0].update(ego_origin_side=False, ego_highway_side=True)),
            'no_crossing': ('trace', lambda x: x[2].update(ego_origin_side=True, ego_highway_side=False)),
            'missing_traffic_join': ('trace', lambda x: [r.pop('approaching_traffic_native_frame') for r in x]),
            'partial_traffic_join': ('trace', lambda x: x[2].pop('approaching_traffic_native_frame')),
            'bad_time': ('trace', lambda x: x[2].update(time_s=0.04)),
            'side_distance_mismatch': ('trace', lambda x: x[2].update(ego_boundary_signed_distance_m=-0.5)),
            'return_off_highway': ('trace', lambda x: x.append({
                **x[2], 'frame': 3, 'native_frame': 104, 'time_s': 0.15,
                'ego_origin_side': True, 'ego_highway_side': False,
                'ego_boundary_signed_distance_m': -0.5,
                'approaching_traffic_native_frame': 104})),
        }
        for label, (target, mutate) in variants.items():
            m, t = copy.deepcopy(manifest), copy.deepcopy(trace)
            mutate(m if target == 'manifest' else t)
            write(mp, m)
            tp.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in t))
            try:
                audit(mp, tp)
            except ValueError as error:
                failures[label] = str(error)
            else:
                raise AssertionError(label + ' unexpectedly passed')
        print(json.dumps({'positive': positive, 'negative_rejections': failures,
                          'diagnostic_only': True}, sort_keys=True))


if __name__ == '__main__':
    main()
