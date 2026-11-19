import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze import analyze_rows, verify_media


def source_rows(count=600):
    frames, actors = [], []
    for index in range(count):
        x = -5 if index < 300 else 0
        vertices = [[x+dx,dy,z] for z in (0, 1)
                    for dx,dy in ((-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5))]
        frames.append({'video_frame':index,'carla_frame':100+index,
                       'native_frame':100+index,'time_s':index*.05})
        actors.append({'video_frame':index,'frame':100+index,
            'time_s':index*.05,
            'source_kind':'original_carla_actor_and_map_readback',
            'warning_person_actor_id':12,
            'warning_person_type_id':'walker.pedestrian.0001',
            'warning_person_xyz_m':[2,0,0],
            'ego_body_vertices_xyz_m':vertices})
    return frames,actors


READBACK={'warning_person_actor_id':12,
          'plan':{'repair_polygon_xy_m':[[-1,-1],[1,-1],[1,1],[-1,1]]}}


class SourceAnalysisTest(unittest.TestCase):
    def test_measures_full_duration_and_body_contact(self):
        frames,actors=source_rows()
        result=analyze_rows(frames,actors,READBACK)
        self.assertEqual(result['source_frames'],600)
        self.assertAlmostEqual(result['source_elapsed_s'],30)
        self.assertEqual(result['pavement_footprint_contact_frames'],list(range(300,600)))
        self.assertFalse(result['warning_act_verified'])

    def test_rejects_short_or_broken_join(self):
        frames,actors=source_rows(599)
        with self.assertRaisesRegex(ValueError,'600 joined'):
            analyze_rows(frames,actors,READBACK)
        frames,actors=source_rows()
        actors[400]['frame']+=1
        with self.assertRaisesRegex(ValueError,'frame join'):
            analyze_rows(frames,actors,READBACK)

    def test_decodes_four_short_diagnostic_videos(self):
        names=('overview','approach','reference_corner','driver_reference')
        specs=[(name,16,16,90,(0,0,0),0) for name in names]
        with tempfile.TemporaryDirectory() as directory:
            for name in names:
                subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi',
                    '-i','color=c=black:s=16x16:r=20','-frames:v','3','-c:v','ffv1',
                    str(Path(directory)/(name+'.mkv'))],check=True)
            media=verify_media(directory,3,camera_specs=specs)
            self.assertEqual([m['name'] for m in media],list(names))
            self.assertTrue(all(m['decoded_frames']==3 for m in media))


if __name__=='__main__':
    unittest.main()
