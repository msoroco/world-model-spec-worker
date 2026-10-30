#!/usr/bin/env python3
"""Measured window reports and event-focused WebM views of saved recordings."""
import argparse
import fcntl
import hashlib
import json
import math
from pathlib import Path
import subprocess
from batch_pipeline.store import atomic
from batch_pipeline.speed_policy import MPH_MPS


def rows(path):
    with Path(path).open() as stream:return [json.loads(line) for line in stream]


def units(value):
    return {'m/s':value,'mph':value/MPH_MPS,'km/h':value*3.6}


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def evaluate_speed(case, trace, window, limit, complete, applicability=None, delivered_speeds=None):
    selected=[r for r in trace if window and window[0]<=r['time_s']<=window[1]]
    valid=bool(complete and trace and all(math.isfinite(r.get('speed_mps',float('nan'))) for r in trace))
    if delivered_speeds is not None:
        valid=valid and len(delivered_speeds)==len(trace) and all(math.isfinite(v) for v in delivered_speeds)
    known=bool(applicability is not None and len(applicability)==len(trace)
               and all(isinstance(v,bool) for v in applicability))
    label_trace=[dict(r,speed_mps=v) for r,v in zip(trace,delivered_speeds)] if delivered_speeds is not None else trace
    applicable=[r for r,v in zip(label_trace,applicability or []) if v is True]
    breaches=[r for r in applicable if r['speed_mps']>limit]
    outside=[r for r in breaches if not window or not window[0]<=r['time_s']<=window[1]]
    values=[r['speed_mps'] for r in selected] if all(math.isfinite(r['speed_mps']) for r in selected) else []
    target=case['variable_assignments']['commanded_approach_speed']['value']
    label=('non_compliant' if breaches else 'compliant') if valid and known and applicable else 'unknown'
    return {'scope':'Full delivered trace, restricted only by evidenced rule applicability',
        'label_scope':'full_delivered_trace','window_purpose':'controller_target_attainment_only',
        'sample_window_s':window,'first_original_frame':selected[0]['frame'] if selected else None,
        'last_original_frame':selected[-1]['frame'] if selected else None,'samples':len(selected),
        'limit':units(limit),'requested':units(target),
        'mean':units(sum(values)/len(values)) if values else None,
        'minimum':units(min(values)) if values else None,'maximum':units(max(values)) if values else None,
        'maximum_tracking_error_mph':max(abs(v-target)/MPH_MPS for v in values) if values else None,
        'expected_speed_rule_label':label,'intended_numeric_label':'non_compliant' if case['case_id'].endswith('-above') else 'compliant',
        'label_speed_source':'Delivered TrafficSpec subject kin.speed in m/s' if delivered_speeds is not None else 'Provided measured trace speed_mps',
        'applicability_confirmed':known,'applicable_samples':len(applicable),
        'applicable_frames':[r['frame'] for r in applicable],
        'full_trace_maximum':units(max(r['speed_mps'] for r in trace)) if valid else None,
        'middle_overshoot_flag':bool(case['case_id'].endswith('-at') and breaches),
        'exceedance_frames':[r['frame'] for r in breaches],
        'exceedance_times_s':[r['time_s'] for r in breaches],
        'first_exceedance_time_s':breaches[0]['time_s'] if breaches else None,
        'last_exceedance_time_s':breaches[-1]['time_s'] if breaches else None,
        'outside_window_exceedance_frames':[r['frame'] for r in outside],
        'outside_window_exceedance_times_s':[r['time_s'] for r in outside],
        'automatic_rerun':False,'clamped':False,
        'failure_reason':None if label!='unknown' else 'Incomplete evidence or unconfirmed rule applicability'}


def archive_report(path):
    if path.exists():
        contents=path.read_bytes();folder=path.parent/'report_history';folder.mkdir(exist_ok=True)
        archived=folder/(path.stem+'-'+hashlib.sha256(contents).hexdigest()+path.suffix)
        if not archived.exists():archived.write_bytes(contents)


