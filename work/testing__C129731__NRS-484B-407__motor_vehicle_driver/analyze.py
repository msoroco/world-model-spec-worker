"""Saved native capability measurements and same-case follow-up decision."""
import argparse
import json
import pathlib
import statistics
import hashlib
import sys
import math

for parent in pathlib.Path(__file__).resolve().parents:
    supplied=parent/'runtime/main-pipeline-v1/scenario_pipeline'
    if supplied.is_dir():
        sys.path.insert(0,str(supplied))
        break
from worker_exchange.media import audit as audit_source_video
from worker_exchange.native_output import write_result


def native_result(attempt,report):
    """Build a draft shared-validator input from saved original measurements.

    Unknown physical causes remain false/pending, so this cannot assert
    acceptance merely because source files decoded.
    """
    import runner
    cfg=json.loads((attempt/'config.json').read_text())
    case=cfg['case']
    rows=[json.loads(s) for s in (attempt/'physical_samples.jsonl').read_text().splitlines() if s]
    mech=cfg['mechanism']
    if mech=='yield':
        requested=float(case['variable_assignments']['yield_hold_s']['value'])
        measured=sum(.05 for r in rows if -20<r['ego']['position_m'][0]<-9 and r['ego']['speed_mps']<.1)
        target='yield_hold_s';tolerance=.5
    elif mech=='uturn':
        requested=float(case['variable_assignments']['maneuver_station_m']['value'])
        measured=next((r['ego']['position_m'][0] for r in rows if r['route_index']>=70),rows[-1]['ego']['position_m'][0])
        target='maneuver_station_m';tolerance=5.0
    elif mech=='following':
        requested=float(case['variable_assignments']['commanded_surface_gap']['value'])
        measured=report['measurements']['observed_gap_m_last_100_mean']
        if measured is None:measured=0.0
        target='commanded_surface_gap';tolerance=2.0
    else:
        requested=runner.path_for(cfg,case)[-1][0]
        measured=rows[-1]['ego']['position_m'][0]
        target='reverse_end_x_m';tolerance=2.0
    endpoint=runner.path_for(cfg,case)[-1]
    last=rows[-1]['ego']
    completed=math.dist(last['position_m'][:2],endpoint)<=2.0 and last['speed_mps']<2.0
    evidence=[{'name':c['name'],'unit':c['unit'],'reference':'channels/'+c['name']+'.jsonl'}
              for c in case['recording_description']['channels']]
    evidence += [{'name':c['name'],'unit':c['unit'],'reference':'context.json'}
                 for c in case['recording_description']['context_inputs']]
    return {'status':'draft','case_id':case['case_id'],'measured_values':report['measurements'],
        'requested_variable_assignments':{k:v for k,v in case['variable_assignments'].items() if v['kind'] in ('controller','world_setup')},
        'target_checks':[{'target':target,'requested':requested,'measured':measured,
            'method':'saved native physical_samples.jsonl, exact case window','tolerance':tolerance,
            'matched':abs(requested-measured)<=tolerance,'physical_cause_confirmed':False,
            'cause_evidence':'physical_samples.jsonl; original physical meaning and visibility still require local inspection'}],
        'setup_confirmed':False,'behavior_attempted':bool(rows),'maneuver_completed':completed,
        'termination_reason':'route_endpoint_observed' if completed else 'bounded_episode_or_incomplete_motion',
        'physical_failure_flags':{'detection_validated':False},
        'trace_reference':'trace.jsonl','video_references':['view%d.mkv'%i for i in range(4)],
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':case['recording_description'],'recording_evidence':evidence,
        'realized_observables':report.get('realized_observables',{}),
        'physical_acceptance':False}


