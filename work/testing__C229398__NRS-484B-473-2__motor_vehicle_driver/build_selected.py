"""Build source-gated exact parked-light Native bundles without original claims."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from parked_lamps import CASES
from source_packet import ASSIGNMENT

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))
BUNDLE_TEST = '''import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner

class BundleTests(TestCase):
    def test_exact_case(self):
        self.assertEqual(runner.check()[0]["selected_case_id"],
                         json.loads((runner.HERE / "config.json").read_text())["selected_case_id"])

    def test_reviewed_sources_required_before_carla(self):
        with patch("sys.argv", ["runner.py", "--host", "localhost", "--port", "2000",
                                "--output-dir", "attempt"]):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(ValueError, "source-hashed reviewed parked-light"):
                    runner.main()
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build():
    plan_bytes = (HERE / 'case-plan.json').read_bytes()
    plan = json.loads(plan_bytes)
    exact = {ASSIGNMENT + '__' + case.name for case in CASES}
    if {row['case_id'] for row in plan['cases']} != exact or len(plan['comparisons']) != 5:
        raise ValueError('exact parked-light plan differs')
    source_files = ('runner.py', 'parked_lamps.py', 'source_packet.py',
                    'native_acquisition.py', 'native_output_bridge.py', 'capture_seal.py',
                    'process_saved.py', 'analysis.py', 'delivery_audit.py',
                    'comparison_audit.py', 'case-plan.json')
    content = {name: (HERE / name).read_text() for name in source_files}
    entries = []
    for case in CASES:
        case_id = ASSIGNMENT + '__' + case.name
        channels = [
            {'name': name, 'method': method, 'unit': 'structured',
             'time_window': 'all 900 original world ticks',
             'reference_frame': 'reviewed C229398 original world frame',
             'sampling_rate_hz': 20,
             'uncertainty': 'actual Native lamp readback and physical parking await original review'}
            for name, method in (
                ('original_vehicle_motion', 'source-joined original speed and parking interval'),
                ('lamp_state', 'original displayed, cowl and parking lamp readback with beam aim'),
                ('camera_pixels', 'four synchronized original camera images'))]
        description = {'channels': channels,
                       'context_inputs': [{'name': name, 'unit': 'structured',
                                          'method': 'independently reviewed original ' + name}
                                         for name in ('vehicle_identity', 'highway',
                                                      'parking_lawfulness', 'nighttime',
                                                      'displayed_lights', 'beam_aim',
                                                      'cowl_lamp', 'parking_lamp',
                                                      'vehicle_motion')],
                       'limitations': ['Beam aim is a measurement, not an invented statutory numeric cutoff.',
                                       'Original Native motion and lamp readback remain physically unverified.']}
        config = {'assignment_id': ASSIGNMENT, 'law_id': 'NRS-484B-473-2',
                  'cell_id': 'C229398', 'actor': 'motor_vehicle_driver',
                  'selected_case_id': case_id, 'supported_case_ids': sorted(exact),
                  'plan_sha256': hashlib.sha256(plan_bytes).hexdigest(),
                  'rate_hz': 20, 'duration_s': 45,
                  'required_atoms': [], 'source_packets': [],
                  'cameras': [{'name': name, 'width': width, 'height': height,
                               'fov_deg': 80,
                               'pose_strategy': 'reviewed curb, lamp body and highway approach'}
                              for name, width, height in CAMERAS],
                  'case': {'case_id': case_id, 'recording_description': description}}
        for candidate, offset in (('primary', 12.0), ('fallback1', 18.0)):
            config['approach_offset_m'] = offset
            files = dict(content)
            files['config.json'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
            files['tests/test_case.py'] = BUNDLE_TEST
            construction = {'law_id': 'NRS-484B-473-2', 'cell_id': 'C229398',
                            'actor': 'motor_vehicle_driver', 'case_id': case_id,
                            'entrypoint': 'runner.py', 'recording_description': description,
                            'measurement_plan': {'case_id': case_id,
                                                 'source_packets': ['source-packet.json',
                                                                    'original-ticks.jsonl',
                                                                    'camera-source-manifest.json'],
                                                 'procedure': 'parked_lamps.py:measure_original',
                                                 'legal_judgment': 'unresolved'},
                            'static_checks': ['reviewed original highway, parking, night, lamp hardware and beam sources',
                                              'source-hashed 900 ticks and four camera sources'],
                            'termination_rules': ['900 original 20 Hz Native world ticks',
                                                  'observed physically parked interval'],
                            'mechanisms': ['source-gated reviewed operator and OpenDRIVE',
                                           'actual vehicle route and lamp-state commands',
                                           'original source and owner-lifecycle readback'],
                            'files': [{'path': name, 'content': value} for name, value in files.items()]}
            rel = Path('cases') / case.name / ('construction.json' if candidate == 'primary'
                                                else 'fallback1/construction.json')
            path = HERE / rel
            write(path, construction)
            if case == CASES[0] and candidate == 'primary':
                write(HERE / 'config.json', config)
                write(HERE / 'construction.json', construction)
                (HERE / 'tests/test_case.py').write_text(BUNDLE_TEST)
            if candidate == 'primary':
                entries.append({'case_id': case_id, 'kind': 'delivery',
                                'construction': str(rel), 'construction_sha256': sha(path),
                                'measurement_contract': str(Path('cases') / case.name / 'measurement-contract.json'),
                                'fixture_recipe': str(Path('work') / ASSIGNMENT / 'cases' / case.name / 'fixture-recipe.json'),
                                'measurement_procedure': {'entrypoint': 'analysis.py',
                                                          'method': 'saved source-bound original parked-light measurements'},
                                'acquisition': {channel['name']: {
                                    'entrypoint': 'analysis.py', 'method': channel['method'],
                                    'evidence': 'channels/' + channel['name'] + '.jsonl'}
                                    for channel in channels},
                                'candidate_risk': {'status': 'physical',
                                                   'reason': 'The parked route or lamp readback may miss the reviewed curb and camera geometry.'},
                                'candidates': [],
                                'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                                   'host_env_var': 'CARLA_HOST',
                                                   'port_env_var': 'CARLA_PORT'}})
            else:
                entries[-1]['candidates'].append({
                    'id': 'fallback1', 'construction': str(rel),
                    'construction_sha256': sha(path),
                    'changed_knobs': ['source-gated approach offset 18 m instead of 12 m'],
                    'trigger': {'source': 'original route station, vehicle speed and lamp readback',
                                'metric': 'parking approach and lamp visibility',
                                'failure_condition': 'primary approach does not realize the reviewed parking and lamp visibility target'}})
    write(HERE / 'execution-manifest.json', {
        'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
        'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
        'cases': entries})
    return len(entries)


if __name__ == '__main__':
    print(build())
