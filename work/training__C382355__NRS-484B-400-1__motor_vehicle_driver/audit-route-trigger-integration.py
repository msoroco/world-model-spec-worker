"""Audit three fallback gates against each saved 480-frame synthetic turn."""
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

spec=importlib.util.spec_from_file_location('saved_fixture',HERE/'saved-fixture-proof.py')
fixture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    records=[]
    with tempfile.TemporaryDirectory(prefix='c382355-400-saved-trigger-',dir=ROOT/'.runtime-work') as tmp:
        for suffix,y in (('witness_1',5.25),('witness_2',1.75)):
            folder=Path(tmp)/suffix
            fixture.make_base(folder,suffix,y,480)
            samples=folder/'native_samples.jsonl'
            mapping=folder/'map-audit.json'
            pixels=folder/'pixel-audit.json'
            video=folder/'overview.mkv'
            rows=[json.loads(line) for line in samples.read_text().splitlines()]
            assert len(rows)==480
            route=parameters(suffix,'primary')['native_route_xy_m']

            def packet(link=True,visible=456):
                fixture.write_rows(samples,rows)
                mapping.write_text(json.dumps({'source_kind':'synthetic_map_readback',
                    'native_samples_sha256':sha(samples),
                    'connected_right_turn_lane_link':link}))
                pixels.write_text(json.dumps({'source_kind':'synthetic_camera_pixels',
                    'native_samples_sha256':sha(samples),'video_sha256':sha(video),
                    'full_body_and_lane_marking_visible_frames':visible,
                    'approach_frames':480,
                    'annotation_scope':'synthetic count bound to generated video'}))

            def check():return evaluate(samples,mapping,pixels,video,route)

            packet();base=check()
            assert base['declared_source_kind']=='synthetic_map_readback'
            assert [base[f'fallback{i}'] for i in (1,2,3)]==[False,False,False],base
            hashes=base['source_hashes']
            packet(link=False)
            assert [check()[f'fallback{i}'] for i in (1,2,3)]==[True,False,False]
            rows[200]['native_center_xy_m'][0]+=2.0
            for corner in rows[200]['native_body_xy_m']:corner[0]+=2.0
            packet()
            assert [check()[f'fallback{i}'] for i in (1,2,3)]==[False,True,False]
            rows[200]['native_center_xy_m'][0]-=2.0
            for corner in rows[200]['native_body_xy_m']:corner[0]-=2.0
            packet(visible=455)
            assert [check()[f'fallback{i}'] for i in (1,2,3)]==[False,False,True]
            packet();samples.write_text(samples.read_text()+'\n')
            try:check()
            except ValueError as error:assert 'Native sample hash mismatch' in str(error)
            else:raise AssertionError('Changed saved rows accepted')
            packet();video.write_bytes(video.read_bytes()+b'changed')
            try:check()
            except ValueError as error:assert 'Pixel audit source hash mismatch' in str(error)
            else:raise AssertionError('Changed generated video accepted')
            records.append({'case_suffix':suffix,'saved_rows':480,
                'baseline_metrics':base['metrics'],'baseline_source_hashes':hashes,
                'isolated_fallbacks':[1,2,3],
                'changed_samples_and_video_rejected':True})
    return {'passed':True,'records':records,'native_executed':False,
        'scope':'Saved synthetic case fixtures; visibility count is annotation, not original-pixel measurement'}


if __name__=='__main__':print(json.dumps(run(),indent=2))