def speed_applicability(case,attempt,trace,config,result):
    if not result.get('setup_confirmed'):return None,'Setup not confirmed'
    if case.get('target_law_id')=='NRS-484B-600-1e':
        return [True]*len(trace),'80 mph numeric cap over the complete authored highway recording; synthetic law-test context'
    if case.get('target_law_id')=='NRS-484B-600-1c':
        path=attempt/'governed_portion_occupancy.jsonl'
        if not path.exists() or not config.get('zone') or not config.get('posting'):return None,'Missing posted-zone evidence'
        records=rows(path)
        if len(records)!=len(trace) or any(abs(a['time_s']-b['time_s'])>1e-6 for a,b in zip(records,trace)):
            return None,'Posted-zone evidence is not joined to all recorded frames'
        flags=[r['value'].get('center_within_governed_portion') for r in records]
        return flags,'Per-frame governed_portion_occupancy.jsonl under the explicitly authored synthetic posted zone; not controller-window selection'
    return None,'Unsupported numeric rule'


def speed_review_focus(case, speed, trace):
    """Keep the posted-control approach alongside the later tracking interval."""
    focus=speed['sample_window_s']
    if case.get('target_law_id')=='NRS-484B-600-1c':
        active=set(speed.get('applicable_frames',[]))
        entry=next((r['time_s'] for r in trace if r['frame'] in active),None)
        # Missing applicability must not silently hide the control approach.
        start=entry if entry is not None else trace[0]['time_s']
        focus=[min(start,focus[0]),focus[1]] if focus else [trace[0]['time_s'],trace[-1]['time_s']]
    return focus


