"""Measure C146314 saved actor/body geometry without assigning a legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def body_bounds(points, cx, cy):
    require(isinstance(points, list) and len(points) == 4 and
            all(isinstance(p, list) and len(p) == 2 and
                all(map(finite, p)) for p in points), 'body vertices')
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    corners = {(round(cx+dx, 6), round(cy+dy, 6))
               for dx, dy in ((-2.3,-1),(-2.3,1),(2.3,1),(2.3,-1))}
    require({(round(p[0],6),round(p[1],6)) for p in points} == corners,
            'body corner identity')
    require(abs((min(xs)+max(xs))/2-cx) < .005 and
            abs((min(ys)+max(ys))/2-cy) < .005 and
            abs(max(xs)-min(xs)-4.6) < .005 and
            abs(max(ys)-min(ys)-2) < .005, 'body/pose correspondence')
    return min(xs), max(xs), min(ys), max(ys)


def measure(bundle, saved):
    bundle, saved = Path(bundle), Path(saved)
    cfg = read(bundle/'config.json')
    request = rows(bundle/'requested-tracks.jsonl')
    actor = rows(saved/'native-observed.jsonl')
    camera = rows(saved/'camera-frames.jsonl')
    back = read(saved/'readback.json')
    require(back['source_kind'] == 'synthetic_cpu' and
            back['road_sha256'] == cfg['road_sha256'] and
            back['config_sha256'] == sha(bundle/'config.json') and
            back['tracks_sha256'] == cfg['tracks_sha256'] and
            back['observed_sha256'] == sha(saved/'native-observed.jsonl') and
            back['camera_sha256'] == sha(saved/'camera-frames.jsonl') and
            all(back[k] is False for k in
                ('one_way_designation_verified','pavement_condition_verified',
                 'object_pixel_reviewed')) and back['legal_verdict'] is None,
            'source/readback binding')
    require(len(actor) == len(camera) == len(request) == 240,
            'saved frame coverage')
    previous = None
    passing_frames = 0
    obstruction_frames = 0
    min_clearance = None
    for i, (a, c, req) in enumerate(zip(actor, camera, request)):
        t = (i+1)/20
        require(a['frame'] == c['frame'] == req['frame'] == i and
                a['native_frame'] == c['native_frame'] == 1000+i and
                abs(a['time_s']-t) < 1e-6 and
                abs(c['time_s']-t) < 1e-6 and
                c['forward_frame'] == c['overview_frame'] == i and
                a['source_kind'] == c['source_kind'] == 'synthetic_cpu' and
                c['object_pixel_reviewed'] is False and
                c['lane_pixel_reviewed'] is False and
                a['road_id'] == 210 and
                a['ego_actor_id'] == 1 and a['lead_actor_id'] == 2 and
                a['ego_lane_id'] in (-1,-2) and a['lead_lane_id'] == -1 and
                all(finite(a[k]) for k in
                    ('ego_x_m','ego_y_m','lead_x_m','lead_y_m')) and
                a['one_way_designation_verified'] is False and
                a['pavement_condition_verified'] is False and
                a['legal_verdict'] is None,
                f'saved actor/camera join {i}')
        eb = body_bounds(a['ego_body_xy_m'], a['ego_x_m'], a['ego_y_m'])
        lb = body_bounds(a['lead_body_xy_m'], a['lead_x_m'], a['lead_y_m'])
        if previous is not None:
            require(0 <= a['ego_x_m']-previous['ego_x_m'] <= .5 and
                    abs(a['lead_x_m']-previous['lead_x_m']-.2) < .005,
                    f'actor displacement {i}')
        right = eb[3] < lb[2] and a['ego_lane_id'] == -2
        if right and eb[0] > lb[1]:
            passing_frames += 1
        has_object = cfg['right_lane_obstruction_requested']
        require(a['obstruction_actor_id'] == (3 if has_object else None) and
                a['obstruction_x_m'] == cfg['obstruction_x_m'] and
                a['obstruction_y_m'] == cfg['obstruction_y_m'] and
                a['obstruction_radius_m'] == cfg['obstruction_radius_m'],
                f'obstruction source {i}')
        if has_object:
            ox, oy, radius = (a['obstruction_x_m'], a['obstruction_y_m'],
                              a['obstruction_radius_m'])
            dx = max(eb[0]-ox, 0, ox-eb[1])
            dy = max(eb[2]-oy, 0, oy-eb[3])
            clearance = math.hypot(dx, dy)-radius
            min_clearance = clearance if min_clearance is None else min(
                min_clearance, clearance)
            if abs(a['ego_x_m']-ox) < 3 and a['ego_lane_id'] == -2:
                obstruction_frames += 1
        previous = a
    require((min_clearance is None) == (not cfg['right_lane_obstruction_requested']),
            'obstruction coverage')
    result = {'format':'c146314-saved-measurement-v1',
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'source_kind':'synthetic_cpu','frames':240,
        'passing_right_geometry_frames':passing_frames,
        'requested_obstruction_longitudinal_overlap_frames':obstruction_frames,
        'min_ego_body_to_obstruction_clearance_m':
            None if min_clearance is None else round(min_clearance,6),
        'one_way_designation_verified':False,
        'pavement_condition_verified':False,
        'original_native_observed':False,'accepted':False,
        'legal_verdict':None,'delivery_ready':False,
        'saved_hashes':{name:sha(saved/name) for name in
            ('native-observed.jsonl','camera-frames.jsonl','readback.json')}}
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--saved-dir', type=Path, required=True)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    result = measure(a.bundle, a.saved_dir)
    if a.output:
        a.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
