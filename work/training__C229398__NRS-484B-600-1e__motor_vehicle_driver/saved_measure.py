"""Measure original approach speed from Native velocity in a reviewed park cell."""
import hashlib
import json
import math
from pathlib import Path

from source_review import join, require, sha

VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')
CAMERAS = tuple(name.removesuffix('.mkv') for name in VIDEOS)


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def measure(attempt, case_id, diagnostic=False):
    attempt = Path(attempt)
    for name in ('native-speed.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                 'visibility-review.json', 'road.xodr', *VIDEOS):
        require((attempt/name).is_file(), 'Missing required source: '+name)
    source = join(attempt, case_id, diagnostic=diagnostic)
    trace, frames, core = (rows(attempt/name) for name in
                           ('native-speed.jsonl','video_frames.jsonl','trace.jsonl'))
    visible = json.loads((attempt/'visibility-review.json').read_text())
    require(visible.get('case_id') == case_id and
            visible.get('review_kind') == source['review_kind'] and
            len(visible.get('frames',[])) == 600,
            'Full four-view subject visibility review missing')
    require(len(trace) == len(frames) == len(core) == 600,
            'Complete 600-frame Native/Core/source join missing')
    config = json.loads((attempt/'config.json').read_text())
    speeds = []
    phases = []
    source_id = None
    for i, (native, fmap, seen, core_frame) in enumerate(zip(trace,frames,visible['frames'],core)):
        require(native.get('frame') == fmap.get('video_frame') == seen.get('frame') == i and
                native.get('native_frame') == fmap.get('native_frame') and
                core_frame.get('frame') == native.get('native_frame') and
                abs(native.get('t_s', -1)-fmap.get('time_s', -2)) < .051,
                'Original frame/time identity mismatch')
        require(set(fmap.get('camera_native_frames',{})) == set(CAMERAS) and
                all(fmap['camera_native_frames'][name] == native['native_frame']
                    for name in CAMERAS), 'Four-camera Native frame join missing')
        require(seen.get('visible_views') == list(CAMERAS),
                'Vehicle visibility review lacks exact four views')
        sample = native.get('sample',{})
        require(sample.get('road_id') == 229398 and sample.get('lane_id') in (-1,-2),
                'Native road and lane readback differs')
        if source_id is None:
            source_id = sample.get('actor_id')
        require(source_id is not None and sample.get('actor_id') == source_id and
                sample.get('blueprint') == config['ego_blueprint'],
                'Native subject identity changed')
        vector = sample.get('velocity_xyz_mps')
        require(isinstance(vector,list) and len(vector)==3 and
                all(type(v) in (int,float) and math.isfinite(v) for v in vector),
                'Original Native velocity source missing')
        speed = math.sqrt(sum(v*v for v in vector))*2.2369362920544
        require(abs(speed-sample.get('observed_speed_mph',-100)) < .01,
                'Reported speed differs from original Native velocity')
        require(native.get('requested_speed_mph') == config['requested_approach_speed_mph'],
                'Requested speed control differs from selected case')
        phase = native.get('phase')
        require(phase in ('approach_driving','curb_parking','parked'),
                'Original temporal phase missing')
        phases.append(phase)
        speeds.append(speed)
    require(phases[:400] == ['approach_driving']*400 and
            phases[400:520] == ['curb_parking']*120 and
            phases[520:] == ['parked']*80,
            'Same-recording approach-to-curb phase sequence missing')
    require(all(trace[i]['sample']['lane_id'] == -1 for i in range(400)) and
            all(trace[i]['sample']['lane_id'] == -2 for i in range(520,600)),
            'Driving approach and parked curb lane readback missing')
    require(max(speeds[520:]) <= .5,
            'Parked phase has unverified motion')
    return {'case_id':case_id,'frame_count':600,'approach_frame_range':[0,399],
            'parking_frame_range':[400,519],'parked_frame_range':[520,599],
            'max_approach_speed_mph':max(speeds[:400]),
            'approach_frames_above_80_mph':[i for i in range(400) if speeds[i] > 80],
            'max_parked_speed_mph':max(speeds[520:]),
            'requested_speed_used_for_measurement':False,
            'source_join':source,
            'source_sha256':{name:sha(attempt/name) for name in
                             ('native-speed.jsonl','video_frames.jsonl','trace.jsonl',
                              'visibility-review.json','road.xodr',*VIDEOS)},
            'physical_acceptance_claimed':False,'legal_result':None}