def report(case, attempt, *, production=False):
    adapter_path=attempt/'traffic_spec/adapter_report.json'
    if adapter_path.exists():
        adapter=json.loads(adapter_path.read_text())
        if 'legal_verdict' in adapter:
            archive_report(adapter_path);adapter.pop('legal_verdict');atomic(adapter_path,adapter)
    trace=rows(attempt/'trace.jsonl');result=json.loads((attempt/'result.json').read_text())
    config=json.loads((attempt/'config.json').read_text()) if (attempt/'config.json').exists() else {}
    from trace_scope_audit import verify
    try:trace_audit=verify(attempt,trace)
    except Exception as exc:
        trace_audit={'passed':False,'error':str(exc),'all_subject_motor_vehicle':False,'all_scenes_have_lane':False,'governed_speed_sign_present':False}
        archive_report(attempt/'trace_scope_audit.json');atomic(attempt/'trace_scope_audit.json',trace_audit)
    speed=None
    if not production and case.get('probe',{}).get('primary_variable')=='ego_speed':
        window=result.get('evaluation_window',{}).get('sample_window_s')
        if not window and config.get('evaluation_x_m'):
            subset=[r for r in trace if config['evaluation_x_m'][0]<=r['position']['x']<=config['evaluation_x_m'][1]]
            window=[subset[0]['time_s'],subset[-1]['time_s']] if subset else None
        if not window:window=result.get('measured_values',{}).get('evaluation_sample_window_s')
        manifest=json.loads((attempt/'capture/manifest.json').read_text())
        complete=bool(result['maneuver_completed'] and manifest.get('extraction_confirmed') and manifest['frames']==len(trace))
        applicability,evidence=speed_applicability(case,attempt,trace,config,result)
        if not trace_audit['all_subject_motor_vehicle'] or not trace_audit['all_scenes_have_lane']:
            applicability=None;evidence='Required subject/highway context not evidenced throughout trace'
        if case.get('target_law_id')=='NRS-484B-600-1c' and not trace_audit['governed_speed_sign_present']:
            applicability=None;evidence='No governed speed sign in delivered trace'
        if case.get('target_law_id')=='NRS-484B-600-1c':
            portions=[p for p in trace_audit.get('authored_speed_control_applicability',[]) if abs(p['speed_mps']-config['evaluation_limit_mps'])<1e-6]
            if portions and all(len(p['applicable_frames'])==len(trace) for p in portions):
                applicability=[any(p['applicable_frames'][i] for p in portions) for i in range(len(trace))]
                evidence='Full-body occupancy of explicitly authored longitudinal speed-control portions in the delivered Lean JSON; native observed sign/trigger-lane evidence and declaration retained in adapter report'
            else:
                applicability=None;evidence='Delivered Lean JSON does not represent the declared longitudinal sign-governed portion; native whole-lane trigger association alone is insufficient'
        speed=evaluate_speed(case,trace,window,config['evaluation_limit_mps'],complete,applicability,trace_audit.get('subject_speeds_mps'))
        speed['applicability_evidence']=evidence
        if case.get('target_law_id')=='NRS-484B-600-1c' and trace_audit['passed']:
            try:
                from control_evidence import posted_sign_evidence
                speed['physical_control_evidence']=posted_sign_evidence(attempt,trace,trace_audit,config['evaluation_limit_mps'])
            except Exception as exc:
                speed['physical_control_error']=str(exc)
                speed['expected_speed_rule_label']='unknown'
    target_checks=result.get('target_checks');target_projection_reference=None
    for filename,key in [('offline_recovery.json','projected_target_checks'),('signal_reporting_audit.json','target_checks')]:
        if (attempt/filename).exists():
            saved=json.loads((attempt/filename).read_text())
            if saved.get(key) is not None:target_checks=saved[key];target_projection_reference=str(attempt/filename)
    m=result.get('measured_values',{})
    onset=(m.get('departure_annotation') or {}).get('time_bracket_s')
    if not onset:
        a=m.get('course_change_annotation',{});onset=a.get('time_bracket_s') or a.get('heading_deflection_bracket_s') or a.get('onset_time_bracket_s')
    signal=None
    indicator_rows=[]
    if (attempt/'ego_turn_indicator.jsonl').exists():
        indicator_rows=rows(attempt/'ego_turn_indicator.jsonl')
        for r in indicator_rows:
            v=r['value'];state=v.get('reported_device_state',v.get('state')) if isinstance(v,dict) else v
            if state=='left':signal=r['time_s'];break
    api_lead=None
    if case['case_id'].startswith('C245490') and onset and len(indicator_rows)==len(trace):
        from lane_signal_measurement import measure
        observations=[]
        for point,indicator in zip(trace,indicator_rows):
            v=indicator['value']
            observations.append({'frame':point['frame'],'time_s':point['time_s'],'x':point['position']['x'],'y':-point['position']['y'],
                                 'reported_device_state':v.get('reported_device_state',v.get('state'))})
        api_lead=measure(observations,{'time_bracket_s':onset})
    finish=None
    if case['case_id'].startswith('C329610'):
        finish=next((r['time_s'] for r in trace if -r['position']['y']>=14 and 75<=-r['heading_deg']<=105),None)
        if not onset:
            onset=next(([trace[max(0,i-1)]['time_s'],r['time_s']] for i,r in enumerate(trace) if -r['heading_deg']>1 and r['speed_mps']>.5),None)
    elif case['case_id'].startswith('C245490'):
        finish=next((r['time_s'] for r in trace if r['position']['x']>=config['lane_change_interval_m'][1] and abs(-r['position']['y']-5.25)<.25),None)
    if speed:
        focus=speed_review_focus(case,speed,trace)
    elif onset:
        start=onset[0]
        if case.get('target_law_id') in ('NRS-484B-413-2','NRS-484B-223-1b') and signal is not None:start=min(start,signal)
        focus=[start,finish or onset[1]+10]
    elif case.get('target_law_id')=='NRS-484A-450-2' and (not production or (attempt/'stopping_and_entry_evidence.jsonl').exists()):
        stopping=rows(attempt/'stopping_and_entry_evidence.jsonl')
        held=next((r['time_s'] for r in stopping if r['value']['phase']=='hold'),None)
        crossing=next((r['time_s'] for r in stopping if r['value']['route_station_m']>1 and r['value']['physical_line_distance_m']==0),None)
        event=held if held is not None else crossing
        focus=[event-1,(crossing or event)+1] if event is not None else [trace[0]['time_s'],trace[-1]['time_s']]
    elif case.get('target_law_id')=='NRS-484B-307-6a' and (not production or (attempt/'footprint_boundary_relationships.jsonl').exists()):
        body=rows(attempt/'footprint_boundary_relationships.jsonl')
        entry=next((r['time_s'] for r in body if r['value']['relations']['first_overlap']),None)
        focus=[entry-4,entry+2] if entry is not None else [trace[0]['time_s'],trace[-1]['time_s']]
    elif config.get('applicability_negative_single_lane'):
        segment=[r for r in trace if 200<=r['position']['x']<=260]
        focus=[segment[0]['time_s'],segment[-1]['time_s']] if segment else [trace[0]['time_s'],trace[-1]['time_s']]
    else:focus=[trace[0]['time_s'],trace[-1]['time_s']]
    first=next((i for i,r in enumerate(trace) if r['time_s']>=max(trace[0]['time_s'],focus[0]-2)),0) if focus else 0
    last=max((i for i,r in enumerate(trace) if r['time_s']<=min(trace[-1]['time_s'],focus[1]+2)),default=len(trace)-1) if focus else len(trace)-1
    data={'case_id':case['case_id'],'law_id':case.get('target_law_id'),'full_recording_window_s':[trace[0]['time_s'],trace[-1]['time_s']],
          'full_trace_frames':len(trace),'target_attainment':{'window_purpose':'engineering_only','sample_window_s':result.get('evaluation_window',{}).get('sample_window_s') or result.get('measured_values',{}).get('evaluation_sample_window_s'),'recorded_target_checks':target_checks,'audited_projection_reference':target_projection_reference,'execution_status':result.get('status')},'speed_evaluation':speed,'maneuver_onset_bracket_s':onset,
          'signal_api_onset_s':signal,'maneuver_completion_s':finish,
          'api_signal_lead':api_lead,
          'preview_source_video_frames':[first,last],'preview_source_window_s':[trace[first]['time_s'],trace[last]['time_s']],
          'review_source_video_frames':[0,len(trace)-1],'review_source_window_s':[trace[0]['time_s'],trace[-1]['time_s']],
          'course_change_event_source':'Recorded trajectory with original sampling brackets'}
    data['report_revision']=6
    data['context_variant']=case.get('context_variant')
    if config.get('applicability_negative_single_lane'):
        segment=[r for r in trace if r['position']['x']>=config['lane_change_interval_m'][0]]
        data['engineering_comparison_reference']={'time_s':segment[0]['time_s'] if segment else None,'kind':'straight-travel passage of counterpart maneuver start station; no actual departure or legal onset'}
    data['trace_integrity_audit']=str(attempt/'trace_scope_audit.json')
    data['trace_integrity_confirmed']=trace_audit['passed']
    data['trace_integrity_error']=trace_audit.get('error')
    data['trace_coverage']={'kind':'full_recording','time_range_s':data['full_recording_window_s'],'frames':len(trace)}
    archive_report(attempt/'measured_review.json')
    atomic(attempt/'measured_review.json',data)
    return data


