"""Verify four fixed-motion officer-direction synthetic comparisons."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    results = []
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        folders = [HERE / 'saved-fixtures' / case / candidate for case in
                   ('exception_1_1', 'exception_1_2')]
        first, second = [rows(folder / 'actor-frames.jsonl') for folder in folders]
        reports = [json.loads((folder / 'analysis-report.json').read_text()) for folder in folders]
        assert len(first) == len(second) == 480
        assert all(a['subject'] == b['subject'] and a['approach'] == b['approach']
                   and a['subject_body_xy_m'] == b['subject_body_xy_m']
                   for a, b in zip(first, second))
        assert not any(a['direction_requested'] or a['direction_review']['cue_visible']
                       for a in first)
        assert any(b['direction_requested'] and b['direction_review']['cue_visible']
                   for b in second)
        values = [r['measurements']['officer_direction_timing']['value'] for r in reports]
        assert values[0]['catchup_frame'] == values[1]['catchup_frame']
        assert values[0]['synthetic_cue_frames'] == 0
        assert values[1]['synthetic_cue_frames'] > 0
        assert all(v['legal_exception_verdict'] is None for v in values)
        results.append({'candidate_id': candidate,
                        'fixed_motion_frame_count': len(first),
                        'catchup_frame': values[0]['catchup_frame'],
                        'negative_cue_frames': 0,
                        'positive_synthetic_cue_frames': values[1]['synthetic_cue_frames']})
    return {'passed': True, 'controlled_pairs': results,
            'physical_or_legal_result_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
