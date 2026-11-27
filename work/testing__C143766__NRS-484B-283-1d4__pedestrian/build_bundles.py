"""Build seven exact 1d4 crossing bundles with one path-speed fallback each."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULES = ('runner.py', 'native_entry.py', 'reviewed_site.py',
           'pedestrian_crossing.py', 'crossing_measurement.py', 'analysis.py')
OFFLINE_TEST = '''import json
import unittest
from pathlib import Path
from runner import check

class SelectedCrossingOffline(unittest.TestCase):
    def test_source_gate_and_identity(self):
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
        cid = case['case_id']
        short = cid.split('__')[-1]
        folder = HERE / 'cases' / short
        description = {'channels': [
            {'name': name, 'unit': unit, 'sampling_rate_hz': 20,
             'method': method, 'time_window': '900 original frames',
             'reference_frame': 'reviewed original trail, crossing, signal and destination',
             'uncertainty': 'physical source and visibility pending'}
            for name, unit, method in (
                ('signal_phase', 'indication', 'same-frame official facing pedestrian signal phase and countdown readback'),
                ('pedestrian_route', 'state', 'original position, first highway entry and destination arrival'),
                ('safety_destination', 'source', 'source-hashed curb, accessible sidewalk, provided safety zone or reviewed other safe place'),
                ('exception_context', 'inventory', 'source-hashed NRS 484B.287, .290 and .350 context'))],
            'context_inputs': [{'name': 'reviewed_crossing_site', 'unit': 'source',
                'method': 'reviewed original OpenDRIVE, trail, highway, signal, route and destination source hashes'}],
            'limitations': ['Observed Walk entry is not a legal finding of lawful prior entry.',
                'Introductory exceptions and actual safety-place status require independent review.']}
        config = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
            'actor': plan['actor'], 'selected_case_id': cid,
            'supported_case_ids': ids, 'required_atoms': [], 'source_packets': [],
            'rate_hz': 20, 'duration_s': 45,
            'cameras': [{'name': name, 'width': width, 'height': height,
                'fov_deg': 75, 'pose_strategy': 'reviewed original crossing/signal/destination pose'}
                for name, width, height in (('overview', 1920, 1080),
                    ('approach', 1280, 720), ('reference_corner', 1280, 720),
                    ('driver_reference', 1280, 720))],
            'physical_completion': {'criterion': 'travel_progress',
                'motion_source': 'trace.jsonl', 'position_key': 'position_m',
                'minimum_progress_m': 5.0, 'minimum_samples': 3,
                'engineering_tolerances_not_legal': True,
                'completion_goal_method': 'At least 5m original pedestrian progress as an engineering proxy; independently audit actual highway entry, destination, signal transition and original pixels.'},
            'case': {'case_id': cid, 'physical_target': 'reviewed crossing entry and arrival during and relative to steady signal indication',
                'recording_description': description}}
        spec = {key: case[key] for key in ('case_id', 'entry_phase', 'destination', 'arrival_phase', 'countdown')}
        spec['source_status'] = 'reviewed_original_crossing_packet_required_at_capture'
        write(folder / 'config.json', config)
        write(folder / 'case-spec.json', spec)
        entry = None
        for candidate_id, speed in (('primary', 1.2), ('fallback1', 0.8)):
            controller = {'walker_speed_mps': speed,
                'source': 'predeclared route tracking on unchanged reviewed original trail/crossing site',
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
                'actor': plan['actor'], 'case_id': cid, 'entrypoint': 'runner.py',
                'files': files, 'recording_description': description,
                'measurement_plan': {'selected_requirement': plan['requirement_dispositions'][1]['requirement'],
                    'original_source': 'reviewed original signal and pedestrian 900-frame readback',
                    'saved_method': 'source-bound first highway entry, destination arrival and steady transition'},
                'mechanisms': ['source-gated original trail/highway/signal/destination selection',
                    'same-tick pedestrian and four-camera capture with world restoration'],
                'static_checks': ['exact case, 20 Hz and four cameras',
                    'reviewed original source packet required before Native world mutation'],
                'termination_rules': {'duration_s': 45,
                    'early_termination': 'retain failed capture; never publish it as a completed crossing'}}
            name = 'construction.json' if candidate_id == 'primary' else 'fallback1-construction.json'
            digest = write(folder / name, construction)
            if candidate_id == 'primary':
                entry = {'case_id': cid, 'construction': str((folder / name).relative_to(HERE)),
                    'construction_sha256': digest, 'kind': 'delivery',
                    'measurement_procedure': {'entrypoint': 'analysis.py'},
                    'fixture_recipe': str((folder / 'fixture-recipe.json').relative_to(ROOT)),
                    'measurement_contract': str((folder / 'measurement-contract.json').relative_to(HERE)),
                    'acquisition': {channel['name']: {'entrypoint': 'analysis.py',
                        'method': channel['method'], 'evidence': 'channels/' + channel['name'] + '.jsonl'}
                        for channel in description['channels']},
                    'candidate_risk': {'status': 'physical',
                        'reason': 'Original trail-to-highway route, safety destination or signal pixels may leave the four-camera footprint'},
                    'candidates': [],
                    'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                        'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}}
            else:
                entry['candidates'].append({'id': 'fallback1',
                    'construction': str((folder / name).relative_to(HERE)),
                    'construction_sha256': digest,
                    'trigger': {'source': 'original route and four-view frame/pixel audit',
                        'metric': 'crossing/destination path deviation or camera loss',
                        'failure_condition': 'primary missed reviewed crossing/destination or lost a synchronized view'},
                    'changed_knobs': ['walker speed 1.2 to 0.8 m/s on unchanged site, route and signal schedule']})
        entries.append(entry)
        print(short, 'primary/fallback1 source-deferred constructions', flush=True)
    write(HERE / 'execution-manifest.draft.json', {'format': 'worker-execution-manifest',
        'assignment_id': HERE.name, 'status': 'reviewed_original_crossing_packet_required_at_capture',
        'runtime_manifest_sha256': hashlib.sha256((ROOT / 'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
        'cases': entries})
    first = plan['cases'][0]['case_id'].split('__')[-1]
    for name in ('config.json', 'construction.json'):
        (HERE / name).write_bytes((HERE / 'cases' / first / name).read_bytes())
    return entries


if __name__ == '__main__':
    build()
