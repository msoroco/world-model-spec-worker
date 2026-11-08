"""Measure saved heavy-vehicle body occupancy; no City or statutory verdict."""
import hashlib
import json
import math
from pathlib import Path

BLUEPRINT = 'vehicle.carlamotors.carlacola'
SOURCES = ('native-observed.jsonl', 'native-map-readback.json',
           'video_frames.jsonl', 'capture/evidence.jsonl',
           'native-capture-report.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def records(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure(folder, expected_hashes=None):
    folder = Path(folder)
    files = {name: folder/name for name in SOURCES}
    if any(not path.is_file() for path in files.values()):
        raise ValueError('Required saved Native source absent')
    hashes = {name: sha(path) for name,path in files.items()}
    if expected_hashes is not None and hashes != expected_hashes:
        raise ValueError('Saved Native source hash differs')
    observed = records(files['native-observed.jsonl'])
    video = records(files['video_frames.jsonl'])
    evidence = records(files['capture/evidence.jsonl'])
    map_record = json.loads(files['native-map-readback.json'].read_text())
    report = json.loads(files['native-capture-report.json'].read_text())
    if any(len(group) != 480 for group in (observed, video, evidence)):
        raise ValueError('Saved Native frame count differs')
    kinds = {row.get('source_kind') for row in observed}
    if len(kinds) != 1 or not kinds <= {'synthetic_cpu', 'original_native'}:
        raise ValueError('Saved actor provenance differs')
    kind = kinds.pop()
    width = map_record.get('observed_body_width_m')
    if (map_record.get('sidewalk_road_id') != 1 or
            map_record.get('sidewalk_lane_id') != -2 or
            map_record.get('subject_blueprint') != BLUEPRINT or
            not isinstance(width,(int,float)) or not math.isfinite(width) or
            not 1.5 <= width <= 3.6 or
            report.get('observed_frames') != 480 or
            report.get('requested_frames') != 480 or
            report.get('error') is not None or report.get('accepted') is not False):
        raise ValueError('Saved map, body geometry or capture report differs')
    if kind == 'original_native' and report.get('restoration') is None:
        raise ValueError('Original Native restoration absent')
    moving, overlap, inside, lane_readback = [], [], [], []
    first_frame, first_time = observed[0].get('native_frame'), observed[0].get('time_s')
    if type(first_frame) is not int or not isinstance(first_time,(int,float)) or not math.isfinite(first_time):
        raise ValueError('Saved initial Native frame/time invalid')
    for index, (row, frame, captured) in enumerate(zip(observed, video, evidence)):
        timestamp = row.get('time_s')
        if (row.get('frame') != index or row.get('native_frame') != first_frame+index or
                not isinstance(timestamp,(int,float)) or not math.isfinite(timestamp) or
                abs(timestamp-first_time-index/20) > 1e-4 or
                frame.get('video_frame') != index or
                frame.get('native_frame') != first_frame+index or
                frame.get('carla_frame') != first_frame+index or
                captured.get('original_frame') != first_frame+index or
                abs(frame.get('time_s',float('inf'))-timestamp) > 1e-4 or
                abs(captured.get('recording_time_s',float('inf'))-timestamp) > 1e-4):
            raise ValueError('Saved Native/video/capture frame join differs')
        if row.get('source_kind') != kind or row.get('vehicle_blueprint') != BLUEPRINT:
            raise ValueError('Saved actor identity differs')
        body, center, speed = row.get('body_native_xy_m'), row.get('center_native_xy_m'), row.get('speed_mps')
        if (not isinstance(body,list) or len(body) != 4 or
                not isinstance(center,list) or len(center) != 2 or
                not isinstance(speed,(int,float)) or not math.isfinite(speed) or speed < 0):
            raise ValueError('Saved actor body, center or speed absent')
        if any(not isinstance(point,list) or len(point) != 2 or
               any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in point)
               for point in body):
            raise ValueError('Saved body vertex invalid')
        if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in center):
            raise ValueError('Saved center invalid')
        if (len({tuple(point) for point in body}) != 4 or
                abs(sum(p[0] for p in body)/4-center[0]) > .1 or
                abs(sum(p[1] for p in body)/4-center[1]) > .1):
            raise ValueError('Saved body/center disagreement')
        xmin, xmax = min(p[0] for p in body), max(p[0] for p in body)
        ymin, ymax = min(p[1] for p in body), max(p[1] for p in body)
        if abs(ymax-ymin-width) > .2:
            raise ValueError('Saved body width differs from Native readback')
        if speed > .1:
            moving.append(index)
            if xmax > 0 and xmin < 140 and ymax > 3.5 and ymin < 7.5:
                overlap.append(index)
            if xmin >= 0 and xmax <= 140 and ymin >= 3.5 and ymax <= 7.5:
                inside.append(index)
        if row.get('native_lane_id') == -2:
            lane_readback.append(index)
    longest, run, prior = 0, 0, -2
    for index in overlap:
        run = run+1 if index == prior+1 else 1
        longest = max(longest,run)
        prior = index
    return {'format':'c422978-heavy-saved-sidewalk-measurement-v1',
            'source_kind':kind, 'frames':480, 'moving_frames':len(moving),
            'moving_sidewalk_overlap_frames':len(overlap),
            'first_moving_sidewalk_overlap_frame':overlap[0] if overlap else None,
            'longest_moving_sidewalk_overlap_frames':longest,
            'full_body_inside_sidewalk_frames':len(inside),
            'native_sidewalk_lane_readback_frames':len(lane_readback),
            'observed_body_width_m':width,
            'city_sidewalk_verified':bool(map_record.get('city_location_verified')),
            'legal_verdict':None, 'source_hashes':hashes}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    print(json.dumps(measure(args.folder), indent=2))
