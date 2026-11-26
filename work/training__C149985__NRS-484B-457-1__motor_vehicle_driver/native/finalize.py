"""Finalize sealed parking sources, retaining unassessed authority and verdict."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from measure_saved import measure_attempt

CAMERAS=('overview','approach','reference_corner','driver_reference')
SOURCES=('parking-context.json','native-parking.jsonl','video_frames.jsonl')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_reference(attempt):
    return measure_attempt(attempt)


def finalize(attempt,output):
    attempt,output=Path(attempt).resolve(),Path(output).resolve()
    for parent in (attempt,*attempt.parents):
        if (parent/'runtime'/'scenario_pipeline').is_dir():
            sys.path.insert(0,str(parent/'runtime'));break
    from scenario_pipeline.worker_exchange.native_output import write_result
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Use a fresh saved analysis version')
    for name in ('config.json','construction.json','trace.jsonl','capture/evidence.jsonl',
                 *SOURCES,*(name+'.mkv' for name in CAMERAS)):
        if not (attempt/name).is_file():raise ValueError('Missing required source: '+name)
    config=json.loads((attempt/'config.json').read_text())
    construction=json.loads((attempt/'construction.json').read_text())
    case=config.get('selected_case_id',config.get('case_id'))
    if case!=construction.get('case_id'):raise ValueError('Exact saved case identity differs')
    metric=measure_reference(attempt)
    target=config['case_target']
    if target['parking_kind'].startswith('angle'):
        target_matched=abs(metric['maximum_heading_difference_deg']-target['requested_heading_deg'])<=5
        target_tolerance={'heading_deg':5}
    else:
        target_matched=abs(metric['front_wheel_gap_in_max']-target['requested_gap_in'])<=.5 and abs(metric['rear_wheel_gap_in_max']-target['requested_gap_in'])<=.5
        target_tolerance={'wheel_gap_in':.5}
    rows=[json.loads(line) for line in (attempt/'native-parking.jsonl').read_text().splitlines()]
    context=json.loads((attempt/'parking-context.json').read_text())
    values={
        'ego_pose':lambda row:row['ego'],
        'wheel_curb_geometry':lambda row:{'ego':row['ego'],'curbs':context.get('curb_objects'),
                                        'kind':context['parking_kind']},
        'parking_state':lambda row:{'speed_mps':row['ego']['speed_mps'],
                                    'rest_mode_request':row['rest_mode_request']},
        'administrative_context':lambda row:{'requested':context.get('authority_source_required'),
                                              'local_left_ordinance_status':context.get('local_left_ordinance_status'),
                                              'local_angle_ordinance_status':context.get('local_angle_ordinance_status'),
                                              'dot_width_determination_status':context.get('dot_width_determination_status')},
        'right_wheel_curb_clearance':lambda row:{'metric':metric,'source_frame':row['video_frame']},
    }
    channels=attempt/'channels';channels.mkdir()
    evidence=[]
    for name,get_value in values.items():
        path=channels/(name+'.jsonl')
        with path.open('x') as stream:
            for row in rows:
                stream.write(json.dumps({'time_s':row['time_s'],'value':get_value(row)},allow_nan=False)+'\n')
        evidence.append({'name':name,'unit':'structured','reference':'channels/'+path.name})
    result={'case_id':case,'measured_values':metric,
        'target_checks':[{'target':'source-bound wheel-to-curb and rest measurement',
            'requested':target,'measured':metric,
            'method':'measure_reference','tolerance':target_tolerance,'matched':target_matched,
            'physical_cause_confirmed':False,
            'cause_evidence':list(SOURCES)}],
        'setup_confirmed':False,'behavior_attempted':not metric['diagnostic_fixture'],
        'maneuver_completed':not metric['diagnostic_fixture'],
        'termination_reason':'600-frame saved parking source; original physical and authority review pending',
        'physical_failure_flags':['Original curb and wheel geometry, camera pixels, physical parking and administrative authority review pending'],
        'trace_reference':'trace.jsonl','video_references':[name+'.mkv' for name in CAMERAS],
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':construction['recording_description'],
        'recording_evidence':evidence,'realized_observables':{},
        'provenance_kind':'synthetic_local_diagnostic' if metric['diagnostic_fixture'] else 'native',
        'accepted':False}
    write_result(attempt,result)
    measurements={key:{'method':'measure_reference','value':metric,
        'sources':{name:sha(attempt/name) for name in SOURCES}}
        for key in ('default_position_measurement','left_ordinance_measurement',
                    'angle_ordinance_measurement','reviewed_scope_measurement')}
    report={'format':'worker-analysis-report','case_id':case,
        'measurements':measurements,
        'source_complete':True,'diagnostic_fixture':metric['diagnostic_fixture'],
        'physical_or_legal_acceptance':False}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    finalize(args.attempt,args.output)
