"""Independent CPU geometry and exact eight-request audit."""
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
sys.path.insert(0, str(ROOT / '.runtime-work/python-deps'))
from traffic_spec_adapter.geometry import static_map


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads((HERE / 'drafts/manifest.json').read_text())
assignment = ROOT / 'inputs' / CASE.name / 'assignment.json'
plan = CASE / 'case-plan.json'
road = HERE / 'road.xodr'
assert manifest['assignment_sha256'] == sha(assignment)
assert manifest['case_plan_sha256'] == sha(plan)
assert manifest['road_sha256'] == sha(road)
assert manifest['physical_or_legal_result_observed'] is False
assert manifest['delivery_ready'] is False and len(manifest['entries']) == 8
tree = ET.parse(road)
lanes = {int(x.attrib['id']): x for x in tree.findall('.//lane')}
assert {k: v.attrib['type'] for k, v in lanes.items()} == {
    1: 'driving', 0: 'none', -1: 'driving', -2: 'sidewalk'}
assert float(lanes[-2].find('width').attrib['a']) == 4.0
assert not tree.findall('.//junction') and not tree.findall('.//signal')
regions, shapes, keys = static_map(road, include_non_driving=True)
sidewalk_ids = [r['id'] for r in regions if r['kind'] == 'sidewalk']
assert len(sidewalk_ids) == 1 and shapes[sidewalk_ids[0]].is_valid
assert abs(shapes[sidewalk_ids[0]].area - 560) < 1
assert abs(shapes[keys[(1, 0, -1)]].area - 490) < 1
index = {(e['case_id'].rsplit('__', 1)[-1], e['candidate_id']): e for e in manifest['entries']}
assert len(index) == 8
measurements = []
for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
    pair = {}
    for case in ('reference', 'contrast'):
        entry = index[(case, candidate)]
        config_path, track_path = CASE / entry['config'], CASE / entry['tracks']
        config = json.loads(config_path.read_text())
        tracks = [json.loads(line) for line in track_path.read_text().splitlines()]
        assert config['case_id'] == CASE.name + '__' + case
        assert config['candidate_id'] == candidate and config['rate_hz'] == 20
        assert config['road_sha256'] == sha(road) and config['tracks_sha256'] == sha(track_path)
        assert config['assignment_sha256'] == sha(assignment) and config['case_plan_sha256'] == sha(plan)
        assert config['status'] == 'unselected_native_request' and len(tracks) == 480
        assert all(r['frame'] == i and abs(r['time_s']-i/20) < 1e-5 and
                   r['subject_blueprint_request'] == 'vehicle.carlamotors.carlacola' and
                   r['source_kind'] == 'authored_native_request' and
                   r['driveway_or_alley_requested'] is False for i, r in enumerate(tracks))
        overlap = [i for i, r in enumerate(tracks) if
                   r['requested_center_xy_m'][1]-1.2 < -3.5 and
                   r['requested_center_xy_m'][1]+1.2 > -7.5]
        inside = [i for i, r in enumerate(tracks) if
                  r['requested_center_xy_m'][1]-1.2 >= -7.5 and
                  r['requested_center_xy_m'][1]+1.2 <= -3.5]
        assert entry['metric'] == {
            'requested_moving_sidewalk_overlap_frames': len(overlap),
            'first_requested_overlap_frame': overlap[0] if overlap else None,
            'requested_full_body_inside_frames': len(inside),
            'first_requested_full_body_inside_frame': inside[0] if inside else None}
        assert bool(overlap) == (case == 'contrast')
        if case == 'contrast': assert len(inside) >= 350
        pair[case] = tracks
        measurements.append({'case': case, 'candidate': candidate,
                             'tracks_sha256': sha(track_path),
                             'overlap_frames': len(overlap), 'inside_frames': len(inside)})
    for a, b in zip(pair['reference'], pair['contrast']):
        aa, bb = dict(a), dict(b)
        aa.pop('requested_center_xy_m'); bb.pop('requested_center_xy_m')
        assert aa == bb
        assert a['requested_center_xy_m'][0] == b['requested_center_xy_m'][0]
    assert any(a['requested_center_xy_m'][1] != b['requested_center_xy_m'][1]
               for a, b in zip(pair['reference'], pair['contrast']))
assert index[('contrast','fallback1')]['metric']['first_requested_overlap_frame'] < \
       index[('contrast','primary')]['metric']['first_requested_overlap_frame']
assert index[('contrast','fallback2')]['metric']['first_requested_full_body_inside_frame'] > \
       index[('contrast','primary')]['metric']['first_requested_full_body_inside_frame']
assert all(index[(case,'fallback3')]['metric'] == index[(case,'primary')]['metric']
           for case in ('reference','contrast'))
audit = {'format': 'c422978-heavy-native-construction-audit-v1',
         'passed': True, 'manifest_sha256': sha(HERE/'drafts/manifest.json'),
         'road_sha256': sha(road), 'candidate_rows': measurements,
         'parser_valid_sidewalk_area_m2': shapes[sidewalk_ids[0]].area,
         'original_native_or_legal_result_proven': False}
(HERE/'cpu-audit.json').write_text(json.dumps(audit, indent=2) + '\n')
print('heavy sidewalk Native request audit: 8 variants, 3840 rows, map parsed')
