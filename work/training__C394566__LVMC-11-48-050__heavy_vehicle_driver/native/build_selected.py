"""Build exact inline Native bundles for the route-designation comparison."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
NATIVE = FOLDER/'native'
AID = 'training__C394566__LVMC-11-48-050__heavy_vehicle_driver'
ROOT = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    base=json.loads((NATIVE/'config.json').read_text())
    fixed={name:(NATIVE/name).read_text() for name in
           ('runner.py','finalize.py','source_contract.py','route_measurement.py')}
    fixed['restriction_measure.py']=(FOLDER/'restriction_measure.py').read_text()
    test='''import json\nimport unittest\nfrom pathlib import Path\nfrom runner import check, survey_check\nfrom finalize import measure_activation, measure_night_window\n\nclass BundleTest(unittest.TestCase):\n    def test_case_and_capture(self):\n        cfg=json.loads(Path('config.json').read_text())\n        self.assertFalse(check(cfg)['simulation_started'])\n        self.assertEqual(len(cfg['cameras']),4)\n        self.assertEqual(cfg['frames'],600)\n    def test_factual_methods(self):\n        facts={'vehicle_over_8000_lb':True,'residence_district':True,'non_truck_route':False,'night_window':'inside'}\n        self.assertFalse(measure_activation(facts)['non_truck_route'])\n        self.assertFalse(measure_night_window(facts)['clock_endpoint_unresolved'])\n    def test_missing_original_route(self):\n        with self.assertRaisesRegex(ValueError,'Missing reviewed Native survey source'):\n            survey_check({})\n'''
    manifest={'format':'worker-execution-manifest','assignment_id':AID,
              'runtime_manifest_sha256':sha(ROOT/'runtime/SOURCE-MANIFEST.json'),
              'status':'draft_offline_probe','cases':[]}
    for suffix,route in (('truck_route',True),('non_truck_route',False)):
        case=AID+'__'+suffix
        entry={'case_id':case,'kind':'delivery','candidate_risk':{'status':'physical',
            'reason':'Surveyed original route may fail to reach the intended segment within 600 frames.'},
            'measurement_contract':f'../measurement-{suffix}.json',
            'measurement_procedure':{'entrypoint':'finalize.py','output_schema':'worker-analysis-report'},
            'fixture_recipe':f'work/{FOLDER.name}/fixture-recipe-{suffix}.json',
            'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'},
            'candidates':[]}
        for candidate,speed in (('primary',5.0),('fallback1',3.5)):
            cfg=dict(base);cfg.update(case_id=case,selected_case_id=case,
                                       candidate_id=candidate,target_speed_mps=speed,
                                       requested_truck_route=route)
            cfg['case']={'case_id':case,'requested_setting':suffix}
            plan=json.loads((FOLDER/'case-plan.json').read_text())
            cfg['supported_case_ids']=[item['case_id'] for item in plan['cases']]
            files=[{'path':name,'content':content} for name,content in fixed.items()]
            files += [{'path':'config.json','content':json.dumps(cfg,indent=2)+'\n'},
                      {'path':'tests/test_bundle.py','content':test}]
            construction={'format':'worker-construction','assignment_id':AID,'case_id':case,
                          'law_id':'LVMC-11-48-050','cell_id':'C394566','actor':'heavy_vehicle_driver',
                          'entrypoint':'runner.py','recording_description':cfg['recording_description'],
                          'files':files,'measurement_plan':{'source':'sealed original Native and cited factual authority',
                          'expected_frames':600,'legal_verdict':None},
                          'static_checks':['identity','four camera profile','original-source requirement'],
                          'termination_rules':['600 joined original frames or explicit failure'],
                          'mechanisms':['surveyed heavy vehicle route','source-joined factual context']}
            path=NATIVE/suffix/candidate/'construction.json';path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(construction,indent=2)+'\n')
            relative=str(path.relative_to(NATIVE));digest=sha(path)
            if candidate=='primary':entry.update(construction=relative,construction_sha256=digest)
            else:entry['candidates'].append({'id':'fallback1','construction':relative,
                'construction_sha256':digest,
                'trigger':{'source':'original Native road/pose trace',
                           'metric':'distance and arrival at surveyed road target within 600 frames',
                           'failure_condition':'primary overshoots or fails to reach surveyed target with joined original frames'},
                'changed_knobs':['target_speed_mps: 5.0 -> 3.5']})
        manifest['cases'].append(entry)
    path=NATIVE/'route-probe-manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    print(json.dumps({'cases':len(build()['cases'])}))
