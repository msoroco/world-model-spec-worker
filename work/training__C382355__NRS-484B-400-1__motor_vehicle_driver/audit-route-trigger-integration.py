"""480-row synthetic source-contract audit of three independent fallback triggers."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/'native'))
from fallback_triggers import evaluate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True)+'\n')


def rows(path, values):
    path.write_text(''.join(json.dumps(v, sort_keys=True)+'\n' for v in values))


def sample(index):
    if index < 200:
        x, y, road = -20, 5.25, 1
    elif index < 300:
        x, y, road = -5, 5.25, 13
    else:
        x, y, road = -5, 12, 4
    return {'native_frame':100+index, 'time_s':(index+1)/20,
            'native_center_xy_m':[x,y], 'native_road_id':road,
            'native_lane_id':-2,
            'native_body_xy_m':[[x-1,y-1],[x-1,y+1],[x+1,y+1],[x+1,y-1]]}


def main():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        motion=root/'native_samples.jsonl'
        mapping=root/'map-audit.json'
        pixels=root/'pixel-audit.json'
        video=root/'overview.mkv'
        video.write_bytes(b'synthetic encoded-camera stand-in; no original pixels')
        data=[sample(i) for i in range(480)]
        route=[[-20,5.25],[-5,5.25],[-5,12]]
        def prepare(visible=456, link=True):
            rows(motion,data)
            write(mapping,{'source_kind':'native_map_readback',
                           'native_samples_sha256':sha(motion),
                           'connected_right_turn_lane_link':link})
            write(pixels,{'source_kind':'original_camera_pixels',
                          'native_samples_sha256':sha(motion),
                          'video_sha256':sha(video),
                          'full_body_and_lane_marking_visible_frames':visible,
                          'approach_frames':480})
        def trigger():
            return evaluate(motion,mapping,pixels,video,route)
        prepare()
        assert [trigger()[k] for k in ('fallback1','fallback2','fallback3')]==[False]*3
        prepare(link=False)
        assert [trigger()[k] for k in ('fallback1','fallback2','fallback3')]==[True,False,False]
        data[250]['native_center_xy_m'][0]=-4.64
        prepare()
        assert [trigger()[k] for k in ('fallback1','fallback2','fallback3')]==[False,True,False]
        data[250]=sample(250)
        prepare(visible=455)
        assert [trigger()[k] for k in ('fallback1','fallback2','fallback3')]==[False,False,True]
        video.write_bytes(b'changed synthetic source')
        try:
            trigger()
        except ValueError as error:
            assert 'Pixel audit source hash mismatch' in str(error)
        else:
            raise AssertionError('Changed video source accepted')
        print(json.dumps({'passed':True,'synthetic_rows':480,
                          'baseline_and_three_isolated_trigger_variants':True,
                          'changed_camera_source_rejected':True,
                          'scope':'synthetic source-contract only; no CARLA or original pixels'}))


if __name__=='__main__':
    main()
