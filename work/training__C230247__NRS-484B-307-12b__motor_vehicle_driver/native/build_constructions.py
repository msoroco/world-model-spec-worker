"""Rebuild the two source-preserving red-X Native construction bundles."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSIGNMENT = 'training__C230247__NRS-484B-307-12b__motor_vehicle_driver'
CAMERAS = [
    {'name': name, 'width': width, 'height': height,
     'pose_strategy': 'fixed original Native world view of actor, overhead signal and lane boundary',
     'fov_deg': 85}
    for name, width, height in (
        ('overview', 1920, 1080), ('approach', 1280, 720),
        ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))
]
CHANNELS = [
    {'name': name, 'unit': unit,
     'method': 'original Native 600-frame map, signal, actor body, trace and camera source join',
     'sampling_rate_hz': 20, 'time_window': '30 s / 600 original frames',
     'reference_frame': 'original Native map and frame',
     'uncertainty': 'official provenance, red-X pixels and physical lane entry pending independent local review'}
    for name, unit in (
        ('dev.lane_control_signal', 'structured'), ('dev.governs', 'structured'),
        ('st.lane', 'structured'), ('rel.occupies', 'lane overlap'),
        ('drv.lane_change', 'lane entry event'), ('kin.velocity', 'm/s'))
]
DESCRIPTION = {
    'channels': CHANNELS,
    'context_inputs': [],
    'limitations': ['Highway classification and official device authority await original local review.',
                    'CPU fixture does not prove actual red-X pixels or physical entry']
}

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for tag, lane in (('probe_1', -2), ('probe_2', -1)):
    cid = ASSIGNMENT + '__' + tag
    cfg = {
        'case_id': cid, 'selected_case_id': cid,
        'supported_case_ids': [ASSIGNMENT + '__probe_1', ASSIGNMENT + '__probe_2'],
        'law_id': 'NRS-484B-307-12b', 'cell_id': 'C230247',
        'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'duration_s': 30,
        'cameras': CAMERAS, 'required_atoms': [], 'source_packets': [],
        'case': {'case_id': cid, 'start_lane_id': -2, 'target_lane_id': lane,
                 'governed_lane_id': -1, 'signal_indication': 'red_x',
                 'recording_description': DESCRIPTION},
        'recording_description': DESCRIPTION,
        'physical_completion': {'criterion': 'travel_progress', 'motion_source': 'trace.jsonl',
                                'position_key': 'position_m', 'minimum_progress_m': 40.0,
                                'minimum_samples': 600, 'engineering_tolerances_not_legal': True}
    }
    if tag == 'probe_1':
        dump(ROOT / 'config.json', cfg)
        target = ROOT / 'construction.json'
    else:
        dump(ROOT / 'cases' / tag / 'config.json', cfg)
        target = ROOT / 'cases' / tag / 'construction.json'
    files = [
        {'path': name, 'content': (HERE / name).read_text()}
        for name in ('runner.py', 'draft_runner.py', 'capture.py', 'signal_source.py',
                     'lane_red_x_meter.py', 'finalize.py', 'road.xodr')
    ]
    files.append({'path': 'config.json', 'content': json.dumps(cfg, indent=2, ensure_ascii=False) + '\n'})
    files.append({'path': 'tests/test_native.py', 'content': (HERE / 'test_native.py').read_text()})
    construction = {
        'case_id': cid, 'law_id': 'NRS-484B-307-12b', 'cell_id': 'C230247',
        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py', 'files': files,
        'recording_description': DESCRIPTION, 'status': 'exact_native_construction',
        'measurement_plan': 'Original 600-frame signal, map, actor-body, motion and four-camera joins',
        'termination_rules': ['600 original frames at 20 Hz', 'fail on missing red-X actor or source',
                              'restore exclusively owned Native world'],
        'mechanisms': ['two lane highway OpenDRIVE and overhead signal governed by lane -1',
                       'red-X-only Native actor readback',
                       'lane -2 straight travel' if lane == -2 else 'lane -2 approach and lateral crossing into lane -1'],
        'supported_case_ids': cfg['supported_case_ids']
    }
    dump(target, construction)
    print(cid, target.relative_to(ROOT), sha(target))
