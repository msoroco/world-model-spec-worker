"""Build a 30-second synthetic source fixture for saved-path diagnosis only."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from saved_analysis import sha256
from source_measurement import analyze
from source_provenance import SYNTHETIC


HERE = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False)+'\n')


def build(destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Retain prior diagnostic fixture; choose a fresh destination')
    if '.runtime-work' not in destination.parts:
        raise ValueError('Diagnostic fixture belongs under .runtime-work')
    destination.mkdir(parents=True)
    shutil.copyfile(HERE/'config.json', destination/'config.json')
    write(destination/'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True,
        'speed_source': SYNTHETIC,
        'physical_acceptance_claimed': False})
    write(destination/'native-map-readback.json', {
        'format': 'c179480-original-map-readback-v1', 'case': 'reference',
        'map_name': 'synthetic_diagnostic_road', 'road_id': 7, 'lane_id': -1})
    actor_path = destination/'native-actors.jsonl'
    frame_path = destination/'video_frames.jsonl'
    with actor_path.open('x') as actors, frame_path.open('x') as frames:
        for i in range(600):
            speed = 4.0 if i < 200 else max(0.0, 4.0-(i-200)*0.2)
            x = min(40.0, i*.2)
            row = {
                'frame': 101+i, 'video_frame': i, 'source_kind': SYNTHETIC,
                'ego_speed_mps': speed, 'ego_on_roadway': True,
                'ego_lane_overlap': True, 'following_speed_mps': 3.0,
                'following_gap_m': 12.0, 'ego_velocity_xyz_mps': [speed,0.,0.],
                'ego_body_vertices_xyz_m': [[x-2.,-1.,0.],[x-2.,1.,0.],
                                            [x+2.,1.,0.],[x+2.,-1.,0.]],
                'ego_x_m': x, 'ego_y_m': 0., 'ego_yaw_deg': 0.,
                'ego_body_lateral_min_m': -1., 'ego_body_lateral_max_m': 1.,
                'driving_lane_width_m': 3.7, 'driving_road_id': 7,
                'driving_lane_id': -1, 'following_velocity_xyz_mps': [3.,0.,0.],
                'following_x_m': x-12., 'following_y_m': 0.,
                'following_on_driving_lane': True,
            }
            actors.write(json.dumps(row, allow_nan=False)+'\n')
            frames.write(json.dumps({'video_frame':i,'carla_frame':101+i,
                                     'time_s':i/20}, allow_nan=False)+'\n')
    measured = analyze(actor_path, frame_path)
    measured.update(format='c179480-source-measurements-v1', case='reference',
                    actor_source_sha256=sha256(actor_path),
                    frame_map_sha256=sha256(frame_path),
                    map_readback_sha256=sha256(destination/'native-map-readback.json'))
    write(destination/'source-measurements.json', measured)
    # Small diagnostic pixels exercise decoding; the authored Native profile
    # remains four 1920/1280-wide camera streams in config.json.
    video = destination/'overview.mkv'
    subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
                    '-f','lavfi','-i','color=c=blue:s=16x16:r=20',
                    '-frames:v','600','-c:v','ffv1',str(video)], check=True)
    for camera in ('approach','reference_corner','driver_reference'):
        shutil.copyfile(video,destination/(camera+'.mkv'))
    return {'source_frames':600,'duration_s':30,
            'provenance_kind':'synthetic_fixture',
            'physical_acceptance_claimed':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination',type=Path)
    print(json.dumps(build(parser.parse_args().destination),sort_keys=True))
