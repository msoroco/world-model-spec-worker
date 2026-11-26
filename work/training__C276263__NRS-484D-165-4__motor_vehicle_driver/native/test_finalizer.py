"""Synthetic source-shape proof; cannot prove real beam or parking activity."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from finalize_original import finalize
from parked_lamps import VIEWS

ROOT=Path(__file__).resolve().parents[3]/'.runtime-work'

def write(path,value):
    path.write_text(value if isinstance(value,str) else json.dumps(value)+'\n')

def fixture(attempt):
    road=Path(__file__).resolve().parent/'sloped-curb-road.xodr'
    (attempt/'road.xodr').write_bytes(road.read_bytes())
    for view in VIEWS: (attempt/(view+'.mkv')).write_bytes(b'synthetic-'+view.encode())
    write(attempt/'parking-activity-review.json',{'source_kind':'original_native',
        'review_status':'verified','source_basis':'synthetic fixture only',
        'legal_verdict':None})
    write(attempt/'beam-aim-intensity-review.json',{'source_kind':'original_native',
        'review_status':'verified','source_basis':'synthetic fixture only',
        'legal_verdict':None})
    camera_hash=hashlib.sha256((attempt/'overview.mkv').read_bytes()).hexdigest()
    native=[];frames=[];observed=[]
    for i in range(600):
        frame=1000+i;t=(i+1)/20
        native.append({'frame':i,'native_frame':frame,'time_s':t,
            'source_kind':'original_native','ego_actor_id':3,
            'ego_blueprint_id':'vehicle.lamp.test',
            'ego_center_xyz_m':[4.85,0,2.4],'ego_speed_mps':0,
            'observed_footprint_xyz_m':[[4,0,2],[5,0,2],[4,1,2],[5,1,2]],
            'observed_curb_lane_id':-2,'requested_headlamp_lit':True,
            'requested_beam_state':'low_beam','observed_light_state_bits':1,
            'observed_beam_state':'low_beam',
            'source_cameras':dict.fromkeys(VIEWS,frame)})
        frames.append({'video_frame':i,'native_frame':frame,'time_s':t,
            'camera_native_frames':dict.fromkeys(VIEWS,frame)})
        observed.append({'frame':i,'native_frame':frame,'time_s':t,
            'observed_parking_activity':'parked',
            'beam_pixel_review':{'status':'reviewed','source_path':'overview.mkv',
                'source_sha256':camera_hash,'aim_elevation_deg':-1.2,
                'relative_intensity':.5}})
    for name,data in [('native-rows.jsonl',native),('video_frames.jsonl',frames),
                      ('observed-lamp-review.jsonl',observed)]:
        write(attempt/name,''.join(json.dumps(row)+'\n' for row in data))
    source_names=('parking-activity-review.json','beam-aim-intensity-review.json',
        'native-rows.jsonl','video_frames.jsonl','observed-lamp-review.jsonl',
        'road.xodr')+tuple(
            view+'.mkv' for view in VIEWS)
    manifest={'source_kind':'original_native',
        'case_id':'training__C276263__NRS-484D-165-4__motor_vehicle_driver__probe_a',
        'synthetic_cpu_fixture':True,
        'legal_verdict':None,'sha256':{name:hashlib.sha256((attempt/name).read_bytes()).hexdigest()
        for name in source_names}}
    write(attempt/'source-review-manifest.json',manifest)
    return attempt/'source-review-manifest.json'

class FinalizerTest(unittest.TestCase):
    def test_join_and_pending_verdict(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            attempt=Path(directory);manifest=fixture(attempt)
            result=finalize(attempt,manifest)
            self.assertEqual(result['frames'],600)
            self.assertFalse(result['original_native_observed'])
            self.assertIsNone(result['legal_verdict'])

    def test_missing_or_changed_source_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            attempt=Path(directory);manifest=fixture(attempt)
            (attempt/'overview.mkv').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'hash differs'):
                finalize(attempt,manifest)

    def test_pending_review_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            attempt=Path(directory);manifest=fixture(attempt)
            review=json.loads((attempt/'parking-activity-review.json').read_text())
            review['review_status']='pending'
            write(attempt/'parking-activity-review.json',review)
            record=json.loads(manifest.read_text())
            record['sha256']['parking-activity-review.json']=hashlib.sha256(
                (attempt/'parking-activity-review.json').read_bytes()).hexdigest()
            write(manifest,record)
            with self.assertRaisesRegex(ValueError,'pending'):
                finalize(attempt,manifest)

    def test_changed_parking_activity_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            attempt=Path(directory);manifest=fixture(attempt)
            path=attempt/'observed-lamp-review.jsonl'
            lines=path.read_text().splitlines()
            row=json.loads(lines[200]);row['observed_parking_activity']='loading'
            lines[200]=json.dumps(row);write(path,'\n'.join(lines)+'\n')
            record=json.loads(manifest.read_text())
            record['sha256']['observed-lamp-review.jsonl']=hashlib.sha256(
                path.read_bytes()).hexdigest()
            write(manifest,record)
            with self.assertRaisesRegex(ValueError,'parked and lighted'):
                finalize(attempt,manifest)

if __name__=='__main__':unittest.main()
