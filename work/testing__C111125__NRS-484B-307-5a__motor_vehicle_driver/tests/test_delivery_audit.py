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
from native_capture import apply_phase_sources
from phase_source import load as load_phase_source
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
        phase_names=[];phase_bindings={}
        if occupied:
            phase_dir=attempt/'reviewed-phase-sources/participant-0';phase_dir.mkdir(parents=True)
            phase_text=phase_dir/'phase-source.txt'
            phase_text.write_text('Synthetic reviewed governing phase fixture.\n')
            phase_packet={'format':'c111125-reviewed-participant-phase-v1',
                'review_method':'original-governing-signal-and-entry-rule',
                'reviewer':'CPU fixture reviewer','source_ref':'synthetic fixture',
                'source_file':phase_text.name,'source_sha256':sha(phase_text),
                'participant_actor_id':17,'participant_role':'pedestrian',
                'governing_signal_actor_id':29,'permitted_entry_states':['Green'],
                'entry_rule_source_ref':'synthetic fixture only'}
            phase_path=phase_dir/'review.json';write(phase_path,phase_packet)
            phase_names=[str(phase_path.relative_to(attempt)),str(phase_text.relative_to(attempt))]
            phase_bindings={17:load_phase_source(phase_path,phase_text)}
        write(attempt/'acquisition-provenance.json',
              {'reviewed_arrow_sources':['reviewed-arrow-sources/head-0.json','reviewed-arrow-sources/head-0.mesh'],
               'reviewed_phase_sources':phase_names})
        context={'facing_head_id':7,'stop_line_x_m':-8,
                 'intersection_bounds_m':[-5,-5,8,5],
                 'adjacent_crosswalk_bounds_m':[[-8,-5,-5,5],[8,-5,11,5]],
                 'arrow_review_packet_sha256':sha(packet_path),'arrow_review_asset_sha256':sha(asset)}
        write(attempt/'intersection-context.json',context)
        files={name:[] for name in ('signal-head-history.jsonl','ego-body-history.jsonl',
                                     'participant-history.jsonl','controller-history.jsonl',
                                     'trace.jsonl','video_frames.jsonl')}
        first_arrow_frame=None;exhibition_occupants=None
        prior_inside={};entry_status={}
        xs=(-12,-12,-12,-9,-4) if occupied else (-12,-4)
        for index,x in enumerate(xs):
            frame=100+index;time_s=index/20
            arrow_green=not occupied or index>=2
            aspect={'source_verified':arrow_green,'source_ref':'reviewed-asset-sha256:'+sha(asset)+';packet-sha256:'+sha(packet_path),
                    'head_id':7,'observed_frame':frame,
                    'illuminated_indications':([{'color':'green','shape':'arrow','direction':'straight'}]
                                               if arrow_green else []),
                    'packet_sha256':sha(packet_path),'asset_sha256':sha(asset)}
            common={'frame':frame,'time_s':time_s}
            candidate={'actor_id':7,'state':'Green' if arrow_green else 'Red','blueprint_id':'traffic.traffic_light',
                       'position_m':[0,0,4],'yaw_deg':90}
            files['signal-head-history.jsonl'].append(dict(common,facing_head_id=7,aspect=aspect,
                candidate_lights=[candidate,{'actor_id':29,'state':'Green'}] if occupied else [candidate]))
            files['ego-body-history.jsonl'].append(dict(common,heading_deg=0,
                body_vertices_m=[[x,-.5,0],[x+1,-.5,0],[x+1,.5,0],[x,.5,0]]))
            people=[]
            if occupied:
                y=-10 if index==0 else (0 if index in (1,2) else 8)
                people=[{'id':17,'role':'pedestrian','lawfully_present':None,
                         'lawful_presence_source':None,
                         'body_vertices_m':[[0,y,0],[1,y,0],[1,y+1,0],[0,y+1,0]]}]
                people=apply_phase_sources(people,files['signal-head-history.jsonl'][-1]['candidate_lights'],
                                           context,phase_bindings,prior_inside,entry_status,frame)
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
                      'reviewed-arrow-sources/head-0.mesh',*phase_names)}
        write(attempt/'acquisition.json',acquisition)
        write(attempt/'result.json',{'case_id':case,'setup_confirmed':True,
                                    'behavior_attempted':True,'maneuver_completed':True})
        sealed={name:sha(attempt/name) for name in (*files,'intersection-context.json',
                'acquisition.json','acquisition-provenance.json','result.json',
                'reviewed-arrow-sources/head-0.json','reviewed-arrow-sources/head-0.mesh',*phase_names)}
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

    def test_rejects_live_arrow_state_against_authored_schedule(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt,_,_,_=self.make(Path(temp))
            signals=delivery.rows(attempt/'signal-head-history.jsonl')
            signals[0]['authored_state']='Red'
            with self.assertRaisesRegex(ValueError,'predeclared schedule'):
                delivery.audit_arrow_source(attempt,delivery.read(attempt/'acquisition.json'),
                    delivery.read(attempt/'capture-seal.json'),signals,
                    delivery.read(attempt/'intersection-context.json'))

    def test_occupied_case_rejects_missing_phase_source_after_reseal(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt,processing,decode,case=self.make(Path(temp),occupied=True)
            provenance=attempt/'acquisition-provenance.json'
            value=json.loads(provenance.read_text());value['reviewed_phase_sources']=[]
            write(provenance,value)
            seal=json.loads((attempt/'capture-seal.json').read_text())
            seal['sources']['acquisition-provenance.json']=sha(provenance)
            write(attempt/'capture-seal.json',seal)
            exit_record=json.loads((attempt/'native-exit.json').read_text())
            exit_record['capture_seal_sha256']=sha(attempt/'capture-seal.json')
            write(attempt/'native-exit.json',exit_record)
            owner=json.loads((attempt/'owner-release.json').read_text())
            owner['native_exit_sha256']=sha(attempt/'native-exit.json')
            write(attempt/'owner-release.json',owner)
            with self.assertRaisesRegex(ValueError,'lacks reviewed original participant phase source'):
                delivery.audit(attempt,processing,decode,case,lambda *a,**k:None)

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
