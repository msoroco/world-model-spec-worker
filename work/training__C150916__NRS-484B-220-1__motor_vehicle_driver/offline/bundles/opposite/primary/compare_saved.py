"""Compare two source-bound saved one-way captures under fixed context."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_saved import FILES, measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def compare(designated, opposite, expected_hashes=None):
    designated, opposite = Path(designated), Path(opposite)
    sources = {case: {name: sha(folder/name) for name in FILES}
               for case, folder in (('designated', designated), ('opposite', opposite))}
    if expected_hashes is not None and sources != expected_hashes:
        raise ValueError('Saved comparison source hashes differ')
    if any(sources['designated'][name] != sources['opposite'][name]
           for name in ('road-readback.json', 'designation-record.json')):
        raise ValueError('Saved comparison fixed road or designation differs')
    forward, reverse = measure(designated), measure(opposite)
    if forward['case'] != 'designated' or reverse['case'] != 'opposite':
        raise ValueError('Saved comparison case pairing differs')
    if forward['source_kind'] != reverse['source_kind']:
        raise ValueError('Saved comparison source kinds differ')
    a, b = rows(designated/'native-observed.jsonl'), rows(opposite/'native-observed.jsonl')
    for i, (left, right) in enumerate(zip(a, b)):
        if (left['frame'] != i or right['frame'] != i or
                left['time_s'] != right['time_s'] or
                left['native_frame'] != right['native_frame'] or
                left['ego_speed_mps'] != right['ego_speed_mps'] or
                left['ego_y_m'] != right['ego_y_m'] or
                left['lane_id'] != right['lane_id'] or
                left['ego_heading_deg'] != 0 or right['ego_heading_deg'] != 180 or
                abs(left['ego_x_m'] + right['ego_x_m'] - 200) > 1e-4 or
                abs(left['ego_velocity_x_mps'] + right['ego_velocity_x_mps']) > 1e-4):
            raise ValueError('Saved comparison fixed controls or mirror differ')
    if (forward['signed_ego_displacement_m'] != -reverse['signed_ego_displacement_m'] or
            not forward['direction_matches_designation'] or
            reverse['direction_matches_designation']):
        raise ValueError('Saved comparison directional contrast differs')
    return {'format': 'c150916-saved-controlled-comparison-v1',
            'source_kind': forward['source_kind'], 'source_hashes': sources,
            'paired_frames': len(a), 'fixed_road_and_designation_bytes': True,
            'fixed_frame_time_speed_lane': True, 'mirror_center_x_m': 100,
            'designated_measurement': forward, 'opposite_measurement': reverse,
            'direction_match_contrast': [True, False],
            'original_native_observed': forward['source_kind'] == 'original_native',
            'accepted_comparison': False, 'legal_verdict': None, 'delivery_ready': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('designated', type=Path)
    parser.add_argument('opposite', type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(args.designated, args.opposite), indent=2))
