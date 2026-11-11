"""Exact Native source contracts for the six unbuilt rider comparisons."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator'
COMMON = ['video_frames.jsonl', 'trace.jsonl', 'rider_motion.jsonl',
          'rider_arm_bones.jsonl', 'rider_signal_review.jsonl',
          'rider_context.json', 'overview.mkv', 'approach.mkv',
          'reference_corner.mkv', 'driver_reference.mkv']
SPECS = {
    'electric_bicycle_signal_once': {
        'device': 'electric_bicycle', 'signal_frames': [35],
        'construction_step': 'select an original Native electric-bicycle asset or build a visually and mechanically distinct electric-bicycle device with source-linked actor identity',
        'additional_originals': ['device_blueprint_readback.json', 'device_visual_review.jsonl'],
        'acceptance_guard': 'electric drive and bicycle form must each be supported by actor readback and visible original frames'},
    'electric_scooter_signal_once': {
        'device': 'electric_scooter', 'signal_frames': [35],
        'construction_step': 'select or build a Native electric-scooter device with a standing operator and visible handlebar/arm geometry',
        'additional_originals': ['device_blueprint_readback.json', 'device_visual_review.jsonl'],
        'acceptance_guard': 'electric scooter class, standing rider and visible signal must each have original readback/video support'},
    'turn_lane_no_signal': {
        'device': 'bicycle', 'signal_frames': [],
        'construction_step': 'route the bicycle from a marked left-turn lane and capture lane marking/sign geometry from the rider approach',
        'additional_originals': ['lane_waypoint_readback.jsonl', 'turn_lane_marking_review.jsonl'],
        'acceptance_guard': 'turn-lane designation requires Native lane geometry plus original visible sign or marking review'},
    'both_hands_no_signal': {
        'device': 'bicycle', 'signal_frames': [],
        'construction_step': 'construct a control-demand perturbation and retain two-hand contact, steering stability and source-video review through the turn',
        'additional_originals': ['hand_contact_readback.jsonl', 'control_stability.jsonl', 'hand_contact_review.jsonl'],
        'acceptance_guard': 'both-hands safety need remains a separate judgment; command or contact alone cannot establish it'},
    'safety_wide': {
        'device': 'bicycle', 'signal_frames': [35],
        'construction_step': 'spawn a participant on a reproducible intersecting path with wide intended clearance and record both actor trajectories',
        'additional_originals': ['participant_motion.jsonl', 'clearance_samples.jsonl'],
        'acceptance_guard': 'original participant path, closest approach and time to conflict required; legal safety threshold stays open'},
    'safety_narrow': {
        'device': 'bicycle', 'signal_frames': [35],
        'construction_step': 'hold rider route and participant path family fixed while shifting participant timing for narrower intended clearance',
        'additional_originals': ['participant_motion.jsonl', 'clearance_samples.jsonl'],
        'acceptance_guard': 'original participant path, closest approach and time to conflict required; legal safety threshold stays open'},
}


def check_receipt(spec, source_hashes):
    required = set(spec['required_originals'])
    absent = sorted(required - set(source_hashes))
    if absent:
        raise ValueError('Missing original construction sources: ' + ', '.join(absent))
    for name in required:
        digest = source_hashes[name]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Invalid original source hash: ' + name)
    return True


def build():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    planned = {item['case_id']: item for item in plan['cases']}
    for slug, detail in SPECS.items():
        case_id = ASSIGNMENT + '__' + slug
        if case_id not in planned:
            raise ValueError('Pending construction has no planned case: ' + slug)
        folder = ROOT / 'cases' / slug
        folder.mkdir(exist_ok=True)
        contract = {'format': 'worker-rider-native-construction-input',
                    'case_id': case_id, 'status': 'source_contract_only',
                    'device': detail['device'], 'signal_frame_indices': detail['signal_frames'],
                    'rate_hz': 20, 'frames': 200,
                    'construction_step': detail['construction_step'],
                    'required_originals': COMMON + detail['additional_originals'],
                    'acceptance_guard': detail['acceptance_guard'],
                    'physical_visibility_verified': False,
                    'legal_acceptance_claimed': False}
        path = folder / 'native-source-contract.json'
        path.write_text(json.dumps(contract, indent=2) + '\n')
        try:
            check_receipt(contract, {})
        except ValueError as exc:
            assert str(exc).startswith('Missing original construction sources: ')
        else:
            raise AssertionError('Missing Native originals accepted for ' + slug)
        print(slug, sha256(path.read_bytes()).hexdigest(), 'missing-source negative passed')


if __name__ == '__main__':
    build()
