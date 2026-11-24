"""Synthetic original-shaped tests; no real sidewalk or audible-human claim."""
import copy
import importlib.util
import json
import struct
import tempfile
import unittest
import wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('c142510_sidewalk',ROOT/'sidewalk_overtake.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def body(x,y):return [[x-.1,y-.1],[x+.1,y-.1],[x+.1,y+.1],[x-.1,y+.1]]


class SidewalkTest(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        self.site={'assignment_id':m.ASSIGNMENT,'cell_id':'C142510',
            'case_id':m.ASSIGNMENT+'__signal_before', 'reviewer':'synthetic fixture',
            'sidewalk_source_citation':'fixture sidewalk','sidewalk_id':'walk A',
            'connected_route_citation':'fixture route','microphone_calibration_source':'fixture sound',
            'physical_surface_kind':'sidewalk','sidewalk_connected':True,
            'rider_kind':'bicycle','rider_actor_id':11,'pedestrian_actor_id':22,
            'sidewalk_travel_unit_xy':[1,0],
            'sidewalk_polygon_xy_m':[[-5,-1],[5,-1],[5,1],[-5,1]],
            'microphone_sample_rate_hz':1000,'microphone_start_time_s':0.0,
            'signal_rms_detection_threshold':.1}
        self.rider=self.rows(11,[-2,-1.5,-.5,.5,1.5])
        self.pedestrian=self.rows(22,[0]*5)
        self.sound_start=50
        self.write()

    @staticmethod
    def rows(actor,xs):
        return [{'frame':100+i,'time_s':i*.05,'actor_id':actor,
                 'body_vertices_xy_m':body(x,0),
                 **({'rider_speed_mps':2.0,'rider_brake_applied':i==1} if actor==11 else {})}
                for i,x in enumerate(xs)]

    def write(self):
        (self.root/'road.xodr').write_text('<OpenDRIVE fixture="true"/>')
        self.site['map_sha256']=m.sha(self.root/'road.xodr')
        self.site['sidewalk_map_sha256']=self.site['map_sha256']
        (self.root/'site-context.json').write_text(json.dumps(self.site))
        for name,rows in (('rider',self.rider),('pedestrian',self.pedestrian)):
            (self.root/f'{name}-body-history.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
        samples=[0]*500
        if self.sound_start is not None:
            for i in range(self.sound_start,min(self.sound_start+50,len(samples))):
                samples[i]=10000
        with wave.open(str(self.root/'pedestrian-microphone.wav'),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(1000)
            w.writeframes(struct.pack('<'+'h'*len(samples),*samples))
        (self.root/'source-manifest.json').write_text(json.dumps({name:{
            'kind':'original_native','sha256':m.sha(self.root/name)} for name in m.SOURCES}))

    def test_original_pass_and_detected_prepass_audio(self):
        result=m.measure(self.root)
        self.assertEqual(result['pass_frame'],103)
        self.assertTrue(result['detected_signal_before_pass'])
        self.assertAlmostEqual(result['pass_bracket_s'][0],.1)
        self.assertAlmostEqual(result['pass_bracket_s'][1],.15)
        self.assertEqual(result['audible_to_pedestrian'],'unresolved_physical_and_legal_review')
        self.assertFalse(result['legal_verdict_claimed'])

    def test_late_signal_pair_and_fixed_context(self):
        early=m.measure(self.root)
        self.site['case_id']=m.ASSIGNMENT+'__signal_late'
        self.sound_start=200;self.write()
        late=m.measure(self.root)
        self.assertFalse(late['detected_signal_before_pass'])
        self.assertEqual(m.compare(early,late)['declared_difference'],'signal_timing')
        changed=copy.deepcopy(late);changed['sidewalk_id']='different'
        with self.assertRaisesRegex(ValueError,'fixed comparison condition'):
            m.compare(early,changed)

    def test_missing_stale_and_non_sidewalk_rejected(self):
        (self.root/'pedestrian-microphone.wav').unlink()
        with self.assertRaisesRegex(ValueError,'missing or stale original source'):
            m.measure(self.root)
        self.write();(self.root/'road.xodr').write_text('changed')
        with self.assertRaisesRegex(ValueError,'missing or stale original source'):
            m.measure(self.root)
        self.write();self.site['physical_surface_kind']='nonmotorized_trail';self.write()
        with self.assertRaisesRegex(ValueError,'connected sidewalk'):
            m.measure(self.root)

    def test_bad_frame_actor_and_unrealized_pass_rejected(self):
        self.pedestrian[2]['frame']+=1;self.write()
        with self.assertRaisesRegex(ValueError,'frame/time join'):
            m.measure(self.root)
        self.pedestrian[2]['frame']-=1
        self.rider[2]['actor_id']=99;self.write()
        with self.assertRaisesRegex(ValueError,'actor identity'):
            m.measure(self.root)
        self.rider=self.rows(11,[-2,-1.8,-1.6,-1.4,-1.2]);self.write()
        with self.assertRaisesRegex(ValueError,'did not overtake'):
            m.measure(self.root)

    def test_silent_microphone_is_observed_missing_signal(self):
        self.sound_start=None;self.write()
        result=m.measure(self.root)
        self.assertIsNone(result['microphone']['onset_time_s'])
        self.assertFalse(result['detected_signal_before_pass'])

    def test_rider_response_pair_uses_original_brake_history(self):
        braking=m.measure(self.root)
        self.site['case_id']=m.ASSIGNMENT+'__signal_before_advance'
        for row in self.rider:row['rider_brake_applied']=False
        self.write()
        advancing=m.measure(self.root)
        self.assertEqual(m.compare(braking,advancing,'rider_response')['declared_difference'],
                         'rider_response')
        self.rider[0].pop('rider_speed_mps');self.write()
        with self.assertRaisesRegex(ValueError,'speed or brake source'):
            m.measure(self.root)


if __name__=='__main__':unittest.main()
