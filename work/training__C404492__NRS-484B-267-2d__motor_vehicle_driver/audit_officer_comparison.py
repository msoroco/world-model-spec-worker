"""Independent exact motion/context comparison for officer direction."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(undirected, directed):
    undirected, directed = Path(undirected), Path(directed)
    a = json.loads((undirected / 'emergency_context.json').read_text())
    b = json.loads((directed / 'emergency_context.json').read_text())
    if (a.get('case_id') != AID + '__controlled_2'
            or b.get('case_id') != AID + '__officer_directed'):
        raise ValueError('Exact directed-officer comparison identities differ')
    if a.get('officer_directed_otherwise') is not False or b.get('officer_directed_otherwise') is not True:
        raise ValueError('Reviewed officer-direction difference absent')
    fixed = ('assignment_id', 'review_kind', 'ego_actor_id', 'emergency_actor_id',
             'emergency_vehicle_authorized', 'qualifying_flash_equipment_reviewed',
             'ego_driver_source', 'ego_vehicle_source', 'emergency_authorization_source',
             'qualifying_flash_equipment_source', 'flashing_light_visual_source',
             'lane_boundary_source')
    for key in fixed:
        if a.get(key) != b.get(key):
            raise ValueError('Fixed source/authority context differs: ' + key)
    sources = b.get('officer_instruction_sources')
    if not isinstance(sources, dict):
        raise ValueError('Officer instruction source set absent')
    for key in ('officer_instruction_source', 'officer_identity_source',
                'officer_instruction_text', 'officer_instruction_recipient',
                'officer_instruction_timing_source', 'officer_instruction_reviewer'):
        if not isinstance(sources.get(key), str) or not sources[key]:
            raise ValueError('Officer instruction source absent: ' + key)
    if b['review_kind'] == 'original_source_review' and any(
            value.startswith('synthetic-fixture:') for value in sources.values()):
        raise ValueError('Original comparison cannot use synthetic officer source')
    for name in ('vehicle_poses.jsonl', 'video_frames.jsonl', 'trace.jsonl'):
        left, right = undirected / name, directed / name
        if not left.is_file() or not right.is_file():
            raise ValueError('Original source missing: ' + name)
        if rows(left) != rows(right):
            raise ValueError('Fixed original motion or camera/time source differs: ' + name)
    poses = rows(undirected / 'vehicle_poses.jsonl')
    frames = rows(undirected / 'video_frames.jsonl')
    if len(poses) != 600 or len(frames) != 600:
        raise ValueError('Exact 600-frame source plan absent')
    if not all(row['emergency']['speed_mps'] > 0 for row in poses):
        raise ValueError('Moving reference vehicle source absent')
    return {'format': 'c404492-officer-direction-comparison-v1',
            'passed': True, 'undirected_case_id': a['case_id'],
            'directed_case_id': b['case_id'],
            'fixed_motion_sha256': sha(undirected / 'vehicle_poses.jsonl'),
            'fixed_camera_plan_sha256': sha(undirected / 'video_frames.jsonl'),
            'directed_officer_source_keys': sorted(sources),
            'diagnostic_only': b['review_kind'] != 'original_source_review',
            'physical_acceptance_claimed': False, 'legal_result': None}
