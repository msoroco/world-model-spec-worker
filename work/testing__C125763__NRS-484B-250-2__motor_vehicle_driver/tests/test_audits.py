import copy
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


def _write_rows(path,rows):
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))


def build_attempt(root,variant='left',map_name=None):
    root.mkdir()
    finalizer_fixture.FinalizerTests().attempt(root)
    cfg=json.loads((root/'config.json').read_text())
    cfg['duration_s']=.25
    suffix={'left':'yield_ego_left_near_time',
            'right':'yield_ego_right_near_time',
            'separated':'yield_ego_left_separated'}[variant]
    cfg['selected_case_id']=ASSIGNMENT+'__'+suffix
    cfg['other_release_frame']=0 if variant=='separated' else 2
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
            report=audit_pair('yield_sign_relative_side',left,right)
            self.assertTrue(report['software_comparison_passed'])
            self.assertEqual(report['entry_time_differences_s'][0],
                             report['entry_time_differences_s'][1])
            context=json.loads((right/'junction_context.json').read_text())
            context['intersection_id']=999
            (right/'junction_context.json').write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError,'source hash differs'):
                audit_pair('yield_sign_relative_side',left,right)
            changed=build_attempt(parent/'changed','right',map_name='DifferentTown')
            with self.assertRaisesRegex(ValueError,'Fixed crossing'):
                audit_pair('yield_sign_relative_side',left,changed)

    def test_timing_comparison_and_declared_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp)
            left=build_attempt(parent/'left')
            right=build_attempt(parent/'right','right')
            separated=build_attempt(parent/'separated','separated')
            report=audit_comparisons(ROOT,{
                ASSIGNMENT+'__yield_ego_left_near_time':left,
                ASSIGNMENT+'__yield_ego_right_near_time':right,
                ASSIGNMENT+'__yield_ego_left_separated':separated})
            self.assertEqual(len(report['comparisons']),2)
            self.assertLess(report['comparisons'][1]['entry_time_differences_s'][0],
                            report['comparisons'][1]['entry_time_differences_s'][1])
            self.assertFalse(report['delivery_ready'])
            with self.assertRaisesRegex(ValueError,'Missing exact comparison attempt'):
                audit_comparisons(ROOT,{ASSIGNMENT+'__yield_ego_left_near_time':left})

if __name__=='__main__':unittest.main()
