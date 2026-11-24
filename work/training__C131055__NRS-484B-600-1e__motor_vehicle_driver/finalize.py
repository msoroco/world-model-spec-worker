"""Measure retained original-frame synthetic speed samples; no physical verdict."""
import argparse
import hashlib
import json
from pathlib import Path
from measure import measure
SOURCES=('roundabout-speed-history.jsonl','roundabout-survey.json','video_frames.jsonl','trace.jsonl','capture/evidence.jsonl')
VIDEOS=('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def measure_speed(attempt):
    attempt=Path(attempt)
    for name in SOURCES:
        if not (attempt/name).is_file():raise ValueError('Missing required source: '+name)
    metric=measure(attempt/'roundabout-speed-history.jsonl',attempt/'roundabout-survey.json')
    frames=[json.loads(x) for x in (attempt/'video_frames.jsonl').read_text().splitlines()]
    trace=[json.loads(x) for x in (attempt/'trace.jsonl').read_text().splitlines()]
    if len(frames)!=600 or len(trace)!=600:raise ValueError('Expected 600 frame joins')
    for i,(f,t) in enumerate(zip(frames,trace)):
        if f['native_frame']!=i or t['frame']!=i or abs(f['time_s']-i/20)>1e-6 or abs(t['time_s']-i/20)>1e-6:
            raise ValueError('Original frame/time join differs')
    metric['physical_speed_verified']=False
    metric['legal_verdict_claimed']=False
    return metric

def finalize(attempt,output):
    attempt,output=Path(attempt),Path(output)
    if output.exists() or (attempt/'result.json').exists():raise ValueError('Retain prior analysis; use fresh attempt')
    for name in (*SOURCES,*VIDEOS,'config.json','construction.json'):
        if not (attempt/name).is_file():raise ValueError('Missing required source: '+name)
    config=json.loads((attempt/'config.json').read_text())
    construction=json.loads((attempt/'construction.json').read_text())
    if config['case_id']!=construction['case_id'] or config['case_id'] not in (
        'training__C131055__NRS-484B-600-1e__motor_vehicle_driver__controlled_1',
        'training__C131055__NRS-484B-600-1e__motor_vehicle_driver__controlled_2',
        'training__C131055__NRS-484B-600-1e__motor_vehicle_driver__controlled_3'):
        raise ValueError('Exact diagnostic case differs')
    metric=measure_speed(attempt)
    rows=[json.loads(x) for x in (attempt/'roundabout-speed-history.jsonl').read_text().splitlines()]
    channels=attempt/'channels';channels.mkdir()
    evidence=[]
    for channel in construction['recording_description']['channels']:
        name=channel['name'];path=channels/(name+'.jsonl')
        with path.open('x') as stream:
            for row in rows:
                stream.write(json.dumps({'time_s':row['time_s'],'value':row['velocity_xyz_mps']})+'\n')
        evidence.append({'name':name,'unit':channel['unit'],'reference':'channels/'+path.name})
    report={'format':'worker-analysis-report','case_id':config['case_id'],
        'measurements':{'roundabout_speed_measurement':{'method':'measure_speed','value':metric,
          'sources':{name:sha(attempt/name) for name in SOURCES}}},
        'source_complete':True,'diagnostic_fixture':True,'physical_or_legal_acceptance':False}
    high=config['case_id'].endswith('__controlled_2')
    at=config['case_id'].endswith('__controlled_3')
    matched=(metric['samples_at_80_mph']>0 and metric['samples_above_80_mph']==0) if at else ((metric['samples_above_80_mph']>0)==high)
    result={'case_id':config['case_id'],'measured_values':metric,
        'target_checks':[{'target':'synthetic saved speed exactly 80 mph' if at else ('synthetic saved speed crosses 80 mph' if high else 'synthetic saved speed remains at or below 80 mph'),
          'requested':True,'measured':matched,'method':'measure_speed',
          'tolerance':0,'matched':matched,
          'physical_cause_confirmed':False,'cause_evidence':list(SOURCES)}],
        'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
        'termination_reason':'600-frame synthetic CPU diagnostic',
        'physical_failure_flags':['Original Native speed, lane retention and pixels unverified'],
        'trace_reference':'trace.jsonl','video_references':list(VIDEOS),
        'video_frame_map_reference':'video_frames.jsonl','recording_description':construction['recording_description'],
        'recording_evidence':evidence,'realized_observables':{},
        'provenance_kind':'synthetic_local_diagnostic','accepted':False}
    from worker_exchange.native_output import write_result
    write_result(attempt,result)
    output.write_text(json.dumps(report,indent=2)+'\n')
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();finalize(a.attempt,a.output)
