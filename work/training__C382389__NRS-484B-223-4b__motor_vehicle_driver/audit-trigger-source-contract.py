"""Measure synthetic fallback gates from the saved 480-frame case fixtures."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from fallback_triggers import evaluate
from geometry import route

spec=importlib.util.spec_from_file_location('saved_fixture',HERE/'saved-fixture-proof.py')
fixture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    records=[]
    with tempfile.TemporaryDirectory(prefix='c382389-saved-trigger-',dir=ROOT/'.runtime-work') as temp:
        for suffix,y,lane in (('reference',1.75,-1),('contrast',5.25,-2)):
            folder=Path(temp)/suffix
            fixture.make_base(folder,suffix,y,480)
            samples=folder/'native_samples.jsonl'
            geometry=folder/'road_geometry.json'
            mapping=folder/'map-audit.json'
            pixels=folder/'pixel-audit.json'
            video=folder/'overview.mkv'
            saved_rows=[json.loads(line) for line in samples.read_text().splitlines()]
            assert len(saved_rows)==480
            assert all(row['native_lane_id']==lane for row in saved_rows)
            authored=[[x,-v] for x,v in route(-y)]

            def source_packet(link=True,visible=456):
                fixture.write_rows(samples,saved_rows)
                map_data=json.loads(geometry.read_text())
                mapping.write_text(json.dumps({'source_kind':'synthetic_map_readback',
                    'native_map_sha256':map_data['native_map_sha256'],
                    'native_samples_sha256':sha(samples),
                    'road_geometry_sha256':sha(geometry),
                    'connected_requested_lane_link':link}))
                pixels.write_text(json.dumps({'source_kind':'synthetic_camera_pixels',
                    'native_samples_sha256':sha(samples),'video_sha256':sha(video),
                    'full_body_and_lane_marking_visible_frames':visible,
                    'approach_frames':480,
                    'annotation_scope':'synthetic count bound to generated video, not pixel measurement'}))

            def check():return evaluate(samples,geometry,mapping,pixels,video,authored,lane)

            source_packet()
            base=check()
            assert base['declared_source_kind']=='synthetic_map_readback'
            assert [base[f'fallback{i}'] for i in (1,2,3)]==[False,False,False],base
            base_hashes=base['source_hashes']
            source_packet(link=False)
            assert [check()[f'fallback{i}'] for i in (1,2,3)]==[True,False,False]
            source_packet()
            saved_rows[200]['native_center_xy_m'][1]+=.5
            for point in saved_rows[200]['native_body_xy_m']:point[1]+=.5
            source_packet()
            assert [check()[f'fallback{i}'] for i in (1,2,3)]==[False,True,False]
            saved_rows[200]['native_center_xy_m'][1]-=.5
            for point in saved_rows[200]['native_body_xy_m']:point[1]-=.5
            source_packet(visible=455)
            assert [check()[f'fallback{i}'] for i in (1,2,3)]==[False,False,True]
            source_packet()
            samples.write_text(samples.read_text()+'\n')
            try:check()
            except ValueError as error:assert 'Native map audit source hash mismatch' in str(error)
            else:raise AssertionError('Changed saved samples accepted')
            source_packet()
            video.write_bytes(video.read_bytes()+b'changed')
            try:check()
            except ValueError as error:assert 'Pixel audit source hash mismatch' in str(error)
            else:raise AssertionError('Changed synthetic video accepted')
            records.append({'case_suffix':suffix,'saved_rows':480,
                'baseline_metrics':base['metrics'],'baseline_source_hashes':base_hashes,
                'isolated_fallbacks':[1,2,3],
                'changed_samples_and_video_rejected':True,
                'generated_video_sha256':base_hashes['overview.mkv']})
    return {'passed':True,'records':records,'native_executed':False,
        'scope':'480-frame saved synthetic case fixtures; visibility counts are synthetic annotations, not original pixel measurements'}


if __name__=='__main__':print(json.dumps(run(),indent=2))
