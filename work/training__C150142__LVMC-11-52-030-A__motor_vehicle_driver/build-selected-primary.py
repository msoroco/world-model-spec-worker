"""Package one exact source-hashed red-curb reference for pinned offline checks."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
NATIVE = ROOT / 'native'
CASE = ROOT.name + '__reference'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


TEST = '''import json
import unittest
from pathlib import Path
import runner
import parking_controller

class SelectedReference(unittest.TestCase):
    def test_exact_sources_and_cameras(self):
        result=runner.check()
        self.assertTrue(result['source_bound'])
        self.assertEqual(result['frames'],240)
        self.assertFalse(result['original_native_observed'])
        cfg=json.loads((Path(__file__).resolve().parents[1]/'config.json').read_text())
        self.assertEqual(cfg['requested_target_x_m'],40)
        self.assertEqual([(v['width'],v['height']) for v in cfg['cameras']],
                         [(1920,1080),(1280,720),(1280,720),(1280,720)])

    def test_controller_uses_measured_speed(self):
        far=parking_controller.command(5,-6.8,2,40,-6.8)
        near=parking_controller.command(39,-6.8,2,40,-6.8)
        self.assertEqual(far['phase'],'approach')
        self.assertEqual(near['phase'],'brake_to_park')
        self.assertEqual(near['throttle'],0)

if __name__=='__main__': unittest.main()
'''


def build():
    draft = NATIVE / 'drafts/reference/primary'
    cfg = json.loads((draft / 'config.json').read_text())
    cfg.update(selected_case_id=CASE, duration_s=12, rate_hz=20,
               required_atoms=[], source_packets=[], supported_case_ids=[CASE],
               physical_success_claimed=False,
               cameras=[{'name': name, 'width': width, 'height': height,
                         'pose_strategy': 'ego_attached', 'fov_deg': fov}
                        for name, width, height, fov in
                        [('overview',1920,1080,85),('approach',1280,720,90),
                         ('reference_corner',1280,720,90),
                         ('driver_reference',1280,720,90)]])
    inventory = {'runner.py': NATIVE/'selected_runner.py',
                 'parking_controller.py': NATIVE/'parking_controller.py',
                 'finalize_selected.py': NATIVE/'finalize_selected.py',
                 'measure_red_curb.py': NATIVE/'measure_red_curb.py',
                 'red-curb-road.xodr': NATIVE/'red-curb-road.xodr',
                 'requested-tracks.jsonl': draft/'requested-tracks.jsonl',
                 'assignment-source.json': REPO/'inputs'/ROOT.name/'assignment.json',
                 'case-plan.json': ROOT/'case-plan.json'}
    files = [{'path': name, 'content': path.read_text()}
             for name, path in inventory.items()]
    files += [{'path':'config.json', 'content':json.dumps(cfg,indent=2)+'\n'},
              {'path':'tests/test_selected.py','content':TEST}]
    construction = {'case_id':CASE,'law_id':'LVMC-11-52-030-A',
                    'cell_id':'C150142','actor':'motor_vehicle_driver',
                    'entrypoint':'runner.py','files':files,
                    'status':'draft_selected_cpu',
                    'recording_description':{
                        'channels':[{'name':name,'unit':unit,'sampling_rate_hz':20,
                                     'method':'original Native actor body and four-camera frame join'}
                                    for name,unit in [('ego_pose','structured'),
                                                      ('ego_speed','m/s'),
                                                      ('red_curb_stop_or_park','bool'),
                                                      ('four_source_views','video')]],
                        'limitations':['Red paint, zone occupancy and statutory exceptions require independent source review.']},
                    'original_native_observed':False,'delivery_ready':False,
                    'measurement_plan':{'source':'original Native body and road paint readback',
                                        'finalizer':'measure_red_curb.py','legal_verdict':None},
                    'termination_rules':{'requested_frames':240,'stop_on_error':True}}
    target = ROOT/'selected-primary/reference/construction.json'
    write(target,construction)
    plan=json.loads((ROOT/'case-plan.json').read_text())
    output_mapping={0:('statute_source_context','statute_context','object',
                       'sourced_context',['assignment-source.json']),
                    1:('red_curb_extent','curb_extent','object','sourced_context',
                       ['native-map-readback.json']),
                    2:('red_curb_stop_or_park_observed','red_occupancy','boolean',
                       'measured',['native-raw-actors.jsonl','video_frames.jsonl',
                                   'native-map-readback.json']),
                    8:('mail_exception_source_text','mail_clause_context','text',
                       'sourced_context',['assignment-source.json']),
                    9:('scope_red_occupancy','scope_occupancy','boolean','measured',
                       ['native-raw-actors.jsonl','video_frames.jsonl',
                        'native-map-readback.json'])}
    requirements=[]
    for index,disp in enumerate(plan['requirement_dispositions']):
        if disp['status']=='selected_required' and CASE in disp.get('case_ids',[]):
            key,method,kind_type,kind,inputs=output_mapping[index]
            requirements.append({'disposition_index':index,
                                 'requirement':disp['requirement'],
                                 'source':disp['source'],'output_key':key,
                                 'method':method,'value_type':kind_type,
                                 'kind':kind,'inputs':inputs})
    contract={'format':'worker-measurement-contract','case_id':CASE,
              'requirements':requirements,
              'negative':{'remove':['native-map-readback.json'],
                          'error_contains':'Missing required source: native-map-readback.json'},
              'scope':'Observed red paint occupancy and frozen statute context; no exception or legal verdict'}
    write(ROOT/'selected-primary/reference/selected-measurement-contracts/reference.json',
          contract)
    batch = json.loads((REPO/'batch.json').read_text())
    manifest = {'format':'worker-execution-manifest','assignment_id':ROOT.name,
                'status':'first_primary_offline_in_progress',
                'runtime_manifest_sha256':sha(REPO/batch['runtime']['root']/'SOURCE-MANIFEST.json'),
                'cases':[{'case_id':CASE,'kind':'delivery',
                          'construction':'construction.json',
                          'construction_sha256':sha(target),
                          'candidate_risk':{'status':'physical',
                                            'reason':'Paint, parked body and four views unverified in Native'},
                          'candidates':[],
                          'measurement_contract':'selected-measurement-contracts/reference.json',
                          'measurement_procedure':{'entrypoint':'measure_red_curb.py',
                                                   'output_schema':'c150142-red-curb-observation-v1'}}],
                'original_native_observed':False,'delivery_ready':False}
    mpath=ROOT/'selected-primary/reference/draft-manifest.json'
    write(mpath,manifest)
    return {'case_id':CASE,'construction':str(target),'manifest':str(mpath),
            'construction_sha256':sha(target)}


if __name__=='__main__': print(json.dumps(build(),sort_keys=True))
