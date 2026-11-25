"""Describe concrete acquisition implementations for exact Native handoff."""
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
path = PACKAGE / 'execution-manifest.json'
manifest = json.loads(path.read_text())
for entry in manifest['cases']:
    entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'}
    entry['acquisition'] = {
        'kin.position': {'entrypoint': 'caravan_capture.py', 'method': 'capture_frames/state',
                         'evidence': 'trace.jsonl and capture/evidence.jsonl'},
        'kin.heading': {'entrypoint': 'caravan_capture.py', 'method': 'capture_frames/state',
                        'evidence': 'trace.jsonl and capture/evidence.jsonl'},
        'kin.velocity': {'entrypoint': 'caravan_capture.py', 'method': 'capture_frames/state',
                         'evidence': 'trace.jsonl and capture/evidence.jsonl'},
        'caravan_member_bodies': {'entrypoint': 'finalizer.py', 'method': '_channel',
                                  'evidence': 'caravan_history.jsonl -> channels/caravan_member_bodies.jsonl'},
        'entering_vehicle_body': {'entrypoint': 'finalizer.py', 'method': '_channel',
                                  'evidence': 'caravan_history.jsonl -> channels/entering_vehicle_body.jsonl'},
        'inter_body_opening': {'entrypoint': 'finalizer.py', 'method': 'source_hashed_body_gap',
                               'evidence': 'caravan_history.jsonl -> channels/inter_body_opening.jsonl'},
        'entrant_gap_occupancy': {'entrypoint': 'finalizer.py', 'method': 'source_hashed_occupancy',
                                  'evidence': 'caravan_history.jsonl -> channels/entrant_gap_occupancy.jsonl'},
        'member_contact': {'entrypoint': 'finalizer.py', 'method': 'source_hashed_occupancy',
                           'evidence': 'caravan_history.jsonl -> channels/member_contact.jsonl'},
    }
path.write_text(json.dumps(manifest, indent=2) + '\n')
