"""Independent audit of retained C405647 synthetic saved motion packets."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAW_SHA256 = '05acca6d9cdbea0707963bae635458009d558500a8d40a96ce4fa9d8ca5a8d86'


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path):
    return json.loads(path.read_text())


def audit():
    summaries = []
    pair = []
    for case in ('witness_1', 'witness_2'):
        folder = ROOT / 'synthetic-local' / case
        scope = _read(folder / 'source-scope.json')
        report = _read(folder / 'analysis-report.json')
        assert report['format'] == 'c405647-1a-saved-analysis-v1'
        assert report['case_id'] == 'training__C405647__NRS-484B-267-1a__motor_vehicle_driver__' + case
        assert report['selected'] is False and report['draft_only'] is True
        assert report['physical_acceptance_claimed'] is False
        assert report['legal_verdict_claimed'] is False
        item = report['measurements']['emergency_approach_clearance']
        assert item['method'] == 'approach_clearance_and_lamp_timing'
        assert item['sources'] == {
            'source-scope.json': _sha(folder / 'source-scope.json'),
            'actor-frames.jsonl': _sha(folder / 'actor-frames.jsonl')}
        measured = item['value']
        rows = [json.loads(line) for line in (folder / 'actor-frames.jsonl').read_text().splitlines()]
        assert scope['assignment_law_text_sha256'] == LAW_SHA256
        assert scope['coordinate_frame'] == 'authored_opendrive_xy'
        assert scope['case_suffix'] == measured['case_suffix'] == case
        assert measured['source_hashes'] == {
            'source-scope.json': _sha(folder / 'source-scope.json'),
            'actor-frames.jsonl': _sha(folder / 'actor-frames.jsonl')}
        assert len(rows) == measured['observed_frame_count'] == 480
        assert measured['provenance_kinds'] == ['synthetic_cpu']
        assert measured['vehicle_authority_verified'] is False
        assert measured['lamp_qualification_verified'] is False
        assert measured['legal_immediacy_or_yield_verdict'] is None
        assert all(row['frame'] == i and abs(row['time_s'] - i / 20) < 1e-8
                   and row['source_kind'] == 'synthetic_cpu'
                   and row['coordinate_frame'] == 'authored_opendrive_xy'
                   and len(row['subject_body_xy_m']) == 4
                   and len({tuple(vertex) for vertex in row['subject_body_xy_m']}) == 4
                   for i, row in enumerate(rows))
        lamps = [row['front_red_flash_on'] for row in rows]
        assert measured['observed_lamp_transitions'] == sum(
            a != b for a, b in zip(lamps, lamps[1:]))
        gaps = [row['subject']['x_m'] - row['approach']['x_m'] for row in rows]
        catchup = next(i for i, gap in enumerate(gaps) if gap <= 4.5)
        clearance = next((i for i, row in enumerate(rows)
                          if max(vertex[1] for vertex in row['subject_body_xy_m']) < -3.5), None)
        assert measured['body_footprint_source'] == 'four retained vertices per saved frame'
        assert measured['coordinate_frame'] == 'authored_opendrive_xy'
        assert measured['initial_longitudinal_gap_m'] == gaps[0] == 50
        assert measured['catchup_frame'] == catchup == 182
        assert measured['first_full_body_inner_lane_clearance_frame'] == clearance
        assert measured['full_body_cleared_before_catchup'] == (case == 'witness_1')
        assert clearance == (81 if case == 'witness_1' else None)
        pair.append(rows)
        summaries.append({'case_suffix': case, 'frames': len(rows),
                          'catchup_frame': catchup, 'clearance_frame': clearance,
                          'report_sha256': _sha(folder / 'analysis-report.json')})
    assert all(a['approach'] == b['approach'] and
               a['front_red_flash_on'] == b['front_red_flash_on']
               for a, b in zip(pair[0], pair[1]))
    assert pair[0][0]['subject'] == pair[1][0]['subject']
    return {'passed': True, 'common_approach_and_lamp_rows': 480,
            'results': summaries, 'physical_or_legal_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
