"""Case-specific saved crosswalk finalization; no legal conclusion."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crosswalk import footprint_relation, measure, require


def measure_crosswalk_contact(context, rows):
    polygon = context['crosswalk_polygon']
    active = [r for r in rows if r['halt_activity'] == context['action'] and r['speed_mps'] < 0.1]
    return {'halt_frame_count': len(active),
            'overlap_frame_count': sum(footprint_relation(r['body_corners_xy'], polygon)['overlap'] for r in active),
            'crosswalk_id': context['crosswalk_id'], 'marking_status': context['marking_status'],
            'geometry_source': context['geometry_source'], 'legal_judgment': None}


def measure_stop_activity(context, rows):
    return {'stop_frames': sum(r['halt_activity'] == 'stop' and r['speed_mps'] < .1 for r in rows),
            'activity_source': context['activity_source'], 'legal_class': None}


def measure_stand_activity(context, rows):
    return {'stand_frames': sum(r['halt_activity'] == 'stand' and r['speed_mps'] < .1 for r in rows),
            'activity_source': context['activity_source'], 'legal_class': None}


def measure_park_activity(context, rows):
    return {'park_frames': sum(r['halt_activity'] == 'park' and r['speed_mps'] < .1 for r in rows),
            'activity_source': context['activity_source'], 'legal_class': None}


def _exception(context, rows, key):
    packet = context.get('exception_packet')
    require(isinstance(packet, dict) and packet.get('source_id') == context['exception_source_id'],
            'exception packet identity differs')
    return {'source_frames': sum(bool(r[key]) for r in rows),
            'source_id': packet['source_id'], 'necessity_or_compliance': None}


def measure_traffic_conflict(context, rows): return _exception(context, rows, 'traffic_conflict')
def measure_law_direction(context, rows): return _exception(context, rows, 'law_direction')
def measure_police_direction(context, rows): return _exception(context, rows, 'police_direction')
def measure_device_direction(context, rows): return _exception(context, rows, 'device_direction')


METHODS = {name: globals()[name] for name in (
    'measure_crosswalk_contact', 'measure_stop_activity', 'measure_stand_activity',
    'measure_park_activity', 'measure_traffic_conflict', 'measure_law_direction',
    'measure_police_direction', 'measure_device_direction')}


def analyze(attempt: Path, output: Path) -> dict:
    attempt = Path(attempt)
    config = json.loads((attempt/'config.json').read_text())
    case = config['case']
    contract = json.loads((attempt/'measurement-contract.json').read_text())
    require(contract['case_id'] == case['case_id'], 'exact measurement contract differs')
    if (attempt/'native-receipt.json').is_file():
        from saved_crosswalk import prepare_analysis_sources
        require(not (attempt/'crosswalk-context.json').exists() and
                not (attempt/'crosswalk-rows.jsonl').exists(),
                'original Native source cannot be mixed with prior derived analysis inputs')
        prepare_analysis_sources(attempt, case)
    for requirement in contract['requirements']:
        for source in requirement['inputs']:
            if not (attempt/source).is_file():
                raise ValueError('Missing required source: '+source)
    context = json.loads((attempt/'crosswalk-context.json').read_text())
    rows = [json.loads(s) for s in (attempt/'crosswalk-rows.jsonl').read_text().splitlines() if s]
    require(context['case_id'] == case['case_id'] and context['action'] == case['action'],
            'crosswalk context case or action differs')
    require(context['destination'] == case['destination'] and context['exception'] == case['exception'],
            'crosswalk context variable differs')
    if case['exception'] != 'none':
        packet = json.loads((attempt/'exception-source.json').read_text())
        require(packet.get('kind') == case['exception'] and packet.get('source_id') and
                packet.get('source_id') == context['exception_source_id'],
                'exception source kind or identity differs')
        context['exception_packet'] = packet
    expected = {'case_id': case['case_id'], 'subject_id': context['subject_id'],
                'first_frame': rows[0]['frame'], 'frame_count': len(rows),
                'crosswalk_id': context['crosswalk_id'], 'marking_status': context['marking_status'],
                'crosswalk_polygon': context['crosswalk_polygon'], 'action': case['action'],
                'exception': case['exception']}
    summary = measure(rows, expected)
    measurements = {}
    for requirement in contract['requirements']:
        method = requirement['method']
        measurements[requirement['output_key']] = {
            'method': method, 'value': METHODS[method](context, rows),
            'sources': {source: hashlib.sha256((attempt/source).read_bytes()).hexdigest()
                        for source in requirement['inputs']}}
    report = {'case_id': case['case_id'], 'measurements': measurements,
              'crosswalk_summary': summary, 'physical_completion_verified': False,
              'legal_conclusion': None}
    description = json.loads((attempt/'construction.json').read_text())['recording_description']
    channel_dir = attempt/'channels'
    channel_dir.mkdir(exist_ok=True)
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        path = channel_dir/(name+'.jsonl')
        if path.exists(): raise ValueError('retain prior channel source: '+name)
        with path.open('x') as stream:
            for row in rows:
                stream.write(json.dumps({'time_s':row['time_s'],'value':row})+'\n')
        evidence.append({'name':name,'unit':channel['unit'],
                         'reference':str(path.relative_to(attempt))})
    context_path = channel_dir/'context.json'
    context_path.write_text(json.dumps({'crosswalk_site':context})+'\n')
    for context_input in description.get('context_inputs', []):
        evidence.append({'name':context_input['name'],'unit':context_input['unit'],
                         'reference':str(context_path.relative_to(attempt))})
    target = {'target':'source-bound crosswalk halt observations','requested':True,
              'measured':bool(measurements),'method':'original source join',
              'tolerance':0,'matched':bool(measurements),
              'physical_cause_confirmed':False,'cause_evidence':context['geometry_source']}
    result = {'case_id':case['case_id'],'measured_values':measurements,'target_checks':[target],
              'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
              'termination_reason':'Saved source observations; legal judgment unresolved',
              'physical_failure_flags':[],'trace_reference':'trace.jsonl',
              'video_references':[name+'.mkv' for name in ('overview','approach','reference_corner','driver_reference')],
              'video_frame_map_reference':'video_frames.jsonl','recording_description':description,
              'recording_evidence':evidence,'realized_observables':{}}
    from worker_exchange.native_output import physical_result, validate_result
    result = physical_result(attempt,result)
    validate_result(result)
    (attempt/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    if output.exists(): raise ValueError('retain prior measurement report')
    output.write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    analyze(args.attempt,args.output)


if __name__=='__main__': main()
