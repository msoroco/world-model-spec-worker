"""Build an isolated C125763 primary offline diagnostic bundle.

The site review here is a synthetic schema fixture and is never physical
evidence or a claim about an actual CARLA map.
"""
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
CASE=HERE.name+'__yield_ego_left_near_time'
OUT=HERE/'cases'/'yield_ego_left_near_time'
CODE=('runner.py','native_pair.py','median_yield_route.py','yield_sign_control.py',
      'camera_encoder.py','capture_sources.py','site_packet.py','finalizer.py',
      'simultaneous_entries.py')


def serialized(value):
    return json.dumps(value,indent=2,allow_nan=False)+'\n'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    sys.path.insert(0,str(HERE/'tests'))
    spec=importlib.util.spec_from_file_location('test_runner',HERE/'tests'/'test_runner.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as temporary:
        temp=Path(temporary)
        _,_,config,site=module.RunnerTests().packet(temp)
        config['frames']=60
        config['duration_s']=3
        config['other_release_frame']=20
        config['required_atoms']=['ru.subject','ru.motor_vehicle','kin.position',
                                  'kin.velocity','kin.speed','st.intersection',
                                  'rel.bearing']
        config['physical_completion']={
            'criterion':'intersection_clearance',
            'motion_source':'crossing_history.jsonl',
            'body_key':'ego.body_vertices_xy_m',
            'intersection_polygon_xy_m':site['crossing_polygon_xy_m'],
            'exit_axis':0,'exit_sign':1,
            'context_sources':['site.json']}
        config['recording_description']={
            'channels':[{'name':'entry_timing','unit':'structured record',
                         'method':'complete body entry joined to original frames',
                         'time_window':'entire capture',
                         'reference_frame':'original Native frame',
                         'uncertainty':'legal approximate-time judgment unresolved',
                         'sampling_rate_hz':20}],
            'context_inputs':[{'name':'entry_context','unit':'structured record',
                               'method':'source-bound crossing and yield-sign packet'}],
            'limitations':['Synthetic site; no physical or statutory acceptance'],
        }
        files=[{'path':name,'source':str((HERE/name).relative_to(REPO)),
                'content':(HERE/name).read_text()} for name in CODE]
        files.extend({'path':str(path.relative_to(temp)),'content':path.read_text()}
                     for path in sorted(temp.rglob('*.json')) if path.name!='config.json')
    files.append({'path':'config.json','content':serialized(config)})
    files.append({'path':'tests/test_bundle.py','content':
        'import unittest\nfrom runner import load_config,ASSIGNMENT\n'
        'class BundleTest(unittest.TestCase):\n'
        ' def test_exact_selected_config_and_site(self):\n'
        '  config,site=load_config("config.json")\n'
        '  self.assertEqual(config["selected_case_id"],ASSIGNMENT+"__yield_ego_left_near_time")\n'
        '  self.assertEqual(site["review_status"],"reviewed_candidate")\n'})
    OUT.mkdir(parents=True,exist_ok=True)
    construction={'case_id':CASE,'law_id':'NRS-484B-250-2',
                  'cell_id':'C125763','actor':'motor_vehicle_driver',
                  'entrypoint':'runner.py','status':'synthetic_diagnostic_only',
                  'recording_description':config['recording_description'],
                  'measurement_plan':{'source':'crossing_history.jsonl',
                                      'saved_finalizer':'finalizer.py'},
                  'files':files}
    (OUT/'construction.json').write_text(serialized(construction))
    manifest={'format':'worker-execution-manifest','assignment_id':HERE.name,
              'runtime_manifest_sha256':sha(REPO/'runtime'/'SOURCE-MANIFEST.json'),
              'status':'isolated_partial_primary_diagnostic',
              'cases':[{'case_id':CASE,'kind':'delivery',
                        'construction':'cases/yield_ego_left_near_time/construction.json',
                        'construction_sha256':sha(OUT/'construction.json'),
                        'measurement_procedure':{'entrypoint':'finalizer.py'},
                        'measurement_contract':'measurement-contract.json',
                        'fixture_recipe':str((HERE/'diagnostic-recipe.json').relative_to(REPO)),
                        'native_handoff':{'python_env_var':'CARLA_PYTHON',
                                          'host_env_var':'CARLA_HOST',
                                          'port_env_var':'CARLA_PORT'}}]}
    (HERE/'primary-candidate-manifest.json').write_text(serialized(manifest))
    return manifest


if __name__=='__main__':
    print(serialized(build()),end='')
