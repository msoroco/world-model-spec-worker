"""Saved-only source measurements for marked approach and connected left turn."""
import argparse,hashlib,json
from math import atan2,degrees,isfinite,pi
from pathlib import Path
from lane_footprint import measure_footprint

def required(root,name):
    p=Path(root)/name
    if not p.is_file() or not p.read_bytes():raise ValueError('Missing required source: '+name)
    return p,hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def signed_heading(first,last):
    a=atan2(first[1],first[0]);b=atan2(last[1],last[0]);return degrees((b-a+pi)%(2*pi)-pi)
def original_approach_fraction(original):
    lane=original.get('original_approach_lane')
    if not original.get('approach_active') or not lane:return None
    polygon=lane['polygon_xy_m'];corners=original['ego_corners_xy_m'];width=lane['lane_width_m']
    if width<=0 or len(polygon)<4 or len(corners)<4:raise ValueError('Original turn fraction geometry incomplete')
    center=[sum(point[i] for point in polygon)/len(polygon) for i in (0,1)]
    ego=[sum(point[i] for point in corners)/len(corners) for i in (0,1)]
    heading=lane['lane_heading_xy'];normal=(-heading[1],heading[0])
    return abs(sum((ego[i]-center[i])*normal[i] for i in (0,1)))/width
def measure_marked_turn(root):
    root=Path(root);context=json.loads(required(root,'turn_scene_context.json')[0].read_text())
    if not (context.get('connected_native_waypoints') is True and 45<=context['requested_heading_change_deg']<=135 and context.get('lawful_turn_facts') is None):
        raise ValueError('Connected left route or unresolved lawful facts missing')
    mapping=rows(required(root,'video_frames.jsonl')[0]);trace=rows(required(root,'trace.jsonl')[0]);original=rows(required(root,'turn_originals.jsonl')[0])
    if not mapping or not len(mapping)==len(trace)==len(original):raise ValueError('Turn original frame inventory differs')
    ego=None;measured=[];prior=None
    for i,(f,t,o) in enumerate(zip(mapping,trace,original)):
        identity=(f.get('carla_frame'),f.get('time_s'))
        if (f.get('video_frame')!=i or (t.get('frame'),t.get('time_s'))!=identity or
            (o.get('frame'),o.get('time_s'))!=identity):raise ValueError('Turn original frame join differs')
        if prior is not None and (identity[0]!=prior[0]+1 or identity[1]<=prior[1]):raise ValueError('Turn original frames skipped')
        if ego is None:ego=o['ego_id']
        if o['ego_id']!=ego:raise ValueError('Native ego identity changed')
        lane=o.get('original_approach_lane')
        if o.get('approach_active'):
            if not lane or lane['road_id']!=context['approach_road_id'] or lane['lane_id']!=context['approach_lane_id']:
                raise ValueError('Original marked approach geometry differs')
            metric=measure_footprint(lane['polygon_xy_m'],o['ego_corners_xy_m'])
            measured.append({'frame':identity[0],'time_s':identity[1],
                'minimum_corner_clearance_m':metric['minimum_corner_clearance_m'],
                'full_footprint_inside':metric['full_footprint_inside'],
                'boundary_crossing':metric['boundary_crossing']})
        elif lane is not None:raise ValueError('Unmarked turn phase carries stale approach slice')
        prior=identity
    if len(measured)<2:raise ValueError('Insufficient original marked approach coverage')
    delta=signed_heading(original[0]['heading_xy'],original[-1]['heading_xy'])
    if not isfinite(delta):raise ValueError('Turn heading observation invalid')
    signal=sum('LeftBlinker' in str(o.get('ego_light_state')) for o in original)
    return {'ego_id':ego,'frames':len(original),'approach_frames':len(measured),
            'approach_clearance':measured,'minimum_approach_clearance_m':min(r['minimum_corner_clearance_m'] for r in measured),
            'observed_heading_change_deg':delta,'left_indicator_readback_frames':signal,
            'first_approach_road_id':context['approach_road_id'],
            'planned_exit_road_id':context['exit_road_id'],
            'lawful_turn_facts':None,'legal_exception_claimed':False}
def measure_turn_context(root):
    value=measure_marked_turn(root)
    return {'connected_left_route':True,'observed_heading_change_deg':value['observed_heading_change_deg'],
            'left_indicator_readback_frames':value['left_indicator_readback_frames'],
            'lawful_turn_facts':None,'legal_exception_claimed':False}
