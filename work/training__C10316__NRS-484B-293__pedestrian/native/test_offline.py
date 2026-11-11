import json
from pathlib import Path
import tempfile
import unittest

from engineering import candidate
from fallback_triggers import measure as measure_fallback
from geometry import check as geometry_check
from measure_crosswalk import measure
from finalize import derive_channels
from runner import cameras,check


class CrosswalkOffline(unittest.TestCase):
    def test_exact_bundle_check(self):
        config=json.loads(Path('config.json').read_text())
        result=check(config)
        self.assertFalse(result['native_imported'])
        self.assertFalse(result['physical_success_claimed'])
        self.assertEqual(len(result['camera_names']),4)
        self.assertEqual(result['camera_names'],
                         ['overview','approach','reference_corner','driver_reference'])

    def test_distinct_alternatives(self):
        config=json.loads(Path('config.json').read_text())
        suffix=config['case_suffix']
        plans=[candidate(suffix,ident) for ident in ('primary','fallback1','fallback2','fallback3')]
        self.assertEqual(len({json.dumps(p['engineering'],sort_keys=True) for p in plans}),4)
        self.assertEqual(len({p['case_id'] for p in plans}),1)
        self.assertEqual([(c['width'],c['height']) for c in cameras(plans[0])],
                         [(1920,1080),(1280,720),(1280,720),(1280,720)])

    def test_authored_geometry(self):
        result=geometry_check()
        self.assertEqual(result['crosswalk_length_m'],4)
        self.assertEqual(result['crosswalk_width_m'],3)

    def test_missing_original_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            (path/'crosswalk-context.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'Missing required source: native_samples.jsonl'):
                measure(path/'native_samples.jsonl',path/'crosswalk-context.json')

    def test_fallback_source_digest_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'observations.jsonl'
            path.write_text('{"source_kind":"synthetic_cpu_fixture"}\n')
            with self.assertRaisesRegex(ValueError,'Changed fallback observation source'):
                measure_fallback(path,'0'*64)

    def test_channels_rebuilt_from_raw_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            sample={'native_frame':100,'time_s':0.0,'crosswalk_id':'marked',
                    'pedestrian_xy_m':[1.0,2.0],'pedestrian_forward_xy':[1.0,0.0],
                    'pedestrian_footprint_xy_m':[[0,1],[2,1],[2,3],[0,3]],
                    'speed_mps':0.5}
            frame={'video_frame':0,'native_frame':100,'carla_frame':100,'time_s':0.0}
            (path/'native_samples.jsonl').write_text(json.dumps(sample)+'\n')
            (path/'video_frames.jsonl').write_text(json.dumps(frame)+'\n')
            (path/'channels').mkdir()
            (path/'channels/kin.position.jsonl').write_text('stale fixture channel\n')
            config={'recording_description':{'channels':[{'name':name} for name in
                ('kin.position','kin.heading','rel.occupies','native_pedestrian_pose','camera_frame_join')]}}
            derive_channels(path,config,1)
            position=json.loads((path/'channels/kin.position.jsonl').read_text())
            join=json.loads((path/'channels/camera_frame_join.jsonl').read_text())
            self.assertEqual(position['value'],[1.0,2.0])
            self.assertEqual(join['value'],frame)


if __name__=='__main__':unittest.main()
