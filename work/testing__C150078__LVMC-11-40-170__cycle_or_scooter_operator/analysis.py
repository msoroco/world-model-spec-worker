"""Saved-only original-source parking and pedestrian descriptive finalizer."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from parking_measurement import measure as measure_parking,rows

CHANNELS=('responsible_person_and_device','city_street_one_way_status','parking_placement_and_footprint',
          'rack_sidewalk_curb_building_geometry','pedestrian_passing_history','camera_frame_identity')


def measure(attempt):
    return measure_parking(attempt)

def saved_result(attempt,value):
    from worker_exchange.native_output import physical_result,validate_result
    attempt=Path(attempt)
    cfg=json.loads((attempt/'config.json').read_text())
    construction=json.loads((attempt/'construction.json').read_text())
    description=construction['recording_description']
    events=rows(attempt/'parking-events.jsonl')
    tracks=rows(attempt/'pedestrian-tracks.jsonl')
    frames=rows(attempt/'video_frames.jsonl')
    site=json.loads((attempt/'reviewed-site/site.json').read_text())
    channels=attempt/'channels';channels.mkdir(exist_ok=False)
    samples={
       'responsible_person_and_device':[{'person_id':e['person_id'],'device_id':e['device_id'],'device_class':value['device_class']} for e in events],
       'city_street_one_way_status':[{'source':site['sources']['street']['sha256']}] * len(events),
       'parking_placement_and_footprint':[{'parked':e['parked'],'device_xy':e['device_xy'],'observed_relation':e['placement_relation'],'rack_support_contact':e['rack_support_contact']} for e in events],
       'rack_sidewalk_curb_building_geometry':[{'rack':site['sources']['rack']['sha256'],'sidewalk':site['sources']['sidewalk']['sha256'],'curb':site['sources']['curb']['sha256'],'building':site['sources']['building']['sha256']}] * len(events),
       'pedestrian_passing_history':tracks,
       'camera_frame_identity':frames,
    }
    evidence=[]
    for item in description['channels']:
        name=item['name']
        if name not in CHANNELS:raise ValueError('unsupported parking observation channel: '+name)
        p=channels/(name+'.jsonl')
        with p.open('x') as f:
            for e,s in zip(events,samples[name]):f.write(json.dumps({'time_s':e['time_s'],'value':s},allow_nan=False)+'\n')
        evidence.append({'name':name,'unit':item['unit'],'reference':str(p.relative_to(attempt))})
    context=channels/'context.json';context.write_text(json.dumps({'original_parking_site_and_classification':site,'original_pedestrian_alternatives':value},allow_nan=False)+'\n')
    for item in description['context_inputs']:
        evidence.append({'name':item['name'],'unit':item['unit'],'reference':str(context.relative_to(attempt))})
    result={'case_id':cfg['selected_case_id'],'measured_values':value,
            'target_checks':[{'target':'source-gated covered-device parking and pedestrian passage',
                'requested':True,'measured':value['parked_frame_count']>0,
                'method':'source-sealed original actor, placement, pedestrian and camera frame join',
                'tolerance':0,'matched':value['parked_frame_count']>0,
                'physical_cause_confirmed':False,'cause_evidence':value['sources']}],
            'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
            'termination_reason':'Original physical and legal review pending','physical_failure_flags':[],
            'trace_reference':'trace.jsonl',
            'video_references':[name+'.mkv' for name in ('overview','approach','reference_corner','driver_reference')],
            'video_frame_map_reference':'video_frames.jsonl','recording_description':description,
            'recording_evidence':evidence,'realized_observables':{}}
    result=physical_result(attempt,result);validate_result(result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    value=measure(args.attempt)
    result=saved_result(args.attempt,value)
    attempt=Path(args.attempt)
    (attempt/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    report={'format':'worker-analysis-report','measurements':{'source_gated_parking_and_pedestrian_context':{
            'value':value,'method':'measure','sources':value['sources']}},
            'physical_checks':result['physical_checks'],'realized_observables':result['realized_observables'],
            'limitations':['Original site, person and device classification, placement, passage alternatives, actual pixels, physical motion and legal least obstruction remain independently reviewable.'],
            'analysis_complete':True,'legal_verdict_claimed':False}
    Path(args.output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
