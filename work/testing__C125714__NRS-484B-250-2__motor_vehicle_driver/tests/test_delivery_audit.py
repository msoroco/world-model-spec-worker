"""Independent delivery rejection tests using only small CPU source packets."""
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import ORIGINALS, audit, audit_sources, sha, verify_frame_join, verify_saved_join
from pixel_checks import pixel_presence


class DeliveryAuditTests(unittest.TestCase):
    def packets(self):
        mapping = [{'video_frame': i, 'carla_frame': 10+i,
                    'native_frame': 10+i, 'time_s': .5 + i*.05} for i in range(3)]
        trace = [{'frame': m['carla_frame'], 'time_s': m['time_s']}
                 for m in mapping]
        ego = [dict(row, actor_id=17) for row in trace]
        other = [dict(row, actor_id=29) for row in trace]
        return mapping, trace, ego, other, {'ego_actor_id': 17, 'other_actor_id': 29}

    def test_full_original_join_and_missing_other_rejected(self):
        m, t, e, o, site = self.packets()
        self.assertEqual(verify_frame_join(m, t, e, o, site, 3), 3)
        with self.assertRaisesRegex(ValueError, 'complete original'):
            verify_frame_join(m, t, e, o[:-1], site, 3)

    def test_identity_and_clock_changes_rejected(self):
        m, t, e, o, site = self.packets()
        o[1]['actor_id'] = 17
        with self.assertRaisesRegex(ValueError, 'join changed'):
            verify_frame_join(m, t, e, o, site, 3)
        o[1]['actor_id'] = 29
        m[2]['time_s'] += .1
        t[2]['time_s'] = e[2]['time_s'] = o[2]['time_s'] = m[2]['time_s']
        with self.assertRaisesRegex(ValueError, '20 Hz'):
            verify_frame_join(m, t, e, o, site, 3)

    def test_diagnostic_capture_cannot_be_delivery_audited(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = 'testing__C125714__NRS-484B-250-2__motor_vehicle_driver__timing_inside_training'
            (root/'config.json').write_text(json.dumps({'selected_case_id': case}))
            (root/'acquisition-provenance.json').write_text(json.dumps({
                'provenance_kind': 'fixture', 'diagnostic_fixture': True}))
            with self.assertRaisesRegex(ValueError, 'diagnostic fixture rejected'):
                audit_sources(root, case)

    def test_saved_receipt_requires_exact_case_and_original_hashes(self):
        case = 'testing__C125714__NRS-484B-250-2__motor_vehicle_driver__timing_inside_training'
        native = {'frames':200,'sources':{'road.xodr':'a'*64}}
        saved = {'case_id':case,'originals_preserved':True,'missing_evidence':False,
                 'timestamp_joins':{'passed':True,'frames':200},
                 'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,
                 'original_source_hashes':{'road.xodr':'a'*64}}
        verify_saved_join(saved,native,case)
        changed = dict(saved,case_id=case+'__wrong')
        with self.assertRaisesRegex(ValueError,'exact-case'):
            verify_saved_join(changed,native,case)
        changed = dict(saved,original_source_hashes={'road.xodr':'b'*64})
        with self.assertRaisesRegex(ValueError,'source hashes'):
            verify_saved_join(changed,native,case)
        changed = dict(saved,timestamp_joins={'passed':True,'frames':199})
        with self.assertRaisesRegex(ValueError,'original-frame'):
            verify_saved_join(changed,native,case)

    def test_native_shaped_source_lifecycle_and_physical_completion(self):
        case = 'testing__C125714__NRS-484B-250-2__motor_vehicle_driver__timing_inside_training'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write = lambda name, value: (root/name).write_text(json.dumps(value)+'\n')
            write('config.json', {'selected_case_id':case,'duration_s':.15,'rate_hz':20})
            (root/'road.xodr').write_text('CPU-only unit fixture\n')
            write('site-context.json', {'map_sha256':sha(root/'road.xodr'),
                  'ego_actor_id':17,'other_actor_id':29,'ego_highway':'a',
                  'other_highway':'b','ego_side':'left','other_side':'right',
                  'case_id':case,'approach_relation':'crossing',
                  'official_device_controls_intersection':False,
                  'other_left_turn_intent':False,'other_left_turn_making':False,
                  'subsection_4_context_reviewed':True})
            write('reviewed-context.json', dict(json.loads((root/'site-context.json').read_text()),
                                                reviewer='CPU fixture reviewer'))
            write('acquisition-provenance.json', {'provenance_kind':'native',
                  'diagnostic_fixture':False,
                  'reviewed_context_sha256':sha(root/'reviewed-context.json')})
            m,t,e,o,_ = self.packets()
            for name, values in [('video_frames.jsonl',m),('trace.jsonl',t),
                                 ('ego-body-history.jsonl',e),
                                 ('other-body-history.jsonl',o)]:
                (root/name).write_text(''.join(json.dumps(v)+'\n' for v in values))
            for name in ORIGINALS:
                if not (root/name).exists():
                    (root/name).write_text('CPU-only camera placeholder\n')
            sources = {name:sha(root/name) for name in ORIGINALS}
            write('acquisition.json', {name:{'kind':'original_native','sha256':digest}
                                       for name,digest in sources.items()})
            write('capture-seal.json', {'format':'worker-sealed-capture',
                  'events':['capture_finished','encoders_closed','restoration_verified'],
                  'restoration':{'restored':True},'encoder_exit_codes':{
                      name[:-4]:0 for name in ORIGINALS if name.endswith('.mkv')},
                  'sources':sources})
            write('native-exit.json', {'event':'native_exit',
                  'capture_seal_sha256':sha(root/'capture-seal.json'),
                  'native_process_exit_code':0,'capture_command_failed':False})
            write('owner-release.json', {'event':'owner_released',
                  'operator_attested':True,'native_exit_sha256':sha(root/'native-exit.json')})
            result = {'case_id':case,'setup_confirmed':True,'behavior_attempted':True,
                      'maneuver_completed':True,'physical_checks':{
                          'setup':{'status':'met'},'maneuver':{'status':'met'}},
                      'legal_verdict_claimed':False}
            write('result.json',result)
            self.assertEqual(audit_sources(root,case)['frames'],3)
            reviewed = json.loads((root/'reviewed-context.json').read_text())
            reviewed['other_left_turn_intent'] = True
            write('reviewed-context.json', reviewed)
            provenance = json.loads((root/'acquisition-provenance.json').read_text())
            provenance['reviewed_context_sha256'] = sha(root/'reviewed-context.json')
            write('acquisition-provenance.json', provenance)
            with self.assertRaisesRegex(ValueError, 'exception context differs'):
                audit_sources(root,case)
            reviewed['other_left_turn_intent'] = False
            write('reviewed-context.json', reviewed)
            provenance['reviewed_context_sha256'] = sha(root/'reviewed-context.json')
            write('acquisition-provenance.json', provenance)
            result['physical_checks']['maneuver']['status'] = 'unknown'
            write('result.json',result)
            with self.assertRaisesRegex(ValueError, 'physical completion'):
                audit_sources(root,case)

    def test_blank_primary_rejected_and_two_view_rows_accepted(self):
        width, height = 1920, 1800
        pixels = bytearray(width*height*3)
        frame = SimpleNamespace(width=width, height=height, pixels=pixels)
        with self.assertRaisesRegex(ValueError, 'no varying pixels'):
            pixel_presence(frame)
        pixels[0:width*1080*3] = bytes([25, 75, 125, 130, 80, 30]) * (width*1080//2)
        pixels[width*1080*3:] = bytes([30, 80, 130, 125, 75, 25]) * (width*(height-1080)//2)
        pixel_presence(frame)

    def test_promoted_saved_media_bound_to_source_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attempt, stage = root/'attempt', root/'saved'
            attempt.mkdir();(stage/'traffic_spec').mkdir(parents=True)
            mapping,_,_,_,_ = self.packets()
            (attempt/'video_frames.jsonl').write_text(
                ''.join(json.dumps(row)+'\n' for row in mapping))
            scenes = {'scenes':[{'t':round(row['time_s']*1000)} for row in mapping]}
            (stage/'traffic_spec/trace.json').write_text(json.dumps(scenes))
            (stage/'result.json').write_text('{}\n')
            promoted_video, promoted_trace = attempt/'video.webm', attempt/'trace.json'
            promoted_video.write_bytes(b'CPU test video bytes')
            promoted_trace.write_bytes((stage/'traffic_spec/trace.json').read_bytes())
            saved = root/'processing.json'
            saved.write_text(json.dumps({'format':'worker-saved-processing',
                'passed':True,'recorded_only':True,'case_id':'case',
                'originals_preserved':True,'missing_evidence':False,
                'timestamp_joins':{'passed':True,'frames':3},
                'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,
                'original_source_hashes':{'video_frames.jsonl':sha(attempt/'video_frames.jsonl')},
                'analysis_directory':str(stage),
                'result_sha256':sha(stage/'result.json'),
                'final_video_checks':{'video_sha256':sha(promoted_video)}}))
            from delivery_audit import CHECKS
            import delivery_audit
            checker = sha(ROOT/'pixel_checks.py')
            decode = root/'decode.json'
            decode.write_text(json.dumps({'video_sha256':sha(promoted_video),
                'checks':{'frame_count':'all-decoded-frames','pixel_presence':checker},
                'auditor_sha256':'CPU unit fixture'}))
            native = {'frames':3,'source_result_sha256':'CPU unit fixture',
                      'frame_map_sha256':sha(attempt/'video_frames.jsonl'),
                      'sources':{'video_frames.jsonl':sha(attempt/'video_frames.jsonl')}}
            with patch.object(delivery_audit,'audit_sources',return_value=native):
                result = audit(attempt,saved,decode,'case','job',1,'recording',
                               promoted_video,promoted_trace,
                               media_verify=lambda *a,**kw:None)
                self.assertTrue(all(result['checks'][key] for key in CHECKS))
                self.assertEqual(result['video'],'video.webm')
                promoted_video.write_bytes(b'changed CPU test video bytes')
                with self.assertRaisesRegex(ValueError,'promoted media differs'):
                    audit(attempt,saved,decode,'case','job',1,'recording',
                          promoted_video,promoted_trace,
                          media_verify=lambda *a,**kw:None)


if __name__ == '__main__':
    unittest.main()
