import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from delivery_audit import audit

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value)+'\n')
def body(x,y=0):return [[x,y,0],[x+1,y,0],[x+1,y+1,0],[x,y+1,0]]


class DeliveryAuditTests(unittest.TestCase):
    def fixture(self,root,case=None):
        attempt=root/'attempt';attempt.mkdir()
        case=case or ROOT.name+'__wheelchair_crossing'
        write(attempt/'config.json',{'law_id':'NRS-484B-280-1a','cell_id':'C111301',
              'actor':'motor_vehicle_driver','duration_s':30,'cameras':[]})
        write(attempt/'intersection-context.json',{'route_source':'Native route',
            'manual_wheelchair_asset_source':'Native chair','person_asset_source':'Native person',
            'wheelchair_path_setup':'crossing' if case.endswith('crossing') else 'clear_path',
            'engineering_ttc_brake_s':3.0,'ego_lane_bounds_y_m':[-1.8,1.8],
            'ego_route_geometry':[{'role':role,'x_m':x,'y_m':0,'road_id':1,'lane_id':1}
                    for role,x in [('approach',-30),('crossing',0),('exit',20)]]})
        (attempt/'road.xodr').write_text('diagnostic road')
        history=[];trace=[];frames=[]
        clear=case.endswith('clear_path')
        person_y=5 if clear else 0
        for i,x in enumerate((-5,-3)):
            frame=100+i;time_s=i/20
            pre_x=(-8,-5)[i]
            pre_person={'role':'person_in_manual_wheelchair','source_ref':'Native person','body_vertices_m':body(0,person_y)}
            pre_chair={'kind':'manual_wheelchair','source_ref':'Native chair','body_vertices_m':body(0,person_y)}
            brake=0.0 if clear or i==0 else 1.0
            history.append({'frame':frame,'time_s':time_s,'ego_body_vertices_m':body(x),
               'ego_speed_mps':2,'ego_brake':brake,
               'control_inputs':{'ego_body_vertices_m':body(pre_x),'ego_speed_mps':2,
                    'pedestrian_speed_mps':0 if clear else 1.2,'person':pre_person,
                    'manual_wheelchair':pre_chair},
               'control_command':{'throttle':0.0 if brake else .25,'brake':brake,
                                  'steer':0.0,'legal_due_care_verdict':None},
               'person':{'role':'person_in_manual_wheelchair','source_ref':'Native person','body_vertices_m':body(0,person_y)},
               'manual_wheelchair':{'kind':'manual_wheelchair','source_ref':'Native chair','body_vertices_m':body(0,person_y)},
               'surface_gap_m':((-x-1)**2+16)**.5 if clear else -x-1,'contact_event':False})
            trace.append({'frame':frame,'time_s':time_s,'position_m':[x,0,0]})
            frames.append({'video_frame':i,'carla_frame':frame,'time_s':time_s})
        for name,values in [('encounter-history.jsonl',history),('trace.jsonl',trace),('video_frames.jsonl',frames)]:
            (attempt/name).write_text(''.join(json.dumps(value)+'\n' for value in values))
        write(attempt/'acquisition.json',{name:{'kind':'original_native','sha256':sha(attempt/name)}
              for name in ('encounter-history.jsonl','intersection-context.json')})
        write(attempt/'result.json',{'case_id':case,'setup_confirmed':True,
              'behavior_attempted':True,'maneuver_completed':True})
        names=('encounter-history.jsonl','intersection-context.json','trace.jsonl','video_frames.jsonl',
               'acquisition.json','road.xodr','config.json')
        write(attempt/'capture-seal.json',{'events':['capture_finished','encoders_closed','restoration_verified'],
              'sources':{name:sha(attempt/name) for name in names}})
        write(attempt/'native-exit.json',{'event':'native_exit','capture_seal_sha256':sha(attempt/'capture-seal.json')})
        write(attempt/'owner-release.json',{'event':'owner_released','operator_attested':True,
              'native_exit_sha256':sha(attempt/'native-exit.json')})
        analysis=root/'analysis';analysis.mkdir();(analysis/'raw.mkv').write_bytes(b'diagnostic')
        saved=root/'saved-result.json';write(saved,{'case_id':case})
        processing=root/'processing.json';write(processing,{'format':'worker-saved-processing',
            'passed':True,'recorded_only':True,'result':str(saved),'result_sha256':sha(saved),
            'analysis_directory':str(analysis)})
        decode=root/'decode.json';write(decode,{'diagnostic':True})
        return attempt,processing,decode,case

    def test_accepts_source_bound_complete_delivery_and_rejects_change(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt,processing,decode,case=self.fixture(Path(temp))
            result=audit(attempt,processing,decode,case,media_verify=lambda *a,**k:True)
            self.assertTrue(result['passed'])
            self.assertEqual(result['measurement']['first_brake_frame'],101)
            self.assertTrue(result['controller_audit']['passed'])
            with (attempt/'encounter-history.jsonl').open('a') as stream:stream.write('{}\n')
            with self.assertRaisesRegex(ValueError,'sealed original missing or changed'):
                audit(attempt,processing,decode,case,media_verify=lambda *a,**k:True)

    def test_rejects_resealed_wrong_controller_command(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt,processing,decode,case=self.fixture(Path(temp))
            history=attempt/'encounter-history.jsonl'
            rows=[json.loads(line) for line in history.read_text().splitlines()]
            rows[1]['control_command']['throttle']=.25
            history.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            acquisition=json.loads((attempt/'acquisition.json').read_text())
            acquisition['encounter-history.jsonl']['sha256']=sha(history)
            write(attempt/'acquisition.json',acquisition)
            seal=json.loads((attempt/'capture-seal.json').read_text())
            seal['sources']['encounter-history.jsonl']=sha(history)
            seal['sources']['acquisition.json']=sha(attempt/'acquisition.json')
            write(attempt/'capture-seal.json',seal)
            write(attempt/'native-exit.json',{'event':'native_exit','capture_seal_sha256':sha(attempt/'capture-seal.json')})
            write(attempt/'owner-release.json',{'event':'owner_released','operator_attested':True,
                  'native_exit_sha256':sha(attempt/'native-exit.json')})
            with self.assertRaisesRegex(ValueError,'recorded controller command differs'):
                audit(attempt,processing,decode,case,media_verify=lambda *a,**k:True)


if __name__=='__main__':unittest.main()
