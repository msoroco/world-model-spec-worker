import json
import hashlib
import tempfile
import unittest
from pathlib import Path
import sys
import subprocess
import os
import shutil
import base64
import zlib
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from school_bus_response import measure, audit_motion_comparison, audit_red_pixel_sources, audit_pupil_service_source, audit_first_case_attempt, finalize_first_case
from school_bus_controller import BRANCHES, target, apply, motion_readback, spawn_meeting_scene, select_meeting_waypoints
from school_bus_camera import CAMERAS, LosslessSourceSink, SchoolBusCameraCapture
from school_bus_native import CASE_ID, check_plan, check_scene, close_all, spawn_pupil_service, pupil_readback


def corners(x):
    return [[x-1,-.5],[x+1,-.5],[x+1,.5],[x-1,.5]]


class SourceResponse(unittest.TestCase):
    def test_returned_restart_diagnostic_has_source_bound_temporal_change(self):
        package = Path(__file__).resolve().parents[1]
        spec_path = package/'school-bus-restart-diagnostic.json'
        recipe = json.loads((package/'school-bus-restart-recipe.json').read_text())
        self.assertEqual(recipe['generator']['sha256'], hashlib.sha256(spec_path.read_bytes()).hexdigest())
        spec = json.loads(spec_path.read_text())
        files = spec['files']
        inventory = json.loads(files['native-acquisition-inventory.json'])
        self.assertTrue(inventory['case_id'].endswith('__meeting_restart_before_red_ceases'))
        for name, expected in inventory['source_sha256'].items():
            if name in files:
                self.assertEqual(hashlib.sha256(files[name].encode()).hexdigest(), expected)
        def rows(name):
            return [json.loads(line) for line in files[name].splitlines()]
        motion, signal, trace = (rows(name) for name in
                                 ('motion_original.jsonl', 'signal_command_original.jsonl', 'trace.jsonl'))
        self.assertEqual(len(motion), 160)
        self.assertEqual([r['frame'] for r in motion], inventory['frames'])
        self.assertEqual([(r['frame'], r['time_s']) for r in motion],
                         [(r['frame'], r['time_s']) for r in signal])
        self.assertEqual([(r['frame'], r['time_s']) for r in motion],
                         [(r['frame'], r['time_s']) for r in trace])
        self.assertEqual(signal[79]['red_signal_commanded'], True)
        self.assertEqual(signal[119]['red_signal_commanded'], True)
        self.assertEqual(signal[120]['red_signal_commanded'], False)
        self.assertEqual(motion[79]['subject_speed_mps'], 0)
        self.assertEqual(motion[80]['subject_speed_mps'], 2)
        self.assertEqual(motion[119]['subject_speed_mps'], 2)
        self.assertEqual(motion[80]['subject_corners'][0][0],
                         trace[80]['position_m'][0] - 1)
        self.assertEqual(spec['graphs'][80]['attributes']['observed_evidence']
                         ['rgb_sensors'][0]['position_m'], trace[80]['position_m'])

    def test_returned_first_case_proof_bundle(self):
        package = Path(__file__).resolve().parents[1]
        proof = json.loads((package/'first-case-proof-bundle.json').read_text())
        self.assertEqual(proof['format'], 'worker-first-case-cpu-proof-bundle')
        self.assertEqual(proof['assignment_id'], package.name)
        for field, name in (('construction_sha256','construction.json'),
                            ('execution_manifest_sha256','execution-manifest.json'),
                            ('fixture_recipe_sha256','school-bus-recipe.json'),
                            ('diagnostic_spec_sha256','school-bus-diagnostic.json'),
                            ('measurement_contract_sha256','measurement-contract.json')):
            self.assertEqual(proof[field], hashlib.sha256((package/name).read_bytes()).hexdigest())
        decoded = {}
        for name, item in proof['artifacts'].items():
            raw = zlib.decompress(base64.b64decode(item['zlib_base64']))
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()),
                             (item['bytes'], item['sha256']))
            decoded[name] = raw
        compatibility = json.loads(decoded['compatibility.json'])
        positive = json.loads(decoded['saved-positive-processing.json'])
        missing = json.loads(decoded['saved-missing-processing.json'])
        self.assertTrue(compatibility['passed'])
        self.assertTrue(positive['passed'] and positive['originals_preserved'])
        self.assertFalse(positive['missing_evidence'])
        self.assertTrue(missing['passed'] and missing['missing_evidence'] and
                        missing['originals_preserved'])
        self.assertFalse(proof['checks']['actual_native_capture'])
        self.assertFalse(proof['checks']['physical_acceptance_claimed'])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.context={'bus_id':'bus','subject_id':'car','approach':'meeting',
                      'bus_stopped':True,'pupil_stop_purpose':True,'signs_equipped':True,
                      'divided_other_roadway':False,'traffic_officer_control':False}
        self.signal=[];self.motion=[]
        for i,(active,phase,speed,x) in enumerate(zip(
            (False,True,True,True,False,False),
            (False,True,False,True,False,False),
            (5,5,0,0,2,3),
            (-6,-5,-4,-3,-2,4))):
            self.signal.append({'frame':100+i,'time_s':i*.05,'bus_id':'bus',
                'red_signal_operating':active,'red_phase_on':phase,
                'front_red_visible':phase,'rear_red_visible':phase})
            self.motion.append({'frame':100+i,'time_s':i*.05,'bus_id':'bus','subject_id':'car',
                'subject_speed_mps':speed,'subject_corners':corners(x),
                'bus_corners':corners(0),'travel_tangent_xy':[1,0]})
    def write(self):
        paths=[]
        for name,value in (('context',self.context),('signal',self.signal),('motion',self.motion)):
            path=self.root/(name+'.json');path.write_text(json.dumps(value)+'\n');paths.append(path)
        return paths
    def result(self):
        return measure(*self.write())
    def test_meeting_holds_through_red_and_passes_after_cessation(self):
        result=self.result()
        self.assertEqual((result['red_onset_frame'],result['red_cessation_frame']),(101,104))
        self.assertEqual((result['first_stop_frame'],result['first_full_body_pass_frame']),(102,105))
        self.assertTrue(result['held_stop_until_cessation'])
        self.assertIsNone(result['premature_restart_frame'])
        self.assertFalse(result['physical_acceptance_claimed'])
        self.assertIsNone(result['legal_conclusion'])
        self.assertEqual(set(result['source_sha256']),{'context','signal','motion'})
    def test_overtaking_opposite_tangent_and_premature_restart(self):
        self.context['approach']='overtaking'
        for row in self.motion:
            row['travel_tangent_xy']=[-1,0]
            row['subject_corners']=corners(-row['subject_corners'][0][0]-1)
        self.motion[3]['subject_speed_mps']=2
        result=self.result()
        self.assertEqual(result['premature_restart_frame'],103)
        self.assertFalse(result['held_stop_until_cessation'])
        self.assertEqual(result['first_full_body_pass_frame'],105)
    def test_active_red_pass_and_missing_sources(self):
        self.motion[3]['subject_corners']=corners(4)
        self.assertEqual(self.result()['first_full_body_pass_frame'],103)
        paths=self.write();paths[1].unlink()
        with self.assertRaisesRegex(ValueError,'Missing original'):
            measure(*paths)
    def test_rejects_signal_and_frame_contradictions(self):
        self.signal[3]['rear_red_visible']=False
        with self.assertRaisesRegex(ValueError,'front and rear'):self.result()
        self.signal[3]['rear_red_visible']=True
        self.signal[2]['red_phase_on']=True
        self.signal[2]['front_red_visible']=True
        self.signal[2]['rear_red_visible']=True
        with self.assertRaisesRegex(ValueError,'alternation'):self.result()
        self.signal[2]['red_phase_on']=False
        self.motion[2]['time_s']=.105
        with self.assertRaisesRegex(ValueError,'frames differ'):self.result()
        self.motion[2]['time_s']=.1
        self.motion[2]['subject_corners']=[[0,0]]
        with self.assertRaisesRegex(ValueError,'body corners'):self.result()

    def test_original_front_rear_pixel_audit_decodes_and_rejects_missing_or_dark_source(self):
        width,height=8,4
        frame_map=self.root/'video_frames.jsonl'
        commands=self.root/'signal_command_original.jsonl'
        phases=(False,True,False,True,False,False)
        frame_map.write_text(''.join(json.dumps({'video_frame':i,'carla_frame':100+i,
                                                'native_frame':100+i,'time_s':i*.05})+'\n'
                                     for i in range(len(phases))))
        commands.write_text(''.join(json.dumps({'frame':100+i,'time_s':i*.05,
                                                'red_signal_commanded':i in (1,2,3),
                                                'red_phase_commanded':phase})+'\n'
                                    for i,phase in enumerate(phases)))
        def video(path,lit):
            frames=[]
            for phase in phases:
                frame=bytearray(width*height*3)
                if phase and lit:
                    for y in (1,2):
                        for x in (1,2,3,4):
                            frame[3*(y*width+x)]=255
                frames.append(frame)
            subprocess.run(['ffmpeg','-nostdin','-loglevel','error','-y','-f','rawvideo',
                            '-pix_fmt','rgb24','-s',f'{width}x{height}','-r','20',
                            '-i','pipe:0','-an','-c:v','ffv1',str(path)],
                           input=b''.join(frames),check=True)
        front=self.root/'reference_corner.mkv';rear=self.root/'driver_reference.mkv'
        video(front,True);video(rear,True)
        proof=audit_red_pixel_sources(frame_map,commands,front,rear,[1,1,5,3],[1,1,5,3])
        self.assertEqual(len(proof['frames']),6)
        self.assertEqual(proof['frames'][1]['front_red_pixel_count'],8)
        self.assertEqual(proof['frames'][1]['video_frame'],1)
        self.assertFalse(proof['front_rear_red_visibility_verified'])
        self.assertFalse(proof['roi_lamp_identity_reviewed'])
        output=self.root/'pixel-audit.json'
        script=Path(__file__).resolve().parents[1]/'school_bus_response.py'
        subprocess.run([sys.executable,str(script),'--frame-map',str(frame_map),
                        '--command',str(commands),'--front-video',str(front),
                        '--rear-video',str(rear),'--front-roi','[1,1,5,3]',
                        '--rear-roi','[1,1,5,3]','--output',str(output)],check=True)
        self.assertEqual(json.loads(output.read_text())['source_sha256'],proof['source_sha256'])
        video(rear,False)
        with self.assertRaisesRegex(ValueError,'disagree'):
            audit_red_pixel_sources(frame_map,commands,front,rear,[1,1,5,3],[1,1,5,3])
        rear.unlink()
        with self.assertRaisesRegex(ValueError,'Missing original school-bus camera'):
            audit_red_pixel_sources(frame_map,commands,front,rear,[1,1,5,3],[1,1,5,3])
        records=[json.loads(line) for line in frame_map.read_text().splitlines()]
        records[2]['native_frame']=999
        frame_map.write_text(''.join(json.dumps(row)+'\n' for row in records))
        with self.assertRaisesRegex(ValueError,'canonical frame map identity'):
            audit_red_pixel_sources(frame_map,commands,front,rear,[1,1,5,3],[1,1,5,3])

    def test_original_pupil_service_motion_and_missing_movement_rejection(self):
        motion_path=self.root/'motion_original.jsonl'
        pupil_path=self.root/'pupil_original.jsonl'
        for row in self.motion:row['bus_speed_mps']=0.0
        motion_path.write_text(''.join(json.dumps(row)+'\n' for row in self.motion))
        distances=(4.0,3.4,2.8,2.2,1.6,1.0)
        pupil=[{'frame':row['frame'],'time_s':row['time_s'],
                'bus_id':'bus','pupil_id':'walker','requested_purpose':'receiving',
                'pupil_speed_mps':1.2,'pupil_distance_to_bus_m':distance}
               for row,distance in zip(self.motion,distances)]
        pupil_path.write_text(''.join(json.dumps(row)+'\n' for row in pupil))
        proof=audit_pupil_service_source(pupil_path,motion_path,'receiving')
        self.assertEqual(proof['distance_change_m'],3.0)
        self.assertFalse(proof['pupil_service_verified'])
        output=self.root/'pupil-audit.json'
        script=Path(__file__).resolve().parents[1]/'school_bus_response.py'
        subprocess.run([sys.executable,str(script),'--pupil-original',str(pupil_path),
                        '--motion',str(motion_path),'--pupil-purpose','receiving',
                        '--output',str(output)],check=True)
        self.assertEqual(json.loads(output.read_text())['source_sha256'],proof['source_sha256'])
        for row in pupil:row['pupil_distance_to_bus_m']=4.0
        pupil_path.write_text(''.join(json.dumps(row)+'\n' for row in pupil))
        with self.assertRaisesRegex(ValueError,'movement not observed'):
            audit_pupil_service_source(pupil_path,motion_path,'receiving')
        for row,distance in zip(pupil,distances):
            row['requested_purpose']='discharging'
            row['pupil_distance_to_bus_m']=5.0-distance
        pupil_path.write_text(''.join(json.dumps(row)+'\n' for row in pupil))
        self.assertEqual(audit_pupil_service_source(pupil_path,motion_path,'discharging')
                         ['distance_change_m'],3.0)
        self.motion[2]['bus_speed_mps']=.5
        motion_path.write_text(''.join(json.dumps(row)+'\n' for row in self.motion))
        with self.assertRaisesRegex(ValueError,'bus moved'):
            audit_pupil_service_source(pupil_path,motion_path,'discharging')

    def test_whole_first_case_attempt_reopens_inventory_and_rejects_mutation(self):
        attempt=self.root/'attempt';attempt.mkdir()
        phases=(False,True,False,True,False,False)
        frames=tuple(100+i for i in range(6))
        def rows(name,items):
            (attempt/name).write_text(''.join(json.dumps(item)+'\n' for item in items))
        rows('video_frames.jsonl',[{'video_frame':i,'carla_frame':f,
                                   'native_frame':f,'time_s':i*.05}
                                  for i,f in enumerate(frames)])
        rows('signal_command_original.jsonl',[{
            'frame':f,'time_s':i*.05,'red_signal_commanded':i in (1,2,3),
            'red_phase_commanded':phases[i]} for i,f in enumerate(frames)])
        for row in self.motion:row['bus_speed_mps']=0.0
        rows('motion_original.jsonl',self.motion)
        rows('pupil_original.jsonl',[{
            'frame':f,'time_s':i*.05,'bus_id':'bus','pupil_id':'walker',
            'requested_purpose':'receiving','pupil_speed_mps':1.2,
            'pupil_distance_to_bus_m':4-i*.6} for i,f in enumerate(frames)])
        rows('trace.jsonl',[{'frame':f,'time_s':i*.05} for i,f in enumerate(frames)])
        (attempt/'road.xodr').write_text('<OpenDRIVE/>\n')
        width,height=8,4
        for name in ('overview','approach','reference_corner','driver_reference'):
            data=[]
            for phase in phases:
                pixels=bytearray(width*height*3)
                if phase and name in ('reference_corner','driver_reference'):
                    for y in (1,2):
                        for x in (1,2,3,4):pixels[3*(y*width+x)]=255
                data.append(pixels)
            subprocess.run(['ffmpeg','-nostdin','-loglevel','error','-y','-f','rawvideo',
                            '-pix_fmt','rgb24','-s',f'{width}x{height}','-r','20',
                            '-i','pipe:0','-an','-c:v','ffv1',str(attempt/(name+'.mkv'))],
                           input=b''.join(data),check=True)
        required=('motion_original.jsonl','pupil_original.jsonl','signal_command_original.jsonl',
                  'video_frames.jsonl','trace.jsonl','road.xodr','overview.mkv','approach.mkv',
                  'reference_corner.mkv','driver_reference.mkv')
        inventory={'case_id':CASE_ID,'frames':list(frames),'source_sha256':{
            name:hashlib.sha256((attempt/name).read_bytes()).hexdigest() for name in required}}
        (attempt/'native-acquisition-inventory.json').write_text(json.dumps(inventory)+'\n')
        proof=audit_first_case_attempt(attempt,[1,1,5,3],[1,1,5,3],'receiving')
        self.assertEqual(len(proof['red_pixels']['frames']),6)
        self.assertEqual(proof['pupil_motion']['distance_change_m'],3.0)
        self.assertFalse(proof['physical_acceptance_claimed'])
        output=self.root/'whole-attempt-audit.json'
        script=Path(__file__).resolve().parents[1]/'school_bus_response.py'
        subprocess.run([sys.executable,str(script),'--attempt',str(attempt),
                        '--front-roi','[1,1,5,3]','--rear-roi','[1,1,5,3]',
                        '--pupil-purpose','receiving','--output',str(output)],check=True)
        self.assertEqual(json.loads(output.read_text())['inventory_sha256'],
                         proof['inventory_sha256'])
        (attempt/'config.json').write_text(json.dumps({
            'selected_case_id':CASE_ID,'law_id':'NRS-484B-353-1',
            'cell_id':'C230281','actor':'motor_vehicle_driver',
            'case':{'recording_description':json.loads((Path(__file__).resolve().parents[1]
                    /'config.json').read_text())['case']['recording_description']},
            'school_bus_lamp_review':{'front_roi':[1,1,5,3],
                                      'rear_roi':[1,1,5,3],
                                      'pupil_purpose':'receiving'}})+'\n')
        env=os.environ.copy()
        env['PYTHONPATH']=str(Path(__file__).resolve().parents[3]/'runtime'/'scenario_pipeline')
        saved=self.root/'saved-analysis.json'
        subprocess.run([sys.executable,str(script),'--attempt',str(attempt),
                        '--output',str(saved)],env=env,check=True)
        native=json.loads((attempt/'result.json').read_text())
        self.assertEqual(native['case_id'],CASE_ID)
        self.assertEqual(native['video_references'],[
            'overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'])
        self.assertFalse(native['setup_confirmed'])
        self.assertFalse(native['physical_acceptance_claimed'])
        self.assertEqual(native['realized_observables']['subject_speed_mps']['value'],0.0)
        self.assertTrue(native['target_checks'][0]['matched'])
        self.assertFalse(native['target_checks'][0]['physical_cause_confirmed'])
        response=native['measured_values']['stop_response_candidate']
        self.assertEqual((response['red_onset_frame'],response['red_cessation_frame']),
                         (101,104))
        self.assertTrue(response['held_stop_until_cessation_candidate'])
        self.assertFalse(response['passed_during_red_candidate'])
        self.assertEqual(response['first_full_body_pass_frame'],105)
        self.assertEqual(json.loads(saved.read_text())['case_id'],CASE_ID)
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]/'runtime'))
        from scenario_pipeline.worker_exchange.measurement_contract import validate, verify_report
        package=Path(__file__).resolve().parents[1]
        contract=json.loads((package/'measurement-contract.json').read_text())
        dispositions=json.loads((package/'case-plan.json').read_text())['requirement_dispositions']
        self.assertEqual(len(validate(contract,dispositions,script.read_text(),case_id=CASE_ID)),2)
        self.assertEqual(len(verify_report(contract,json.loads(saved.read_text()),attempt)),2)
        from delivery_audit import audit as independent_audit, _join_timeline
        accepted=independent_audit(attempt,saved,package/'measurement-contract.json')
        self.assertTrue(accepted['software_source_join_passed'])
        self.assertFalse(accepted['physical_acceptance_claimed'])
        self.assertEqual(accepted['frame_count'],6)
        self.assertEqual(set(accepted['source_decode']),{
            'overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'})
        self.assertTrue(all(row['frames']==6 and row['dimensions']==[8,4]
                            for row in accepted['source_decode'].values()))
        frame_map=(attempt/'video_frames.jsonl')
        original_map=frame_map.read_bytes()
        altered=[json.loads(line) for line in original_map.splitlines()]
        altered[2]['native_frame']+=1
        frame_map.write_text(''.join(json.dumps(row)+'\n' for row in altered))
        with self.assertRaisesRegex(ValueError,'canonical frame map differs'):
            _join_timeline(attempt,inventory)
        frame_map.write_bytes(original_map)
        pupil=(attempt/'pupil_original.jsonl').read_bytes()
        (attempt/'pupil_original.jsonl').unlink()
        with self.assertRaisesRegex(ValueError,'Missing required source: pupil_original.jsonl'):
            finalize_first_case(attempt)
        with self.assertRaisesRegex(ValueError,'Missing required source: pupil_original.jsonl'):
            independent_audit(attempt,saved,package/'measurement-contract.json')
        (attempt/'pupil_original.jsonl').write_bytes(pupil)
        (attempt/'road.xodr').write_text('<OpenDRIVE><road/></OpenDRIVE>\n')
        with self.assertRaisesRegex(ValueError,'source hash differs: road.xodr'):
            audit_first_case_attempt(attempt,[1,1,5,3],[1,1,5,3],'receiving')
        with self.assertRaisesRegex(ValueError,'source hash differs: road.xodr'):
            finalize_first_case(attempt)
        (attempt/'road.xodr').write_text('<OpenDRIVE/>\n')
        lamp=attempt/'lamp_state_original.jsonl'
        lamp.write_text(''.join(json.dumps({'frame':f,'time_s':i*.05,
            'source_kind':'synthetic_lamp_command_fixture','diagnostic_fixture':True,
            'front_red_commanded':phases[i],'rear_red_commanded':phases[i]})+'\n'
            for i,f in enumerate(frames)))
        (attempt/'fixture-provenance.json').write_text(json.dumps({'diagnostic_fixture':True})+'\n')
        dark=bytes(width*height*3*len(frames))
        subprocess.run(['ffmpeg','-nostdin','-loglevel','error','-y','-f','rawvideo',
                        '-pix_fmt','rgb24','-s',f'{width}x{height}','-r','20',
                        '-i','pipe:0','-an','-c:v','ffv1',str(attempt/'driver_reference.mkv')],
                       input=dark,check=True)
        inventory['source_sha256']['driver_reference.mkv']=hashlib.sha256(
            (attempt/'driver_reference.mkv').read_bytes()).hexdigest()
        (attempt/'native-acquisition-inventory.json').write_text(json.dumps(inventory)+'\n')
        diagnostic=audit_first_case_attempt(attempt,[1,1,5,3],[1,1,5,3],'receiving')
        self.assertEqual(diagnostic['red_pixels']['pixel_evidence_status'],'unverified')
        self.assertIsNone(diagnostic['red_pixels']['frames'][1]['front_red_pixel_count'])
        self.assertFalse(diagnostic['red_pixels']['front_rear_red_visibility_verified'])
        shutil.rmtree(attempt/'channels')
        shutil.rmtree(attempt/'contexts')
        diagnostic_report, diagnostic_native = finalize_first_case(attempt)
        saved.write_text(json.dumps(diagnostic_report)+'\n')
        (attempt/'result.json').write_text(json.dumps(diagnostic_native)+'\n')
        self.assertTrue(independent_audit(attempt,saved,package/'measurement-contract.json')
                        ['software_source_join_passed'])
        packet = lamp.read_text()
        lamp.write_text(packet.replace('"front_red_commanded": true',
                                       '"front_red_commanded": false',1))
        with self.assertRaisesRegex(ValueError,'source hash differs|provenance differs'):
            independent_audit(attempt,saved,package/'measurement-contract.json')
        lamp.write_text(packet)
        (attempt/'fixture-provenance.json').unlink()
        with self.assertRaisesRegex(ValueError,'red pixels disagree'):
            audit_first_case_attempt(attempt,[1,1,5,3],[1,1,5,3],'receiving')
        (attempt/'fixture-provenance.json').write_text(json.dumps({'diagnostic_fixture':True})+'\n')
        lamp.unlink()
        with self.assertRaisesRegex(ValueError,'Missing original school-bus source'):
            audit_first_case_attempt(attempt,[1,1,5,3],[1,1,5,3],'receiving')

    def test_all_selected_controller_branches_and_actual_apply_call(self):
        self.assertEqual(len(BRANCHES),8)
        class Vehicle:
            applied=None
            def apply_control(self, control):self.applied=control
        vehicle=Vehicle()
        for branch in BRANCHES:
            before=target(branch,red_signal_operating=True,stop_observed=False)
            after=target(branch,red_signal_operating=True,stop_observed=True)
            if branch=='meeting_restart_before_red_ceases':
                self.assertEqual((before['target_speed_mps'],after['target_speed_mps']),(0,5))
            elif branch in ('meeting_stop','overtaking_stop','meeting_resume_after_red_ceases'):
                self.assertEqual(before['target_speed_mps'],0)
            else:
                self.assertEqual(before['target_speed_mps'],5)
            self.assertIsNone(before['legal_conclusion'])
            control=apply(vehicle,dict,before,speed_mps=5)
            self.assertEqual(vehicle.applied,control)
            if before['target_speed_mps']==0:self.assertGreater(control['brake'],0)
            self.assertEqual(target(branch,red_signal_operating=False,stop_observed=True)['target_speed_mps'],5)
        with self.assertRaisesRegex(ValueError,'Unknown school-bus branch'):
            target('invented',red_signal_operating=True,stop_observed=False)

    def test_independent_motion_comparisons_and_fixed_source_rejection(self):
        baseline=self.write()
        variant_dir=self.root/'variant';variant_dir.mkdir()
        variant=[variant_dir/p.name for p in baseline]
        for source,destination in zip(baseline,variant):destination.write_bytes(source.read_bytes())
        restart=json.loads(variant[2].read_text())
        restart[3]['subject_speed_mps']=2
        variant[2].write_text(json.dumps(restart)+'\n')
        proof=audit_motion_comparison(baseline,variant,'premature_restart')
        self.assertEqual(proof['variant']['premature_restart_frame'],103)
        self.assertFalse(proof['physical_acceptance_claimed'])
        self.assertIsNone(proof['legal_conclusion'])
        with self.assertRaisesRegex(ValueError,'lacks passage during red'):
            audit_motion_comparison(baseline,variant,'pass_during_red')
        restart[3]['subject_corners']=corners(4)
        variant[2].write_text(json.dumps(restart)+'\n')
        self.assertEqual(audit_motion_comparison(baseline,variant,'pass_during_red')
                         ['variant']['first_full_body_pass_frame'],103)
        with self.assertRaisesRegex(ValueError,'lacks isolated early restart'):
            audit_motion_comparison(baseline,variant,'premature_restart')
        changed=json.loads(variant[1].read_text())
        changed[3]['red_phase_on']=False
        variant[1].write_text(json.dumps(changed)+'\n')
        with self.assertRaisesRegex(ValueError,'changed fixed original'):
            audit_motion_comparison(baseline,variant,'pass_during_red')
        variant[1].unlink()
        with self.assertRaisesRegex(ValueError,'Missing original'):
            audit_motion_comparison(baseline,variant,'pass_during_red')

    def test_native_actor_motion_readback_and_opposite_tangent(self):
        class Vertex:
            def __init__(self,x,y,z):self.x=x;self.y=y;self.z=z
        class Bounds:
            def __init__(self,x):self.x=x
            def get_world_vertices(self,transform):
                return [Vertex(self.x+dx,dy,z) for z in (0,2)
                        for dx,dy in ((-1,-.5),(1,-.5),(1,.5),(-1,.5))]
        class Actor:
            def __init__(self,ident,x,speed=0):
                self.id=ident;self.bounding_box=Bounds(x);self.speed=speed
            def get_transform(self):return object()
            def get_velocity(self):return Vertex(self.speed,0,0)
        subject,bus=Actor('car',-5,2),Actor('bus',0)
        row=motion_readback(subject,bus,[1,0],100,0.0)
        self.assertEqual((row['subject_id'],row['bus_id'],row['subject_speed_mps']),('car','bus',2))
        self.assertEqual(len(row['subject_corners']),4)
        self.assertEqual(len(row['bus_corners']),4)
        self.assertLess(max(p[0] for p in row['subject_corners']),min(p[0] for p in row['bus_corners']))
        reverse=motion_readback(subject,bus,[-1,0],101,.05)
        self.assertEqual(reverse['travel_tangent_xy'],[-1.0,0.0])
        with self.assertRaisesRegex(ValueError,'tangent'):
            motion_readback(subject,bus,[0,0],102,.1)
        subject.bounding_box.get_world_vertices=lambda transform: []
        with self.assertRaisesRegex(ValueError,'body vertices'):
            motion_readback(subject,bus,[1,0],102,.1)

    def test_four_camera_creation_source_encoding_and_frame_join(self):
        class Blueprint:
            def __init__(self):self.attrs={}
            def set_attribute(self,key,value):self.attrs[key]=value
        class Library:
            def find(self,key):
                self.assert_key=key
                return Blueprint()
        class Sensor:
            def __init__(self):self.callback=None;self.stopped=False;self.destroyed=False
            def listen(self,callback):self.callback=callback
            def stop(self):self.stopped=True
            def destroy(self):self.destroyed=True
        class World:
            def __init__(self):self.spawned=[]
            def get_blueprint_library(self):return Library()
            def spawn_actor(self,blueprint,transform,attach_to):
                sensor=Sensor();self.spawned.append((blueprint,transform,attach_to,sensor));return sensor
        class Carla:
            @staticmethod
            def Location(*values):return values
            @staticmethod
            def Rotation(*values):return values
            @staticmethod
            def Transform(location,rotation):return (location,rotation)
        class Sink:
            def __init__(self):self.frames=[]
            def write(self,image):self.frames.append(image.frame)
        class Image:
            def __init__(self,frame,size):self.frame=frame;self.width,self.height=size
        subject,bus=object(),object()
        world=World();sinks={name:Sink() for name in CAMERAS}
        cameras=SchoolBusCameraCapture(world,Carla,subject,bus,sinks)
        self.assertEqual(len(world.spawned),4)
        self.assertEqual({name for name in CAMERAS},{'overview','approach','reference_corner','driver_reference'})
        for name,(_,_,parent,sensor) in zip(CAMERAS,world.spawned):
            self.assertIs(parent,subject if name=='approach' else bus)
            self.assertEqual(world.spawned[list(CAMERAS).index(name)][0].attrs['sensor_tick'],'0.05')
            sensor.callback(Image(101,CAMERAS[name][3]))
        cameras.wait_for_frame(101,timeout_s=.01)
        self.assertEqual(cameras.verify([101]),{name:1 for name in CAMERAS})
        with self.assertRaisesRegex(ValueError,'Missing or extra original'):
            cameras.verify([101,102])
        world.spawned[0][3].callback(Image(101,CAMERAS['overview'][3]))
        with self.assertRaisesRegex(ValueError,'callback failed'):
            cameras.wait_for_frame(101,timeout_s=.01)
        cameras.close()
        self.assertTrue(all(row[3].stopped and row[3].destroyed for row in world.spawned))

        class Pipe:
            def __init__(self):self.writes=[];self.closed=False
            def write(self,data):self.writes.append(len(data))
            def close(self):self.closed=True
        class Process:
            def __init__(self):self.stdin=Pipe()
            def wait(self):return 0
        calls=[]
        def popen(command,stdin):
            calls.append((command,stdin));return Process()
        source=LosslessSourceSink(self.root,'overview',popen=popen)
        class Data:
            def __init__(self,n):self.n=n
            def __len__(self):return self.n
        class RawImage:pass
        image=RawImage();image.raw_data=Data(source.frame_bytes)
        source.write(image)
        image.raw_data=Data(source.frame_bytes-1)
        with self.assertRaisesRegex(ValueError,'byte count'):
            source.write(image)
        source.close()
        self.assertEqual(calls[0][0][0],'ffmpeg')
        self.assertTrue(source.process.stdin.closed)

    def test_meeting_actor_construction_opposite_road_and_cleanup(self):
        class Vector:
            def __init__(self,x):self.x=x;self.y=0
        class Transform:
            def __init__(self,location):self.location=location
            def get_forward_vector(self):return Vector(self.location.heading)
        class Location:
            def __init__(self,heading,road=7,x=0):
                self.heading=heading;self.road=road;self.x=x;self.y=0
        class Waypoint:
            def __init__(self,location):
                self.road_id=location.road;self.is_junction=False
                self.transform=Transform(location)
        class Mapping:
            def get_waypoint(self,location):return Waypoint(location)
        class Library:
            def find(self,name):return name
        class Actor:
            def __init__(self):self.control=None;self.destroyed=False
            def apply_control(self,control):self.control=control
            def destroy(self):self.destroyed=True
        class World:
            def __init__(self):self.actors=[];self.fail_second=False
            def get_map(self):return Mapping()
            def get_blueprint_library(self):return Library()
            def try_spawn_actor(self,blueprint,transform):
                if self.fail_second and len(self.actors)==1:return None
                actor=Actor();self.actors.append((blueprint,transform,actor));return actor
        class Carla:
            @staticmethod
            def VehicleControl(**keys):return keys
        scene={'bus_blueprint_id':'vehicle.school_bus','subject_blueprint_id':'vehicle.car',
               'bus_transform':Transform(Location(-1,x=20)),
               'subject_transform':Transform(Location(1))}
        world=World()
        built=spawn_meeting_scene(world,Carla,scene)
        self.assertEqual([item[0] for item in world.actors],
                         ['vehicle.school_bus','vehicle.car'])
        self.assertEqual(built['heading_dot'],-1)
        self.assertTrue(world.actors[0][2].control['hand_brake'])
        self.assertFalse(built['bus_equipment_verified'])
        self.assertFalse(built['undivided_road_verified'])
        self.assertEqual(built['initial_forward_separation_m'],20)
        scene['subject_transform']=Transform(Location(-1))
        with self.assertRaisesRegex(ValueError,'opposite travel'):
            spawn_meeting_scene(World(),Carla,scene)
        scene['subject_transform']=Transform(Location(1,8))
        with self.assertRaisesRegex(ValueError,'one nonjunction road'):
            spawn_meeting_scene(World(),Carla,scene)
        scene['subject_transform']=Transform(Location(1,x=19))
        with self.assertRaisesRegex(ValueError,'ahead of subject'):
            spawn_meeting_scene(World(),Carla,scene)
        scene['subject_transform']=Transform(Location(1))
        failed=World();failed.fail_second=True
        with self.assertRaisesRegex(ValueError,'subject spawn failed'):
            spawn_meeting_scene(failed,Carla,scene)
        self.assertTrue(failed.actors[0][2].destroyed)

    def test_first_exact_native_check_is_carla_lazy(self):
        package=Path(__file__).resolve().parents[1]
        plan=json.loads((package/'case-plan.json').read_text())
        self.assertTrue(check_plan(plan,CASE_ID))
        scene={'bus_blueprint_id':'vehicle.school_bus',
               'subject_blueprint_id':'vehicle.car',
               'pupil_service':{'purpose':'receiving','walker_blueprint_id':'walker.pedestrian.0001'},
               'bus':{'location':[20,0,0],'rotation':[0,180,0]},
               'subject':{'location':[0,0,0],'rotation':[0,0,0]}}
        self.assertIs(check_scene(scene),scene)
        with self.assertRaisesRegex(ValueError,'pupil-service'):
            check_scene({**scene,'pupil_service':{'purpose':'unspecified'}})
        with self.assertRaisesRegex(ValueError,'pose missing'):
            check_scene({**scene,'subject':{'location':[0,0,0]}})
        source=self.root/'scene.json';source.write_text(json.dumps(scene)+'\n')
        command=[sys.executable,str(package/'school_bus_native.py'),'--check',
                 '--plan',str(package/'case-plan.json'),'--scene',str(source),
                 '--case-id',CASE_ID]
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse((self.root/'capture').exists())

    def test_native_cleanup_runs_restoration_after_encoder_failure(self):
        calls=[]
        def bad_encoder():
            calls.append('encoder')
            raise ValueError('encoder failed')
        with self.assertRaisesRegex(RuntimeError,'encoder'):
            close_all([('encoder',bad_encoder),
                       ('actor',lambda:calls.append('actor')),
                       ('world_settings_restore',lambda:calls.append('restore'))])
        self.assertEqual(calls,['encoder','actor','restore'])

    def test_map_selected_meeting_route_and_auto_scene_contract(self):
        class Vector:
            def __init__(self,x):self.x=x;self.y=0
        class Location:
            def __init__(self,x,y):self.x=x;self.y=y
        class Transform:
            def __init__(self,x,y,heading):self.location=Location(x,y);self.heading=heading
            def get_forward_vector(self):return Vector(self.heading)
        class Waypoint:
            def __init__(self,road,lane,s,x,y,heading):
                self.road_id=road;self.lane_id=lane;self.s=s;self.is_junction=False
                self.transform=Transform(x,y,heading)
        class Mapping:
            rows=[Waypoint(7,1,0,0,0,1),Waypoint(7,-1,23,23,4,-1),
                  Waypoint(8,1,0,0,0,1)]
            def generate_waypoints(self,distance):
                self.distance=distance;return self.rows
        mapping=Mapping()
        found=select_meeting_waypoints(mapping)
        self.assertEqual((found['road_id'],found['subject_waypoint'].lane_id,
                          found['bus_waypoint'].lane_id),(7,-1,1))
        self.assertEqual(mapping.distance,4.0)
        auto={'bus_blueprint_id':'vehicle.school_bus',
              'subject_blueprint_id':'vehicle.car','auto_meeting_route':True,
              'pupil_service':{'purpose':'discharging','walker_blueprint_id':'walker.pedestrian.0001'}}
        self.assertIs(check_scene(auto),auto)
        with self.assertRaisesRegex(ValueError,'mixes automatic'):
            check_scene({**auto,'bus':{}})
        mapping.rows=[Waypoint(7,1,0,0,0,1)]
        with self.assertRaisesRegex(ValueError,'No two-way'):
            select_meeting_waypoints(mapping)

    def test_constructed_pupil_service_actor_and_original_readback(self):
        from types import SimpleNamespace as N
        class Transform:
            def __init__(self,location,rotation):self.location=location;self.rotation=rotation
            def get_right_vector(self):return N(x=0.0,y=1.0)
        class Actor:
            id=34
            def __init__(self,location):self.location=location
            def get_location(self):return self.location
            def get_velocity(self):return N(x=0.0,y=-1.2,z=0.0)
        class Bus(Actor):
            id=12
            def get_transform(self):return Transform(self.location,N(yaw=0.0))
        class World:
            spawned=[]
            def get_blueprint_library(self):return N(find=lambda name:name)
            def try_spawn_actor(self,blueprint,transform):
                self.spawned.append((blueprint,transform));return Actor(transform.location)
        class Carla:
            Location=staticmethod(lambda x,y,z:N(x=x,y=y,z=z))
            Vector3D=staticmethod(lambda x,y,z:N(x=x,y=y,z=z))
        Carla.Transform=Transform
        bus=Bus(N(x=10.0,y=5.0,z=0.0));world=World()
        for purpose,expected_y,expected_direction in (('receiving',9.0,-1.0),
                                                       ('discharging',6.8,1.0)):
            pupil,direction=spawn_pupil_service(world,Carla,bus,{
                'purpose':purpose,'walker_blueprint_id':'walker.pedestrian.0001'})
            self.assertAlmostEqual(pupil.get_location().y,expected_y)
            self.assertEqual(direction.y,expected_direction)
            self.assertEqual(world.spawned[-1][0],'walker.pedestrian.0001')
            row=pupil_readback(pupil,bus,100,.05,purpose)
            self.assertEqual((row['pupil_id'],row['bus_id']),(str(pupil.id),str(bus.id)))
            self.assertFalse(row['pupil_service_verified'])
            self.assertGreater(row['pupil_distance_to_bus_m'],0)
        class Failed(World):
            def try_spawn_actor(self,*args):return None
        with self.assertRaisesRegex(ValueError,'spawn failed'):
            spawn_pupil_service(Failed(),Carla,bus,{
                'purpose':'receiving','walker_blueprint_id':'walker.pedestrian.0001'})

    def test_returned_first_case_config_and_scene_preflight(self):
        package=Path(__file__).resolve().parents[1]
        plan=json.loads((package/'case-plan.json').read_text())
        config=json.loads((package/'config.json').read_text())
        self.assertTrue(check_plan(plan,config['selected_case_id']))
        self.assertIs(check_scene(config),config)
        self.assertEqual([camera['name'] for camera in config['cameras']],list(CAMERAS))
        self.assertEqual([camera['width'] for camera in config['cameras']],
                         [CAMERAS[name][3][0] for name in CAMERAS])
        self.assertEqual(config['source_observation_terms'],
                         [row['term'] for row in plan['observations']])
        self.assertEqual(config['school_bus_lamp_review']['roi_status'].split()[0],
                         'unreviewed')

if __name__=='__main__':unittest.main()
