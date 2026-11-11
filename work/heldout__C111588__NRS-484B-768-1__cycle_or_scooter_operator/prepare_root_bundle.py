"""Materialize the first exact rider bundle as the assignment root dispatch shell."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
construction = json.loads((ROOT / 'first-construction.json').read_text())
plan = json.loads((ROOT / 'case-plan.json').read_text())
ids = [case['case_id'] for case in plan['cases']]
for item in construction['files']:
    if item['path'] == 'config.json':
        config = json.loads(item['content'])
        config['supported_case_ids'] = ids
        item['content'] = json.dumps(config, indent=2) + '\n'
    target = ROOT / item['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_text() != item['content'] and item['path'] not in ('probe-config.json', 'config.json', 'runner.py'):
        raise ValueError('Root bundle source differs: ' + item['path'])
    target.write_text(item['content'])
(ROOT / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')
plan['camera_plan'] = {
    'profile': 'overview1080-capability', 'duration_s': 10,
    'composition': 'synchronized_four_view_primary',
    'coverage': [
        {'subject': 'rider, device, participant and turn path', 'view': 'overview', 'interval': 'startup through clearance'},
        {'subject': 'approach roadway and arm signal', 'view': 'approach', 'interval': 'approach through turn'},
        {'subject': 'lane designation and rider/participant relation', 'view': 'reference_corner', 'interval': 'approach through turn'},
        {'subject': 'rider hands, device form and signal', 'view': 'driver_reference', 'interval': 'startup through clearance'}]}
terms = {item['term'] for item in json.loads((REPO / 'inputs' / plan['assignment_id'] / 'assignment.json').read_text())['source_observation_terms']}
source = {
    'ru.subject': ('Original rider_context and rider_motion identify the subject; physical rider visibility pending.', ['rider_context.json','rider_motion.jsonl']),
    'ru.bicycle': ('Native bicycle blueprint and original video review required.', ['rider_context.json','driver_reference.mkv']),
    'ru.electric_bicycle': ('Electric bicycle candidate blueprint and original video review required; drive unverified.', ['device_blueprint_readback.json','device_visual_review.jsonl']),
    'ru.electric_scooter': ('Electric scooter candidate blueprint and original video review required; standing form unverified.', ['device_blueprint_readback.json','device_visual_review.jsonl']),
    'st.roadway': ('Connected Native roadway waypoints and occupancy pixels require review.', ['rider_context.json','road.xodr']),
    'drv.turning': ('Original rider yaw, trace and four-camera frame map measure turn attempt.', ['rider_motion.jsonl','trace.jsonl']),
    'sig.hand_signal': ('Reviewed source-video arm signal joined to original frame.', ['rider_signal_review.jsonl','driver_reference.mkv']),
    'drv.time_to_conflict': ('Participant relative motion and conflict-zone geometry still require acquisition.', ['participant_motion.jsonl','trace.jsonl']),
    'st.turn_lane': ('Lane waypoint and original pixel review needed for designated lane.', ['lane_waypoint_readback.jsonl','lane_designation_review.jsonl']),
    'ru.rider_posture': ('Hand-bone readback and original pixel review needed for both-hands exception.', ['hand_contact_readback.jsonl','hand_contact_review.jsonl'])}
assert terms == set(source)
plan['source_observation_mapping'] = {term: {'evidence': text,
    'channels': ['rider_signal_event'] if term == 'sig.hand_signal' else [],
    'source_refs': refs} for term, (text, refs) in source.items()}
(ROOT / 'case-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
print('Root rider dispatch shell and source-observation mapping authored')
