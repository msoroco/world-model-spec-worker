"""Build five exact source-gated timing constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SUFFIXES = ('precedence', 'advance', 'timing_below', 'timing_inside', 'timing_above')
CAMERAS = ('front', 'rear', 'left', 'right')

RUNNER = '''"""Exact median-crossing timing diagnostic bundle."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'config.json').read_text())
    raw = (root / 'case-plan.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != config['plan_sha256']:
        raise ValueError('Exact timing case plan changed')
    plan = json.loads(raw)
    selected = [row for row in plan['cases'] if row['case_id'] == config['selected_case_id']]
    if len(selected) != 1 or not config['selected_case_id'].startswith(config['assignment_id']+'__'):
        raise ValueError('Exact timing case missing')
    if (config['requested_ego_response'] != selected[0]['requested_ego_response'] or
            config['requested_entry_difference_s'] != selected[0]['requested_entry_difference_s']):
        raise ValueError('Timing or response construction target changed')
    if (config['law_id'] != 'NRS-484B-250-2' or config['cell_id'] != 'C125751' or
            config['crossing_kind'] != 'median_opening_roadway_crossing' or
            config['governing_device'] != 'official_traffic_light'):
        raise ValueError('Crossing/device context changed')
    if (config['rate_hz'] != 20 or config['frame_count'] != 900 or
            config['duration_s'] != 45 or config['cameras'] != ['front','rear','left','right']):
        raise ValueError('Original timing/camera source contract changed')
    return config['selected_case_id']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--survey')
    parser.add_argument('--survey-sha256')
    parser.add_argument('--map-source')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    case = check()
    if args.check:
        print('diagnostic entry-timing bundle passed: '+case)
        return
    survey_arg = args.survey or os.getenv('C125751_SURVEY')
    survey_sha256 = args.survey_sha256 or os.getenv('C125751_SURVEY_SHA256')
    map_arg = args.map_source or os.getenv('C125751_MAP_SOURCE')
    if not all((args.output_dir,survey_arg,survey_sha256,map_arg)):
        raise ValueError('Reviewed original crossing, governing device and actor sources required')
    survey_path = Path(survey_arg).resolve()
    map_path = Path(map_arg).resolve()
    if not survey_path.is_file() or not map_path.is_file():
        raise ValueError('Reviewed original crossing source file missing')
    if hashlib.sha256(survey_path.read_bytes()).hexdigest() != survey_sha256:
        raise ValueError('Reviewed original crossing survey hash differs')
    survey = json.loads(survey_path.read_text())
    if hashlib.sha256(map_path.read_bytes()).hexdigest() != survey.get('opendrive_sha256'):
        raise ValueError('Reviewed original OpenDRIVE hash differs')
    from native_capture import capture
    from carla_native_adapter import CarlaNativeAdapter
    import carla
    client = carla.Client(args.host,args.port)
    client.set_timeout(20.0)
    adapter = CarlaNativeAdapter(client,carla,survey)
    attempt = Path(args.output_dir).resolve()
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore
    from scenario_pipeline.worker_exchange.native_output import seal_capture
    from runtime_source_bridge import export
    from analysis import run as analyze
    import shutil
    saved_world = snapshot(client)
    failure = None
    restoration = None
    try:
        capture(adapter,survey_path,survey_sha256,map_path,case,attempt)
        acquisition = attempt/'acquisition'
        acquisition.mkdir()
        shutil.copy2(attempt/'source-manifest.json',acquisition/'source-manifest.json')
        (attempt/'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind':'native','diagnostic_fixture':False},indent=2)+'\\n')
        export(attempt,survey_path,attempt/'runtime-export')
        for name in ('overview.mkv','approach.mkv','reference_corner.mkv',
                     'driver_reference.mkv'):
            shutil.copy2(attempt/'runtime-export'/name,attempt/name)
        shutil.copy2(attempt/'overview.mkv',attempt/'raw.mkv')
        analyze(attempt,attempt/'analysis-report.json')
    except Exception as error:
        failure = error
    finally:
        try:
            restoration = restore(client,saved_world)
        except Exception as error:
            if failure is None:
                failure = error
    if failure is not None:
        (attempt/'native-run-status.json').write_text(json.dumps({
            'errors':[str(failure)],'restoration':restoration},indent=2)+'\\n')
        raise failure
    try:
        seal_capture(attempt,frames=900,restoration=restoration,errors=[],encoder_exit_codes={})
    except Exception as error:
        (attempt/'native-run-status.json').write_text(json.dumps({
            'errors':[str(error)],'restoration':restoration},indent=2)+'\\n')
        raise


