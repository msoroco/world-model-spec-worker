"""Independent source-bound trigger audit on the saved 480-frame synthetic fixture."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from engineering import parameters
from fallback_triggers import evaluate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


spec=importlib.util.spec_from_file_location('saved_fixture',HERE/'saved-fixture-proof.py')
fixture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def run():
    records=[]
    with tempfile.TemporaryDirectory(prefix='c382355-4a-trigger-',dir=ROOT/'.runtime-work') as temp:
        for suffix in ('controlled_1','controlled_2'):
            folder=Path(temp)/suffix
            fixture.make_base(folder,suffix,5.25,480)
            samples=folder/'native_samples.jsonl'
            geometry=folder/'road_geometry.json'
            video=folder/'overview.mkv'
            mapping=folder/'map-audit.json'
            pixels=folder/'pixel-audit.json'
            config=parameters(suffix,'primary')
            route=config['native_route_xy_m']
            movement=config['requested_movement']
            original_rows=[json.loads(line) for line in samples.read_text().splitlines()]
            assert len(original_rows)==480

            def write_sources(link=True,visible=456):
                mapping.write_text(json.dumps({
                    'source_kind':'synthetic_map_readback',
                    'native_map_sha256':json.loads(geometry.read_text())['native_map_sha256'],
                    'native_samples_sha256':sha(samples),
                    'road_geometry_sha256':sha(geometry),
                    'connected_requested_lane_link':link}))
                pixels.write_text(json.dumps({
                    'source_kind':'synthetic_camera_pixels',
                    'native_samples_sha256':sha(samples),'video_sha256':sha(video),
                    'full_body_and_lane_marking_visible_frames':visible,
                    'approach_frames':480}))

            def check():
                return evaluate(samples,geometry,mapping,pixels,video,route,movement)

            write_sources()
            baseline=check()
            assert baseline['declared_source_kind']=='synthetic_map_readback'
            assert [baseline[f'fallback{i}'] for i in (1,2,3)]==[False,False,False],baseline
            assert baseline['metrics']['maximum_connector_entry_route_error_m']<=.35,baseline
            write_sources(link=False)
            assert [check()[f'fallback{i}'] for i in (1,2,3)]==[True,False,False]

            perturbed=[dict(row) for row in original_rows]
            row=dict(perturbed[200])
            row['native_center_xy_m']=list(row['native_center_xy_m'])
            row['native_body_xy_m']=[list(p) for p in row['native_body_xy_m']]
            dx=6.0-row['native_center_xy_m'][0]
            dy=6.0-row['native_center_xy_m'][1]
            row['native_center_xy_m']=[6.0,6.0]
            for point in row['native_body_xy_m']:
                point[0]+=dx
                point[1]+=dy
            perturbed[200]=row
            fixture.write_rows(samples,perturbed)
            write_sources()
            deviation=check()
            assert [deviation[f'fallback{i}'] for i in (1,2,3)]==[False,True,False],deviation
            fixture.write_rows(samples,original_rows)

            write_sources(visible=455)
            assert [check()[f'fallback{i}'] for i in (1,2,3)]==[False,False,True]
            write_sources()
            samples.write_text(samples.read_text()+'\n')
            try:
                check()
            except ValueError as error:
                assert 'Native map audit source hash mismatch' in str(error)
            else:
                raise AssertionError('Changed saved samples accepted')
            fixture.write_rows(samples,original_rows)
            write_sources()
            video.write_bytes(video.read_bytes()+b'tamper')
            try:
                check()
            except ValueError as error:
                assert 'Pixel audit source hash mismatch' in str(error)
            else:
                raise AssertionError('Changed saved video accepted')
            records.append({
                'case_suffix':suffix,'rows':480,'requested_movement':movement,
                'three_isolated_triggers':True,'changed_samples_rejected':True,
                'changed_video_rejected':True,'baseline_metrics':baseline['metrics'],
                'baseline_source_hashes':baseline['source_hashes'],
                'source_kind':baseline['declared_source_kind']})
    return {'passed':True,'records':records,'native_executed':False,
            'scope':'source-bound synthetic saved-fixture audit; no physical Native observation'}


if __name__=='__main__':
    print(json.dumps(run(),indent=2))
