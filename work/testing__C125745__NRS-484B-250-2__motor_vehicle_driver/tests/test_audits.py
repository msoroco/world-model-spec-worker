import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(REPO/'runtime'/'scenario_pipeline'))
import test_finalizer as finalizer_fixture
from finalizer import finalize
from runner import ASSIGNMENT
from audit_delivery import audit as audit_delivery
from audit_comparisons import audit_pair,audit as audit_comparisons
from audit_compatibility_comparisons import audit_surrogate_grid,audit_opposite_context,audit_device_context,audit_turn_trajectory,audit_turn_diagnostic,audit_exact_sweeps,compare_exact_sweeps,require_sweep_declarations,SWEEP_AXES


def _write_rows(path,rows):
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))


def build_attempt(root,variant='left',map_name=None):
    root.mkdir()
    finalizer_fixture.FinalizerTests().attempt(root)
    cfg=json.loads((root/'config.json').read_text())
    cfg['duration_s']=.25
    suffix={'left':'stop_ego_left_near_time',
            'right':'stop_ego_right_near_time',
            'separated':'stop_ego_left_separated'}[variant]
    cfg['selected_case_id']=ASSIGNMENT+'__'+suffix
    (root/'config.json').write_text(json.dumps(cfg))
    context=json.loads((root/'junction_context.json').read_text())
    context['other_approach_forward_xy']=[0,-1] if variant=='right' else [0,1]
    if map_name is not None:context['native_map_id']=map_name
    (root/'junction_context.json').write_text(json.dumps(context))
    history=[json.loads(line) for line in (root/'crossing_history.jsonl').read_text().splitlines()]
    frames=[json.loads(line) for line in (root/'video_frames.jsonl').read_text().splitlines()]
    controls=[json.loads(line) for line in (root/'controller_history.jsonl').read_text().splitlines()]
    if variant=='right':
        history[0]['other']['body_vertices_xy_m']=[[x,y+10] for x,y in
            ((-1,-1),(-1,1),(1,1),(1,-1))]
    for i in (3,4):
        new=copy.deepcopy(history[-1]);new['frame']=100+i;new['time_s']=1+i*.05
        history.append(new)
        frame={'video_frame':i,'carla_frame':100+i,'time_s':1+i*.05}
        frames.append(frame)
        control=copy.deepcopy(controls[-1]);control['frame']=100+i
        control['time_s']=1+i*.05;controls.append(control)
    if variant=='separated':
        for i in (2,3):
            history[i]['ego']['body_vertices_xy_m']=[[x,y] for x,y in
                ((-1,-1),(-1,1),(1,1),(1,-1))]
    _write_rows(root/'crossing_history.jsonl',history)
    _write_rows(root/'video_frames.jsonl',frames)
    _write_rows(root/'controller_history.jsonl',controls)
    finalize(root,root/'saved-analysis.json')
    return root


