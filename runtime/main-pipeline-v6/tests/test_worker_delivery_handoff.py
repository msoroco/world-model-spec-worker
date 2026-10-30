import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from worker_exchange.common import read, sha, write
from worker_exchange.delivery_handoff import validate_case, validate_queue
from worker_exchange.semantic_delivery import validate as validate_semantic


class DeliveryHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = pathlib.Path(self.temp.name)
        write(self.repo/'batch.json', {})
        self.aid = 'testing__C1__LAW-1__motor_vehicle_driver'
        self.folder = self.repo / 'work' / self.aid
        self.folder.mkdir(parents=True)
        self.case_ids = [self.aid + '__stop', self.aid + '__roll']
        self.description = {'channels': [{'name': 'kin.speed', 'unit': 'm/s',
            'sampling_rate_hz': 20, 'method': 'Native velocity', 'time_window': 'full original',
            'reference_frame': 'world', 'uncertainty': '20 Hz'}],
            'context_inputs': [], 'limitations': []}
        self.assignment = {'assignment_id': self.aid, 'law_id': 'LAW-1', 'cell_id': 'C1',
                           'actor': 'motor_vehicle_driver', 'law': {'id': 'LAW-1', 'text': 'A driver shall stop.'},
                           'cell': {'cell_id': 'C1'}}

    def proposal(self, stage, result):
        path = 'proposals/' + stage + '.json'
        write(self.folder / path, result)
        return {'path': path, 'sha256': sha(self.folder / path)}

    def semantic_fixture(self):
        relevance = {'cell_id': 'C1', 'actor': 'motor_vehicle_driver', 'status': 'draft',
                     'relevant_laws': [{'law_id': 'LAW-1', 'quote': 'A driver shall stop.',
                        'applies_to': ['motor_vehicle_driver'], 'confidence': 'high'}],
                     'borderline_excluded': []}
        template = {'template_id': 'LAW-1@motor_vehicle_driver', 'law_id': 'LAW-1',
                    'actor': 'motor_vehicle_driver', 'quote': 'A driver shall stop.',
                    'structure': {'activation': {}, 'obligation': {}, 'exceptions': [],
                                  'timing': {}, 'judgment_calls_needed': []},
                    'parameter_refs': [{'name': 'commanded_speed', 'kind': 'controller', 'range_or_domain': '0..5 m/s'}]}
        binding = {'cell_id': 'C1', 'actor': 'motor_vehicle_driver', 'status': 'draft',
                   'law_refs': [{'template_id': template['template_id'], 'binding_kind': 'direct'}],
                   'context_refs': [], 'established_contexts': [], 'fixed_parameters': [],
                   'variable_parameters': [{'name': 'commanded_speed', 'kind': 'controller',
                                            'range_or_domain': '0..5 m/s', 'used_by_laws': ['LAW-1']}]}
        cases = []
        for cid, target, speed in [(self.aid+'__baseline', 'baseline', 0),
                                   (self.case_ids[0], 'compliant_attempt', 0),
                                   (self.case_ids[1], 'violating_attempt', 3)]:
            case = {'case_id': cid, 'target_law_id': None if target == 'baseline' else 'LAW-1',
                    'target_type': target, 'rationale': 'fixture',
                    'variable_assignments': {'commanded_speed': {'kind': 'controller', 'value': speed}},
                    'unresolved_judgment_calls': [], 'recording_description': self.description}
            if target != 'baseline':
                case.update(paired_probe_id='halt', deliberate_differences=['commanded_speed'],
                            probe={'primary_variable': 'commanded_speed',
                                   'comparison_or_standard': 'stopping action',
                                   'target_value_or_branch': target})
            cases.append(case)
        refs = {'relevance_batch': self.proposal('relevance_batch', relevance),
                'relevance': self.proposal('relevance', relevance),
                'template': self.proposal('template', template),
                'judgment_observables': [],
                'bindings': self.proposal('bindings', binding),
                'cases': self.proposal('cases', {'cell_id': 'C1', 'actor': 'motor_vehicle_driver',
                                                'status': 'draft', 'cases': cases, 'sweep_specs': []})}
        write(self.folder / 'proposals/semantic-index.json',
              {'format': 'worker-semantic-delivery-v1', 'assignment_id': self.aid, 'stages': refs})
        manifest = {'cases': []}
        for cid in self.case_ids:
            path = 'cases/' + cid + '/construction.json'
            write(self.folder / path, {'recording_description': self.description})
            manifest['cases'].append({'case_id': cid, 'kind':'delivery', 'construction': path})
        return manifest

    def test_complete_semantic_chain_and_source_hash(self):
        manifest = self.semantic_fixture()
        self.assertEqual(validate_semantic(self.folder, self.assignment, manifest)['selected_cases'], 2)
        write(self.folder / 'proposals/template.json', {'changed': True})
        with self.assertRaisesRegex(ValueError, 'source hash'):
            validate_semantic(self.folder, self.assignment, manifest)

    def test_delivery_acceptance_proof(self):
        case = self.case_ids[0]
        for name in ('audit.py', 'positive.log', 'negative.log'):
            (self.folder / name).write_text(name)
        receipt = {'case_id': case, 'sets': ['demo-test', 'full-test'],
                   'checks': sorted(['native_source', 'all_participants', 'time_join',
                                     'full_video_decode', 'actual_pixels', 'physical_completion']),
                   'command': 'python audit.py --case '+case,
                   'negative_command': 'python audit.py --case '+case+' --negative',
                   'script': 'audit.py', 'script_sha256': sha(self.folder/'audit.py'),
                   'test_log': 'positive.log', 'test_log_sha256': sha(self.folder/'positive.log'),
                   'negative_log': 'negative.log', 'negative_log_sha256': sha(self.folder/'negative.log'),
                   'test_exit_code': 0, 'negative_exit_code': 1,
                   'negative_expected_error': 'negative.log'}
        validate_case(self.folder, {'case_id': case, 'delivery_acceptance': receipt})
        receipt['sets'] = ['demo-test']
        with self.assertRaisesRegex(ValueError, 'set or independent check'):
            validate_case(self.folder, {'case_id': case, 'delivery_acceptance': receipt})

    def test_complete_queue(self):
        write(self.folder/'execution-manifest.json', {'cases': [{'case_id': cid} for cid in self.case_ids]})
        write(self.folder/'case-plan.json', {'comparisons': [{'comparison_id': 'halt'}]})
        rows = [{'order': i, 'assignment_id': self.aid, 'case_id': cid,
                 **{name: cid for name in ('capture_command', 'postprocessing_command',
                                          'owner_release_command', 'additional_source_audit_command')}}
                for i, cid in enumerate(self.case_ids, 1)]
        write(self.repo/'work/_shared/gpu-queue.json',
              {'format': 'worker-ordered-gpu-queue-v1', 'cases': rows,
               'comparison_audit_commands': [{'assignment_id': self.aid,
                                              'comparison_id': 'halt', 'command': 'audit halt'}]})
        self.assertEqual(validate_queue(self.repo, {self.aid: {}})['cases'], 2)
        rows.pop()
        write(self.repo/'work/_shared/gpu-queue.json',
              {'format': 'worker-ordered-gpu-queue-v1', 'cases': rows,
               'comparison_audit_commands': []})
        with self.assertRaisesRegex(ValueError, 'every exact case'):
            validate_queue(self.repo, {self.aid: {}})

    def test_canonical_queue_requires_local_job_commands(self):
        write(self.repo/'batch.json', {'canonical_delivery_queue_required':True})
        write(self.folder/'execution-manifest.json', {'cases': [
            {'case_id':cid,'candidates':[{'id':'fallback1'}]} for cid in self.case_ids]})
        write(self.folder/'case-plan.json', {'comparisons': []})
        rows=[{'order':i,'assignment_id':self.aid,'case_id':cid,
               **{name:cid for name in ('capture_command','postprocessing_command',
                    'owner_release_command','additional_source_audit_command')}}
              for i,cid in enumerate(self.case_ids,1)]
        write(self.repo/'work/_shared/gpu-queue.json',
              {'format':'worker-ordered-gpu-queue-v1','cases':rows,
               'comparison_audit_commands':[]})
        with self.assertRaisesRegex(ValueError, 'canonical prepare_command'):
            validate_queue(self.repo,{self.aid:{}})

    @unittest.skipUnless((pathlib.Path(__file__).resolve().parents[1]/'pipeline.py').is_file(),
                         'Local campaign integration is outside portable worker runtime')
    def test_local_model_free_semantic_adoption(self):
        from batch_pipeline.store import Store
        from batch_pipeline.run_inputs import freeze_job_revision
        from worker_exchange.local_delivery import prepare
        manifest = self.semantic_fixture()
        self.assignment.update(role='testing', summary={'id':'LAW-1','subject':'driver'})
        write(self.repo/'inputs'/self.aid/'assignment.json',self.assignment)
        write(self.repo/'batch.json',{'assignments':{self.aid:{}},'batch_id':'batch'})
        root=self.repo/'artifacts';(root/'state').mkdir(parents=True)
        write(root/'inputs/catalog/vocabulary_catalog.json',
              {'cells':[self.assignment['cell']], 'law_records':{'LAW-1':self.assignment['law']}})
        for sid in ('demo-test','full-test'):
            write(root/'sets'/sid/'scope.json',{'assignments':[{'law_id':'LAW-1',
                    'cell_id':'C1','actor':'motor_vehicle_driver'}]})
        db=root/'state/delivery.sqlite'
        imported={'destinations':{self.aid:self.folder},
                  'results':{self.aid:{'status':'ready'}}, 'package_sha256':'fixture-package',
                  'return_git':{'commit':'fixture-commit'}}
        def import_catalog(store,path):
            store.db.execute('INSERT OR IGNORE INTO catalogs VALUES(?,?,?)',
                             ('fixture-catalog',str(path),json.dumps(read(path))))
            return 'fixture-catalog'
        def freeze_one(root_arg,repo_arg,batch_arg,db_arg,run,base,config_file,assignment_ids=None):
            store=Store(db_arg)
            try:
                info=store.db.execute('SELECT catalog_id,config FROM runs WHERE id=?',(run,)).fetchone()
                catalog=json.loads(store.db.execute('SELECT payload FROM catalogs WHERE id=?',(info[0],)).fetchone()[0])
                revision=freeze_job_revision(store,run,catalog,read(config_file),
                        {'worker_exchange_package':'fixture-package'})
                return {'input_revision':revision}
            finally:store.db.close()
        with (patch('worker_exchange.exchange.check_return',return_value={'package_sha256':'fixture-package'}),
              patch('worker_exchange.exchange.import_return',return_value=imported),
              patch('worker_exchange.local.import_return',return_value=imported),
              patch('worker_exchange.local_delivery.assignments',return_value={self.aid:{}}),
              patch('worker_exchange.execution_manifest.validate',return_value=manifest),
              patch('worker_exchange.candidate_constructions.select',return_value=(None,{},None)),
              patch('worker_exchange.local_delivery.freeze',side_effect=freeze_one),
              patch('worker_exchange.local_delivery.prepare_manifest_jobs',
                    return_value={'exact_execution_job_ids':[]}),
              patch('pipeline.import_catalog',side_effect=import_catalog),
              patch('batch_pipeline.run_inputs.partition_snapshot',return_value={}),
              patch('batch_pipeline.runtime_dependencies.discover',return_value=[]),
              patch('batch_pipeline.runtime_dependencies.snapshot',return_value={}),
              patch('law_split.assignment_allowed',return_value=True)):
            result=prepare(root,self.repo,'batch',db,self.aid,self.case_ids[0])
            fallback=prepare(root,self.repo,'batch',db,self.aid,self.case_ids[0],'fallback1')
        self.assertTrue(result['semantic_jobs_completed'])
        self.assertNotEqual(result['run'],fallback['run'])
        self.assertNotEqual(result['input_revision'],fallback['input_revision'])
        store=Store(db)
        try:
            completed={row[0] for row in store.db.execute("SELECT stage FROM jobs WHERE status='completed'")}
            self.assertEqual(completed,{'relevance_batch','relevance','template','bindings','cases'})
        finally:store.db.close()

    @unittest.skipUnless((pathlib.Path(__file__).resolve().parents[1]/'pipeline.py').is_file(),
                         'Local campaign integration is outside portable worker runtime')
    def test_exact_dispatch_cannot_run_other_jobs(self):
        from worker_exchange.local_delivery import execute_exact
        root=self.repo/'artifacts';(root/'state').mkdir(parents=True)
        db=root/'state/delivery.sqlite'
        write(self.repo/'batch.json',{'assignments':{self.aid:{}}})
        write(self.repo/'inputs'/self.aid/'assignment.json',self.assignment)
        case=self.case_ids[0]
        class FakeDb:
            def execute(self,*_args):return self
            def fetchone(self):return (1,)
            def close(self):pass
        class FakeStore:
            def __init__(self,_path):self.db=FakeDb()
            def job(self,_ident):return {'stage':'execution','status':'pending',
                'actor':'motor_vehicle_driver','payload':json.dumps({
                    'case':{'case_id':case,'target_law_id':'LAW-1'},
                    'cell':{'cell_id':'C1'}})}
        with (patch('worker_exchange.exchange.check_return'),
              patch('worker_exchange.branch_coverage.assignments',return_value={self.aid:{}}),
              patch('worker_exchange.branch_coverage.assignment_path',
                    return_value=self.repo/'inputs'/self.aid/'assignment.json'),
              patch('batch_pipeline.store.Store',FakeStore),
              patch('batch_pipeline.engines.execute_pool',return_value=1) as execute):
            execute_exact(root,self.repo,'batch',db,'run',self.aid,case,7,
                          '/tmp/native-python','127.0.0.1',22100)
        self.assertEqual(execute.call_args.kwargs['job_ids'],(7,))

    @unittest.skipUnless((pathlib.Path(__file__).resolve().parents[1]/'pipeline.py').is_file(),
                         'Local campaign integration is outside portable worker runtime')
    def test_local_acceptance_references_one_recording_in_both_sets(self):
        from worker_exchange.local_delivery import accept
        root=self.repo/'artifacts';(root/'state').mkdir(parents=True)
        db=root/'state/delivery.sqlite';db.touch()
        write(self.repo/'batch.json',{'assignments':{self.aid:{}}})
        write(self.repo/'inputs'/self.aid/'assignment.json',self.assignment)
        for sid in ('demo-test','full-test'):
            write(root/'sets'/sid/'selection.json',{'frozen':True,'members':[],
                                                   'selection_version':'before'})
        rid='a'*64;attempt=root/'recordings'/rid/'evidence';attempt.mkdir(parents=True)
        write(attempt.parent/'metadata.json',{'recording_id':rid,'campaign':'run',
              'job_id':7,'attempt':1,'cell_id':'C1','actor':'motor_vehicle_driver',
              'case_id':self.case_ids[0],'status':'recording','phases':{}})
        write(attempt/'result.json',{'completion':{'binding':{}}})
        write(attempt/'trace.json',{'scenes':[{'t':50}]})
        (attempt/'video.webm').write_bytes(b'fixture-video')
        (attempt/'video_frames.jsonl').write_text(json.dumps({'video_frame':0,'time_s':0.05})+'\n')
        audit={'format':'worker-delivery-audit-v1','passed':True,
               'case_id':self.case_ids[0],'job_id':7,'attempt':1,'recording_id':rid,
               'frames':1,'source_result_sha256':sha(attempt/'result.json'),
               'video':'video.webm','video_sha256':sha(attempt/'video.webm'),
               'trace':'trace.json','trace_sha256':sha(attempt/'trace.json'),
               'checks':{key:True for key in ('native_source','all_participants','time_join',
                        'full_video_decode','actual_pixels','physical_completion')}}
        write(attempt/'audit.json',audit)
        job={'id':7,'stage':'execution','status':'completed','attempts':1,
             'actor':'motor_vehicle_driver','artifact_id':'artifact',
             'payload':json.dumps({'cell':{'cell_id':'C1'},'case':{
                 'case_id':self.case_ids[0],'target_law_id':'LAW-1'}})}
        class FakeDB:
            def execute(self,*args):return self
            def fetchone(self):return (1,)
            def close(self):pass
        class FakeStore:
            def __init__(self,path):self.db=FakeDB()
            def job(self,ident):return job
            def artifact(self,ident):return {'payload':{'completion':{'binding':{}}}}
        with (patch('batch_pipeline.store.Store',FakeStore),
              patch('worker_exchange.execution_manifest.validate',return_value={
                  'cases':[{'case_id':self.case_ids[0],'kind':'delivery'}]}),
              patch('worker_exchange.delivery_handoff.validate_case'),
              patch('recording_store.stored_attempt_path',return_value=attempt),
              patch('batch_pipeline.completion.verify'),
              patch('worker_exchange.media.audit'),
              patch('organize_work.refresh_workspaces')):
            audit['passed']=False
            write(attempt/'audit.json',audit)
            with self.assertRaisesRegex(ValueError,'audit incomplete'):
                accept(root,self.repo,'batch',db,'run',self.aid,self.case_ids[0],7,1,attempt/'audit.json')
            for sid in ('demo-test','full-test'):
                self.assertEqual(read(root/'sets'/sid/'selection.json')['members'],[])
            audit['passed']=True
            write(attempt/'audit.json',audit)
            result=accept(root,self.repo,'batch',db,'run',self.aid,self.case_ids[0],7,1,attempt/'audit.json')
        self.assertEqual(result['recording_id'],rid)
        for sid in ('demo-test','full-test'):
            self.assertEqual(read(root/'sets'/sid/'selection.json')['members'][0]['recording_id'],rid)


if __name__ == '__main__': unittest.main()
