"""Positive and source-tamper controls for the C5191 comparison audit."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from turn_comparison_audit import audit

ROOT = Path(__file__).resolve().parents[2]
PREFIX = ROOT / '.runtime-work'
NAMES = ('left_turn_lane_contained_approach', 'left_turn_early_boundary_crossing_no_signal', 'left_turn_early_boundary_crossing_signaled')
ROOTS = [PREFIX / f'c5191-{name}-primary-compat' for name in NAMES]

def altered_signaled(original, change):
    with TemporaryDirectory(prefix='c5191-contrast-') as path:
        tmp = Path(path)
        for child in original.iterdir():
            if child.name != 'turn_originals.jsonl':
                (tmp / child.name).symlink_to(child, target_is_directory=child.is_dir())
        rows = [json.loads(line) for line in (original / 'turn_originals.jsonl').read_text().splitlines()]
        change(rows)
        (tmp / 'turn_originals.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        audit(ROOTS[0], ROOTS[1], tmp)

if __name__ == '__main__':
    proof = audit(*ROOTS)
    assert proof['minimum_clearances_m'] == [0.85, -1.25, -1.25]
    assert proof['indicator_frames'] == [0, 0, 9]
    for change, expected in (
        (lambda rows: rows[0].update(ego_id=999), 'indicator comparison geometry changed'),
        (lambda rows: [row.update(ego_light_state=0) for row in rows], 'controlled path/signal contrast missing'),
    ):
        try:
            altered_signaled(ROOTS[2], change)
        except ValueError as error:
            assert expected in str(error), str(error)
        else:
            raise AssertionError('Source-tampered C5191 comparison was accepted')
    print('PASS C5191 paired path and signal audit; independent original-source identity, two tamper rejections')