if __name__ == '__main__':
    main()
'''

TEST = '''import json
import hashlib
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root/'config.json').read_text())['selected_case_id'])

    def test_unsourced_launch_rejected(self):
        with patch('sys.argv', ['runner.py','--output-dir','.']):
            with patch.dict(os.environ, {'C125751_SURVEY':'',
                                      'C125751_SURVEY_SHA256':'',
                                      'C125751_MAP_SOURCE':''}):
                with self.assertRaisesRegex(ValueError, 'Reviewed original crossing'):
                    runner.main()

    def test_environment_source_handoff_requires_existing_files(self):
        with patch('sys.argv', ['runner.py','--output-dir','.']):
            with patch.dict(os.environ, {'C125751_SURVEY':'/missing/survey.json',
                                      'C125751_SURVEY_SHA256':'0'*64,
                                      'C125751_MAP_SOURCE':'/missing/map.xodr'}):
                with self.assertRaisesRegex(ValueError, 'source file missing'):
                    runner.main()

    def test_native_closure_requires_restoration_before_sealing(self):
        scratch = Path(__file__).resolve().parents[2]/'c125751-bundle-tests'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            root = Path(tmp)
            survey = root/'survey.json'
            source_map = root/'map.xodr'
            source_map.write_bytes(b'original map')
            survey.write_text(json.dumps({'opendrive_sha256':hashlib.sha256(source_map.read_bytes()).hexdigest()})+'\\n')
            attempt = root/'attempt'
            attempt.mkdir()
            events = []
            client = SimpleNamespace(set_timeout=lambda _:None)
            def fake_export(_attempt,_survey,destination):
                events.append('export')
                destination.mkdir()
                for name in ('overview.mkv','approach.mkv','reference_corner.mkv',
                             'driver_reference.mkv'):
                    (destination/name).write_bytes(b'source')
            def fake_restore(_client,_saved):
                events.append('restore')
                return {'restored':True}
            def fake_capture(_adapter,_survey,_sha,_map,_case,destination):
                events.append('capture')
                (destination/'source-manifest.json').write_text('{}\\n')
            def fake_seal(_attempt,**kwargs):
                events.append('seal')
                self.assertTrue(kwargs['restoration']['restored'])
            argv = ['runner.py','--output-dir',str(attempt),'--survey',str(survey),
                    '--survey-sha256',hashlib.sha256(survey.read_bytes()).hexdigest(),
                    '--map-source',str(source_map)]
            with patch('sys.argv',argv), patch.dict(sys.modules,{'carla':SimpleNamespace(Client=lambda *_:client)}), \\
                 patch('carla_native_adapter.CarlaNativeAdapter',return_value=object()), \\
                 patch('native_capture.capture',side_effect=fake_capture), \\
                 patch('runtime_source_bridge.export',side_effect=fake_export), \\
                 patch('analysis.run',side_effect=lambda *_:events.append('analysis')), \\
                 patch('scenario_pipeline.worker_exchange.world_restore.snapshot',return_value=object()), \\
                 patch('scenario_pipeline.worker_exchange.world_restore.restore',side_effect=fake_restore), \\
                 patch('scenario_pipeline.worker_exchange.native_output.seal_capture',side_effect=fake_seal):
                runner.main()
            self.assertEqual(events,['capture','export','analysis','restore','seal'])
            self.assertTrue((attempt/'acquisition-provenance.json').is_file())
            self.assertTrue((attempt/'raw.mkv').is_file())