def analyze(attempt,*,write_channel=True):
    root=Path(attempt);config=json.loads(required(root,'config.json')[0].read_text());case=config.get('selected_case_id','')
    if (config.get('law_id'),config.get('cell_id'),config.get('actor'))!=('LVMC-11-18-030-B','C5191','motor_vehicle_driver') or not case.startswith('heldout__C5191__LVMC-11-18-030-B__motor_vehicle_driver__'):
        raise ValueError('Wrong C5191 exact turn identity')
    value=measure_marked_turn(root);sources={n:required(root,n)[1] for n in ('video_frames.jsonl','trace.jsonl','turn_originals.jsonl','turn_scene_context.json')}
    obs={'marked_turn_observation':{'method':'measure_marked_turn','value':value,'sources':sources}}
    if not case.endswith('__left_turn_lane_contained_approach'):
        obs['turn_preparation_context']={'method':'measure_turn_context','value':measure_turn_context(root),'sources':sources}
    if write_channel:
        original=rows(root/'turn_originals.jsonl');by_frame={r['frame']:r for r in value['approach_clearance']}
        channels={'lane_clearance_m':[(o['frame'],o['time_s'],by_frame[o['frame']]['minimum_corner_clearance_m']) for o in original if o['frame'] in by_frame],
                  'turn_indicator_state':[(o['frame'],o['time_s'],o['ego_light_state']) for o in original],
                  'ego_turn_motion':[(o['frame'],o['time_s'],{'position_xy_m':o['position_xy_m'],'heading_xy':o['heading_xy']}) for o in original],
                  'marked_approach_context':[(o['frame'],o['time_s'],o['original_approach_lane']) for o in original if o['approach_active']]}
        if '__turn_excursion-' in case:
            channels['lane_crossing_fraction']=[(o['frame'],o['time_s'],original_approach_fraction(o)) for o in original if o['approach_active']]
        for name,values in channels.items():
            path=root/(name+'.jsonl')
            if path.exists():raise ValueError('Derived turn channel already exists: '+name)
            path.write_text(''.join(json.dumps({'frame':frame,'time_s':time_s,'value':value},allow_nan=False)+'\n' for frame,time_s,value in values))
    return {'format':'worker-analysis-report','case_id':case,'measurements':obs,
            'limitations':['Synthetic fixture and connected route intent do not establish physical turn completion or lawful-turn exception.'],
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}
def build_result(attempt,report):
    root=Path(attempt);config=json.loads((root/'config.json').read_text());description=config['case']['recording_description'];value=report['measurements']['marked_turn_observation']['value']
    evidence=[{'name':item['name'],'unit':item['unit'],'reference':item['name']+'.jsonl','sha256':required(root,item['name']+'.jsonl')[1]} for item in description['channels']]
    realized={'lane_clearance_m':{'unit':'m','method':'signed original body-corner clearance','time_window':'marked approach frames','statistic':'min','reference':'lane_clearance_m.jsonl','value':value['minimum_approach_clearance_m'],'sample_window_s':[value['approach_clearance'][0]['time_s'],value['approach_clearance'][-1]['time_s']]}}
    if '__turn_excursion-' in report['case_id']:
        fraction=rows(root/'lane_crossing_fraction.jsonl')
        realized['lane_crossing_fraction']={'unit':'fraction','method':'maximum absolute original ego-center displacement from marked approach lane center divided by original lane width','time_window':'marked approach original frames','statistic':'max','reference':'lane_crossing_fraction.jsonl','value':max(row['value'] for row in fraction),'sample_window_s':[fraction[0]['time_s'],fraction[-1]['time_s']]}
    return {'case_id':report['case_id'],'measured_values':{k:v['value'] for k,v in report['measurements'].items()},
            'target_checks':[{'target':'original marked approach and connected left turn','requested':'retained physical boundary and heading history','measured':value['minimum_approach_clearance_m'],'method':'original Native corners, waypoint lane slice and heading','tolerance':None,'matched':False,'physical_cause_confirmed':False,'cause_evidence':'Original source joined; Native physical and lawful review pending'}],
            'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,
            'termination_reason':'Saved marked-turn measurements complete; physical and lawful outcomes unverified',
            'physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl',
            'video_references':['overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'],
            'video_frame_map_reference':'video_frames.jsonl','recording_description':description,
            'recording_evidence':evidence,'realized_observables':realized,
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True);args=parser.parse_args();report=analyze(args.attempt);out=Path(args.output)
    if out.exists():raise ValueError('Retain prior turn analysis report')
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt,build_result(args.attempt,report))
if __name__=='__main__':main()
