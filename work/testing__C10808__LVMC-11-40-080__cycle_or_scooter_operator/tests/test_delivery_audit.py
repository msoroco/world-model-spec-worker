"""Synthetic Native-shaped source and rejection checks for the independent audit."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('c10808_delivery_audit',ROOT/'delivery_audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
CASE='testing__C10808__LVMC-11-40-080__cycle_or_scooter_operator__dismount_before_uturn'


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


class DeliveryAuditTests(unittest.TestCase):
    def fixture(self,base,case_id=CASE):
        attempt=base/'attempt';attempt.mkdir()
        stage=base/'saved';stage.mkdir()
        write(attempt/'acquisition-provenance.json',{
            'provenance_kind':'native','diagnostic_fixture':False})
        write(attempt/'config.json',{'selected_case_id':case_id,
            'law_id':'LVMC-11-40-080','cell_id':'C10808',
            'actor':'cycle_or_scooter_operator','duration_s':30,'rate_hz':20})
        (attempt/'sign-authorization-source').write_text('mock authorization source')
        write(attempt/'sign-inventory.json',{'message':'NO U TURN',
            'erected':True,'sign_actor_id':3,
            'sign_blueprint':'static.prop.sign.no_uturn',
            'bicycle_blueprint':'static.prop.bicycle',
            'operator_blueprint':'walker.pedestrian.test',
            'fixed_scene_sha256':'fixture-scene-hash',
            'camera_contract_sha256':'fixture-camera-hash',
            'map_context':{'road_id':1,'junction_id':2},
            'authorization_source_sha256':audit.sha(attempt/'sign-authorization-source')})
        (attempt/'road.xodr').write_text('<OpenDRIVE/>')
        for name in audit.VIDEOS:(attempt/name).write_text('synthetic media test bytes')
        dismounted=case_id.endswith('__dismount_before_uturn')
        phases=(['mounted_approach','dismount_hold','afoot_reversal','turn_complete']
                if dismounted else ['mounted_approach','mounted_reversal',
                                    'mounted_reversal','turn_complete'])
        events=[];contexts=[];trace=[];mapping=[]
        for i,phase in enumerate(phases):
            x=2 if dismounted and i>=2 else 0
            def body(value):return [[value-.2,-.2,0.],[value-.2,.2,0.],
                                    [value+.2,-.2,0.],[value+.2,.2,0.]]
            events.append({'frame':100+i,'time_s':(i+1)/20,
                'phase':phase,'operator_id':1,'bicycle_id':2,'sign_id':3,
                'operator_body_vertices_m':body(x),
                'bicycle_body_vertices_m':body(0)})
            contexts.append({'frame':100+i,'time_s':(i+1)/20,
                'operator_id':1,'operator_position_m':[float(x),0.,0.],
                'nearest_road_projection':None,
                'nearby_crosswalk_vertices_m':[],
                'nearby_control_devices':[],
                'pedestrian_regulation_assessment':'unresolved'})
            trace.append({'frame':100+i,'time_s':(i+1)/20,
                          'position_m':[x,0.,0.]})
            mapping.append({'video_frame':i,'carla_frame':100+i,
                            'time_s':(i+1)/20})
        for name,items in [('phase-events.jsonl',events),
                           ('pedestrian-context.jsonl',contexts),('trace.jsonl',trace),
                           ('video_frames.jsonl',mapping)]:
            (attempt/name).write_text(''.join(json.dumps(item)+'\n' for item in items))
        write(attempt/'acquisition.json',{name:{'kind':'original_native',
            'sha256':audit.sha(attempt/name)} for name in audit.ORIGINAL})
        write(attempt/'capture-seal.json',{'provenance_kind':'native',
            'events':['capture_finished','encoders_closed','restoration_verified'],
            'restoration':{'restored':True},
            'sources':{name:audit.sha(attempt/name) for name in audit.ORIGINAL}})
        write(attempt/'native-exit.json',{'event':'native_exit',
            'capture_seal_sha256':audit.sha(attempt/'capture-seal.json')})
        write(attempt/'owner-release.json',{'event':'owner_released',
            'operator_attested':True,
            'native_exit_sha256':audit.sha(attempt/'native-exit.json')})
        result=stage/'result.json'
        write(result,{'case_id':case_id,'setup_confirmed':True,
            'behavior_attempted':True,'maneuver_completed':True,
            'diagnostic_fixture':False})
        (stage/'raw.mkv').write_text('synthetic media test bytes')
        processing=base/'processing.json'
        write(processing,{'format':'worker-saved-processing','passed':True,
            'recorded_only':True,'case_id':case_id,'result':str(result),
            'result_sha256':audit.sha(result),'analysis_directory':str(stage)})
        decode=base/'source-decode.json';write(decode,{'synthetic':True})
        return attempt,processing,decode,result

    def run_audit(self,attempt,processing,decode):
        return audit.audit(attempt,processing,decode,CASE,
            media_verify=lambda *args,**kwargs: True)

    def test_source_join_and_negative_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt,processing,decode,result=self.fixture(Path(directory))
            self.assertTrue(self.run_audit(attempt,processing,decode)['passed'])
            (attempt/'sign-authorization-source').write_text('changed source')
            with self.assertRaisesRegex(ValueError,'sealed original missing or changed'):
                self.run_audit(attempt,processing,decode)

    def test_incomplete_physical_result_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt,processing,decode,result=self.fixture(Path(directory))
            value=audit.read(result);value['maneuver_completed']=False;write(result,value)
            saved=audit.read(processing);saved['result_sha256']=audit.sha(result)
            write(processing,saved)
            with self.assertRaisesRegex(ValueError,'physical completion remains unconfirmed'):
                self.run_audit(attempt,processing,decode)

    def test_diagnostic_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt,processing,decode,_=self.fixture(Path(directory))
            write(attempt/'fixture-provenance.json',{'diagnostic_fixture':True})
            with self.assertRaisesRegex(ValueError,'diagnostic fixture'):
                self.run_audit(attempt,processing,decode)


if __name__=='__main__':unittest.main()