class AuditTests(unittest.TestCase):
    def test_short_saved_diagnostic_requires_explicit_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=build_attempt(Path(tmp)/'short')
            config=json.loads((root/'config.json').read_text())
            config['duration_s']=.3
            (root/'config.json').write_text(json.dumps(config))
            result=json.loads((root/'result.json').read_text())
            result['diagnostic_fixture']=True
            result['provenance_kind']='synthetic_fixture'
            result['source_evidence_hashes']['config.json']=hashlib.sha256(
                (root/'config.json').read_bytes()).hexdigest()
            (root/'result.json').write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError,'Incomplete original frame count'):
                audit_delivery(root)
            report=audit_delivery(root,diagnostic=True)
            self.assertTrue(report['diagnostic_fixture'])
            self.assertFalse(report['delivery_ready'])
            (root/'approach.mkv').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'source hash differs'):
                audit_delivery(root,diagnostic=True)

    def test_exact_sweep_comparison_rejects_changed_source_and_fixed_actor(self):
        plan=json.loads((ROOT/'case-plan.json').read_text())
        declared=require_sweep_declarations(plan)
        self.assertEqual(len(declared),5)
        broken=copy.deepcopy(plan)
        broken['comparisons'][-2]['case_ids'].reverse()
        with self.assertRaisesRegex(ValueError,'sweep comparison declaration'):
            require_sweep_declarations(broken)
        broken=copy.deepcopy(plan)
        broken['comparisons'][-1]['case_ids'].reverse()
        with self.assertRaisesRegex(ValueError,'opposite-context comparison declaration'):
            require_sweep_declarations(broken)
        report=audit_exact_sweeps()
        self.assertTrue(report['source_integrity_passed'])
        self.assertEqual(len(report['axes']),2)
        self.assertFalse(report['delivery_ready'])
        manifest=json.loads((ROOT/'execution-manifest.json').read_text())
        entries={row['case_id']:row for row in manifest['cases']}
        receipts={suffix:json.loads((ROOT/entries[ASSIGNMENT+'__'+suffix]
                                    ['compatibility']['receipt']).read_text())
                  for group in SWEEP_AXES.values() for suffix in group}
        changed=copy.deepcopy(receipts)
        (changed['c125745-1-0002']['measurement_examples']['entry_timing']
         ['sources']['crossing_history.jsonl'])='0'*64
        with self.assertRaisesRegex(ValueError,'source hash differs'):
            compare_exact_sweeps(changed)
        changed=copy.deepcopy(receipts)
        (changed['c125745-2-0002']['measurement_examples']['entry_timing']
         ['value']['first_body_entry']['other']['frame'])=1095
        with self.assertRaisesRegex(ValueError,'entry time|moving actor'):
            compare_exact_sweeps(changed)

    def test_opposite_turn_trajectory_requires_observed_exit(self):
        diagnostic=json.loads((ROOT/'fourth-diagnostic.json').read_text())
        files=diagnostic['files']
        context=json.loads(files['junction_context.json'])
        crossing=[json.loads(line) for line in files['crossing_history.jsonl'].splitlines()]
        controls=[json.loads(line) for line in files['controller_history.jsonl'].splitlines()]
        frames=[json.loads(line) for line in files['video_frames.jsonl'].splitlines()]
        report=audit_turn_trajectory(context,crossing,controls,frames)
        self.assertEqual(report['trajectory_status'],'unverified')
        bound=audit_turn_diagnostic(ROOT/'fourth-diagnostic.json')
        self.assertEqual(bound['trajectory_status'],'unverified')
        self.assertEqual(len(bound['source_sha256']),4)
        self.assertIsNone(report['exit_frame'])
        self.assertFalse(report['physical_acceptance_claimed'])
        for y,expected in [(-12,'met'),(12,'not_met')]:
            body=copy.deepcopy(crossing[-1]);body['frame']=103;body['time_s']=1.15
            body['other']['body_vertices_xy_m']=[[14,y-1],[14,y+1],[16,y+1],[16,y-1]]
            control=copy.deepcopy(controls[-1]);control['frame']=103;control['time_s']=1.15
            frame={'video_frame':3,'carla_frame':103,'time_s':1.15}
            outcome=audit_turn_trajectory(context,crossing+[body],controls+[control],frames+[frame])
            self.assertEqual(outcome['trajectory_status'],expected)
            self.assertEqual(outcome['exit_frame'],103)
            self.assertFalse(outcome['legal_acceptance_claimed'])
        changed=copy.deepcopy(controls);changed[1]['other_left_turn_intended']=False
        with self.assertRaisesRegex(ValueError,'Recorded left-turn intent'):
            audit_turn_trajectory(context,crossing,changed,frames)
        changed=copy.deepcopy(frames);changed[1]['carla_frame']=999
        with self.assertRaisesRegex(ValueError,'Original frame/time join'):
            audit_turn_trajectory(context,crossing,controls,changed)

    def test_device_context_receipts_require_fixed_sign_sources_and_open_review(self):
        names={
            'stop_ego_left_near_time':'primary-compatibility-receipt-v3.json',
            'stop_ego_right_near_time':'second-primary-compatibility-receipt-v2.json',
            'stop_ego_left_separated':'third-primary-compatibility-receipt-v2.json',
            'stop_opposite_left_turn':'fourth-primary-compatibility-receipt-v1.json',
        }
        receipts={suffix:json.loads((ROOT/file).read_text()) for suffix,file in names.items()}
        report=audit_device_context(receipts)
        self.assertTrue(report['fixed_sign_and_source_contract_passed'])
        self.assertFalse(report['delivery_ready'])
        changed=copy.deepcopy(receipts)
        changed['stop_ego_left_separated']['fixture_manifest'].pop('overview.mkv')
        with self.assertRaisesRegex(ValueError,'four original camera'):
            audit_device_context(changed)
        changed=copy.deepcopy(receipts)
        changed['stop_opposite_left_turn']['measurement_examples']['device_qualification_context']['value']['official_device_judgment']='official'
        with self.assertRaisesRegex(ValueError,'unresolved official-device review'):
            audit_device_context(changed)

    def test_opposite_context_receipts_preserve_crossing_sign_and_open_judgment(self):
        receipts={
            'stop_ego_left_near_time':json.loads((ROOT/'primary-compatibility-receipt-v3.json').read_text()),
            'stop_opposite_left_turn':json.loads((ROOT/'fourth-primary-compatibility-receipt-v1.json').read_text()),
        }
        report=audit_opposite_context(receipts)
        self.assertTrue(report['opposite_approach_contrast_passed'])
        self.assertFalse(report['delivery_ready'])
        changed=copy.deepcopy(receipts)
        changed['stop_opposite_left_turn']['measurement_examples']['device_qualification_context']['value']['native_stop_sign_id']=999
        with self.assertRaisesRegex(ValueError,'Fixed stop-sign identity'):
            audit_opposite_context(changed)
        changed=copy.deepcopy(receipts)
        changed['stop_opposite_left_turn']['measurement_examples']['opposite_left_turn_context']['value']['exception_judgment']='left turn proved'
        with self.assertRaisesRegex(ValueError,'unresolved turn judgment'):
            audit_opposite_context(changed)

    def test_independent_surrogate_grid_audit_and_tamper_rejection(self):
        from build_primary_diagnostic import build
        with tempfile.TemporaryDirectory() as tmp:
            for axis,values in [('other_release_frame',(32,40,48)),
                                ('ego_hold_after_clear_frames',(0,8,16))]:
                points={}
                for value in values:
                    folder=Path(tmp)/'work'/(axis+str(value))
                    folder.mkdir(parents=True)
                    config_name='third-config.json' if axis=='ego_hold_after_clear_frames' else 'config.json'
                    for name in (config_name,'site.json'):
                        (folder/name).write_bytes((ROOT/name).read_bytes())
                    build(folder,surrogate=True,
                          config_name=config_name,
                          diagnostic_name='third-diagnostic.json' if axis=='ego_hold_after_clear_frames' else 'diagnostic.json',
                          recipe_name='third-diagnostic-recipe.json' if axis=='ego_hold_after_clear_frames' else 'diagnostic-recipe.json',
                          other_release_frame=value if axis=='other_release_frame' else 40,
                          ego_hold_after_clear_frames=value if axis=='ego_hold_after_clear_frames' else 0)
                    points[value]=folder/('third-diagnostic.json' if axis=='ego_hold_after_clear_frames' else 'diagnostic.json')
                report=audit_surrogate_grid(points,axis)
                self.assertTrue(report['source_integrity_passed'])
                self.assertFalse(report['delivery_ready'])
                self.assertEqual(len(report['points']),3)
                target=points[values[-1]]
                target.write_text(target.read_text()+' ')
                with self.assertRaisesRegex(ValueError,'hash differs'):
                    audit_surrogate_grid(points,axis)

    def test_independent_source_audit_rehashes_and_rejects_stale_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=build_attempt(Path(tmp)/'left')
            report=audit_delivery(root)
            self.assertTrue(report['software_source_integrity_passed'])
            self.assertFalse(report['delivery_ready'])
            (root/'approach.mkv').write_bytes(b'altered')
            with self.assertRaisesRegex(ValueError,'source hash differs'):
                audit_delivery(root)

    def test_relative_side_comparison_checks_fixed_timing_and_crossing(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp)
            left=build_attempt(parent/'left')
            right=build_attempt(parent/'right','right')
            report=audit_pair('stop_sign_relative_side',left,right)
            self.assertTrue(report['software_comparison_passed'])
            self.assertEqual(report['entry_time_differences_s'][0],
                             report['entry_time_differences_s'][1])
            context=json.loads((right/'junction_context.json').read_text())
            context['intersection_id']=999
            (right/'junction_context.json').write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError,'source hash differs'):
                audit_pair('stop_sign_relative_side',left,right)
            changed=build_attempt(parent/'changed','right',map_name='DifferentTown')
            with self.assertRaisesRegex(ValueError,'Fixed crossing'):
                audit_pair('stop_sign_relative_side',left,changed)

    def test_timing_comparison_and_declared_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp)
            left=build_attempt(parent/'left')
            right=build_attempt(parent/'right','right')
            separated=build_attempt(parent/'separated','separated')
            report=audit_comparisons(ROOT,{
                ASSIGNMENT+'__stop_ego_left_near_time':left,
                ASSIGNMENT+'__stop_ego_right_near_time':right,
                ASSIGNMENT+'__stop_ego_left_separated':separated})
            self.assertEqual(len(report['comparisons']),2)
            self.assertLess(report['comparisons'][1]['entry_time_differences_s'][0],
                            report['comparisons'][1]['entry_time_differences_s'][1])
            self.assertFalse(report['delivery_ready'])
            with self.assertRaisesRegex(ValueError,'Missing exact comparison attempt'):
                audit_comparisons(ROOT,{ASSIGNMENT+'__stop_ego_left_near_time':left})

if __name__=='__main__':unittest.main()
