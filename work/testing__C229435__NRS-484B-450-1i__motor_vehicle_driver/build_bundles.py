"""Build four exact source-deferred nearest-rail constructions and fallbacks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULES = ('runner.py', 'native_entry.py', 'reviewed_site.py', 'rail_proximity.py', 'analysis.py')
OFFLINE_TEST = '''import json
import unittest
from pathlib import Path
from runner import check

class SelectedRailParkingOffline(unittest.TestCase):
    def test_reviewed_source_gate(self):
        root = Path(__file__).resolve().parents[1]
        result = check(root)
        self.assertEqual(result["case_id"], json.loads((root / "config.json").read_text())["selected_case_id"])
        self.assertIn("reviewed original", result["source_gate"])

if __name__ == "__main__":
    unittest.main()
'''


def write(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> list[dict]:
    plan = json.loads((HERE / 'case-plan.json').read_text())
    ids = [case['case_id'] for case in plan['cases']]
    entries = []
    channels = [
        ('railroad_site', 'classification', 'reviewed original carrier and all nearby rail source readback'),
        ('vehicle_rail_distance', 'm', 'original complete ego footprint to every rail segment distance'),
        ('vehicle_parking_action', 'state', 'original ego approach, stop and parking action readback'),
        ('traffic_and_exceptions', 'state', 'original other-vehicle motion and four independent exception source reviews')]
    for case in plan['cases']:
        case_id = case['case_id']
        short = case_id.split('__')[-1]
        folder = HERE / 'cases' / short
        description = {'channels': [{'name': name, 'unit': unit, 'sampling_rate_hz': 20,
            'method': method, 'time_window': '900 original frames',
            'reference_frame': 'reviewed railroad XY',
            'uncertainty': 'original physical rail/vehicle readback pending'}
            for name, unit, method in channels],
            'context_inputs': [{'name': 'reviewed_railroad_site', 'unit': 'source',
                'method': 'source-hashed original railroad, carrier, geometry and exception review'}],
            'limitations': ['50 feet is exactly 15.24 m; retain raw distances and boundary uncertainty.',
                'Another vehicle presence alone does not establish traffic-conflict necessity.']}
        config = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'], 'actor': plan['actor'],
            'selected_case_id': case_id, 'supported_case_ids': ids,
            'required_atoms': [], 'source_packets': [], 'rate_hz': 20, 'duration_s': 45,
            'cameras': [{'name': name, 'width': width, 'height': height, 'fov_deg': 75,
                'pose_strategy': 'reviewed original railroad/ego/other-vehicle view'}
                for name, width, height in (('overview', 1920, 1080), ('approach', 1280, 720),
                    ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))],
            'physical_completion': {'criterion': 'travel_progress', 'motion_source': 'trace.jsonl',
                'position_key': 'position_m', 'minimum_progress_m': 3.0, 'minimum_samples': 3,
                'engineering_tolerances_not_legal': True,
                'completion_goal_method': 'Original ego approach travel proxy; independently audit final parking action, footprint and nearest rail.'},
            'case': {'case_id': case_id,
                'requested_nearest_vehicle_to_rail_m': case['requested_nearest_vehicle_to_rail_m'],
                'physical_target': 'reviewed original parking adjacent to nearest railroad rail with distinct other vehicle',
                'recording_description': description}}
        spec = {key: case[key] for key in ('case_id', 'requested_nearest_vehicle_to_rail_m',
            'requested_traffic_conflict_necessity_status')}
        spec['source_status'] = 'reviewed_original_rail_packet_required_at_capture'
        write(folder / 'config.json', config)
        write(folder / 'case-spec.json', spec)
        entry = None
        for candidate_id, speed in (('primary', 2.0), ('fallback1', 1.0)):
            controller = {'parking_approach_speed_mps': speed,
                'source': 'predeclared parking route to unchanged reviewed railroad site',
                'physical_acceptance': False}
            source_name = 'controller-' + candidate_id + '.json'
            write(folder / source_name, controller)
            files = [{'path': name, 'source': str((HERE / name).relative_to(ROOT)),
                'content': (HERE / name).read_text()} for name in MODULES]
            for name, value, source in (('config.json', config, folder / 'config.json'),
                    ('case-spec.json', spec, folder / 'case-spec.json'),
                    ('controller.json', controller, folder / source_name)):
                files.append({'path': name, 'source': str(source.relative_to(ROOT)),
                    'content': json.dumps(value, indent=2, sort_keys=True) + '\n'})
            files.append({'path': 'tests/test_offline.py', 'content': OFFLINE_TEST})
            construction = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                'actor': plan['actor'], 'case_id': case_id, 'entrypoint': 'runner.py',
                'files': files, 'recording_description': description,
                'measurement_plan': {'selected_requirement': plan['requirement_dispositions'][0]['requirement'],
                    'original_source': 'reviewed railroad identity, all rails, 900-frame ego/other vehicle and exceptions',
                    'saved_method': 'source-bound complete vehicle footprint to nearest rail distance'},
                'mechanisms': ['source-gated original railroad and parking site selection',
                    'same-tick ego, other vehicle and four-camera capture'],
                'static_checks': ['exact rail case, 20 Hz and four cameras',
                    'reviewed source packet required before Native world mutation'],
                'termination_rules': {'duration_s': 45,
                    'early_termination': 'retain failed capture; do not publish as original rail parking'}}
            name = 'construction.json' if candidate_id == 'primary' else 'fallback1-construction.json'
            digest = write(folder / name, construction)
            if candidate_id == 'primary':
                entry = {'case_id': case_id, 'construction': str((folder / name).relative_to(HERE)),
                    'construction_sha256': digest, 'kind': 'delivery',
                    'measurement_procedure': {'entrypoint': 'analysis.py'},
                    'fixture_recipe': str((folder / 'fixture-recipe.json').relative_to(ROOT)),
                    'measurement_contract': str((folder / 'measurement-contract.json').relative_to(HERE)),
                    'acquisition': {channel['name']: {'entrypoint': 'analysis.py',
                        'method': channel['method'], 'evidence': 'channels/' + channel['name'] + '.jsonl'}
                        for channel in description['channels']},
                    'candidate_risk': {'status': 'physical',
                        'reason': 'Original railroad site or parking path may miss the rail-distance target or four-camera footprint'},
                    'candidates': [],
                    'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                        'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}}
            else:
                entry['candidates'].append({'id': 'fallback1',
                    'construction': str((folder / name).relative_to(HERE)),
                    'construction_sha256': digest,
                    'trigger': {'source': 'original ego path, footprint-to-rail distance and four-view frame/pixel audit',
                        'metric': 'parking path deviation or camera loss',
                        'failure_condition': 'primary missed reviewed parking position or lost a synchronized view'},
                    'changed_knobs': ['parking approach speed 2.0 to 1.0 m/s on unchanged site and route']})
        entries.append(entry)
        print(short, 'primary/fallback1 source-deferred railroad constructions', flush=True)
    write(HERE / 'execution-manifest.draft.json', {'format': 'worker-execution-manifest',
        'assignment_id': HERE.name, 'status': 'reviewed_original_rail_packet_required_at_capture',
        'runtime_manifest_sha256': hashlib.sha256((ROOT / 'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
        'cases': entries})
    return entries


if __name__ == '__main__':
    build()
