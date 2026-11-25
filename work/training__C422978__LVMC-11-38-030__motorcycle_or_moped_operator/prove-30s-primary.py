"""Independently audit the unselected 600-frame sidewalk witness pair."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
OUT = HERE / 'extended-primary'
SCRATCH = ROOT / '.runtime-work/c422978-30s-v4'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def evaluate(construction, assignment, law_text):
    files = {f['path']: f['content'].encode() for f in construction['files']}
    cfg = json.loads(files['config.json'])
    rows = [json.loads(line) for line in files['requested-tracks.jsonl'].splitlines()]
    if len(rows) != 600 or cfg['rate_hz'] != 20 or cfg['duration_s'] != 30:
        raise ValueError('Thirty-second timing differs')
    if cfg['assignment_sha256'] != sha(assignment) or files['assignment-source.json'] != assignment:
        raise ValueError('Frozen assignment differs')
    if json.loads(assignment)['law']['text'] != law_text:
        raise ValueError('Frozen statutory text differs')
    if cfg['tracks_sha256'] != sha(files['requested-tracks.jsonl']) or cfg['road_sha256'] != sha(files['authored-road.xodr']):
        raise ValueError('Construction source hash differs')
    lanes = {int(node.attrib['id']): node.attrib['type'] for node in
             ET.fromstring(files['authored-road.xodr']).findall('.//lane')}
    if lanes.get(-2) != 'sidewalk' or lanes.get(-1) != 'driving' or lanes.get(1) != 'driving':
        raise ValueError('Frozen cell road or sidewalk differs')
    overlap = []
    longitudinal = []
    for i, row in enumerate(rows):
        if row['frame'] != i or abs(row['time_s'] - i / 20) > 1e-5:
            raise ValueError('Frame-time join differs')
        if row['motorcycle_blueprint'] != 'vehicle.kawasaki.ninja' or row['requested_speed_mps'] != 4:
            raise ValueError('Motorcycle identity or speed differs')
        if row['source_kind'] != 'authored_native_request':
            raise ValueError('Request improperly claims observation')
        x, y = row['requested_center_xy_m']
        if abs(x - (10 + .2 * i)) > 1e-4:
            raise ValueError('Longitudinal trajectory differs')
        longitudinal.append(x)
        if y - .4 < -3.5 and y + .4 > -5.5:
            overlap.append(i)
    return rows, overlap, longitudinal


def main():
    assignment = (ROOT / 'inputs' / AID / 'assignment.json').read_bytes()
    plan = json.loads((HERE / 'case-plan.json').read_text())
    law_text = plan['source_law']['text']
    manifest = json.loads((OUT / 'manifest.json').read_text())
    if manifest['assignment_sha256'] != sha(assignment) or len(manifest['cases']) != 2:
        raise ValueError('Manifest or frozen assignment differs')
    results = []
    tracks = []
    for index, suffix in enumerate(('witness_1', 'witness_2')):
        entry = manifest['cases'][index]
        if entry['case_id'] != AID + '__' + suffix:
            raise ValueError('Witness identity differs')
        source = OUT / entry['construction']
        if sha(source.read_bytes()) != entry['construction_sha256']:
            raise ValueError('Construction reference hash differs')
        construction = json.loads(source.read_text())
        rows, overlap, longitudinal = evaluate(construction, assignment, law_text)
        if len(overlap) != (0 if index == 0 else 520):
            raise ValueError('Requested sidewalk occupancy differs')
        log = SCRATCH / (suffix + '-primary') / 'offline.log'
        if not log.is_file() or 'OK' not in log.read_text():
            raise ValueError('Pinned offline test proof absent')
        tracks.append(rows)
        results.append({'case_id': entry['case_id'], 'construction_sha256': sha(source.read_bytes()),
                        'offline_log_sha256': sha(log.read_bytes()), 'frames': len(rows),
                        'duration_s': 30, 'requested_sidewalk_overlap_frames': len(overlap),
                        'first_overlap_frame': overlap[0] if overlap else None,
                        'last_request_x_m': longitudinal[-1]})
    for left, right in zip(*tracks):
        if left['frame'] != right['frame'] or left['requested_center_xy_m'][0] != right['requested_center_xy_m'][0]:
            raise ValueError('Pair time or longitudinal motion differs')
    construction = json.loads((OUT / 'witness_2/construction.json').read_text())
    negatives = []
    for label, mutate in (
        ('changed_frozen_law', lambda c: next(f for f in c['files'] if f['path'] == 'assignment-source.json').update(content='{}')),
        ('changed_track_hash', lambda c: next(f for f in c['files'] if f['path'] == 'config.json').update(content=next(f for f in c['files'] if f['path'] == 'config.json')['content'].replace('"tracks_sha256": "', '"tracks_sha256": "0'))),
    ):
        copy = json.loads(json.dumps(construction))
        mutate(copy)
        try:
            evaluate(copy, assignment, law_text)
        except (ValueError, KeyError):
            negatives.append(label)
        else:
            raise ValueError('Negative unexpectedly passed: ' + label)
    report = {'format': 'c422978-30s-unselected-pair-proof-v1',
              'source_law_sha256': plan['source_law']['sha256'],
              'assignment_sha256': sha(assignment),
              'manifest_sha256': sha((OUT / 'manifest.json').read_bytes()),
              'results': results, 'negative_rejections': negatives,
              'comparison_fixed': ['motorcycle blueprint', '20 Hz frame times', '4 m/s requested speed', 'longitudinal path', 'authored road and four camera names'],
              'deliberate_difference': 'requested lateral motorcycle path relative to right sidewalk lane',
              'original_native_observed': False, 'city_authority_reviewed': False,
              'driveway_rule_composition_reviewed': False, 'legal_verdict': None,
              'delivery_ready': False}
    (OUT / 'proof.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'proof_sha256': sha((OUT / 'proof.json').read_bytes()),
                      'overlap': [r['requested_sidewalk_overlap_frames'] for r in results],
                      'negatives': negatives}))


if __name__ == '__main__':
    main()