def analyze(attempt):
    attempt=pathlib.Path(attempt)
    cfg=json.loads((attempt/'config.json').read_text())
    rows=[json.loads(s) for s in (attempt/'physical_samples.jsonl').read_text().splitlines() if s]
    if not rows:raise ValueError('No original native samples')
    case=cfg['case']
    mech=cfg['mechanism']
    report={'format':'partition03-capability-report-v1','case_id':case['case_id'],'mechanism':mech,
            'sample_count':len(rows),'original_window_s':[rows[0]['time_s'],rows[-1]['time_s']],
            'physical_acceptance':False,'law_verdict':None,'measurements':{},'missing':[]}
    m=report['measurements']
    mapping=[json.loads(s) for s in (attempt/'video_frames.jsonl').read_text().splitlines() if s]
    evidence=[json.loads(s) for s in (attempt/'capture/evidence.jsonl').read_text().splitlines() if s]
    if len(mapping)!=len(rows) or len(evidence)!=len(rows):
        report['missing'].append('source/video/evidence frame count join')
    else:
        joined=all(a['frame']==b['native_frame']==c['original_frame'] and
                   abs(a['time_s']-b['time_s'])<.00001 for a,b,c in zip(rows,mapping,evidence))
        m['original_frame_join_valid']=joined
        if not joined:report['missing'].append('original frame identity or timestamp mismatch')
    for channel in case['recording_description']['channels']:
        path=attempt/'channels'/(channel['name']+'.jsonl')
        if not path.exists():
            report['missing'].append('missing channel '+channel['name']);continue
        values=[json.loads(s) for s in path.read_text().splitlines() if s]
        if len(values)!=len(rows) or any(abs(v['time_s']-r['time_s'])>.00001 or v['value'] is None for v,r in zip(values,rows)):
            report['missing'].append('channel count/time/value mismatch '+channel['name'])
    decoded={}
    mapping_sha=hashlib.sha256((attempt/'video_frames.jsonl').read_bytes()).hexdigest()
    for i in range(4):
        video=attempt/('view%d.mkv'%i)
        if not video.is_file():
            report['missing'].append('missing camera '+str(i));continue
        try:
            receipt=audit_source_video(video,len(rows),mapping_sha256=mapping_sha,
                receipt=attempt/('view%d.source-decode.json'%i))
            decoded[str(i)]={'frames':receipt['frames'],'dimensions':receipt['dimensions'],
                             'source_sha256':receipt['video_sha256'],
                             'receipt':'view%d.source-decode.json'%i}
        except (OSError,ValueError) as exc:
            report['missing'].append('source camera decode '+str(i)+': '+str(exc))
    m['decoded_source_views']=decoded
    if mech=='yield':
        occupancy=[r for r in rows if r['others'] and -7<=r['others'][0]['position_m'][0]<=7 and -7<=r['others'][0]['position_m'][1]<=7]
        m['counterpart_intersection_occupancy_samples']=len(occupancy)
        m['ego_min_speed_while_counterpart_inside_mps']=min((r['ego']['speed_mps'] for r in occupancy),default=None)
        m['ego_entered_during_counterpart_occupancy']=any(-7<=r['ego']['position_m'][0]<=7 for r in occupancy)
        m['counterpart_first_occupancy_s']=occupancy[0]['time_s'] if occupancy else None
        ego_entry=next((r['time_s'] for r in rows if r['ego']['position_m'][0]>=-7),None)
        m['ego_first_intersection_entry_s']=ego_entry
        m['realized_time_to_conflict_s']=None if ego_entry is None or not occupancy else ego_entry-occupancy[0]['time_s']
        if case['target_type']=='judgment_sweep':
            source=attempt/'channels/counterpart_initial_gap_m.jsonl'
            values=[json.loads(s) for s in source.read_text().splitlines() if s]
            report['realized_observables']={'counterpart_initial_gap_m':{
                'value':values[0]['value'],'unit':'m',
                'method':'native counterpart body leading edge minus intersection north edge y=7 m',
                'time_window':'entire original episode','statistic':'first',
                'sample_window_s':[values[0]['time_s'],values[-1]['time_s']],
                'reference':'channels/counterpart_initial_gap_m.jsonl'}}
        visible=[r for r in rows if r['ego']['position_m'][0]<-7 and
                 r.get('counterpart_visibility',{}).get('visible_body_samples',0)>=3]
        m['nearest_observed_approach_view_location_m']=max((r['ego']['position_m'][0] for r in visible),default=None)
        m['nearest_observed_approach_view_time_s']=max(visible,key=lambda r:r['ego']['position_m'][0])['time_s'] if visible else None
        m['view_measurement']='Actual ego-eye rays to eight native counterpart body vertices; three visible body samples is an engineering reporting criterion, not a legal threshold.'
        if not occupancy:report['missing'].append('counterpart native intersection occupancy')
        if not visible:report['missing'].append('actual approaching counterpart visibility on ego approach')
        report['missing'].append('native yield-sign placement and physical near-side line/crosswalk absence confirmation')
    elif mech=='uturn':
        m['turn_station_m']=case['variable_assignments']['maneuver_station_m']['value']
        scans=[r for r in rows if 'visibility_profile' in r]
        m['two_approach_scan_frames']=[r['frame'] for r in scans]
        m['requested_horizon_m']=case['variable_assignments']['requested_sight_distance']['value']
        horizons={}
        for side in ('-1','1'):
            horizon=[]
            for r in scans:
                profile=r['visibility_profile'][side]
                visible=[p['requested_distance_m'] for p in profile if p.get('visible_sample_count',0)>=3]
                horizon.append({'frame':r['frame'],'time_s':r['time_s'],
                    'farthest_three_of_nine_body_samples_visible_m':max(visible) if visible else None,
                    'censored_at_230_m':bool(visible and max(visible)==230)})
            horizons[side]=horizon
        m['potential_driver_body_visibility_horizons']=horizons
        if not scans:report['missing'].append('two-approach potential-driver body visibility scans during actual maneuver')
        report['missing'].append('physical camera interpretation and legal meaning of visibility remain unresolved')
    elif mech=='following':
        gaps=[]
        for r in rows:
            if r['others']:
                lead=r['others'][0]['body_vertices_m'];ego=r['ego']['body_vertices_m']
                gaps.append(min(v[0] for v in lead)-max(v[0] for v in ego))
        m['observed_gap_m_last_100_mean']=statistics.mean(gaps[-100:]) if gaps else None
        m['requested_gap_m']=case['variable_assignments']['commanded_surface_gap']['value']
        m['gap_error_m']=None if not gaps else m['observed_gap_m_last_100_mean']-m['requested_gap_m']
        widths=[]
        for r in rows:
            for actor in [r['ego']]+r['others']:
                body=actor['body_vertices_m']
                widths.append(max(v[1] for v in body)-min(v[1] for v in body))
        m['minimum_overall_body_width_m']=min(widths) if widths else None
        m['all_observed_actors_at_least_80_inches_wide']=bool(widths) and min(widths)>=2.032
        report['missing'].append('native truck overall width and single same-direction lane confirmation')
    elif mech=='reverse':
        suffix=case['case_id'].rsplit('__',1)[-1]
        m['minimum_body_x_m']=min(v[0] for r in rows for v in r['ego']['body_vertices_m'])
        m['maximum_body_x_m']=max(v[0] for r in rows for v in r['ego']['body_vertices_m'])
        m['all_controls_reverse']=all(r['ego']['applied_control']['reverse'] for r in rows)
        m['target_variant']=suffix
        def overlaps(body,x0,x1,y0,y1):
            return min(v[0] for v in body)<=x1 and max(v[0] for v in body)>=x0 and \
                min(v[1] for v in body)<=y1 and max(v[1] for v in body)>=y0
        m['crosswalk_body_overlap_frames']=[r['frame'] for r in rows if overlaps(r['ego']['body_vertices_m'],16.5,19.5,-7,0)]
        m['intersection_body_overlap_frames']=[r['frame'] for r in rows if overlaps(r['ego']['body_vertices_m'],-7,7,-7,7)]
        report['missing'].append('native physical crosswalk rendering and boundary survey')
    report['decision']='inspect_and_repair_same_case' if report['missing'] else 'inspect_original_evidence'
    report['follow_up_configuration']={'selected_case_id':case['case_id'],'source_config':'config.json',
                                      'freeze_targets':True,'new_attempt_required_for_construction_repair':True}
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    attempt=pathlib.Path(a.attempt)
    report=analyze(attempt)
    pathlib.Path(a.output).write_text(json.dumps(report,indent=2)+'\n')
    write_result(attempt,native_result(attempt,report))
