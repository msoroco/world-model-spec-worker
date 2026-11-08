"""Compare source-bound synthetic roadway/sidewalk motorcycle pairs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
SOURCES = ('native-observed.jsonl', 'native-map-readback.json',
           'video_frames.jsonl', 'capture/evidence.jsonl')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def compare(candidate, roadway=None, sidewalk=None):
    if candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown exact candidate')
    roadway = Path(roadway) if roadway else HERE / 'saved-fixtures/witness_1' / candidate
    sidewalk = Path(sidewalk) if sidewalk else HERE / 'saved-fixtures/witness_2' / candidate
    configs = [read(HERE / 'drafts' / case / candidate / 'config.json')
               for case in ('witness_1', 'witness_2')]
    for key in ('candidate_id', 'cell_id', 'law_id', 'actor', 'rate_hz', 'duration_s',
                'road_sha256', 'assignment_sha256', 'policy'):
        if configs[0][key] != configs[1][key]:
            raise ValueError('Paired construction changed fixed condition: ' + key)
    if configs[0]['candidate_id'] != candidate:
        raise ValueError('Candidate/config binding differs')
    packets = []
    reports = []
    for case, folder in (('witness_1', roadway), ('witness_2', sidewalk)):
        manifest = read(CASE / 'draft-execution-manifest.json')
        entry = next(x for x in manifest['cases'] if x['case_id'].endswith('__' + case))
        ref = entry if candidate == 'primary' else next(
            x for x in entry['candidates'] if x['id'] == candidate)
        if ref['construction_sha256'] != sha(CASE / ref['construction']):
            raise ValueError('Exact construction hash differs')
        report = read(CASE / 'draft-candidates' / case / candidate / 'finalization-analysis.json')
        result = read(CASE / 'draft-candidates' / case / candidate / 'finalization-result.json')
        measured = report['measurements']['motorcycle_sidewalk_occupancy']['value']
        if report['case_id'] != entry['case_id'] or result['case_id'] != entry['case_id']:
            raise ValueError('Measured case binding differs')
        if result['accepted'] or result['provenance_kind'] != 'synthetic_local_diagnostic':
            raise ValueError('Synthetic evidence cannot claim acceptance')
        for source in SOURCES:
            if measured['source_hashes'][source] != sha(folder / source):
                raise ValueError('Measured source hash differs: ' + source)
        if measured['frames'] != 480 or measured['source_kind'] != 'synthetic_cpu':
            raise ValueError('Synthetic measurement frame/provenance differs')
        packets.append(rows(folder / 'native-observed.jsonl'))
        reports.append(measured)
    left, right = packets
    if len(left) != len(right) or len(left) != 480:
        raise ValueError('Paired frame count differs')
    for index, (a, b) in enumerate(zip(left, right)):
        for key in ('frame', 'native_frame', 'time_s', 'motorcycle_blueprint',
                    'speed_mps', 'native_road_id'):
            if a[key] != b[key]:
                raise ValueError(f'Paired fixed observation changed: {key} frame {index}')
        if a['center_native_xy_m'][0] != b['center_native_xy_m'][0]:
            raise ValueError('Paired longitudinal position changed')
        if a['speed_mps'] != 4.0:
            raise ValueError('Paired speed differs from fixed 4 m/s request')
        if a['motorcycle_blueprint'] != 'vehicle.kawasaki.ninja':
            raise ValueError('Paired subject is not motorcycle')
    for source in ('native-map-readback.json', 'video_frames.jsonl',
                   'capture/evidence.jsonl'):
        if sha(roadway / source) != sha(sidewalk / source):
            raise ValueError('Paired fixed source changed: ' + source)
    if reports[0]['moving_sidewalk_overlap_frames'] != 0:
        raise ValueError('Roadway witness has sidewalk occupancy')
    if reports[1]['moving_sidewalk_overlap_frames'] < 390:
        raise ValueError('Sidewalk witness lacks planned occupancy')
    if reports[0]['city_sidewalk_verified'] or reports[1]['city_sidewalk_verified']:
        raise ValueError('Synthetic city location must remain unverified')
    return {'candidate_id': candidate,
            'roadway_overlap_frames': reports[0]['moving_sidewalk_overlap_frames'],
            'sidewalk_overlap_frames': reports[1]['moving_sidewalk_overlap_frames'],
            'difference_frames': reports[1]['moving_sidewalk_overlap_frames'] -
                                 reports[0]['moving_sidewalk_overlap_frames'],
            'fixed_motorcycle_blueprint': 'vehicle.kawasaki.ninja',
            'fixed_frame_count': 480, 'fixed_speed_mps': 4.0,
            'source_hashes': {case: {name: sha(folder / name) for name in SOURCES}
                              for case, folder in (('witness_1', roadway),
                                                   ('witness_2', sidewalk))},
            'scope': 'unselected synthetic controlled measurement; no original Native or legal verdict'}
