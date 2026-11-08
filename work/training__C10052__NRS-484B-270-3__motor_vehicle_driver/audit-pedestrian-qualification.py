"""Independently recompute saved source/receipt and controlled-pair measurements."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'native'))
from pedestrian_engineering import NAMES, measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    summary = read(ROOT/'pedestrian-qualification-cpu-summary.json')
    assert summary['accepted'] is False and len(summary['receipts']) == 8
    pairs = []
    for candidate in NAMES:
        outcomes = {}
        for response in ('clear', 'conflict'):
            folder = ROOT/'draft-pedestrian-cases'/response/candidate
            receipt = read(folder/'receipt.json')
            assert receipt in summary['receipts'] and receipt['accepted'] is False
            for key, file in (('construction_sha256', 'construction.json'),
                              ('source_sha256', 'source-rows.jsonl'),
                              ('measurement_sha256', 'measurement.json'),
                              ('negative_sha256', 'negative-receipts.json')):
                assert receipt[key] == sha(folder/file), (candidate, response, key)
            rows = [json.loads(line) for line in (folder/'source-rows.jsonl').read_text().splitlines()]
            actual = measure(rows, read(folder/'construction.json'))
            assert actual == read(folder/'measurement.json')
            assert actual['qualifying_synthetic_geometry'] and actual['accepted'] is False
            # A changed saved source must fail its pinned receipt. A changed frame
            # identity must fail the source join even before any timing inference.
            changed = [dict(row) for row in rows]
            changed[200] = dict(changed[200], native_frame=2001)
            try:
                measure(changed, read(folder/'construction.json'))
            except ValueError as exc:
                assert 'Frame/time join' in str(exc)
            else:
                raise AssertionError('Changed frame identity accepted')
            negatives = read(folder/'negative-receipts.json')
            assert set(negatives) == {'passable_sidewalk', 'late_sidewalk_return'}
            assert all(n['qualification_rejected'] and not n['measured']['qualifying_synthetic_geometry']
                       for n in negatives.values())
            outcomes[response] = (rows, actual)
        clear_rows, clear = outcomes['clear']
        conflict_rows, conflict = outcomes['conflict']
        assert all(a['pedestrian_body_xy'] == b['pedestrian_body_xy'] and
                   a['sidewalk_obstructed'] == b['sidewalk_obstructed'] and
                   a['buffer_impassable'] == b['buffer_impassable'] and
                   a['native_frame'] == b['native_frame'] and a['time_s'] == b['time_s']
                   for a, b in zip(clear_rows, conflict_rows))
        assert clear['simultaneous_conflict_frames'] == 0
        assert conflict['simultaneous_conflict_frames'] == 20
        pairs.append({'candidate_id': candidate,
                      'clear_ego_entry_frame': clear['first_ego_conflict_frame'],
                      'conflict_ego_entry_frame': conflict['first_ego_conflict_frame'],
                      'pedestrian_conflict_frames': [clear['first_pedestrian_conflict_frame'],
                                                     clear['last_pedestrian_conflict_frame']],
                      'simultaneous_frames': [0, 20],
                      'return_gap_after_obstacle_frames': clear['return_gap_after_obstacle_frames']})
    proof = {'format': 'c10052-pedestrian-independent-source-audit-v1',
             'summary_sha256': sha(ROOT/'pedestrian-qualification-cpu-summary.json'),
             'source_bound_positive_receipts': 8, 'qualification_negatives': 16,
             'changed_frame_join_negatives': 8,
             'pairs': pairs, 'accepted': False,
             'original_native_verified': False, 'legal_yield_finding': None}
    (ROOT/'pedestrian-qualification-independent-audit.json').write_text(
        json.dumps(proof, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'pairs': len(pairs), 'source_bound_positive_receipts': 8,
                      'qualification_negatives': 16}))


if __name__ == '__main__':
    audit()
