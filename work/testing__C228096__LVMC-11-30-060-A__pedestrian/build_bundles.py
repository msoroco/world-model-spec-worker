"""Build four exact source-deferred outside-crosswalk constructions and fallbacks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULES = ('runner.py', 'native_entry.py', 'reviewed_site.py',
           'outside_crosswalk_entry.py', 'analysis.py')
OFFLINE_TEST = '''import json
import unittest
from pathlib import Path
from runner import check

class SelectedOutsideCrosswalkOffline(unittest.TestCase):
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
    for case in plan['cases']:
        case_id = case['case_id']
        short = case_id.split('__')[-1]
        folder = HERE / 'cases' / short
        description = {'channels': [
            {'name': 'outside_crosswalk_site', 'unit': 'classification', 'sampling_rate_hz': 20,
             'method': 'original roadway, marked/unmarked crosswalk and 11.30.070 source readback',
             'time_window': '900 original frames', 'reference_frame': 'reviewed roadway geometry',
             'uncertainty': 'crosswalk and prohibition status pending original review'},
            {'name': 'pedestrian_roadway_motion', 'unit': 'state', 'sampling_rate_hz': 20,
             'method': 'original pedestrian road-entry and crossing transform readback',
             'time_window': '900 original frames', 'reference_frame': 'reviewed roadway XY',
             'uncertainty': 'physical crossing pending'},
            {'name': 'vehicle_roadway_motion', 'unit': 'state', 'sampling_rate_hz': 20,
             'method': 'original all-vehicle roadway occupancy and trajectory readback',
             'time_window': '900 original frames', 'reference_frame': 'reviewed roadway XY',
             'uncertainty': 'actual all-vehicle inventory pending'},
            {'name': 'yield_trajectory', 'unit': 'state', 'sampling_rate_hz': 20,
             'method': 'original pedestrian yield throughout crossing and vehicle conflict readback',
             'time_window': '900 original frames', 'reference_frame': 'reviewed crossing route',
             'uncertainty': 'legal right-of-way judgment pending'}],
            'context_inputs': [{'name': 'reviewed_outside_crosswalk_site', 'unit': 'source',
                'method': 'reviewed original roadway, crosswalk, routes and prohibition source hashes'}],
            'limitations': ['Entry observation alone does not prove yield throughout crossing.',
                '11.30.070 prohibited-place applicability requires separate original review.']}
        config = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
            'actor': plan['actor'], 'selected_case_id': case_id,
            'supported_case_ids': ids, 'required_atoms': [], 'source_packets': [],
            'rate_hz': 20, 'duration_s': 45,
            'cameras': [{'name': name, 'width': width, 'height': height,
                'fov_deg': 75, 'pose_strategy': 'reviewed original roadway/crossing/vehicle view'}
                for name, width, height in (('overview', 1920, 1080),
                    ('approach', 1280, 720), ('reference_corner', 1280, 720),
                    ('driver_reference', 1280, 720))],
            'physical_completion': {'criterion': 'travel_progress',
                'motion_source': 'trace.jsonl', 'position_key': 'position_m',
                'minimum_progress_m': 5.0, 'minimum_samples': 3,
                'engineering_tolerances_not_legal': True,
                'completion_goal_method': 'At least 5m original pedestrian progress as an engineering motion proxy; independently audit full roadway crossing.'},
            'case': {'case_id': case_id,
                'physical_target': 'reviewed crossing outside both crosswalk categories and separate vehicle yield interaction',
                'recording_description': description}}
        spec = {key: case[key] for key in ('case_id', 'requested_vehicle_on_roadway',
            'requested_pedestrian_yield', 'requested_prohibited_place_under_11_30_070')}
        spec['source_status'] = 'reviewed_original_crossing_packet_required_at_capture'
        write(folder / 'config.json', config)
        write(folder / 'case-spec.json', spec)
        entry = None
        for candidate_id, speed in (('primary', 1.2), ('fallback1', 0.8)):
            controller = {'walker_speed_mps': speed,
                'source': 'predeclared path tracking on unchanged reviewed original site',
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
                    'original_source': 'reviewed roadway/crosswalk, pedestrian and vehicle 900-frame readback',
                    'saved_method': 'source-bound first road entry and all-vehicle yield history'},
                'mechanisms': ['source-gated original outside-crosswalk crossing selection',
                    'same-tick pedestrian, vehicle and four-camera capture'],
                'static_checks': ['exact case, 20 Hz and four cameras',
                    'reviewed source packet required before Native world mutation'],
                'termination_rules': {'duration_s': 45,
                    'early_termination': 'retain failed capture; do not publish as original crossing'}}
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
                        'reason': 'Pedestrian crossing or separate vehicle may leave the four-camera footprint'},
                    'candidates': [],
                    'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                        'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}}
            else:
                entry['candidates'].append({'id': 'fallback1',
                    'construction': str((folder / name).relative_to(HERE)),
                    'construction_sha256': digest,
                    'trigger': {'source': 'original pedestrian path and four-view frame/pixel audit',
                        'metric': 'roadway crossing path deviation or camera loss',
                        'failure_condition': 'primary missed reviewed crossing or lost a synchronized view'},
                    'changed_knobs': ['pedestrian speed 1.2 to 0.8 m/s on unchanged site and route']})
        entries.append(entry)
        print(short, 'primary/fallback1 source-deferred constructions', flush=True)
    write(HERE / 'execution-manifest.draft.json', {'format': 'worker-execution-manifest',
        'assignment_id': HERE.name, 'status': 'reviewed_original_crossing_packet_required_at_capture',
        'runtime_manifest_sha256': hashlib.sha256((ROOT / 'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
        'cases': entries})
    return entries


if __name__ == '__main__':
    build()
