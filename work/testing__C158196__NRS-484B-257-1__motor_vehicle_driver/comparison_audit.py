"""Independent source comparison of the two C158196 signal mechanisms."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from shapely.geometry import MultiPoint, Polygon

PREFIX = 'testing__C158196__NRS-484B-257-1__motor_vehicle_driver__'
CAMERAS = ('overview','approach','reference_corner','driver_reference')
FIXED = ('native_map_id','intersection_id','ego_road_id','ego_lane_id',
         'ego_route_lanes','intersection_polygon_xy_m','signed_entrance_source',
         'junction_source','through_road_id','through_lane_id','through_route_lanes')
PAIRS = {'signal_exception_control':('signal_controls_ego','signal_visible_not_governing'),
         'signal_exception_state':('signal_controls_ego','signal_off')}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing comparison original: '+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def source(root):
    root = Path(root)
    config = json.loads((root/'config.json').read_text())
    case = config.get('selected_case_id')
    if not isinstance(case,str) or not case.startswith(PREFIX):
        raise ValueError('Comparison selects a different exact case')
    context = json.loads((root/'signal_context.json').read_text())
    signal, interaction, frames = (rows(root/name) for name in
                                   ('signal_history.jsonl','interaction_history.jsonl','video_frames.jsonl'))
    if len(signal)<3 or len(signal)!=len(interaction) or len(signal)!=len(frames):
        raise ValueError('Comparison original histories differ')
    polygon = Polygon(context['intersection_polygon_xy_m'])
    if not polygon.is_valid or polygon.area<=0:
        raise ValueError('Comparison intersection polygon invalid')
    entry = None
    for index,(s,b,f) in enumerate(zip(signal,interaction,frames)):
        fid = f.get('carla_frame')
        if (s.get('frame')!=fid or b.get('frame')!=fid or f.get('video_frame')!=index or
                s.get('time_s')!=f.get('time_s') or b.get('time_s')!=f.get('time_s') or
                f.get('camera_frames')!={name:fid for name in CAMERAS}):
            raise ValueError('Comparison original frame join invalid')
        body = MultiPoint([(v[0],v[1]) for v in b['ego']['body_vertices_m']]).convex_hull
        if entry is None and body.intersects(polygon):entry = s
    if entry is None or entry is signal[0]:
        raise ValueError('Comparison lacks original approach and entry')
    review = json.loads((root/'signal_head_review.json').read_text())
    if (review.get('case_id')!=case or
            review.get('reviewed_carla_frames')!=[f['carla_frame'] for f in frames] or
            review.get('observations',{}).get('signed_entrance_visible') is not True):
        raise ValueError('Comparison lacks source-camera signed-entrance review')
    profile=[]
    for name in CAMERAS:
        video = root/(name+'.mkv')
        if review.get('camera_sha256',{}).get(name)!=sha(video):
            raise ValueError('Comparison camera review source changed')
        probe = subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
                '-show_entries','stream=width,height,r_frame_rate','-of','json',str(video)],text=True)
        profile.append(json.loads(probe)['streams'][0])
    hashes={name:sha(root/name) for name in ('config.json','signal_context.json',
            'signal_history.jsonl','interaction_history.jsonl','video_frames.jsonl',
            'signal_head_review.json')}
    result = json.loads((root/'result.json').read_text())
    if (result.get('case_id') != case or any(
            result.get('source_evidence_hashes', {}).get(name) != digest
            for name,digest in hashes.items())):
        raise ValueError('Sealed comparison source hash differs')
    return {'case_id':case,'context':context,'entry':entry,'profile':profile,'hashes':hashes}


def audit(left,right,comparison_id):
    if comparison_id not in PAIRS:
        raise ValueError('Unknown exact signal comparison')
    first,second=source(left),source(right)
    if (first['case_id'],second['case_id'])!=tuple(PREFIX+s for s in PAIRS[comparison_id]):
        raise ValueError('Comparison selects different exact cases')
    if any(first['context'].get(k)!=second['context'].get(k) for k in FIXED) or first['profile']!=second['profile']:
        raise ValueError('Comparison changed fixed intersection, route or camera profile')
    a,b=first['entry'],second['entry']
    if comparison_id=='signal_exception_control':
        if (a['signal_controls_ego'] is not True or b['signal_controls_ego'] is not False or
                a['signal_state']!=b['signal_state'] or a['signal_state']=='Off' or
                first['context']['native_signal_id']==second['context']['native_signal_id']):
            raise ValueError('Comparison lacks isolated governing-head difference')
    else:
        if (a['signal_controls_ego'] is not True or b['signal_controls_ego'] is not True or
                a['signal_state']=='Off' or b['signal_state']!='Off' or
                first['context']['native_signal_id']!=second['context']['native_signal_id']):
            raise ValueError('Comparison lacks isolated operative-state difference')
    return {'format':'worker-c158196-independent-comparison-audit',
            'comparison_id':comparison_id,'case_ids':[first['case_id'],second['case_id']],
            'fixed_conditions_checked':[*FIXED,'four_camera_capture_profile'],
            'declared_difference_observed':True,
            'source_hashes':{'primary':first['hashes'],'comparison':second['hashes']},
            'physical_acceptance_claimed':False,'legal_conclusion':'unresolved'}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--left',required=True)
    parser.add_argument('--right',required=True)
    parser.add_argument('--comparison',required=True)
    args=parser.parse_args()
    print(json.dumps(audit(args.left,args.right,args.comparison),indent=2))
