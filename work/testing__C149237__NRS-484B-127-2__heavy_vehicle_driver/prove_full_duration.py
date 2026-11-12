"""Authored-road, 900-frame CPU source and media diagnostic for truck following.

This generated motion and colored video are synthetic. They test the full
duration envelope and source joins, not CARLA behavior or actual visibility.
"""
import argparse
import json
import math
import subprocess
from pathlib import Path

from delivery_audit import CAMERAS, SIZES, digest, media_module, source_join
from truck_measurements import analyze
from truck_site import validate_site, initial_pair, validate_motion_envelope, ROAD

HERE=Path(__file__).resolve().parent


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def dump_rows(path,items):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n'
                            for row in items))


def vertices(x,y,width,z=False):
    h=width/2
    xy=[[x-5,y-h],[x-5,y+h],[x+5,y-h],[x+5,y+h]]
    if z:
        return [[a,b,c] for c in (0,2.8) for a,b in xy]
    return xy


def actor(actor_id,blueprint,x,y,width):
    return {'actor_id':actor_id,'blueprint_id':blueprint,'road_id':149237,
            'lane_id':-1,'overall_width_m':width,
            'overall_width_source':'synthetic sample dimensions; not Native measurement',
            'is_truck_or_combination':True,'body_vertices_xy_m':vertices(x,y,width),
            'velocity_mps':[12,0,0]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args()
    root=args.output_root.resolve()
    if root.exists():
        raise ValueError('Use a fresh full-duration diagnostic root')
    root.mkdir(parents=True)
    config=json.loads((HERE/'config.json').read_text())
    case=config['selected_case_id']
    if config['rate_hz']!=20 or config['duration_s']!=45:
        raise ValueError('Current truck capture duration changed')
    site=validate_site()
    placement=initial_pair('gap_below_500ft',5.0,5.0)
    envelope=validate_motion_envelope(placement,5.0,speed_mps=12.0,duration_s=45.0)
    write(root/'config.json',config)
    context={'native_map_id':'synthetic-authored-road-diagnostic',
             'road_id':site['road_id'],'lane_id':site['lane_id'],
             'same_direction_lane_count':site['same_direction_lane_count'],
             'lane_forward_xy':[1.0,0.0],
             'lane_count_source':'authored OpenDRIVE XML; not a Native readback',
             'authored_road_sha256':site['road_sha256']}
    write(root/'road_context.json',context)
    (root/'road.xodr').write_bytes(ROAD.read_bytes())
    history,mapping,trace,evidence=[],[],[],[]
    y=placement['ego_center_xy_m'][1]
    for index in range(900):
        frame=1000+index;time_s=round((index+1)/20,8)
        dx=12*index/20
        ego=actor(205,site['blueprint_ids'][0],placement['ego_center_xy_m'][0]+dx,y,2.2)
        lead=actor(206,site['blueprint_ids'][1],placement['lead_center_xy_m'][0]+dx,y,2.2)
        history.append({'frame':frame,'time_s':time_s,'ego':ego,'lead':lead})
        mapping.append({'video_frame':index,'carla_frame':frame,'native_frame':frame,'time_s':time_s})
        trace.append({'frame':frame,'time_s':time_s,'case_id':case})
        participants=[{'actor_id':item['actor_id'],'blueprint':item['blueprint_id'],
                       'body_vertices_m':vertices((placement['ego_center_xy_m'][0] if item is ego else
                                                   placement['lead_center_xy_m'][0])+dx,y,2.2,z=True),
                       'velocity_mps':[12,0,0]} for item in (ego,lead)]
        evidence.append({'original_frame':frame,'recording_time_s':time_s,
                         'original_observations':{'participant_inventory':'all two generated truck actors',
                                                  'participants':participants}})
    for name,items in [('truck_history.jsonl',history),('video_frames.jsonl',mapping),
                       ('trace.jsonl',trace),('capture/evidence.jsonl',evidence)]:
        dump_rows(root/name,items)
    joined=source_join(root,case,expected_frames=900)
    measured=analyze(root)
    gaps=[row['longitudinal_body_gap_m'] for row in measured['samples']]
    if len(gaps)!=900 or any(not math.isclose(gap,150.0,abs_tol=1e-6) for gap in gaps):
        raise ValueError('Full duration body gap differs from authored target')
    if history[-1]['lead']['body_vertices_xy_m'][-1][0] > 1150:
        raise ValueError('Diagnostic lead truck exceeded road margin')
    media=media_module()
    videos={}
    for name,(width,height) in SIZES.items():
        path=root/(name+'.mkv')
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
                        '-f','lavfi','-i',f'color=c=black:s={width}x{height}:r=20',
                        '-vf','drawbox=x=16:y=16:w=32:h=32:color=red:t=fill',
                        '-frames:v','900','-c:v','ffv1','-pix_fmt','yuv444p',str(path)],check=True)
        videos[name]=path
    media.check_four_view_sources(videos)
    decodes={name:media.audit(path,900,mapping_sha256=joined['sources']['video_frames.jsonl'],
                             receipt=root/(name+'-decode.json'))
             for name,path in videos.items()}
    if any(value['frames']!=900 for value in decodes.values()):
        raise ValueError('Full source camera decode is incomplete')
    try:
        source_join(root,case,expected_frames=901)
    except ValueError as error:
        if 'frame count differs from planned capture' not in str(error):
            raise
        negative=str(error)
    else:
        raise ValueError('Incomplete frame count was accepted')
    receipt={'format':'worker-full-duration-truck-cpu-diagnostic','passed':True,
             'diagnostic_fixture':True,'physical_acceptance_claimed':False,
             'case_id':case,'frames':900,'rate_hz':20,'duration_s':45,
             'site':site,'motion_envelope':envelope,'sample_half_lengths_m':[5.0,5.0],
             'realized_native_dimensions_claimed':False,
             'source_join':joined,'minimum_body_gap_m':min(gaps),
             'maximum_body_gap_m':max(gaps),
             'camera_sources':{name:{'sha256':digest(path),
                                     'decode_receipt_sha256':digest(root/(name+'-decode.json'))}
                               for name,path in videos.items()},
             'negative_expected_error':negative,
             'limitations':['generated truck motion','colored media has no truck pixels',
                            'authored OpenDRIVE was parsed, not loaded into CARLA']}
    write(args.receipt,receipt)
    print(json.dumps({'frames':900,'cameras':len(videos),'passed':True,
                      'diagnostic_fixture':True,'physical_acceptance_claimed':False},sort_keys=True))


if __name__=='__main__':
    main()
