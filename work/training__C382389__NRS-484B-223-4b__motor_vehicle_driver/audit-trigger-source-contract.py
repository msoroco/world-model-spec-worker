"""Independent 480-row synthetic contract for both 4(b) lane probes."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from fallback_triggers import evaluate
from geometry import route


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    records=[]
    with tempfile.TemporaryDirectory(prefix='c382389-4b-trigger-',dir=ROOT/'.runtime-work') as temp:
        root=Path(temp)
        for suffix,lateral,lane in (('reference',-1.75,-1),('contrast',-5.25,-2)):
            folder=root/suffix;folder.mkdir()
            samples=folder/'native_samples.jsonl';geometry=folder/'road_geometry.json'
            mapping=folder/'map-audit.json';pixels=folder/'pixel-audit.json';video=folder/'overview.mkv'
            video.write_bytes(b'480-frame synthetic camera audit placeholder')
            geometry.write_text(json.dumps({'native_map_sha256':'a'*64}))
            authored=route(lateral)
            rows=[]
            for index in range(480):
                x,y=authored[round(index*(len(authored)-1)/479)]
                road=1 if index<160 else 14 if index<320 else 2
                rows.append({'native_frame':100+index,'time_s':(index+1)/20,
                    'native_center_xy_m':[x,y],'native_forward_xy':[1,0],
                    'native_body_xy_m':[[x-1,y-1],[x-1,y+1],[x+1,y+1],[x+1,y-1]],
                    'native_road_id':road,'native_lane_id':lane})
            def write_sources(link=True,visible=456):
                samples.write_text(''.join(json.dumps(row)+'\n' for row in rows))
                mapping.write_text(json.dumps({'source_kind':'native_map_readback',
                    'native_map_sha256':'a'*64,'native_samples_sha256':sha(samples),
                    'road_geometry_sha256':sha(geometry),'connected_requested_lane_link':link}))
                pixels.write_text(json.dumps({'source_kind':'original_camera_pixels',
                    'native_samples_sha256':sha(samples),'video_sha256':sha(video),
                    'full_body_and_lane_marking_visible_frames':visible,'approach_frames':480}))
            def check():return evaluate(samples,geometry,mapping,pixels,video,authored,lane)
            write_sources();base=check()
            assert [base[f'fallback{i}'] for i in (1,2,3)]==[False,False,False],base
            write_sources(link=False);assert [check()[f'fallback{i}'] for i in (1,2,3)]==[True,False,False]
            rows[200]['native_center_xy_m'][1]+=.5
            for point in rows[200]['native_body_xy_m']:point[1]+=.5
            write_sources();assert [check()[f'fallback{i}'] for i in (1,2,3)]==[False,True,False]
            rows[200]['native_center_xy_m'][1]-=.5
            for point in rows[200]['native_body_xy_m']:point[1]-=.5
            write_sources(visible=455);assert [check()[f'fallback{i}'] for i in (1,2,3)]==[False,False,True]
            write_sources();samples.write_text(samples.read_text()+'\n')
            try:check()
            except ValueError as error:assert 'Native map audit source hash mismatch' in str(error)
            else:raise AssertionError('Changed Native samples accepted')
            records.append({'case_suffix':suffix,'rows':480,'three_isolated_triggers':True,
                            'changed_source_rejected':True,'baseline_metrics':base['metrics']})
    return {'passed':True,'records':records,'native_executed':False,
            'scope':'synthetic source-contract audit, not physical trigger observation'}


if __name__=='__main__':print(json.dumps(run(),indent=2))
