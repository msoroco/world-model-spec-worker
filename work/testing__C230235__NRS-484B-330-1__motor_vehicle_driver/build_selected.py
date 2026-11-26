"""Build seven exact source-gated flagger delivery constructions."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
FILES = ('runner.py', 'native_acquisition.py', 'native_output_bridge.py',
         'flagger_zone.py', 'source_packet.py', 'capture_seal.py', 'analysis.py',
         'process_saved.py', 'delivery_audit.py', 'comparison_audit.py', 'case-plan.json')
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))
BUNDLE_TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner

class BundleTests(unittest.TestCase):
    def test_selected_exact_case(self):
        self.assertEqual(runner.check()['case_id'],
                         json.loads((runner.HERE / 'config.json').read_text())['selected_case_id'])

    def test_original_reviewed_source_is_required(self):
        with patch('sys.argv', ['runner.py', '--host', 'localhost', '--port', '2000',
                                '--output-dir', 'attempt']):
            with patch.dict('os.environ', {}, clear=True):
                with self.assertRaisesRegex(ValueError, 'source-hashed reviewed flagger'):
                    runner.main()
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n')


def build():
    plan_bytes = (HERE / 'case-plan.json').read_bytes()
    plan = json.loads(plan_bytes)
    ids = [row['case_id'] for row in plan['cases']]
    if len(ids) != 7 or len(set(ids)) != 7:
        raise ValueError('seven exact selected flagger cases required')
    source = {name: (HERE / name).read_text() for name in FILES}
    channels = [{'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                 'method': method, 'time_window': 'all 900 original world ticks',
                 'reference_frame': 'reviewed C230235 CARLA world frame',
                 'uncertainty': 'physical realization and visibility pending'}
                for name, method in (
                    ('original_vehicle_motion', 'original actor body, position and speed readback'),
                    ('flagger_signal', 'source-bound flagger signal, orientation, visibility and recipient readback'),
                    ('camera_pixels', 'four synchronized original RGB sensor frames'))]
    description = {'channels': channels,
                   'context_inputs': [{'name': name, 'unit': 'source',
                                       'method': 'independently reviewed original source'}
                                      for name in ('zone_designation', 'construction_marking',
                                                   'flagger_authorization', 'traffic_control_role',
                                                   'signal_content', 'intended_recipient',
                                                   'vehicle_motion')],
                   'limitations': ['Neither synthetic fixtures nor signal appearance establish authorization or designation.',
                                   'Original physical response and legal failure/refusal remain unresolved.']}
    entries = []
    for row in plan['cases']:
        case_id = row['case_id']
        name = case_id.removeprefix(AID + '__')
        config = {'assignment_id': AID, 'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                  'actor': plan['actor'], 'selected_case_id': case_id,
                  'supported_case_ids': ids, 'plan_sha256': hashlib.sha256(plan_bytes).hexdigest(),
                  'rate_hz': 20, 'duration_s': 45, 'capture_frames': 900,
                  'required_atoms': [], 'source_packets': [],
                  'cameras': [{'name': view, 'width': width, 'height': height, 'fov_deg': 80,
                               'pose_strategy': 'reviewed flagger, marked zone, recipient and response'}
                              for view, width, height in CAMERAS],
                  'case': dict(row, recording_description=description)}
        files = dict(source)
        files['config.json'] = json.dumps(config, indent=2, sort_keys=True, ensure_ascii=False) + '\n'
        files['candidate-tuning.json'] = json.dumps({'camera_mount_offset_m': 0}, sort_keys=True) + '\n'
        files['tests/test_bundle.py'] = BUNDLE_TEST
        construction = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                        'actor': plan['actor'], 'case_id': case_id,
                        'entrypoint': 'runner.py', 'recording_description': description,
                        'measurement_plan': {'case_id': case_id,
                                             'source_packets': ['reviewed flagger source packet', 'original ticks'],
                                             'procedure': 'analysis.py', 'legal_judgment': 'unresolved'},
                        'static_checks': ['reviewed original map and separate official area/flagger/signal sources',
                                          'exact driver, vehicle, flagger and recipient identities',
                                          '900 original 20 Hz ticks and four synchronized RGB sources'],
                        'termination_rules': ['900 original Native ticks',
                                              'active stop/proceed interval and release observed'],
                        'mechanisms': ['source-hashed reviewed CARLA Native operator',
                                       'physical flagger and vehicle with source-bound route',
                                       'source-readback signal and recipient',
                                       'four camera RGB callbacks and restored world'],
                        'files': [{'path': path, 'content': text} for path, text in files.items()]}
        relative = Path('cases') / name / 'construction.json'
        write(HERE / relative, construction)
        if not entries:
            write(HERE / 'construction.json', construction)
            write(HERE / 'config.json', config)
            (HERE / 'candidate-tuning.json').write_text(files['candidate-tuning.json'])
        alternate = json.loads(json.dumps(construction))
        for item in alternate['files']:
            if item['path'] == 'candidate-tuning.json':
                item['content'] = json.dumps({'camera_mount_offset_m': 1.5}, sort_keys=True) + '\n'
        fallback = Path('cases') / name / 'fallback1' / 'construction.json'
        write(HERE / fallback, alternate)
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': str(relative), 'construction_sha256': sha(HERE / relative),
                        'measurement_contract': str(Path('cases') / name / 'measurement-contract.json'),
                        'fixture_recipe': str(Path('work') / AID / 'cases' / name / 'fixture-recipe.json'),
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Flagger signal and intended recipient may not be visible or physically realized in original four-camera capture.'},
                        'candidates': [{'id': 'fallback1', 'construction': str(fallback),
                                        'construction_sha256': sha(HERE / fallback),
                                        'trigger': {'source': 'original four-camera visibility audit',
                                                    'metric': 'flagger signal and recipient simultaneously visible',
                                                    'failure_condition': 'either is outside the primary synchronized views'},
                                        'changed_knobs': ['camera_mount_offset_m: 0 to 1.5 m; Native operator must read back applied mount offset']}],
                        'measurement_procedure': {'entrypoint': 'analysis.py',
                                                  'method': 'saved original flagger/zone/signal/response measurement'},
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                           'host_env_var': 'CARLA_HOST',
                                           'port_env_var': 'CARLA_PORT'},
                        'acquisition': {
                            'original_vehicle_motion': {'entrypoint': 'native_acquisition.py',
                                'method': 'acquire', 'evidence': 'original-ticks.jsonl, 900 source actor body/speed frames'},
                            'flagger_signal': {'entrypoint': 'source_packet.py',
                                'method': 'verify', 'evidence': 'source-packet.json and per-tick original signal readback'},
                            'camera_pixels': {'entrypoint': 'native_acquisition.py',
                                'method': 'acquire', 'evidence': 'camera-source-manifest.json and 900 PNGs per view'}}})
    write(HERE / 'execution-manifest.json', {'format': 'worker-execution-manifest',
          'assignment_id': AID, 'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
          'cases': entries})
    (HERE / 'tests/test_bundle.py').write_text(BUNDLE_TEST)
    return len(entries)


if __name__ == '__main__':
    print(build())