if __name__ == '__main__':
    unittest.main()
'''


def build():
    raw = (HERE/'case-plan.json').read_bytes()
    plan = json.loads(raw)
    if {row['case_id'] for row in plan['cases']} != {AID+'__'+s for s in SUFFIXES}:
        raise ValueError('five exact timing cases required')
    semantic = json.loads((HERE/'proposals/cases.json').read_text())
    descriptions = {row['case_id']:row['recording_description'] for row in semantic['cases']}
    if set(descriptions) != {AID+'__baseline'} | {row['case_id'] for row in plan['cases']}:
        raise ValueError('canonical semantic cases differ from exact timing cases')
    rows = []
    for item in plan['cases']:
        case = item['case_id']
        config = {'assignment_id': AID, 'law_id': 'NRS-484B-250-2',
                  'cell_id': 'C125751', 'actor': 'motor_vehicle_driver',
                  'selected_case_id': case, 'plan_sha256': hashlib.sha256(raw).hexdigest(),
                  'crossing_kind': 'median_opening_roadway_crossing',
                  'governing_device': 'official_traffic_light',
                  'requested_ego_response': item['requested_ego_response'],
                  'requested_entry_difference_s': item['requested_entry_difference_s'],
                  'rate_hz': 20, 'frame_count': 900, 'duration_s': 45,
                  'cameras': list(CAMERAS), 'required_atoms': [],
                  'diagnostic_only': False}
        files = {'runner.py': RUNNER, 'entry_timing.py': (HERE/'entry_timing.py').read_text(),
                 'analysis.py': (HERE/'analysis.py').read_text(),
                 'native_capture.py': (HERE/'native_capture.py').read_text(),
                 'saved_delivery.py': (HERE/'saved_delivery.py').read_text(),
                 'saved_finalizer.py': (HERE/'saved_finalizer.py').read_text(),
                 'canonical_evidence.py': (HERE/'canonical_evidence.py').read_text(),
                 'delivery_audit.py': (HERE/'delivery_audit.py').read_text(),
                 'comparison_audit.py': (HERE/'comparison_audit.py').read_text(),
                 'carla_native_adapter.py': (HERE/'carla_native_adapter.py').read_text(),
                 'runtime_source_bridge.py': (HERE/'runtime_source_bridge.py').read_text(),
                 'case-plan.json': raw.decode(), 'config.json': json.dumps(config,indent=2)+'\n',
                 'tests/test_bundle.py': TEST}
        construction = {'law_id': config['law_id'], 'cell_id': config['cell_id'],
                        'actor': config['actor'], 'case_id': case,
                        'entrypoint': 'runner.py', 'diagnostic_only': False,
                        'recording_description': descriptions[case],
                        'files': [{'path': name, 'content': body} for name,body in files.items()]}
        suffix = case.removeprefix(AID+'__')
        path = HERE/('construction-'+suffix+'.json')
        path.write_text(json.dumps(construction,indent=2)+'\n')
        rows.append({'case_id': case, 'construction': path.name,
                     'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'kind': 'delivery',
                     'measurement_contract': 'measurement-contract-'+suffix+'.json',
                     'measurement_contract_sha256': hashlib.sha256(
                         (HERE/('measurement-contract-'+suffix+'.json')).read_bytes()).hexdigest(),
                     'measurement_procedure': {'entrypoint': 'analysis.py'},
                     'candidate_risk': {'status': 'physical', 'reason': item['physical_risk']['risk']}})
    (HERE/'execution-manifest.draft.json').write_text(json.dumps({
        'assignment_id': AID, 'status': 'diagnostic_offline_only_original_sources_pending',
        'cases': rows},indent=2)+'\n')
    print('built five exact source-gated entry-timing constructions')


if __name__ == '__main__':
    build()
