"""Build three exact roadway-stop CPU bundles for offline proof.

This draft is not the canonical four-case execution manifest. It establishes
three primaries before compatibility and saved-processing receipts are bound.
"""
import hashlib
import json
from pathlib import Path

from native_channels import channels_for
from native_controller import camera_specs


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ('reference', 'contrast', 'safe_operation_stop')
MODULES = ('runner.py', 'native_runner.py', 'native_controller.py',
           'capture_attempt.py', 'candidate_tuning.py', 'stop_construction.py',
           'scene_inventory.py', 'sweep_native_controller.py',
           'control_phase_measurement.py', 'sweep_case.py',
           'source_measurement.py', 'saved_analysis.py', 'native_channels.py',
           'native_finalize.py', 'source_provenance.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build():
    plan = json.loads((HERE/'case-plan.json').read_text())
    def description_for(case):
        return {
            'channels': [
                {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                 'reference_frame': 'original CARLA frame joined to four video sources',
                 'time_window': 'all 600 frames / 30 seconds',
                 'method': 'native_channels.derive from original actor/map/frame rows',
                 'uncertainty': '50 ms sampling; original pixels and legal effect require independent review'}
                for name in channels_for(case)],
            'context_inputs': [
                {'name':'surveyed_map_lane_shoulder_and_blueprints',
                 'unit':'structured','method':'Native survey and live map readback',
                 'reference_frame':'surveyed CARLA map identity',
                 'uncertainty':'Original map and actor identity require Native execution'}],
            'limitations': ['normal and reasonable impediment, safe-operation necessity, '
                            'law compliance and physical acceptance require original-source review'],
        }
    common = {
        'assignment_id': HERE.name,
        'supported_case_ids': [case['case_id'] for case in plan['cases']],
        'law_id': 'NRS-484B-627-2', 'cell_id': 'C179480',
        'actor': 'motor_vehicle_driver', 'candidate_id': 'primary',
        'rate_hz': 20, 'frames': 600, 'duration_s': 30,
        'comparison_variable': 'roadway_stop_blocks_traffic',
        'cameras': [
            {'name': x['name'], 'width': x['width'], 'height': x['height'],
             'fov_deg': x['fov'], 'pose_strategy': 'surveyed_ego_relative'}
            for x in camera_specs()],
        'required_atoms': [], 'source_packets': [],
        'survey_contract': {'environment_variable': 'CARLA_SURVEY',
                            'live_map_readback_required': True,
                            'survey_frame_count': 600},
        'legal_verdict': None, 'physical_acceptance_claimed': False,
    }
    test = '''import json\nimport unittest\nfrom pathlib import Path\nimport runner\nfrom candidate_tuning import tuning\n\nclass BundleTest(unittest.TestCase):\n    def test_exact_primary_contract(self):\n        checked=runner.check()\n        config=json.loads((Path(__file__).parents[1]/'config.json').read_text())\n        self.assertEqual(checked['case_id'],config['case_id'])\n        self.assertEqual(checked['frames'],600)\n        self.assertFalse(checked['physical_acceptance_claimed'])\n    def test_risk_candidate_is_source_specified(self):\n        self.assertIsNotNone(tuning('fallback1').risk_trigger)\n        with self.assertRaises(ValueError):\n            tuning('unknown')\n'''
    entries=[]
    for case in CASES:
        case_id=HERE.name+'__'+case
        description=description_for(case)
        config=dict(common,case_id=case_id,selected_case_id=case_id,
                    case_suffix=case,case={'case_id':case_id},
                    comparison_requested_value={
                        'reference':'roadway_lane_overlap_target',
                        'contrast':'shoulder_clear_target',
                        'safe_operation_stop':'roadway_stop_with_source_visible_hazard'}[case],
                    recording_description=description)
        if case=='reference':
            write(HERE/'config.json',config)
        files=[{'path': name, 'content': (HERE/name).read_text()} for name in MODULES]
        files.extend([{'path':'config.json','content':json.dumps(config,indent=2,sort_keys=True)+'\n'},
                      {'path':'tests/test_bundle.py','content':test}])
        construction={
            'format':'worker-construction','status':'selected_cpu_preparation_incomplete',
            'law_id':config['law_id'],'cell_id':config['cell_id'],
            'actor':config['actor'],'case_id':case_id,'entrypoint':'runner.py',
            'files':files,
            'mechanisms':['surveyed driving lane and shoulder','ego and following actor',
                          'four original RGB cameras','source-bound stop finalizer']+
                         (['source-visible held-brake other-vehicle hazard']
                          if case=='safe_operation_stop' else []),
            'raw_sources':['native-actors.jsonl','video_frames.jsonl',
                           'native-map-readback.json','source-measurements.json',
                           'overview.mkv','approach.mkv','reference_corner.mkv',
                           'driver_reference.mkv'],
            'source_cameras':[x['name'] for x in camera_specs()],
            'recording_description':description,
            'measurement_plan':{
                'source':'case-plan.json','requirements':plan['requirement_dispositions'],
                'per_case_contracts':[{'case_id':case_id,
                                       'observations':plan['observations']}]},
            'termination_rules':{'planned_frames':600,
                                 'early_failure':'survey, actor, camera, frame or source integrity error'},
            'static_checks':['20 Hz 600-frame exact case','four source cameras',
                             'original actor/frame/map hashes and saved-only finalizer'],
        }
        relative=('construction.json' if case=='reference'
                  else 'draft-'+case+'-construction.json')
        path=HERE/relative
        write(path,construction)
        entries.append({'case_id':case_id,'construction':relative,
                        'construction_sha256':sha(path)})
    draft={'format':'worker-execution-manifest','assignment_id':HERE.name,
           'runtime_manifest_sha256':sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json'),
           'status':'draft_primary_offline_only','cases':entries}
    write(HERE/'draft-reference-manifest.json', draft)
    return {'case_count':len(entries),'constructions':entries,
            'draft_manifest_sha256': sha(HERE/'draft-reference-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
