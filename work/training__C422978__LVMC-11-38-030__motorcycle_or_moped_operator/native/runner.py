"""Exact C422978 Native construction preflight for the paired sidewalk cases.

The check path is CPU only. Original Native execution is pending physical work.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
AID = 'training__C422978__LVMC-11-38-030__motorcycle_or_moped_operator'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(folder, case, candidate):
    folder = Path(folder)
    if case not in ('witness_1', 'witness_2') or candidate not in (
            'primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown exact case or candidate')
    config = json.loads((folder / 'config.json').read_text())
    if (config['case_id'] != AID + '__' + case or
            config['candidate_id'] != candidate or
            config['cell_id'] != 'C422978' or
            config['law_id'] != 'LVMC-11-38-030' or
            config['actor'] != 'motorcycle_or_moped_operator' or
            config['rate_hz'] != 20 or config['duration_s'] != 24):
        raise ValueError('Exact motorcycle case configuration differs')
    road = folder / 'road.xodr'
    tracks = folder / 'requested-tracks.jsonl'
    if sha(road) != config['road_sha256'] or sha(tracks) != config['tracks_sha256']:
        raise ValueError('Authored road or motorcycle tracks differ')
    source = folder / 'assignment-source.json'
    if sha(source) != config['assignment_sha256']:
        raise ValueError('Frozen motorcycle assignment source differs')
    lanes = {int(lane.attrib['id']): lane.attrib['type'] for lane in
             ET.parse(road).findall('.//lane')}
    if lanes.get(1) != 'driving' or lanes.get(-1) != 'driving' or lanes.get(-2) != 'sidewalk':
        raise ValueError('Two-way road or sidewalk lane absent')
    rows = [json.loads(line) for line in tracks.read_text().splitlines()]
    if len(rows) != 480:
        raise ValueError('Motorcycle request frame count differs')
    for index, row in enumerate(rows):
        if (row['frame'] != index or abs(row['time_s'] - index/20) > 1e-4 or
                row['motorcycle_blueprint'] != 'vehicle.kawasaki.ninja' or
                row['requested_speed_mps'] != 4.0 or
                row['source_kind'] != 'authored_native_request'):
            raise ValueError('Motorcycle request frame/identity differs')
    overlap = [row['frame'] for row in rows if
               row['requested_center_xy_m'][1] - .4 < -3.5 and
               row['requested_center_xy_m'][1] + .4 > -5.5]
    if (bool(overlap) != (case == 'witness_2') or
            (overlap and len(overlap) < 390)):
        raise ValueError('Paired requested sidewalk occupancy differs')
    return {'passed': True, 'case_id': config['case_id'], 'candidate_id': candidate,
            'track_rows': len(rows), 'requested_sidewalk_overlap_frames': len(overlap),
            'carla_imported': False, 'original_native_observed': False,
            'physical_or_legal_outcome_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=Path, default=HERE)
    parser.add_argument('--case')
    parser.add_argument('--candidate')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    config = json.loads((args.folder / 'config.json').read_text())
    print(json.dumps(check(args.folder, args.case or config['case_suffix'],
                           args.candidate or config['candidate_id'])))
