"""Build the first exact selected right-pass primary for pinned offline proof."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
NATIVE=ROOT/'native'
CASE=ROOT.name+'__reference'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def camera_spec():
    module=ast.parse((NATIVE/'capture.py').read_text())
    node=next(n for n in module.body if isinstance(n,ast.Assign) and
              any(isinstance(t,ast.Name) and t.id=='CAMERAS' for t in n.targets))
    return ast.literal_eval(node.value)


TEST='''import math
import unittest
from pathlib import Path
import capture
import check
import measure_raw

class ExactPrimary(unittest.TestCase):
    def test_sources_and_four_views(self):
        folder=Path(__file__).resolve().parents[1]
        audit=check.audit()
        self.assertEqual(audit['candidates'],1)
        tested=capture.check_bundle(folder)
        self.assertTrue(tested['source_bound'])
        self.assertEqual(tested['frames'],240)
        self.assertEqual(list(tested['camera_views']),list(measure_raw.VIEWS))

    def test_right_lane_controller(self):
        class Location:
            x=5.0
            y=-1.75
        class Rotation:
            yaw=0.0
        class Transform:
            location=Location()
            rotation=Rotation()
        class Velocity:
            x=0.0
            y=0.0
            z=0.0
        class Vehicle:
            def get_transform(self):return Transform()
            def get_velocity(self):return Velocity()
        class Carla:
            @staticmethod
            def VehicleControl(**values):return values
        right=capture.steer_to(Carla,Vehicle(),20,-5.5,8)
        left=capture.steer_to(Carla,Vehicle(),20,1.0,8)
        self.assertLess(right['steer'],0)
        self.assertGreater(left['steer'],0)
        self.assertGreater(right['throttle'],0)

    def test_surface_gap_from_body(self):
        def body(x,y):
            return [[x+dx,y+dy,1] for dx in (-2.25,2.25)
                    for dy in (-.9,.9)]
        self.assertAlmostEqual(measure_raw.footprint_gap(body(0,-5.5),body(0,-1.75)),1.95)
        self.assertEqual(measure_raw.footprint_gap(body(0,-1.75),body(0,-1.75)),0)

if __name__=='__main__':unittest.main()
'''


def build():
    source=NATIVE/'drafts/reference/primary'
    cfg=json.loads((source/'config.json').read_text())
    plan=json.loads((ROOT/'case-plan.json').read_text())
    case=next(x for x in plan['cases'] if x['case_id']==CASE)
    channel_units={'ego_pose':'structured','ego_speed':'m/s',
                   'right_side_pass_lateral_clearance':'m',
                   'four_source_views':'video'}
    recording={'channels':[{'name':name,'unit':unit,'sampling_rate_hz':20,
        'method':'retained original Native actor, body, velocity and four-camera frame join',
        'time_window':'240 frames','reference_frame':'authored OpenDRIVE coordinates',
        'uncertainty':'50 ms bracket; physical safety and pixel visibility unverified'}
        for name,unit in channel_units.items()],
        'context_inputs':[{'name':'right_pass_map_readback','unit':'structured',
            'method':'source-hashed Native OpenDRIVE map/lane readback'}],
        'limitations':['NRS 484B.210(2) is qualitative; engineering clearance does not determine legal safety.']}
    selected={'case_id':CASE,'target_law_id':'NRS-484B-210-2',
        'target_type':'boundary_probe',
        'rationale':'Controlled right-side-pass lateral-clearance reference; legal safety unresolved.',
        'paired_probe_id':ROOT.name+'__comparison_main',
        'deliberate_differences':['right_side_pass_lateral_clearance'],
        'probe':{'primary_variable':'right_side_pass_lateral_clearance',
                 'comparison_or_standard':'physical clearance sweep, no legal cutoff',
                 'target_value_or_branch':'reference'},
        'variable_assignments':{
            'road_and_actors':{'kind':'world_setup','value':'authored two-lane one-way road, ego and lead Tesla','unit':'structured'},
            'commanded_lateral_apex':{'kind':'controller','value':cfg['requested_lateral_apex_y_m'],'unit':'m'},
            'ego_speed':{'kind':'subject_behavior','value':None,'unit':'m/s'},
            'lead_speed':{'kind':'other_behavior','value':None,'unit':'m/s'}},
        'unresolved_judgment_calls':['conditions permitting such movement in safety'],
        'recording_description':recording}
    cfg.update(selected_case_id=CASE,duration_s=12,required_atoms=[],
               source_packets=[],case=selected,supported_case_ids=[CASE],
               physical_success_claimed=False,
               cameras=[{'name':name,'width':width,'height':height,
                         'pose_strategy':'ego_attached','fov_deg':fov}
                        for name,width,height,fov,_,_,_ in camera_spec()])
    bundle_manifest={'format':'c146314-210-2-selected-source-manifest-v1',
        'road_sha256':sha(NATIVE/'right-pass-road.xodr'),
        'assignment_sha256':sha(REPO/'inputs'/ROOT.name/'assignment.json'),
        'case_plan_sha256':sha(ROOT/'case-plan.json'),
        'entries':[{'case_id':CASE,'candidate_id':'primary',
            'config_sha256':hashlib.sha256((json.dumps(cfg,indent=2,allow_nan=False)+'\n').encode()).hexdigest(),
            'tracks_sha256':sha(source/'requested-tracks.jsonl')}]}
    inventory={
        'runner.py':NATIVE/'portable_runner.py',
        'capture.py':NATIVE/'capture.py',
        'check.py':NATIVE/'portable_check.py',
        'measure_raw.py':NATIVE/'measure_raw.py',
        'prepare_raw.py':NATIVE/'prepare_raw.py',
        'finalize_selected.py':NATIVE/'finalize_selected.py',
        'right-pass-road.xodr':NATIVE/'right-pass-road.xodr',
        'requested-tracks.jsonl':source/'requested-tracks.jsonl',
        'assignment-source.json':REPO/'inputs'/ROOT.name/'assignment.json',
        'case-plan.json':ROOT/'case-plan.json',
        'measurement-contract.json':NATIVE/'measurement-contract.json'}
    files=[{'path':name,'content':path.read_text()} for name,path in inventory.items()]
    files += [{'path':'config.json','content':json.dumps(cfg,indent=2,allow_nan=False)+'\n'},
              {'path':'manifest.json','content':json.dumps(bundle_manifest,indent=2,allow_nan=False)+'\n'},
              {'path':'tests/test_exact.py','content':TEST}]
    construction={'case_id':CASE,'law_id':'NRS-484B-210-2','cell_id':'C146314',
        'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
        'status':'draft_selected_cpu','original_native_observed':False,
        'delivery_ready':False,'recording_description':recording,
        'measurement_plan':{'source':'original actor bodies, velocity, map and four cameras',
            'finalizer':'prepare_raw.py','legal_verdict':None},
        'static_checks':['frozen law/source','240 request frames',
                         'four cameras','right-side steering and body gap'],
        'termination_rules':{'requested_frames':240,'stop_on_error':True},
        'mechanisms':{'construction_status':'authored_cpu_unverified_physical',
                      'road':'right-pass-road.xodr','controller':'capture.py'}}
    path=ROOT/'selected-primary/reference/construction.json'
    write(path,construction)
    batch=json.loads((REPO/'batch.json').read_text())
    runtime=REPO/batch['runtime']['root']/'SOURCE-MANIFEST.json'
    manifest={'format':'worker-execution-manifest','assignment_id':ROOT.name,
        'status':'first_primary_offline_in_progress',
        'runtime_manifest_sha256':sha(runtime),
        'source_branch':'right_side_pass_safety_condition',
        'cases':[{'case_id':CASE,'kind':'delivery',
            'construction':'construction.json','construction_sha256':sha(path),
            'candidate_risk':{'status':'physical',
                'reason':'Native body clearance, motion and all four camera views unverified'},
            'candidates':[],
            'measurement_contract':'selected-measurement-contracts/reference.json',
            'measurement_procedure':{'entrypoint':'finalize_selected.py',
                'output_schema':'c146314-210-2-saved-analysis-v1'}}],
        'original_native_observed':False,'delivery_ready':False}
    target=ROOT/'selected-primary/reference/draft-manifest.json'
    write(target,manifest)
    return {'case_id':CASE,'construction_sha256':sha(path),
            'construction_bytes':path.stat().st_size,'manifest':str(target)}


if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
