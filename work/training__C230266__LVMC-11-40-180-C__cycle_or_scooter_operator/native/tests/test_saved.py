import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from measure_sidewalk import measure

NAMES=('overview','approach','reference_corner','driver_reference')


def write_fixture(root, signal_frame=80, pause_requested=True):
    root=Path(root)
    actors=[];mapping=[];images=[];mic_frames=[]
    for i in range(600):
        time_s=i/20
        pause=pause_requested and 80<=i<110
        elapsed=time_s-(1.5 if i>=110 else max(0,time_s-4) if pause else 0)
        rx=-10+1.4*elapsed;px=.3*time_s
        frame=10000+i
        actors.append({'video_frame':i,'native_frame':frame,'time_s':time_s,
            'rider_id':17,'pedestrian_id':19,
            'rider_xyz_m':[rx,-4.5,0], 'pedestrian_xyz_m':[px,-5.7,0],
            'rider_bbox_extent_xyz_m':[.45,.3,.5],
            'pedestrian_bbox_extent_xyz_m':[.35,.3,.9],
            'rider_velocity_xyz_mps':[0 if pause else 1.4,0,0]})
        mapping.append({'video_frame':i,'native_frame':frame,'carla_frame':frame,'time_s':time_s,
            'camera_native_frames':{name:frame for name in NAMES}})
        mic_frames.append({'video_frame':i,'native_frame':frame,
                           'monotonic_ns':1_700_000_000+50_000_000*i,
                           'pedestrian_id':19})
        for name in NAMES:
            images.append({'video_frame':i,'native_frame':frame,'camera':name})
    for name,rows in (('sidewalk-actors.jsonl',actors),('video_frames.jsonl',mapping),
                      ('camera-frames.jsonl',images),('pedestrian-microphone-frames.jsonl',mic_frames)):
        (root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
    raw=bytearray(30*8000*2)
    if signal_frame is not None:
        for sample in range(signal_frame*400,signal_frame*400+2000):
            struct.pack_into('<h',raw,sample*2,12000)
    pcm=root/'pedestrian-microphone.s16le';pcm.write_bytes(raw)
    metadata={'source_kind':'live_external_microphone','pcm_path':pcm.name,
              'sample_rate_hz':8000,'channels':1,'pcm_sha256':hashlib.sha256(raw).hexdigest(),
              'pcm_bytes':len(raw),'start_monotonic_ns':1_000_000_000,
              'first_chunk_monotonic_ns':1_600_000_000,
              'device_placement_verified':False}
    (root/'pedestrian-microphone.json').write_text(json.dumps(metadata)+'\n')


class SavedSidewalkSource(unittest.TestCase):
    def test_source_join_and_audio_order(self):
        with tempfile.TemporaryDirectory() as temp:
            write_fixture(temp)
            result=measure(temp)
            self.assertLess(result['first_microphone_pulse_video_frame_approx'],
                            result['first_footprint_overlap_frame']-20)
            self.assertTrue(result['pulse_precedes_overlap_with_engineering_margin'])
            self.assertIsNone(result['legal_right_of_way_verdict'])
            (Path(temp)/'pedestrian-microphone.json').unlink()
            with self.assertRaisesRegex(ValueError,'microphone'):
                measure(temp)

    def test_encoded_diagnostic_is_explicitly_not_original(self):
        with tempfile.TemporaryDirectory() as temp:
            write_fixture(temp)
            root=Path(temp)
            metadata=json.loads((root/'pedestrian-microphone.json').read_text())
            pcm=root/metadata['pcm_path']
            encoded=root/'pedestrian-microphone.hex'
            encoded.write_text(pcm.read_bytes().hex()+'\n')
            pcm.unlink()
            metadata.update(source_kind='synthetic_cpu',
                            pcm_path=encoded.name,
                            pcm_encoding='hex_s16le_diagnostic')
            (root/'pedestrian-microphone.json').write_text(json.dumps(metadata)+'\n')
            self.assertEqual(measure(root)['source_kind'],'synthetic_cpu')
            metadata['source_kind']='live_external_microphone'
            (root/'pedestrian-microphone.json').write_text(json.dumps(metadata)+'\n')
            with self.assertRaisesRegex(ValueError,'cannot claim original'):
                measure(root)


if __name__=='__main__':
    unittest.main()
