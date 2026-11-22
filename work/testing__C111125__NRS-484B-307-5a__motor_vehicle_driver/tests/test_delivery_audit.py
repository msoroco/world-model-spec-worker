import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runner import control_step,load_scene
spec=importlib.util.spec_from_file_location('arrow_delivery',ROOT/'delivery_audit.py')
delivery=importlib.util.module_from_spec(spec);spec.loader.exec_module(delivery)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value)+'\n')


class DeliveryAuditTests(unittest.TestCase):
    def make(self,folder,occupied=False):
        attempt=folder/'attempt';attempt.mkdir();analysis=folder/'analysis';analysis.mkdir()
        case=ROOT.name+('__yield_straight' if occupied else '__clear_straight')
        reviewed=attempt/'reviewed-arrow-sources';reviewed.mkdir()
        asset=reviewed/'head-0.mesh';asset.write_bytes(b'CPU fixture original arrow mesh')
        packet={'format':'c111125-reviewed-arrow-asset-v1',
                'review_method':'complete-original-head-indication-inventory',
                'reviewer':'CPU fixture reviewer','installation_source_ref':'CPU fixture installation',
                'asset_type':'original_mesh','asset_sha256':sha(asset),
                'actor_id':7,'blueprint_id':'traffic.traffic_light','faces_ego_approach':True,
                'green_indications':[{'color':'green','shape':'arrow','direction':'straight'}],
                'other_illuminated_on_green':[],'position_m':[0,0,4],'yaw_deg':90}
        packet_path=reviewed/'head-0.json';write(packet_path,packet)
        write(attempt/'acquisition-provenance.json',
              {'reviewed_arrow_sources':['reviewed-arrow-sources/head-0.json','reviewed-arrow-sources/head-0.mesh']})
        context={'facing_head_id':7,'stop_line_x_m':-8,
                 'intersection_bounds_m':[-5,-5,8,5],
                 'adjacent_crosswalk_bounds_m':[[-8,-5,-5,5],[8,-5,11,5]],
                 'arrow_review_packet_sha256':sha(packet_path),'arrow_review_asset_sha256':sha(asset)}
        write(attempt/'intersection-context.json',context)
        files={name:[] for name in ('signal-head-history.jsonl','ego-body-history.jsonl',
                                     'participant-history.jsonl','controller-history.jsonl',
                                     'trace.jsonl','video_frames.jsonl')}
        first_arrow_frame=None;exhibition_occupants=None
        for index,x in enumerate((-12,-4)):
            frame=100+index;time_s=index/20
            aspect={'source_verified':True,'source_ref':'reviewed-asset-sha256:'+sha(asset)+';packet-sha256:'+sha(packet_path),
                    'head_id':7,'observed_frame':frame,
                    'illuminated_indications':[{'color':'green','shape':'arrow','direction':'straight'}],
                    'packet_sha256':sha(packet_path),'asset_sha256':sha(asset)}
            common={'frame':frame,'time_s':time_s}
            candidate={'actor_id':7,'state':'Green','blueprint_id':'traffic.traffic_light',
                       'position_m':[0,0,4],'yaw_deg':90}
            files['signal-head-history.jsonl'].append(dict(common,facing_head_id=7,aspect=aspect,
                                                            candidate_lights=[candidate]))
            files['ego-body-history.jsonl'].append(dict(common,heading_deg=0,
                body_vertices_m=[[x,-.5,0],[x+1,-.5,0],[x+1,.5,0],[x,.5,0]]))
            people=[]
            if occupied and index==0:
                people=[{'id':'walker','role':'pedestrian','lawfully_present':True,
                         'lawful_presence_source':'original phase context',
                         'body_vertices_m':[[0,0,0],[1,0,0],[1,1,0],[0,1,0]]}]
            elif occupied:
                people=[{'id':'walker','role':'pedestrian','lawfully_present':True,
                         'lawful_presence_source':'original phase context',
                         'body_vertices_m':[[0,8,0],[1,8,0],[1,9,0],[0,9,0]]}]
            files['participant-history.jsonl'].append(dict(common,participants=people))
            decision=control_step(load_scene(),files['signal-head-history.jsonl'][-1],people,
                                  files['ego-body-history.jsonl'][-1]['body_vertices_m'],
                                  first_arrow_frame=first_arrow_frame,
                                  exhibition_occupants=exhibition_occupants)
            first_arrow_frame=decision['first_arrow_frame']
            exhibition_occupants=decision['exhibition_occupants']
            files['controller-history.jsonl'].append(dict(common,**decision))
            files['trace.jsonl'].append(common)
            files['video_frames.jsonl'].append({'carla_frame':frame,'time_s':time_s,'video_frame':index})
        for name,values in files.items():
            (attempt/name).write_text(''.join(json.dumps(v)+'\n' for v in values))
        acquisition={name:{'kind':'original_native','sha256':sha(attempt/name)} for name in
                     ('signal-head-history.jsonl','ego-body-history.jsonl','participant-history.jsonl',
                      'intersection-context.json','controller-history.jsonl',
                      'reviewed-arrow-sources/head-0.json',
                      'reviewed-arrow-sources/head-0.mesh')}
        write(attempt/'acquisition.json',acquisition)
        write(attempt/'result.json',{'case_id':case,'setup_confirmed':True,
                                    'behavior_attempted':True,'maneuver_completed':True})
        sealed={name:sha(attempt/name) for name in (*files,'intersection-context.json',
                'acquisition.json','acquisition-provenance.json','result.json',
                'reviewed-arrow-sources/head-0.json','reviewed-arrow-sources/head-0.mesh')}
        write(attempt/'capture-seal.json',{'events':['capture_finished','encoders_closed','restoration_verified'],
                                           'sources':sealed})
        write(attempt/'native-exit.json',{'event':'native_exit','capture_seal_sha256':sha(attempt/'capture-seal.json')})
        write(attempt/'owner-release.json',{'event':'owner_released','operator_attested':True,
                                            'native_exit_sha256':sha(attempt/'native-exit.json')})
        saved=analysis/'result.json';write(saved,{'case_id':case})
        (analysis/'raw.mkv').write_bytes(b'diagnostic video placeholder')
        processing=folder/'processing.json'
        write(processing,{'format':'worker-saved-processing','passed':True,'recorded_only':True,
                          'result':str(saved),'result_sha256':sha(saved),'analysis_directory':str(analysis)})
        decode=folder/'decode.json';write(decode,{'diagnostic':True})
        return attempt,processing,decode,case

    def test_accepts_clear_and_yield_and_rejects_stale_source(self):
        for occupied in (False,True):
            with tempfile.TemporaryDirectory() as temp:
                attempt,processing,decode,case=self.make(Path(temp),occupied)
                audit=lambda *args,**kwargs:None
                self.assertTrue(delivery.audit(attempt,processing,decode,case,audit)['passed'])
                with (attempt/'signal-head-history.jsonl').open('a') as stream:stream.write('{}\n')
                with self.assertRaisesRegex(ValueError,'sealed original'):
                    delivery.audit(attempt,processing,decode,case,audit)

    def test_rejects_wrong_case_and_missing_owner_release(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt,processing,decode,case=self.make(Path(temp))
            with self.assertRaisesRegex(ValueError,'case identity'):
                delivery.audit(attempt,processing,decode,case+'bad',lambda *a,**k:None)
            (attempt/'owner-release.json').unlink()
            with self.assertRaises(FileNotFoundError):
                delivery.audit(attempt,processing,decode,case,lambda *a,**k:None)

    def test_rejects_unreviewed_green_and_changed_live_actor(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt,processing,decode,case=self.make(Path(temp))
            provenance=attempt/'acquisition-provenance.json'
            write(provenance,{'reviewed_arrow_sources':[]})
            seal=json.loads((attempt/'capture-seal.json').read_text())
            seal['sources']['acquisition-provenance.json']=sha(provenance)
            write(attempt/'capture-seal.json',seal)
            exit_record=json.loads((attempt/'native-exit.json').read_text())
            exit_record['capture_seal_sha256']=sha(attempt/'capture-seal.json')
            write(attempt/'native-exit.json',exit_record)
            owner=json.loads((attempt/'owner-release.json').read_text())
            owner['native_exit_sha256']=sha(attempt/'native-exit.json')
            write(attempt/'owner-release.json',owner)
            with self.assertRaisesRegex(ValueError,'packet/asset pair absent'):
                delivery.audit(attempt,processing,decode,case,lambda *a,**k:None)
        with tempfile.TemporaryDirectory() as temp:
            attempt,processing,decode,case=self.make(Path(temp))
            source=attempt/'signal-head-history.jsonl'
            values=[json.loads(line) for line in source.read_text().splitlines()]
            values[1]['candidate_lights'][0]['state']='Red'
            source.write_text(''.join(json.dumps(value)+'\n' for value in values))
            acquisition=json.loads((attempt/'acquisition.json').read_text())
            acquisition[source.name]['sha256']=sha(source)
            write(attempt/'acquisition.json',acquisition)
            seal=json.loads((attempt/'capture-seal.json').read_text())
            seal['sources'][source.name]=sha(source)
            seal['sources']['acquisition.json']=sha(attempt/'acquisition.json')
            write(attempt/'capture-seal.json',seal)
            exit_record=json.loads((attempt/'native-exit.json').read_text())
            exit_record['capture_seal_sha256']=sha(attempt/'capture-seal.json')
            write(attempt/'native-exit.json',exit_record)
            owner=json.loads((attempt/'owner-release.json').read_text())
            owner['native_exit_sha256']=sha(attempt/'native-exit.json')
            write(attempt/'owner-release.json',owner)
            with self.assertRaisesRegex(ValueError,'per-frame arrow claim differs'):
                delivery.audit(attempt,processing,decode,case,lambda *a,**k:None)

    def test_rejects_controller_decision_even_when_resealed(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt,processing,decode,case=self.make(Path(temp))
            source=attempt/'controller-history.jsonl'
            decisions=[json.loads(line) for line in source.read_text().splitlines()]
            decisions[0]['control']['throttle']=0
            source.write_text(''.join(json.dumps(item)+'\n' for item in decisions))
            acquisition=json.loads((attempt/'acquisition.json').read_text())
            acquisition[source.name]['sha256']=sha(source)
            write(attempt/'acquisition.json',acquisition)
            seal=json.loads((attempt/'capture-seal.json').read_text())
            seal['sources'][source.name]=sha(source)
            seal['sources']['acquisition.json']=sha(attempt/'acquisition.json')
            write(attempt/'capture-seal.json',seal)
            exit_record=json.loads((attempt/'native-exit.json').read_text())
            exit_record['capture_seal_sha256']=sha(attempt/'capture-seal.json')
            write(attempt/'native-exit.json',exit_record)
            owner=json.loads((attempt/'owner-release.json').read_text())
            owner['native_exit_sha256']=sha(attempt/'native-exit.json')
            write(attempt/'owner-release.json',owner)
            with self.assertRaisesRegex(ValueError,'controller decision differs'):
                delivery.audit(attempt,processing,decode,case,lambda *a,**k:None)


if __name__=='__main__':unittest.main()
