"""Measure retained synthetic arrow and intersection request rows; no legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

CASE = 'training__C111603__NRS-484B-307-7a__motor_vehicle_driver__controlled_2'
SOURCES = ('turn-history.jsonl', 'arrow-context.json', 'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def measure_turn(attempt):
    attempt=Path(attempt)
    for name in SOURCES:
        if not (attempt/name).is_file():
            raise ValueError('Missing required source: '+name)
    context=json.loads((attempt/'arrow-context.json').read_text())
    if context.get('source_kind')!='synthetic_cpu_diagnostic' or context.get('official_arrow_verified') is not False:
        raise ValueError('Arrow source context differs')
    rows=[json.loads(x) for x in (attempt/'turn-history.jsonl').read_text().splitlines()]
    mapping=[json.loads(x) for x in (attempt/'video_frames.jsonl').read_text().splitlines()]
    trace=[json.loads(x) for x in (attempt/'trace.jsonl').read_text().splitlines()]
    if len(rows)!=600 or len(mapping)!=600 or len(trace)!=600:
        raise ValueError('Expected 600 saved frames and joins')
    first_entry=None; last_other=None; lit_frames=0
    for i,(row,video,pose) in enumerate(zip(rows,mapping,trace)):
        if row['frame']!=i or video['native_frame']!=i or pose['frame']!=i or abs(row['time_s']-i/20)>1e-6 or abs(video['time_s']-i/20)>1e-6:
            raise ValueError('Original frame/time join differs')
        if row['requested_arrow']['direction']!='right' or row['requested_arrow']['governs_ego']!='requested_unverified' or row['original_native_observed'] is not False:
            raise ValueError('Authored arrow/observation source differs')
        if row['requested_arrow']['flashing_yellow_lit']:
            lit_frames+=1
        if row['requested_other_inside_intersection']:
            last_other=i
        if first_entry is None and row['requested_ego_inside_intersection'] and row['requested_phase']=='requested_right_turn':
            first_entry=i
    if first_entry is None or last_other is None:
        raise ValueError('Expected turn and other-traffic source events')
    return {'frames':600,'first_requested_ego_entry_frame':first_entry,
            'last_requested_other_inside_frame':last_other,
            'other_requested_inside_at_entry':rows[first_entry]['requested_other_inside_intersection'],
            'requested_lit_arrow_frames':lit_frames,
            'official_arrow_verified':False,'governs_ego_verified':False,
            'other_traffic_lawful_status_verified':False,'pedestrian_status_verified':False,
            'cautiousness_legal_judgment':None,'legal_verdict_claimed':False}

def finalize(attempt,output):
    attempt,output=Path(attempt),Path(output)
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior analysis; use a fresh attempt')
    for name in (*SOURCES,*VIDEOS,'config.json','construction.json'):
        if not (attempt/name).is_file():
            raise ValueError('Missing required source: '+name)
    config=json.loads((attempt/'config.json').read_text())
    construction=json.loads((attempt/'construction.json').read_text())
    if config['case_id']!=CASE or construction['case_id']!=CASE:
        raise ValueError('Exact diagnostic case differs')
    metric=measure_turn(attempt)
    rows=[json.loads(x) for x in (attempt/'turn-history.jsonl').read_text().splitlines()]
    channels=attempt/'channels';channels.mkdir()
    evidence=[]
    for channel in construction['recording_description']['channels']:
        name=channel['name'];path=channels/(name+'.jsonl')
        with path.open('x') as stream:
            for row in rows:
                value=row['requested_ego_xy_m'] if name=='ego_request' else row['requested_arrow']['flashing_yellow_lit'] if name=='arrow_request' else row['requested_other_xy_m']
                stream.write(json.dumps({'time_s':row['time_s'],'value':value})+'\n')
        evidence.append({'name':name,'unit':channel['unit'],'reference':'channels/'+path.name})
    report={'format':'worker-analysis-report','case_id':CASE,
            'measurements':{'flashing_arrow_yield_measurement':{'method':'measure_turn','value':metric,
              'sources':{name:sha(attempt/name) for name in SOURCES}}},
            'source_complete':True,'diagnostic_fixture':True,'physical_or_legal_acceptance':False}
    result={'case_id':CASE,'measured_values':metric,
            'target_checks':[{'target':'ego entry relative to requested other passage',
              'requested':True,'measured':metric['other_requested_inside_at_entry'],
              'method':'measure_turn','tolerance':0,
              'matched':metric['other_requested_inside_at_entry'],
              'physical_cause_confirmed':False,'cause_evidence':list(SOURCES)}],
            'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
            'termination_reason':'600-frame synthetic CPU diagnostic',
            'physical_failure_flags':['Official flashing-arrow governance, lawful other traffic, pedestrians and cautiousness unverified'],
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
