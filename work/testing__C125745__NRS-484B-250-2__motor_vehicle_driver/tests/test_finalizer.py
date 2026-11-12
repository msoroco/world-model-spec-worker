import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(REPO/'runtime'/'scenario_pipeline'))
from finalizer import finalize
from runner import ASSIGNMENT
import test_simultaneous_entries as entry_test_module


class FinalizerTests(unittest.TestCase):
    def attempt(self,root):
        entry_test_module.EntryTests().fixture(root)
        cfg={'assignment_id':ASSIGNMENT,'law_id':'NRS-484B-250-2',
             'cell_id':'C125745','actor':'motor_vehicle_driver',
             'selected_case_id':ASSIGNMENT+'__stop_ego_left_near_time',
             'duration_s':.15,'rate_hz':20,'required_atoms':[],
             'recording_description':{}}
        (root/'config.json').write_text(json.dumps(cfg))
        (root/'trace.jsonl').write_text('')
        (root/'capture').mkdir()
        (root/'capture'/'evidence.jsonl').write_text('')
        for name in ('overview','approach','reference_corner','driver_reference'):
            (root/(name+'.mkv')).write_bytes(b'synthetic-test-placeholder')
        rows=[json.loads(line) for line in (root/'crossing_history.jsonl').read_text().splitlines()]
        controls=[{'frame':row['frame'],'time_s':row['time_s'],
                   'ego_stopped_once':True,'other_conflict_clear':False,
                   'commands':{'ego':{'throttle':0.,'brake':1.,'speed_mps':0.}}}
                  for row in rows]
        (root/'controller_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in controls))
        ctx=json.loads((root/'junction_context.json').read_text())
        ctx['physical_acceptance_claimed']=False
        (root/'junction_context.json').write_text(json.dumps(ctx))

    def test_saved_original_source_analysis_and_native_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.attempt(root)
            measured=finalize(root,root/'saved-analysis.json')
            self.assertEqual(set(measured),{'crossing_identity','entry_timing',
                'relative_right_side','device_qualification_context',
                'opposite_left_turn_context','yield_observation'})
            result=json.loads((root/'result.json').read_text())
            self.assertFalse(result['physical_acceptance_claimed'])
            self.assertEqual(result['case_id'],ASSIGNMENT+'__stop_ego_left_near_time')
            self.assertEqual(json.loads((root/'saved-analysis.json').read_text())
                             ['measurements']['entry_timing']['value']
                             ['approximately_same_time_judgment'],'unresolved')
            self.assertEqual(len((root/'channels'/'entry_timing.jsonl').read_text().splitlines()),3)

    def test_missing_source_fails_before_creating_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.attempt(root)
            (root/'controller_history.jsonl').unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source: controller_history.jsonl'):
                finalize(root,root/'saved-analysis.json')
            self.assertFalse((root/'result.json').exists())

    def test_held_control_must_join_original_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.attempt(root)
            rows=[json.loads(line) for line in (root/'controller_history.jsonl').read_text().splitlines()]
            rows[1]['frame']=999
            (root/'controller_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'original-frame join'):
                finalize(root,root/'saved-analysis.json')
            self.assertFalse((root/'channels').exists())

    def test_opposite_exception_requires_controller_intention(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.attempt(root)
            cfg=json.loads((root/'config.json').read_text())
            cfg['selected_case_id']=ASSIGNMENT+'__stop_opposite_left_turn'
            (root/'config.json').write_text(json.dumps(cfg))
            ctx=json.loads((root/'junction_context.json').read_text())
            ctx.update({'approach_relation':'opposite_directions',
                        'other_highway_id':ctx['ego_highway_id'],
                        'other_approach_forward_xy':[-1,0],
                        'turn_intent_source':'controller_history.jsonl'})
            (root/'junction_context.json').write_text(json.dumps(ctx))
            rows=[json.loads(line) for line in (root/'crossing_history.jsonl').read_text().splitlines()]
            for row in rows:row['other_left_turn_intended']=True
            rows[0]['other']['body_vertices_xy_m']=[[x+30,y] for x,y in
                ((-1,-1),(-1,1),(1,1),(1,-1))]
            (root/'crossing_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            controls=[json.loads(line) for line in (root/'controller_history.jsonl').read_text().splitlines()]
            for row in controls:row['other_left_turn_intended']=True
            (root/'controller_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in controls))
            measured=finalize(root,root/'saved-analysis.json')
            self.assertTrue(measured['opposite_left_turn_context']['value']['opposite_approach'])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.attempt(root)
            cfg=json.loads((root/'config.json').read_text())
            cfg['selected_case_id']=ASSIGNMENT+'__stop_opposite_left_turn'
            (root/'config.json').write_text(json.dumps(cfg))
            ctx=json.loads((root/'junction_context.json').read_text())
            ctx.update({'approach_relation':'opposite_directions',
                        'other_highway_id':ctx['ego_highway_id'],
                        'other_approach_forward_xy':[-1,0],
                        'turn_intent_source':'controller_history.jsonl'})
            (root/'junction_context.json').write_text(json.dumps(ctx))
            rows=[json.loads(line) for line in (root/'crossing_history.jsonl').read_text().splitlines()]
            for row in rows:row['other_left_turn_intended']=True
            rows[0]['other']['body_vertices_xy_m']=[[x+30,y] for x,y in
                ((-1,-1),(-1,1),(1,1),(1,-1))]
            (root/'crossing_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError,'controller intention missing'):
                finalize(root,root/'saved-analysis.json')

if __name__=='__main__':unittest.main()
