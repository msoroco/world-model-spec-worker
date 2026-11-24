"""Independent Cartesian source audit for branch requests and placement context."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / 'cases/branch-requests'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def grid(kind, base=BASE):
    if kind == 'signal':
        suffixes = ('signal_red_proceed', 'signal_red_stop',
                    'signal_green_proceed', 'signal_green_stop')
        condition = lambda row: row['signal_state_observed'].rsplit('.', 1)[-1].lower()
        values = ('red', 'green')
    elif kind == 'officer':
        suffixes = ('officer_no_direction_proceed', 'officer_no_direction_stop',
                    'officer_directed_proceed', 'officer_directed_stop')
        condition = lambda row: 'proceed' if row['officer_actor'] else 'none'
        values = ('none', 'proceed')
    else:
        raise ValueError('Unknown comparison grid')
    cells = {}
    roads = set();cameras = set()
    for suffix in suffixes:
        bundle = base / suffix
        cfg = json.loads((bundle / 'config.json').read_text())
        actors = rows(bundle / 'raw-fixture/native-raw-actors.jsonl')
        if len(actors) != 600 or any(row['frame'] != i for i, row in enumerate(actors)):
            raise ValueError('Grid source window differs')
        observed = {condition(row) for row in actors}
        if len(observed) != 1 or next(iter(observed)) not in values:
            raise ValueError('Grid condition source differs')
        stop = suffix.endswith('_stop')
        stopped = sum(row['ego']['speed_mps'] < 0.1 for row in actors)
        if stop != (stopped >= 20):
            raise ValueError('Grid vehicle response source differs')
        key = (next(iter(observed)), stop)
        if key in cells:
            raise ValueError('Duplicate grid corner')
        cells[key] = {'case_id': cfg['case_id'], 'source_sha256': sha(bundle / 'raw-fixture/native-raw-actors.jsonl'),
                      'road_sha256': cfg['road_sha256'], 'camera_policy': cfg['camera_policy'],
                      'stop_request': stop}
        roads.add(cfg['road_sha256']);cameras.add(cfg['camera_policy'])
    if set(cells) != {(value, stop) for value in values for stop in (False, True)}:
        raise ValueError('Incomplete joint comparison grid')
    if len(roads) != 1 or cameras != {'standard'}:
        raise ValueError('Comparison changed fixed road or camera')
    return {'kind': kind, 'cells': [cells[(value, stop)] for value in values for stop in (False, True)],
            'fixed_road_sha256': roads.pop(), 'fixed_camera_policy': 'standard',
            'axes': ['branch_condition', 'commanded_stop_request'], 'legal_verdict_claimed': False}


def placement(base=BASE):
    cells = []
    tracks = set();roads = set()
    for suffix in ('placement_record_absent', 'placement_record_supplied'):
        bundle = base / suffix
        cfg = json.loads((bundle / 'config.json').read_text())
        record = json.loads((bundle / 'placement-record.json').read_text())
        if record['official_placement_verified'] is not False or record['administrative_authenticity_verified'] is not False:
            raise ValueError('Placement source claims authority')
        if record['document_present'] != cfg['placement_document_present']:
            raise ValueError('Placement context did not match case')
        tracks.add(cfg['tracks_sha256']);roads.add(cfg['road_sha256'])
        cells.append({'case_id': cfg['case_id'], 'document_present': record['document_present'],
                      'record_sha256': sha(bundle / 'placement-record.json')})
    if len(tracks) != 1 or len(roads) != 1 or {c['document_present'] for c in cells} != {False, True}:
        raise ValueError('Placement pair changed fixed motion/road or omitted a status')
    return {'kind': 'placement_source_availability', 'cells': cells,
            'fixed_tracks_sha256': tracks.pop(), 'fixed_road_sha256': roads.pop(),
            'official_placement_verified': False, 'legal_verdict_claimed': False}


def main():
    result = {'format': 'c10389-branch-comparison-source-audit-v1',
              'comparisons': [grid('signal'), grid('officer'), placement()],
              'source_kind': 'synthetic_cpu', 'accepted': False}
    path = BASE / 'branch-comparison-proof.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps({'comparison_count': len(main()['comparisons'])}))
