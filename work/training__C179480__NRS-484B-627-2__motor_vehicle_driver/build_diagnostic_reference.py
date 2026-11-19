"""Build a 30-second synthetic source fixture for saved-path diagnosis only."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from saved_analysis import sha256
from source_measurement import analyze, analyze_hazard
from source_provenance import SYNTHETIC


HERE = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False)+'\n')


def build(destination, case='reference'):
    if case not in ('reference', 'contrast', 'safe_operation_stop',
                    'law_required_stop'):
        raise ValueError('Unsupported diagnostic case')
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Retain prior diagnostic fixture; choose a fresh destination')
    if '.runtime-work' not in destination.parts:
        raise ValueError('Diagnostic fixture belongs under .runtime-work')
    destination.mkdir(parents=True)
    if case == 'reference':
        shutil.copyfile(HERE/'config.json', destination/'config.json')
    else:
        construction = json.loads((HERE/f'draft-{case}-construction.json').read_text())
        config = next(item['content'] for item in construction['files']
                      if item['path'] == 'config.json')
        (destination/'config.json').write_text(config)
    write(destination/'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True,
        'speed_source': SYNTHETIC,
        'physical_acceptance_claimed': False})
    write(destination/'native-map-readback.json', {
        'format': 'c179480-original-map-readback-v1', 'case': case,
        'map_name': 'synthetic_diagnostic_road', 'road_id': 7, 'lane_id': -1,
        'surveyed_governing_traffic_light_id': 501 if case == 'law_required_stop' else None})
    actor_path = destination/'native-actors.jsonl'
    frame_path = destination/'video_frames.jsonl'
    with actor_path.open('x') as actors, frame_path.open('x') as frames:
        for i in range(600):
            speed = 4.0 if i < 200 else max(0.0, 4.0-(i-200)*0.2)
            x = min(40.0, i*.2)
            lateral = -4.8 if case == 'contrast' else 0.
            row = {
                'frame': 101+i, 'video_frame': i, 'source_kind': SYNTHETIC,
                'ego_speed_mps': speed, 'ego_on_roadway': case != 'contrast',
                'ego_lane_overlap': case != 'contrast', 'following_speed_mps': 3.0,
                'following_gap_m': 12.0, 'ego_velocity_xyz_mps': [speed,0.,0.],
                'ego_body_vertices_xyz_m': [[x-2.,lateral-1.,0.],[x-2.,lateral+1.,0.],
                                            [x+2.,lateral+1.,0.],[x+2.,lateral-1.,0.]],
                'ego_x_m': x, 'ego_y_m': lateral, 'ego_yaw_deg': 0.,
                'ego_body_lateral_min_m': lateral-1., 'ego_body_lateral_max_m': lateral+1.,
                'driving_lane_width_m': 3.7, 'driving_road_id': 7,
                'driving_lane_id': -1, 'following_velocity_xyz_mps': [3.,0.,0.],
                'following_x_m': x-12., 'following_y_m': 0.,
                'following_on_driving_lane': True,
            }
            if case == 'safe_operation_stop':
                row['hazard_state'] = {
                    'source_kind': SYNTHETIC,
                    'body_vertices_xyz_m': [[x+6.,-1.,0.],[x+6.,1.,0.],
                                            [x+10.,1.,0.],[x+10.,-1.,0.]],
                    'velocity_xyz_mps': [0.,0.,0.],
                    'position_xyz_m': [x+8.,0.,0.],
                    'on_driving_lane': True, 'road_id': 7, 'lane_id': -1,
                    'speed_mps': 0., 'ego_center_gap_m': 8.,
                }
            if case == 'law_required_stop':
                row['governing_control_state'] = {
                    'source_kind': SYNTHETIC,
                    'control_actor_id': 501,
                    'control_type_id': 'traffic.traffic_light',
                    'control_state': 'TrafficLightState.Red',
                    'ego_associated_control_id': 501 if i >= 220 else None,
                    'ego_at_control': i >= 220,
                }
            actors.write(json.dumps(row, allow_nan=False)+'\n')
            frames.write(json.dumps({'video_frame':i,'carla_frame':101+i,
                                     'time_s':i/20}, allow_nan=False)+'\n')
    measured = analyze(actor_path, frame_path)
    measured.update(format='c179480-source-measurements-v1', case=case,
                    actor_source_sha256=sha256(actor_path),
                    frame_map_sha256=sha256(frame_path),
                    map_readback_sha256=sha256(destination/'native-map-readback.json'))
    if case == 'safe_operation_stop':
        measured['hazard_observation'] = analyze_hazard(
            actor_path, frame_path, source_kind=SYNTHETIC)
    if case == 'law_required_stop':
        from source_measurement import analyze_control
        measured['governing_control_observation'] = analyze_control(
            actor_path, frame_path, expected_control_id=501, source_kind=SYNTHETIC)
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
    parser.add_argument('--case', choices=('reference','contrast','safe_operation_stop',
                                           'law_required_stop'), default='reference')
    args = parser.parse_args()
    print(json.dumps(build(args.destination,args.case),sort_keys=True))
