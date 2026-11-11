"""Verify the wide/narrow diagnostic source comparison and stale sample rejection."""
import json
from pathlib import Path
import shutil
import tempfile

from rider_clearance_measurement import measure

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
cases = {}
for slug, suffix in (('safety_wide', 'wide'), ('safety_narrow', 'narrow')):
    path = REPO / '.runtime-work' / f'c111588-{slug}-primary-compat-h' / 'compatibility.json'
    receipt = json.loads(path.read_text())
    assert receipt['passed'] is True and receipt['negative_removed'] == 'participant_motion.jsonl'
    cases[slug] = receipt
wide, narrow = cases['safety_wide'], cases['safety_narrow']
common = ('trace.jsonl', 'video_frames.jsonl', 'rider_motion.jsonl',
          'rider_arm_bones.jsonl', 'rider_signal_review.jsonl',
          'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
for name in common:
    assert wide['fixture_manifest'][name] == narrow['fixture_manifest'][name], name
assert wide['fixture_manifest']['participant_motion.jsonl'] != narrow['fixture_manifest']['participant_motion.jsonl']
assert wide['fixture_manifest']['clearance_samples.jsonl'] != narrow['fixture_manifest']['clearance_samples.jsonl']
def value(receipt):
    return receipt['measurement_examples']['rider_clearance_observation']['value']['minimum_center_distance_m']
assert abs(value(wide)-7.55) < .01 and abs(value(narrow)-2.55) < .01
assert abs(wide['measurement_examples']['rider_clearance_observation']['value']['time_to_conflict_s']-6.75) < .01
assert abs(narrow['measurement_examples']['rider_clearance_observation']['value']['time_to_conflict_s']-1.75) < .01
with tempfile.TemporaryDirectory(prefix='rider-clearance-stale-') as tmp:
    source = REPO / '.runtime-work/c111588-safety_wide-primary-compat-h'
    root = Path(tmp)
    for name in ('trace.jsonl','video_frames.jsonl','participant_motion.jsonl','clearance_samples.jsonl'):
        shutil.copy2(source / name, root / name)
    samples = [json.loads(line) for line in (root / 'clearance_samples.jsonl').read_text().splitlines()]
    samples[2]['center_distance_m'] = 0
    (root / 'clearance_samples.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in samples))
    try:
        measure(root)
    except ValueError as exc:
        assert 'differs from original trajectories' in str(exc)
    else:
        raise AssertionError('stale clearance sample accepted')
print(json.dumps({'wide_m': value(wide), 'narrow_m': value(narrow),
      'wide_ttc_s': wide['measurement_examples']['rider_clearance_observation']['value']['time_to_conflict_s'],
      'narrow_ttc_s': narrow['measurement_examples']['rider_clearance_observation']['value']['time_to_conflict_s'],
      'common_originals_equal': list(common), 'stale_sample_rejected': True,
      'physical_participant_visibility_verified': False,
      'legal_safety_judgment': None}))
