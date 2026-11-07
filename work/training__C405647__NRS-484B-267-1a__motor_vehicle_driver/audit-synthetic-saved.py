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
        rows = [json.loads(line) for line in (folder / 'actor-frames.jsonl').read_text().splitlines()]
        assert scope['assignment_law_text_sha256'] == LAW_SHA256
        assert scope['case_suffix'] == report['case_suffix'] == case
        assert report['source_hashes'] == {
            'source-scope.json': _sha(folder / 'source-scope.json'),
            'actor-frames.jsonl': _sha(folder / 'actor-frames.jsonl')}
        assert len(rows) == report['observed_frame_count'] == 480
        assert report['provenance_kinds'] == ['synthetic_cpu']
        assert report['vehicle_authority_verified'] is False
        assert report['lamp_qualification_verified'] is False
        assert report['legal_immediacy_or_yield_verdict'] is None
        assert all(row['frame'] == i and abs(row['time_s'] - i / 20) < 1e-8
                   and row['source_kind'] == 'synthetic_cpu' for i, row in enumerate(rows))
        lamps = [row['front_red_flash_on'] for row in rows]
        assert report['observed_lamp_transitions'] == sum(
            a != b for a, b in zip(lamps, lamps[1:]))
        gaps = [row['subject']['x_m'] - row['approach']['x_m'] for row in rows]
        catchup = next(i for i, gap in enumerate(gaps) if gap <= 4.5)
        clearance = next((i for i, row in enumerate(rows)
                          if row['subject']['y_m'] + .9 < -3.5), None)
        assert report['initial_longitudinal_gap_m'] == gaps[0] == 50
        assert report['catchup_frame'] == catchup == 182
        assert report['first_full_body_inner_lane_clearance_frame'] == clearance
        assert report['full_body_cleared_before_catchup'] == (case == 'witness_1')
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