def render(case, attempt, data, *, preview=False):
    with (attempt/'review_render.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        return _render(case,attempt,data,preview=preview)


def _render(case, attempt, data, *, preview=False):
    result=json.loads((attempt/'result.json').read_text())
    refs=result['video_references']
    if not refs and (attempt/'offline_recovery.json').exists():
        refs=json.loads((attempt/'offline_recovery.json').read_text())['verified_video_references']
    primary=result.get('primary_video_reference')
    if primary is not None and primary not in refs:raise ValueError('Primary footage must be a verified original-frame video reference')
    source=attempt/primary if primary else next((attempt/r for r in refs if 'chase' in Path(r).stem),next((attempt/r for r in refs if Path(r).stem=='raw'),attempt/refs[0]))
    mapping=rows(attempt/'video_frames.jsonl')
    first,last=data['preview_source_video_frames'] if preview else data['review_source_video_frames']
    if not preview and [first,last]!=[0,len(mapping)-1]:
        raise ValueError('Primary review must cover every delivered trace frame; use an explicit preview for excerpts')
    window=data['preview_source_window_s'] if preview else data['review_source_window_s']
    prefix='preview' if preview else 'review'
    selected=mapping[first:last+1]
    if len(mapping)!=data['full_trace_frames']:raise ValueError('Review source video/frame map mismatch')
    label=attempt/(prefix+'_label.txt')
    text=case['case_id']+' | '+str(case.get('target_law_id'))+'\n'
    text+=('Preview excerpt: ' if preview else 'Full delivered trace: ')+'%.3f-%.3f s'%(selected[0]['time_s'],selected[-1]['time_s'])
    text+='\nFull trace %.3f-%.3f s | %d frames'%(*data['full_recording_window_s'],len(mapping))
    speed=data['speed_evaluation']
    if speed:
        w=speed['sample_window_s']
        text+='\nTarget-attainment window: '+('%.3f-%.3f s'%tuple(w) if w else 'unavailable')
        text+='\nFull-trace numeric label: %s | %d applicable exceedances'%(speed['expected_speed_rule_label'],len(speed['exceedance_frames']))
        outside=sum(not selected[0]['time_s']<=t<=selected[-1]['time_s'] for t in speed['exceedance_times_s'])
        text+=' | %d outside excerpt'%outside
        text+='\nRequested %.3f mph | limit %.3f mph | measured min/max %s'%(speed['requested']['mph'],speed['limit']['mph'],
               '%.3f/%.3f mph'%(speed['minimum']['mph'],speed['maximum']['mph']) if speed['minimum'] else 'unavailable')
    elif data.get('context_variant',{}):text+='\nExplicit one-lane straight-travel applicability variant; no lane change'
    else:text+='\nRecorded maneuver; see expected label and declared scene context'
    label.write_text(text+'\n')
    font=next(p for p in [Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('/usr/share/fonts/truetype/LiberationSans-Regular.ttf')] if p.exists())
    filt='trim=start_frame=%d:end_frame=%d,setpts=PTS-STARTPTS,pad=iw:ih+145:0:145:black,drawtext=fontfile=%s:textfile=%s:x=8:y=5:fontsize=12:fontcolor=white'%(first,last+1,font,label)
    engineering_window=speed.get('sample_window_s')if speed else data.get('target_attainment',{}).get('sample_window_s')
    if engineering_window:
        a,b=engineering_window
        if not (math.isfinite(a)and math.isfinite(b)and data['full_recording_window_s'][0]<=a<=b<=data['full_recording_window_s'][1]):raise ValueError('Declared target-attainment window lies outside recorded evidence')
        evaluated=[i for i,r in enumerate(selected) if a<=r['time_s']<=b]
        if not evaluated:raise ValueError('Review omitted the declared target-attainment window')
        filt+=",drawtext=fontfile=%s:text='Target-attainment window active':x=8:y=122:fontsize=14:fontcolor=yellow:enable='between(n,%d,%d)'"%(font,evaluated[0],evaluated[-1])
        filt+=",drawtext=fontfile=%s:text='Outside target-attainment window':x=8:y=122:fontsize=14:fontcolor=white:enable='not(between(n,%d,%d))'"%(font,evaluated[0],evaluated[-1])
    filt+=",drawtext=fontfile=%s:text='Source time %%{pts\\:flt\\:%.9f}s':x=w-290:y=h-25:fontsize=14:fontcolor=white"%(font,selected[0]['time_s'])
    from speed_overlay import write_overlay,ass_filter
    dimensions=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate','-of','json',str(source)],text=True))['streams'][0]
    num,den=map(int,dimensions['r_frame_rate'].split('/'))
    overlay=attempt/(prefix+'_measured_speed.ass')
    overlay_sha=write_overlay(overlay,rows(attempt/'trace.jsonl'),mapping,first,last+1,
                             dimensions['width'],dimensions['height']+145,103,fps=num/den)
    filt+=','+ass_filter(overlay)
    from scenario_overlay import write_overlay as write_scenario_overlay
    scenario_ass=attempt/(prefix+'_scenario.ass')
    scenario_sha=write_scenario_overlay(scenario_ass,attempt,selected,dimensions['width'],dimensions['height']+145,top=145,fps=num/den)
    if scenario_sha:filt+=','+ass_filter(scenario_ass)
    basename='preview' if preview else 'event_review'
    video=attempt/(basename+'.webm')
    recipe=hashlib.sha256(json.dumps({'filter':filt,'frames':len(selected),'source_sha256':digest(source),
                                    'label':text,'frame_mapping':selected,'speed_overlay_sha256':overlay_sha,'scenario_overlay_sha256':scenario_sha,'trace_sha256':digest(attempt/'traffic_spec/trace.json')},sort_keys=True).encode()).hexdigest()
    receipt_path=attempt/(basename+'.json')
    map_path=attempt/(basename+'_frames.jsonl')
    if receipt_path.exists() and video.exists() and map_path.exists():
        prior=json.loads(receipt_path.read_text())
        if (prior.get('recipe_sha256')==recipe and prior.get('video_sha256')==digest(video)
                and prior.get('frame_map_sha256')==digest(map_path)):
            return prior
    with (attempt/(basename+'_encoder.log')).open('w') as log:
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(source),'-vf',filt,'-frames:v',str(len(selected)),
                        '-an','-c:v','libvpx-vp9','-crf','24','-b:v','0','-cpu-used','5','-threads','4','-pix_fmt','yuv420p',str(video)],stderr=log,check=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=nb_read_frames,width,height:format=duration','-of','json',str(video)],text=True))
    if int(probe['streams'][0]['nb_read_frames'])!=len(selected):raise ValueError('Review lost source frames')
    with map_path.open('w') as out:
        for i,r in enumerate(selected):out.write(json.dumps(dict(r,source_video_frame=r['video_frame'],video_frame=i))+'\n')
    receipt={'video':str(video),'source_video':str(source),'source_video_sha256':digest(source),'frames':len(selected),'ffprobe':probe,
             'source_frame_interval':[first,last],'source_simulation_window_s':window,
             'frame_map':str(map_path),'source_time_overlay':True,'target_attainment_window_overlay':bool(engineering_window),'trace_coverage':data['trace_coverage'],'excerpt_window_s':window,'coverage_kind':'preview' if preview else 'full_delivered_trace',
             'trace_sha256':digest(attempt/'traffic_spec/trace.json'),
             'measured_speed_overlay':True,'speed_source':'trace.jsonl speed_mps joined by original frame and time',
             'speed_overlay_sha256':overlay_sha,'scenario_overlay_sha256':scenario_sha,
             'recipe_sha256':recipe,'video_sha256':digest(video),'frame_map_sha256':digest(map_path)}
    archive_report(receipt_path)
    atomic(receipt_path,receipt)
    return receipt


