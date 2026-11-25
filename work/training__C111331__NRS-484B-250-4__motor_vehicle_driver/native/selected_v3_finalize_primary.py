"""Measure an authored signal-outage request from retained synthetic frame rows."""
import argparse
import hashlib
import json
from pathlib import Path

CASE = 'training__C111331__NRS-484B-250-4__motor_vehicle_driver__controlled_1'
SOURCES = ('vehicle-history.jsonl', 'signal-context.json', 'video_frames.jsonl',
           'trace.jsonl', 'capture/evidence.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_stop(attempt):
    attempt = Path(attempt)
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    context = json.loads((attempt / 'signal-context.json').read_text())
    if (context.get('source_kind') != 'synthetic_cpu_diagnostic' or
            context.get('official_signal_state_verified') is not False or
            context.get('marked_stop_line_x_m') != -26):
        raise ValueError('Signal/source context differs')
    rows = [json.loads(x) for x in (attempt / 'vehicle-history.jsonl').read_text().splitlines()]
    mapping = [json.loads(x) for x in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    trace = [json.loads(x) for x in (attempt / 'trace.jsonl').read_text().splitlines()]
    if len(rows) != 600 or len(mapping) != 600 or len(trace) != 600:
        raise ValueError('Expected 600 saved frames and joins')
    stop_frames = []; first_line_cross = None
    for i, (row, video, pose) in enumerate(zip(rows, mapping, trace)):
        if (row['frame'] != i or video['native_frame'] != i or pose['frame'] != i or
                abs(row['time_s'] - i/20) > 1e-6 or abs(video['time_s'] - i/20) > 1e-6):
            raise ValueError('Original frame/time join differs')
        if (row['signal_display_requested'] != 'inoperative_dark' or
                row['signal_installed_requested'] is not True or
                row['signal_uncovered_requested'] is not True or
                row['marked_stop_line_x_m'] != -26):
            raise ValueError('Authored signal/stop-point source differs')
        if i and row['ego_center_xy_m'] == rows[i-1]['ego_center_xy_m'] and row['ego_front_x_m'] < -26:
            stop_frames.append(i)
        if first_line_cross is None and row['ego_front_x_m'] >= -26:
            first_line_cross = i
    if first_line_cross is None:
        raise ValueError('Body never crosses authored stop line')
    return {'frames':600,'pre_line_stationary_frames':len(stop_frames),
            'first_stop_line_cross_frame':first_line_cross,
            'requested_dark_signal_frames':600,
            'official_signal_state_verified':False,
            'complete_stop_physically_verified':False,
            'yielding_and_cautious_entry_verified':False,
            'legal_verdict_claimed':False}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if (attempt/'native-raw-actors.jsonl').is_file():
        from original_finalize import finalize_original
        return finalize_original(attempt,output,CASE)
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior analysis; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json','construction.json'):
        if not (attempt/name).is_file():
            raise ValueError('Missing required source: '+name)
    config=json.loads((attempt/'config.json').read_text())
    construction=json.loads((attempt/'construction.json').read_text())
    if config['case_id']!=CASE or construction['case_id']!=CASE:
        raise ValueError('Exact diagnostic case differs')
    metric=measure_stop(attempt)
    rows=[json.loads(x) for x in (attempt/'vehicle-history.jsonl').read_text().splitlines()]
    channels=attempt/'channels';channels.mkdir()
    evidence=[]
    for channel in construction['recording_description']['channels']:
        name=channel['name'];path=channels/(name+'.jsonl')
        with path.open('x') as stream:
            for row in rows:
                value=row['ego_front_x_m'] if name=='ego_front' else row['signal_display_requested']
                stream.write(json.dumps({'time_s':row['time_s'],'value':value})+'\n')
        evidence.append({'name':name,'unit':channel['unit'],'reference':'channels/'+path.name})
    report={'format':'worker-analysis-report','case_id':CASE,
            'measurements':{'inoperative_signal_stop_measurement':{
                'method':'measure_stop','value':metric,
                'sources':{name:sha(attempt/name) for name in SOURCES}}},
            'source_complete':True,'diagnostic_fixture':True,
            'physical_or_legal_acceptance':False}
    result={'case_id':CASE,'measured_values':metric,
            'target_checks':[{'target':'stationary before authored marked stop line',
              'requested':True,'measured':metric['pre_line_stationary_frames']>0,
              'method':'measure_stop','tolerance':0,
              'matched':metric['pre_line_stationary_frames']>0,
              'physical_cause_confirmed':False,'cause_evidence':list(SOURCES)}],
            'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
            'termination_reason':'600-frame synthetic CPU diagnostic',
            'physical_failure_flags':['Original signal state, stop, yielding and cautious entry unverified'],
            'trace_reference':'trace.jsonl','video_references':list(VIDEOS),
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':construction['recording_description'],
            'recording_evidence':evidence,'realized_observables':{},
            'provenance_kind':'synthetic_local_diagnostic','accepted':False}
    from worker_exchange.native_output import write_result
    write_result(attempt,result)
    output.write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();finalize(args.attempt,args.output)
