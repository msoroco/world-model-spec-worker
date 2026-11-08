"""Independent source/geometry audit for the C422978 unselected CPU drafts."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
AID = CASE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    manifest = read(HERE / 'drafts/manifest.json')
    proof = read(HERE / 'trigger-proof.json')
    assert manifest['format'] == 'c422978-sidewalk-native-request-v1'
    assert not manifest['delivery_ready'] and not manifest['original_native_observed']
    assert manifest['assignment_sha256'] == sha(ROOT / 'inputs' / AID / 'assignment.json')
    assert manifest['case_plan_sha256'] == sha(CASE / 'case-plan.json')
    assert manifest['road_sha256'] == sha(HERE / 'road.xodr')
    tree = ET.parse(HERE / 'road.xodr')
    lanes = {int(lane.attrib['id']): lane for lane in tree.findall('.//lane')}
    assert lanes[-1].attrib['type'] == 'driving'
    assert lanes[-2].attrib['type'] == 'sidewalk'
    assert lanes[1].attrib['type'] == 'driving'
    assert len(manifest['entries']) == 8
    entries = {(e['case_id'].split('__')[-1], e['candidate_id']): e for e in manifest['entries']}
    assert len(entries) == 8
    for case in ('witness_1', 'witness_2'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            entry = entries[(case, candidate)]
            config_path = CASE / entry['config']
            tracks_path = CASE / entry['tracks']
            config = read(config_path)
            rows = lines(tracks_path)
            assert config['case_id'] == AID + '__' + case
            assert config['candidate_id'] == candidate
            assert config['actor'] == 'motorcycle_or_moped_operator'
            assert config['road_sha256'] == manifest['road_sha256']
            assert config['tracks_sha256'] == sha(tracks_path)
            assert config['assignment_sha256'] == manifest['assignment_sha256']
            assert len(rows) == 480
            assert all(row['frame'] == i and abs(row['time_s'] - i/20) < 1e-6
                       for i, row in enumerate(rows))
            assert all(row['motorcycle_blueprint'] == 'vehicle.kawasaki.ninja'
                       and row['source_kind'] == 'authored_native_request'
                       and row['requested_speed_mps'] == 4.0 for row in rows)
            overlap = [row['frame'] for row in rows if
                       row['requested_center_xy_m'][1] - .4 < -3.5 and
                       row['requested_center_xy_m'][1] + .4 > -5.5]
            assert len(overlap) == entry['metric']['requested_sidewalk_overlap_frames']
            assert (overlap[0] if overlap else None) == entry['metric']['first_requested_overlap_frame']
            if case == 'witness_1': assert not overlap
            else: assert len(overlap) >= 390
            if candidate == 'fallback1':
                assert config['policy']['lateral_start_frame'] == 45
            elif candidate == 'fallback2':
                assert config['policy']['lateral_duration_frames'] == 55
            elif candidate == 'fallback3':
                assert config['policy']['camera_fov_deg'] == 100
    assert proof['manifest_sha256'] == sha(HERE / 'drafts/manifest.json')
    assert proof['trigger_code_sha256'] == sha(HERE / 'triggers.py')
    assert not proof['original_native_or_legal_outcome_claimed']
    assert len(proof['rows']) == 12
    for receipt in proof['rows']:
        folder = HERE / 'trigger-fixtures' / receipt['case_suffix'] / receipt['candidate_id'] / receipt['fixture']
        saved = folder / 'actor-frames.jsonl'
        assert receipt['saved_sha256'] == sha(saved)
        rows = lines(saved)
        assert len(rows) == 480
        assert all(row['frame'] == i and row['source_kind'] == 'synthetic_cpu'
                   and row['motorcycle_blueprint'] == 'vehicle.kawasaki.ninja'
                   for i, row in enumerate(rows))
        overlaps = [row['frame'] for row in rows if row['speed_mps'] > .1 and
                    min(p[1] for p in row['body_xy_m']) < -3.5 and
                    max(p[1] for p in row['body_xy_m']) > -5.5]
        result = receipt['result']
        assert result['triggered'] == (receipt['fixture'] == 'trigger')
        assert not result['legal_outcome_claimed']
        if receipt['candidate_id'] == 'fallback1':
            expected = (overlaps[0] if overlaps else None) if receipt['case_suffix'] == 'witness_2' else len(overlaps)
        elif receipt['candidate_id'] == 'fallback2':
            expected = len(overlaps) if receipt['case_suffix'] == 'witness_2' else min(
                min(p[1] for p in row['body_xy_m']) + 3.5 for row in rows)
        else:
            visibility = folder / 'visibility.json'
            assert receipt['visibility_sha256'] == sha(visibility)
            packet = read(visibility)
            assert packet['video_path'] == 'synthetic-camera.txt'
            assert packet['video_sha256'] == sha(folder / packet['video_path'])
            expected = packet['visible_fraction']
        assert expected == result['value']
    negative = read(HERE / 'trigger-fixtures/negative-visibility.json')
    assert negative['video_sha256'] == '0' * 64
    output = {'format': 'c422978-independent-construction-audit-v1',
              'manifest_sha256': sha(HERE / 'drafts/manifest.json'),
              'trigger_proof_sha256': sha(HERE / 'trigger-proof.json'),
              'audited_drafts': 8, 'audited_trigger_fixtures': 12,
              'original_native_or_delivery_ready_claimed': False}
    (HERE / 'construction-audit.json').write_text(json.dumps(output, indent=2) + '\n')
    return output


if __name__ == '__main__':
    print(json.dumps(audit()))
