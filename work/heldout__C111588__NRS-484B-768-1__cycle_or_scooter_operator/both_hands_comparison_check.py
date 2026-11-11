"""Check fixed no-signal rider sources and reject stale hand-contact pixels."""
import json
from pathlib import Path
import shutil
import tempfile

from rider_hand_control import measure

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
base = json.loads((ROOT / 'cases/bicycle_no_signal/compat-receipt.json').read_text())
hands = json.loads((REPO / '.runtime-work/c111588-both-hands-primary-compat-a/compatibility.json').read_text())
common = ('trace.jsonl','video_frames.jsonl','rider_motion.jsonl','rider_arm_bones.jsonl',
          'rider_signal_review.jsonl','overview.mkv','approach.mkv',
          'reference_corner.mkv','driver_reference.mkv')
for name in common:
    assert base['fixture_manifest'][name] == hands['fixture_manifest'][name], name
assert hands['negative_removed'] == 'hand_contact_readback.jsonl'
assert hands['measurement_examples']['both_hands_observation']['value']['peak_abs_commanded_steer'] == .03
with tempfile.TemporaryDirectory(prefix='both-hands-stale-review-') as temporary:
    root = Path(temporary)
    original = REPO / '.runtime-work/c111588-both-hands-original-a'
    for name in ('video_frames.jsonl','rider_context.json','hand_contact_readback.jsonl',
                 'control_stability.jsonl','hand_contact_review.jsonl','driver_reference.mkv'):
        shutil.copy2(original / name, root / name)
    rows = [json.loads(line) for line in (root / 'hand_contact_review.jsonl').read_text().splitlines()]
    rows[2]['source_video_sha256'] = '0' * 64
    (root / 'hand_contact_review.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    try:
        measure(root)
    except ValueError as error:
        assert 'Stale hand-contact pixel review' in str(error)
    else:
        raise AssertionError('Stale hand pixel review accepted')
print(json.dumps({'shared_rider_and_video_originals': list(common),
                  'peak_synthetic_steer_command': .03,
                  'stale_hand_pixel_review_rejected': True,
                  'both_hands_required_for_safety': None,
                  'legal_signal_exception_judgment': None}))
