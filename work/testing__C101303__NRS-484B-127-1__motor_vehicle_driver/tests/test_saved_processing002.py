"""CPU-only orchestration regressions, not exact-case physical preparation proof.

A tiny revision-selected analyzer runs as a real subprocess. Converter, renderer,
and decoder are mocked here; the actual case/lifecycle proofs run those separately.
"""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[3]
BOOTSTRAP=ROOT/'work/_shared/runtime002.py'
spec=importlib.util.spec_from_file_location('saved_processing_bootstrap',BOOTSTRAP)
bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)
RUNTIME=bootstrap.prepare_runtime(ROOT);bootstrap.activate_runtime(ROOT,RUNTIME)
from worker_exchange import saved_processing as saved
from worker_exchange import native_output as native
from worker_exchange.common import sha,tree,write
print('Selected immutable runtime manifest SHA256:',sha(RUNTIME/'SOURCE-MANIFEST.json'),flush=True)

CID='orchestration_source_case'
ANALYZER='''import argparse,hashlib,json\nfrom pathlib import Path\nfrom worker_exchange.native_output import provenance_record\np=argparse.ArgumentParser();p.add_argument('--attempt');p.add_argument('--output');args=p.parse_args();root=Path(args.attempt)\n(root/'selected-revision-executed.json').write_text(json.dumps({'revision':'selected-v002'}))\nsource=root/'motion.json'\nif not source.is_file():raise FileNotFoundError('Missing required source: motion.json')\npoints=json.loads(source.read_text())['positions_xy_m'];met=points[-1]!=points[0];status='met' if met else 'not_met'\nsources={'motion.json':hashlib.sha256(source.read_bytes()).hexdigest()}\ncheck={'status':status,'method':'orchestration-test-original-motion','intervals':[{'start_frame':10,'end_frame':11,'start_time_s':0,'end_time_s':.05}],'sources':sources}\ncfg=json.loads((root/'config.json').read_text());(root/'channels').mkdir();(root/'channels'/'motion.jsonl').write_text('new derived channel\\n')\nresult={'case_id':cfg['selected_case_id'],'measured_values':{'sampled_displacement_m':10 if met else 0},'target_checks':[{'target':'physical_test_motion','requested':True,'measured':met,'method':'orchestration-test-original-motion','tolerance':0,'matched':met,'physical_cause_confirmed':False,'cause_evidence':'motion.json'}],'physical_checks':{k:dict(check) for k in ('setup','target','maneuver')},'setup_confirmed':met,'behavior_attempted':met,'maneuver_completed':met,'termination_reason':'orchestration fixture only','physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],'video_frame_map_reference':'video_frames.jsonl','recording_description':cfg['case']['recording_description'],'recording_evidence':[],'realized_observables':{'positions_xy_m':points},'physical_acceptance_claimed':False,**provenance_record(root)}\n(root/'result.json').write_text(json.dumps(result));Path(args.output).write_text(json.dumps({'case_id':cfg['selected_case_id'],'measurements':{'test_positions':{'value':points,'sources':sources}},**provenance_record(root)}))\n'''


