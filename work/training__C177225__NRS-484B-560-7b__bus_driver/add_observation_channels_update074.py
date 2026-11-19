"""Declare three required observations from retained bus and officer sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


CHANNELS = [
    {'name': 'ego_pose', 'unit': 'structured', 'sampling_rate_hz': 20,
     'reference_frame': 'authored road station/lane and original Native frame',
     'time_window': 'entire 30 s / 600-frame attempt',
     'method': 'Retain bus_native_rows.jsonl station_m, lane_y_native_m and heading_native_deg keyed by native_frame',
     'uncertainty': 'Road-relative pose; original placement and camera pixels require review'},
    {'name': 'ego_speed', 'unit': 'm/s', 'sampling_rate_hz': 20,
     'reference_frame': 'original Native bus actor frame',
     'time_window': 'entire 30 s / 600-frame attempt',
     'method': 'Derive speed magnitude from retained bus_native_rows.jsonl velocity_native_xyz_mps',
     'uncertainty': '50 ms sampling; synthetic diagnostic velocities are not original Native observations'},
    {'name': 'bus_obeys_officer_direction', 'unit': 'boolean', 'sampling_rate_hz': 20,
     'reference_frame': 'joined original Native bus/officer/video frames',
     'time_window': 'governing interval in 30 s / 600-frame attempt',
     'method': 'Saved finalizer joins bus_native_rows.jsonl, officer_signal_rows.jsonl and video_frames.jsonl to derive stop/crossing response',
     'uncertainty': 'Software observation only; officer gesture visibility and legal judgment require original review'},
]


def add(description):
    names = {item['name'] for item in description['channels']}
    if any(item['name'] in names for item in CHANNELS):
        raise ValueError('Required channel already declared')
    description['channels'].extend(CHANNELS)


manifest = json.loads(MANIFEST.read_text())
proposal_path = HERE / 'proposals/cases.json'
proposal = json.loads(proposal_path.read_text())
for case in proposal['cases']:
    add(case['recording_description'])
proposal_path.write_text(json.dumps(proposal, indent=2) + '\n')
root_path = HERE / 'construction.json'
root = json.loads(root_path.read_text())
add(root['recording_description'])
root_path.write_text(json.dumps(root, indent=2) + '\n')
for entry in manifest['cases']:
    for target in [entry, *entry['candidates']]:
        path = HERE / target['construction']
        construction = json.loads(path.read_text())
        add(construction['recording_description'])
        path.write_text(json.dumps(construction, indent=2) + '\n')
        target['construction_sha256'] = sha(path)
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'constructions': 9, 'proposal_cases': len(proposal['cases']),
                  'manifest_sha256': sha(MANIFEST)}))
