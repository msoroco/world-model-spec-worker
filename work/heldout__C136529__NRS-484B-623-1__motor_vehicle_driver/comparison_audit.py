"""Independent raw-source comparison of narrow-road slow-speed cases.

This checks fixed construction and declared physical differences. It does not
classify the statutory judgment or infer physical acceptance from fixtures.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

PAIRS={
 'traffic_impedance':('flowing_reference','slow_with_following_traffic',
                       {'ego_target_mps'}),
 'safety_obstruction':('slow_with_following_traffic','slow_for_obstruction',
                       {'obstruction_present'}),
 'lawful_control':('slow_with_following_traffic','slow_under_control',
                  {'control_present','ego_target_mps','follower_cruise_mps'}),
 'safety_speed_response':('slow_for_obstruction','safety_speed_probe__slow_for_obstruction',
                          {'ego_target_mps'}),
 'control_speed_response':('slow_under_control','control_speed_probe__slow_under_control',
                           {'ego_target_mps'}),
}

def _hash(path):return sha256(Path(path).read_bytes()).hexdigest()
def _rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]

def _case(root):
    root=Path(root)
    for name in ('config.json','slow_context.json','video_frames.jsonl',
                 'trace.jsonl','participant_state.jsonl','prop_state.jsonl','road.xodr'):
        if not (root/name).is_file():raise ValueError('Missing comparison original source: '+name)
    cfg=json.loads((root/'config.json').read_text())
    context=json.loads((root/'slow_context.json').read_text())
    if cfg['case_branch']!=context['case_branch'] or not cfg['selected_case_id'].endswith('__'+cfg['case_branch']):
        raise ValueError('Case branch differs from original context')
    weather=context.get('native_weather')
    if not isinstance(weather,dict) or weather.get('precipitation')!=0 or weather.get('wetness')!=0:
        raise ValueError('Dry-weather comparison source absent or differs')
    frames=_rows(root/'video_frames.jsonl');trace=_rows(root/'trace.jsonl')
    actors=_rows(root/'participant_state.jsonl');props=_rows(root/'prop_state.jsonl')
    if not frames or not len(frames)==len(trace)==len(actors)==len(props):
        raise ValueError('Missing synchronized comparison frames')
    for i,(f,t,a,p) in enumerate(zip(frames,trace,actors,props)):
        identity=f['carla_frame'],f['time_s']
        if f['video_frame']!=i or any((row.get('frame'),row.get('time_s'))!=identity for row in (t,a,p)):
            raise ValueError('Comparison original frame join differs')
        if any(a.get(role+'_valid') is not True for role in ('ego','follower','opposing')):
            raise ValueError('Comparison participant missing')
    return {'cfg':cfg,'context':context,'actors':actors,'props':props,
            'frame_count':len(frames),'road_sha256':_hash(root/'road.xodr'),
            'participant_sha256':_hash(root/'participant_state.jsonl'),
            'prop_sha256':_hash(root/'prop_state.jsonl')}

def audit(comparison_id,left,right):
    if comparison_id not in PAIRS:raise ValueError('Unknown exact comparison')
    expected_left,expected_right,allowed=PAIRS[comparison_id]
    a,b=_case(left),_case(right)
    if (not a['cfg']['selected_case_id'].endswith('__'+expected_left)
            or not b['cfg']['selected_case_id'].endswith('__'+expected_right)):
        raise ValueError('Comparison selects another exact case pair')
    fixed=('cell_id','law_id','actor','rate_hz','duration_s','frames','cameras',
           'required_atoms','source_packets')
    for key in fixed:
        if a['cfg'].get(key)!=b['cfg'].get(key):
            raise ValueError('Fixed comparison condition differs: '+key)
    if a['road_sha256']!=b['road_sha256']:
        raise ValueError('Fixed comparison road geometry differs')
    if a['context']['native_weather']!=b['context']['native_weather']:
        raise ValueError('Fixed comparison weather differs')
    if a['frame_count']!=b['frame_count']:
        raise ValueError('Fixed comparison frame count differs')
    changed={key for key in ('ego_target_mps','follower_cruise_mps')
             if a['cfg'].get(key)!=b['cfg'].get(key)}
    left_obstruction=all(p.get('obstruction_present') is True and
                         len((p.get('obstruction_geometry') or {}).get('vertices_xyz',[]))>=4 for p in a['props'])
    right_obstruction=all(p.get('obstruction_present') is True and
                          len((p.get('obstruction_geometry') or {}).get('vertices_xyz',[]))>=4 for p in b['props'])
    left_control=all(p.get('control_present') is True and
                     len((p.get('control_geometry') or {}).get('vertices_xyz',[]))>=4 for p in a['props'])
    right_control=all(p.get('control_present') is True and
                      len((p.get('control_geometry') or {}).get('vertices_xyz',[]))>=4 for p in b['props'])
    if left_obstruction!=right_obstruction:changed.add('obstruction_present')
    if left_control!=right_control:changed.add('control_present')
    if changed!=allowed:raise ValueError('Declared comparison differences absent or extra')
    for key in ('route_step_m','follower_gain','speed_kp','speed_brake_gain'):
        if a['cfg'].get(key)!=b['cfg'].get(key):
            raise ValueError('Shared controller policy differs: '+key)
    if comparison_id=='lawful_control' and not b['context'].get('regulatory_source'):
        raise ValueError('Control difference lacks regulatory source')
    return {'format':'worker-slow-comparison-audit','comparison_id':comparison_id,
            'case_ids':[a['cfg']['selected_case_id'],b['cfg']['selected_case_id']],
            'fixed_conditions_checked':list(fixed)+['road_geometry','native_weather','frame_count','controller_policy'],
            'declared_differences':sorted(changed),
            'mean_ego_speeds_mps':[sum(r['ego_speed_mps'] for r in x['actors'])/x['frame_count'] for x in (a,b)],
            'sources':[{'participant_sha256':x['participant_sha256'],'prop_sha256':x['prop_sha256'],
                        'road_sha256':x['road_sha256']} for x in (a,b)],
            'legal_judgment':'unresolved','physical_acceptance_claimed':False}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--comparison',required=True)
    parser.add_argument('--left',required=True);parser.add_argument('--right',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    out=Path(args.output)
    if out.exists():raise ValueError('Retain previous comparison audit')
    out.write_text(json.dumps(audit(args.comparison,args.left,args.right),indent=2)+'\n')
if __name__=='__main__':main()