class SavedProcessingTests(unittest.TestCase):
    def fixture(self,root,kind='synthetic_fixture',diagnostic=True,analyzer=ANALYZER):
        folder=root/'package';folder.mkdir();attempt=root/'original';attempt.mkdir()
        config={'selected_case_id':CID,'case':{'case_id':CID,'recording_description':{'channels':[]}},'cell_id':'C109705','actor':'motor_vehicle_driver','law_id':'NRS-484B-400-2a'}
        write(attempt/'config.json',config)
        original={'case_id':CID,'files':[{'path':'analyze.py','content':"raise AssertionError('stale Native analyzer must not execute')\n"}]}
        write(attempt/'construction.json',original);(attempt/'analyze.py').write_text(original['files'][0]['content']);(attempt/'runner.py').write_text('# archived Native revision\n')
        write(attempt/'result.json',{'legacy_result':True,'do_not_replace':'original result'})
        write(attempt/'geometry.json',{'original_geometry':'must remain unchanged'})
        (attempt/'body_history.jsonl').write_text('{"frame":10,"original":true}\n')
        (attempt/'channels').mkdir();(attempt/'channels'/'old.jsonl').write_text('original derived legacy channel\n')
        write(attempt/'motion.json',{'positions_xy_m':[[0,0],[10,0]]})
        trace=[{'frame':10+i,'time_s':i*.05,'position_m':[i*10,0,0]} for i in range(2)]
        (attempt/'trace.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in trace))
        mapping=[{'video_frame':i,'carla_frame':r['frame'],'time_s':r['time_s']} for i,r in enumerate(trace)]
        (attempt/'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in mapping))
        (attempt/'raw.mkv').write_bytes(b'diagnostic audit stub; not an encoded recording')
        write(attempt/'acquisition-provenance.json',{'provenance_kind':kind,'diagnostic_fixture':diagnostic})
        current={'case_id':CID,'files':[{'path':'analyze.py','content':analyzer}]}
        write(folder/'construction.json',current)
        write(folder/'manifest.json',{'runtime_manifest_sha256':sha(RUNTIME/'SOURCE-MANIFEST.json'),'cases':[{'case_id':CID,'construction':'construction.json','construction_sha256':sha(folder/'construction.json'),'measurement_procedure':{'entrypoint':'analyze.py'}}]})
        write(folder/'proposals/cases.json',{'cases':[config['case']]})
        return folder/'manifest.json',attempt,root/'derived'

    def mocks(self):
        stack=__import__('contextlib').ExitStack()
        stack.enter_context(mock.patch.object(saved,'process',return_value={'converted':True}))
        stack.enter_context(mock.patch.object(saved,'render',side_effect=lambda stage,out,proposal:{'video':str(stage/'raw.mkv')}))
        stack.enter_context(mock.patch.object(saved,'audit',side_effect=lambda path,*a,**kw:{'passed':True,'video_sha256':sha(Path(path)),'frames':2,'diagnostic_decoder_mock':True}))
        stack.enter_context(mock.patch('batch_pipeline.carla.validate_attempt',return_value={'validated':True}))
        return stack

    def run_saved(self,manifest,attempt,output,owner_receipt=None):
        with self.mocks():return saved.run(manifest,CID,attempt,output,RUNTIME/'library',ROOT/'.runtime-work/decoder/.lake/build/bin/adapterCheck',owner_receipt=owner_receipt)

    def test_stale_result_and_old_analyzer_are_preserved_but_not_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest,attempt,output=self.fixture(Path(tmp));before=tree(attempt)
            receipt=self.run_saved(manifest,attempt,output);stage=Path(receipt['analysis_directory']);result=json.loads((stage/'result.json').read_text())
            self.assertTrue(result['maneuver_completed']);self.assertEqual(receipt['analysis_revision']['analyzer_sha256'],sha(stage/'analyze.py'))
            self.assertNotEqual(receipt['native_revision']['analyzer_sha256'],receipt['analysis_revision']['analyzer_sha256'])
            self.assertEqual(json.loads((stage/'selected-revision-executed.json').read_text())['revision'],'selected-v002')
            self.assertEqual(tree(attempt),before);self.assertTrue(json.loads((attempt/'result.json').read_text())['legacy_result'])
            self.assertNotEqual((attempt/'channels'/'old.jsonl').read_text(),(stage/'channels'/'motion.jsonl').read_text())

    def test_repeated_processing_allocates_new_versions_and_preserves_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest,attempt,output=self.fixture(Path(tmp));first=self.run_saved(manifest,attempt,output);old=tree(output/'v0001')
            second=self.run_saved(manifest,attempt,output)
            self.assertEqual(Path(first['version']).name,'v0001');self.assertEqual(Path(second['version']).name,'v0002');self.assertEqual(tree(output/'v0001'),old)
            self.assertTrue((output/'v0002/analysis/result.json').is_file());self.assertTrue((output/'v0002/processing.json').is_file())

    def test_missing_evidence_runs_selected_analyzer_and_writes_unverified_feedback(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest,attempt,output=self.fixture(Path(tmp));(attempt/'motion.json').unlink();before=tree(attempt)
            receipt=self.run_saved(manifest,attempt,output);stage=Path(receipt['analysis_directory']);result=json.loads((stage/'result.json').read_text())
            self.assertTrue((stage/'selected-revision-executed.json').is_file());self.assertTrue(receipt['missing_evidence'])
            self.assertEqual(result['physical_checks']['maneuver']['status'],'unverified');self.assertFalse(result['maneuver_completed'])
            self.assertTrue(result['physical_checks']['maneuver']['sources']);self.assertEqual(tree(attempt),before)
            self.assertEqual(json.loads((output/'v0001/feedback.json').read_text())['classification'],'incomplete_or_unavailable_law_evidence')
            self.assertEqual(json.loads((output/'v0001/feedback.json').read_text())['physical_status'],'unverified')

    def test_native_style_fixture_keeps_diagnostic_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest,attempt,output=self.fixture(Path(tmp),kind='native',diagnostic=True)
            receipt=self.run_saved(manifest,attempt,output);result=json.loads(Path(receipt['result']).read_text())
            self.assertEqual(result['provenance_kind'],'native');self.assertTrue(result['diagnostic_fixture']);self.assertFalse(result['physical_acceptance_claimed']);self.assertTrue(result['realized_observables'])

    def test_real_native_requires_release_after_verified_native_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest,attempt,output=self.fixture(root,kind='native',diagnostic=False)
            native.seal_capture(attempt,frames=2,restoration={'restored':True},errors=[],encoder_exit_codes={'overview':0})
            with self.assertRaisesRegex(ValueError,'has not exited'):saved.acknowledge_owner_release(attempt,root/'owner.json',True)
            exit_record=saved.record_native_exit(attempt);self.assertEqual(exit_record['event'],'native_exit')
            with self.assertRaisesRegex(ValueError,'owner-release receipt'):self.run_saved(manifest,attempt,output)
            owner=saved.acknowledge_owner_release(attempt,root/'owner.json',True);self.assertEqual(owner['event'],'owner_released');self.assertTrue(owner['no_resource_operation_performed'])
            receipt=self.run_saved(manifest,attempt,output,root/'owner.json');self.assertTrue(receipt['passed'])

    def test_wrong_capture_event_order_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,attempt,_=self.fixture(root)
            native.seal_capture(attempt,frames=2,restoration={'restored':True},errors=[])
            seal=json.loads((attempt/'capture-seal.json').read_text());seal['events']=['restoration_verified','capture_finished','encoders_closed'];write(attempt/'capture-seal.json',seal)
            with self.assertRaisesRegex(ValueError,'closure ordering'):saved.record_native_exit(attempt)

    def test_owner_release_must_bind_actual_native_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest,attempt,output=self.fixture(root,kind='native',diagnostic=False)
            native.seal_capture(attempt,frames=2,restoration={'restored':True},errors=[]);saved.record_native_exit(attempt)
            saved.acknowledge_owner_release(attempt,root/'owner.json',True);owner=json.loads((root/'owner.json').read_text());owner['native_exit_sha256']='0'*64;write(root/'owner.json',owner)
            with self.assertRaisesRegex(ValueError,'[Oo]wner|[Ee]xit'):self.run_saved(manifest,attempt,output,root/'owner.json')

    def test_native_exit_event_cannot_be_spoofed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest,attempt,output=self.fixture(root,kind='native',diagnostic=False)
            native.seal_capture(attempt,frames=2,restoration={'restored':True},errors=[]);saved.record_native_exit(attempt)
            exit_path=attempt/'native-exit.json';exit_record=json.loads(exit_path.read_text());exit_record['event']='wrong_event';write(exit_path,exit_record)
            with self.assertRaisesRegex(ValueError,'[Ee]xit|[Oo]rder|[Oo]wner'):
                saved.acknowledge_owner_release(attempt,root/'owner.json',True);self.run_saved(manifest,attempt,output,root/'owner.json')

    def test_analyzer_cannot_rewrite_staged_original_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);tamper=ANALYZER.replace("source=root/'motion.json'", "(root/'geometry.json').write_text('rewritten acquisition')\nsource=root/'motion.json'")
            manifest,attempt,output=self.fixture(root,analyzer=tamper);before=tree(attempt)
            with self.assertRaisesRegex(ValueError,'[Ss]ource|[Aa]cquisition'):self.run_saved(manifest,attempt,output)
            self.assertEqual(tree(attempt),before)


if __name__=='__main__':unittest.main()
