import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runner import control_step,load_scene
from native_capture import apply_phase_sources
from phase_source import load as load_phase_source
from pixel_review import CAMERAS
from pixel_review import audit as audit_pixels
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
        for camera in CAMERAS:
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                            '-f','lavfi','-i','testsrc2=s=64x64:r=20',
                            '-frames:v',str(len(xs)),'-c:v','ffv1',str(attempt/(camera+'.mkv'))],
                           check=True,capture_output=True)
        pixel_packet=folder/'pixel-review.json'
        claims=['sole_straight_arrow_visible']
        if occupied:claims.append('participant_visible')
        write(pixel_packet,{'format':'c111125-original-pixel-review-v1',
                            'reviewer':'CPU synthetic fixture reviewer',
                            'observations':[{'claim':claim,'camera':'overview',
                                             'source_sha256':sha(attempt/'overview.mkv'),
                                             'video_frame':2 if occupied else 1,
                                             'actor_id':7 if claim=='sole_straight_arrow_visible' else 17,
                                             'roi_xywh':[0,0,64,64]}
                                            for claim in claims]})
        acquisition={name:{'kind':'original_native','sha256':sha(attempt/name)} for name in
                     ('signal-head-history.jsonl','ego-body-history.jsonl','participant-history.jsonl',
                      'intersection-context.json','controller-history.jsonl',
                      'reviewed-arrow-sources/head-0.json',
                      'reviewed-arrow-sources/head-0.mesh',*phase_names,
                      *(camera+'.mkv' for camera in CAMERAS))}
        write(attempt/'acquisition.json',acquisition)
        write(attempt/'result.json',{'case_id':case,'setup_confirmed':True,
                                    'behavior_attempted':True,'maneuver_completed':True})
        sealed={name:sha(attempt/name) for name in (*files,'intersection-context.json',
                'acquisition.json','acquisition-provenance.json','result.json',
                'reviewed-arrow-sources/head-0.json','reviewed-arrow-sources/head-0.mesh',*phase_names,
                *(camera+'.mkv' for camera in CAMERAS))}
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
        processed=json.loads(processing.read_text());processed['pixel_review']=str(pixel_packet)
        write(processing,processed)
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

    def test_pixel_review_rejects_stale_camera_and_wrong_claim_frame(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt,processing,decode,case=self.make(Path(temp),occupied=True)
            processed=json.loads(processing.read_text())
            packet_path=Path(processed['pixel_review'])
            packet=json.loads(packet_path.read_text())
            seal=delivery.read(attempt/'capture-seal.json')
            acquisition=delivery.read(attempt/'acquisition.json')
            signals=delivery.rows(attempt/'signal-head-history.jsonl')
            traffic=delivery.rows(attempt/'participant-history.jsonl')
            context=delivery.read(attempt/'intersection-context.json')
            def check():
                return audit_pixels(attempt,packet_path,seal,acquisition,len(signals),True,
                                    signals,traffic,context)
            self.assertEqual(len(check()['observations']),2)
            packet['observations'][0]['source_sha256']='0'*64
            write(packet_path,packet)
            with self.assertRaisesRegex(ValueError,'source hash differs'):
                check()
            packet['observations'][0]['source_sha256']=sha(attempt/'overview.mkv')
            packet['observations'][1]['video_frame']=0
            write(packet_path,packet)
            with self.assertRaisesRegex(ValueError,'lawful occupied frame'):
                check()
            packet['observations'][1]['video_frame']=2
            packet['observations'][0]['video_frame']=1
            write(packet_path,packet)
            with self.assertRaisesRegex(ValueError,'verified frame'):
                check()

    def test_pixel_review_rejects_uniform_decoded_crop(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt,processing,_,_=self.make(Path(temp))
            camera=attempt/'overview.mkv'
            camera.unlink()
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                            '-f','lavfi','-i','color=c=green:s=64x64:r=20',
                            '-frames:v','2','-c:v','ffv1',str(camera)],
                           check=True,capture_output=True)
            seal=delivery.read(attempt/'capture-seal.json')
            acquisition=delivery.read(attempt/'acquisition.json')
            seal['sources'][camera.name]=sha(camera)
            acquisition[camera.name]['sha256']=sha(camera)
            packet_path=Path(delivery.read(processing)['pixel_review'])
            packet=delivery.read(packet_path)
            packet['observations'][0]['source_sha256']=sha(camera)
            write(packet_path,packet)
            with self.assertRaisesRegex(ValueError,'lacks visible contrast'):
                audit_pixels(attempt,packet_path,seal,acquisition,2,False,
                             delivery.rows(attempt/'signal-head-history.jsonl'),
                             delivery.rows(attempt/'participant-history.jsonl'),
                             delivery.read(attempt/'intersection-context.json'))

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
