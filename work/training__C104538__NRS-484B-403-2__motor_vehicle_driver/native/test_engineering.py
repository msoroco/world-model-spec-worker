"""Two controlled case policies and three isolated saved-source fallback gates."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from engineering import evaluate_fallbacks,parameters
from measure_u_turn import sha

HERE=Path(__file__).resolve().parent.parent


class EngineeringTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)

    def copy_case(self,suffix):
        source=HERE/'draft-u-turn-saved'/('straight' if suffix=='witness_1' else 'u_turn')
        folder=self.root/suffix
        shutil.copytree(source,folder)
        shutil.copyfile(folder/'approach-video-fixture.txt',folder/'approach.mkv')
        return folder

    def refresh(self,folder):
        review=folder/'sign-review.json'
        packet=json.loads(review.read_text())
        packet['native_samples_sha256']=sha(folder/'native_samples.jsonl')
        packet['frame_map_sha256']=sha(folder/'video_frames.jsonl')
        packet['video_sha256']=sha(folder/'approach.mkv')
        review.write_text(json.dumps(packet))

    def test_four_distinct_policies_hold_law_and_route(self):
        for suffix in ('witness_1','witness_2'):
            plans={name:parameters(suffix,name) for name in
                   ('primary','fallback1','fallback2','fallback3')}
            for plan in plans.values():
                self.assertEqual(plan['law_id'],'NRS-484B-403-2')
                self.assertEqual(plan['native_route_xy_m'],plans['primary']['native_route_xy_m'])
                self.assertFalse(plan['selected'])
            self.assertNotEqual(plans['fallback1']['target_speed_mps'],plans['primary']['target_speed_mps'])
            self.assertNotEqual(plans['fallback2']['lookahead_m'],plans['primary']['lookahead_m'])
            self.assertNotEqual(plans['fallback3']['sign_camera_xyz_m'],plans['primary']['sign_camera_xyz_m'])

    def test_isolated_source_measured_triggers_for_both_cases(self):
        for suffix in ('witness_1','witness_2'):
            with self.subTest(suffix=suffix):
                folder=self.copy_case(suffix)
                self.assertEqual([evaluate_fallbacks(folder,suffix)[f'fallback{i}'] for i in (1,2,3)],
                                 [False,False,False])
                samples=folder/'native_samples.jsonl'
                original=samples.read_text();rows=[json.loads(line) for line in original.splitlines()]
                rows[40]['native_center_xy_m'][1]+=.5
                for point in rows[40]['native_body_xy_m']:point[1]+=.5
                samples.write_text(''.join(json.dumps(row)+'\n' for row in rows));self.refresh(folder)
                self.assertEqual([evaluate_fallbacks(folder,suffix)[f'fallback{i}'] for i in (1,2,3)],
                                 [True,False,False])
                samples.write_text(original);self.refresh(folder)
                rows=[json.loads(line) for line in original.splitlines()]
                if suffix=='witness_2':
                    rows[-1]['native_lane_id']=-1
                else:
                    rows[-1]['native_lane_id']=1
                samples.write_text(''.join(json.dumps(row)+'\n' for row in rows));self.refresh(folder)
                self.assertEqual([evaluate_fallbacks(folder,suffix)[f'fallback{i}'] for i in (1,2,3)],
                                 [False,True,False])
                samples.write_text(original);self.refresh(folder)
                review=folder/'sign-review.json';packet=json.loads(review.read_text())
                packet['full_body_and_sign_visible_frames']=113;review.write_text(json.dumps(packet))
                self.assertEqual([evaluate_fallbacks(folder,suffix)[f'fallback{i}'] for i in (1,2,3)],
                                 [False,False,True])


if __name__=='__main__':unittest.main()
