"""Check fixed no-signal rider sources and reject stale lane pixel review."""
import json
from pathlib import Path
import shutil
import tempfile

from rider_turn_lane import measure

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
base = json.loads((ROOT / 'cases/bicycle_no_signal/compat-receipt.json').read_text())
lane = json.loads((ROOT / 'cases/turn_lane_no_signal/proof-compatibility-receipt.json').read_text())
common = ('trace.jsonl','video_frames.jsonl','rider_motion.jsonl','rider_arm_bones.jsonl',
          'rider_signal_review.jsonl','overview.mkv','approach.mkv',
          'reference_corner.mkv','driver_reference.mkv')
for name in common:
    assert base['fixture_manifest'][name] == lane['fixture_manifest'][name], name
assert lane['negative_removed'] == 'lane_waypoint_readback.jsonl'
with tempfile.TemporaryDirectory(prefix='turn-lane-stale-review-') as temporary:
    root = Path(temporary)
    original = REPO / '.runtime-work/c111588-turn-lane-original-b'
    for name in ('video_frames.jsonl','lane_waypoint_readback.jsonl',
                 'turn_lane_marking_review.jsonl','driver_reference.mkv'):
        shutil.copy2(original / name, root / name)
    rows = [json.loads(line) for line in (root / 'turn_lane_marking_review.jsonl').read_text().splitlines()]
    rows[2]['source_video_sha256'] = '0' * 64
    (root / 'turn_lane_marking_review.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    try:
        measure(root)
    except ValueError as error:
        assert 'Stale turn-lane pixel review' in str(error)
    else:
        raise AssertionError('Stale lane pixel review accepted')
print(json.dumps({'shared_rider_and_video_originals': list(common),
                  'stale_lane_pixel_review_rejected': True,
                  'designated_turn_lane_confirmed': None,
                  'legal_signal_exception_judgment': None}))