def main():
    from concurrent.futures import ThreadPoolExecutor,as_completed
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=4);p.add_argument('--previews',action='store_true',help='Also render optional focused previews separately from the full review');args=p.parse_args()
    index=json.loads((args.output/'delivery_index.json').read_text());errors=[];tasks=[]
    from delivery_definitions import resolve
    from workspaces import campaign_path, semantic_directory
    def sibling(run):
        return campaign_path(run,args.output.parents[2]) if args.output.parent.name=='_campaigns' else args.output.parent/run
    for entry in index['cells']:
        root=sibling(entry.get('run_id',index['run_id']))
        cases={c['case_id']:c for c in json.loads((semantic_directory(root,entry['cell_id'],entry.get('actor','motor_vehicle_driver'))/'cases.json').read_text())['cases']}
        for case in entry['cases']:
            if not case.get('execution') or not case.get('decoder_passed'):continue
            definition=resolve(case,cases[case['case_id']])
            if case.get('definition_run_id') and not case.get('definition_file'):
                revised=semantic_directory(sibling(case['definition_run_id']),entry['cell_id'],entry.get('actor','motor_vehicle_driver'))/'cases.json'
                definition=next(c for c in json.loads(revised.read_text())['cases'] if c['case_id']==case['case_id'])
            tasks.append((case,definition,Path(case['execution'])))
    def work(definition,attempt):
        data=report(definition,attempt)
        receipt=render(definition,attempt,data)
        preview_receipt=render(definition,attempt,data,preview=True) if args.previews else None
        return receipt,preview_receipt
    with ThreadPoolExecutor(max_workers=max(1,args.workers)) as pool:
        pending={pool.submit(work,definition,attempt):(case,attempt) for case,definition,attempt in tasks}
        for future in as_completed(pending):
            case,attempt=pending[future]
            try:
                receipt,preview_receipt=future.result()
                if preview_receipt:case['preview']=preview_receipt
                case['measured_review']=str(attempt/'measured_review.json');case['event_review']=receipt
                print(json.dumps({'case':case['case_id'],'review_frames':receipt['frames']}),flush=True)
            except Exception as exc:errors.append({'case':case['case_id'],'error':str(exc)})
    atomic(args.output/'delivery_index.json',index);atomic(args.output/'event_review_audit.json',{'status':'failed' if errors else 'passed','errors':errors})
    if errors:raise ValueError(errors)

if __name__=='__main__':main()
