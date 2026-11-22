"""Saved-only measurement of sign, dismount, and reversal events.

The capture must supply original phase-events.jsonl and sign-inventory.json with
SHA256 bindings in acquisition.json. This finalizer does not assign a legal label.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

REQUIRED = ('phase-events.jsonl', 'pedestrian-context.jsonl', 'sign-inventory.json',
            'sign-authorization-source', 'video_frames.jsonl')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_bound(attempt, acquisition, name):
    path = (attempt / name).resolve()
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    entry = acquisition.get(name)
    if not entry or entry.get('kind') != 'original_native' or not entry.get('sha256'):
        raise ValueError('missing original Native acquisition: ' + name)
    if attempt.resolve() not in path.parents or not path.is_file() or sha(path) != entry['sha256']:
        raise ValueError('missing or changed source: ' + name)
    return path


def body_center(row, key):
    body = row.get(key)
    if (not isinstance(body, list) or len(body) < 4 or
            any(not isinstance(vertex, list) or len(vertex) < 2 or
                any(type(value) not in (int, float) or not math.isfinite(value)
                    for value in vertex[:2]) for vertex in body)):
        raise ValueError('original operator/bicycle body geometry missing: '+key)
    return ((min(v[0] for v in body)+max(v[0] for v in body))/2,
            (min(v[1] for v in body)+max(v[1] for v in body))/2)


def body_separation(row):
    human = body_center(row, 'operator_body_vertices_m')
    bicycle = body_center(row, 'bicycle_body_vertices_m')
    return math.dist(human, bicycle)


def finalize(attempt):
    attempt = Path(attempt)
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    event_path = read_bound(attempt, acquisition, 'phase-events.jsonl')
    context_path = read_bound(attempt, acquisition, 'pedestrian-context.jsonl')
    sign_path = read_bound(attempt, acquisition, 'sign-inventory.json')
    authorization_path = read_bound(attempt, acquisition, 'sign-authorization-source')
    frame_path = read_bound(attempt, acquisition, 'video_frames.jsonl')
    rows = [json.loads(line) for line in event_path.read_text().splitlines() if line.strip()]
    contexts=[json.loads(line) for line in context_path.read_text().splitlines() if line.strip()]
    if not rows or any(rows[i]['frame'] >= rows[i+1]['frame'] or rows[i]['time_s'] >= rows[i+1]['time_s']
                       for i in range(len(rows)-1)):
        raise ValueError('phase events lack monotone original frame/time order')
    operators = {r.get('operator_id') for r in rows}
    bikes = {r.get('bicycle_id') for r in rows}
    signs = {r.get('sign_id') for r in rows}
    if (len(operators) != 1 or None in operators or len(bikes) != 1 or None in bikes
            or len(signs) != 1 or None in signs):
        raise ValueError('sign, operator or bicycle identity changes')
    frames = [json.loads(line) for line in frame_path.read_text().splitlines() if line.strip()]
    if (len(rows) != len(frames) or any(
            row['frame'] != frame.get('carla_frame') or
            abs(row['time_s']-frame.get('time_s',float('inf'))) > 1e-4
            for row,frame in zip(rows,frames))):
        raise ValueError('original phase event/frame map join failed')
    if len(contexts)!=len(rows) or any(
            context.get('frame')!=row['frame'] or
            abs(context.get('time_s',float('inf'))-row['time_s'])>1e-4 or
            context.get('operator_id')!=row['operator_id'] or
            context.get('pedestrian_regulation_assessment')!='unresolved' or
            not isinstance(context.get('nearby_crosswalk_vertices_m'),list) or
            not isinstance(context.get('nearby_control_devices'),list)
            for row,context in zip(rows,contexts)):
        raise ValueError('original pedestrian context/frame and operator join failed')
    separations = [body_separation(row) for row in rows]
    mounted = ('mounted_approach', 'mounted_reversal')
    if any(distance > .5 for row, distance in zip(rows, separations)
           if row.get('phase') in mounted):
        raise ValueError('declared mounted phase lacks original body proximity')
    sign = json.loads(sign_path.read_text())
    if (sign.get('message') != 'NO U TURN' or not sign.get('erected') or
            sign.get('sign_actor_id') != next(iter(signs)) or
            sign.get('authorization_source_sha256') != sha(authorization_path)):
        raise ValueError('governing sign identity/authorization missing')
    phases = {key: [r for r in rows if r.get('phase') == key]
              for key in ('mounted_approach','dismount_hold','afoot_reversal','mounted_reversal','turn_complete')}
    if not phases['mounted_approach'] or not phases['turn_complete']:
        raise ValueError('approach or completed reversal missing')
    start = min((r['time_s'] for name in ('afoot_reversal','mounted_reversal') for r in phases[name]), default=None)
    if start is None or phases['turn_complete'][0]['time_s'] <= start:
        raise ValueError('reversal phase or completion missing')
    dismounted = bool(phases['dismount_hold'])
    if dismounted:
        if not phases['afoot_reversal'] or phases['mounted_reversal']:
            raise ValueError('dismount phase conflicts with reversal body state')
        dismount_time = phases['dismount_hold'][0]['time_s']
        if not dismount_time < start:
            raise ValueError('dismount did not precede reversal')
        if any(distance < 1.0 for row, distance in zip(rows, separations)
               if row.get('phase') in ('afoot_reversal', 'turn_complete')):
            raise ValueError('declared afoot reversal lacks original body separation')
    else:
        if not phases['mounted_reversal'] or phases['afoot_reversal']:
            raise ValueError('mounted reversal body state missing or mixed')
        dismount_time = None
        if any(distance > .5 for row, distance in zip(rows, separations)
               if row.get('phase') == 'turn_complete'):
            raise ValueError('mounted turn completion lacks original body proximity')
    return {'format':'worker-phase-measurements','operator_id':next(iter(operators)),
            'bicycle_id':next(iter(bikes)),'observed_sign':sign,'dismount_time_s':dismount_time,
            'turn_start_s':start,'turn_complete_s':phases['turn_complete'][0]['time_s'],
            'dismounted_before_turn':dismounted,
            'pedestrian_context_frames':len(contexts),
            'post_dismount_context_frames':sum(
                row['phase'] in ('dismount_hold','afoot_reversal','turn_complete')
                for row in rows) if dismounted else 0,
            'original_body_separation_m_by_frame': [
                {'frame': row['frame'], 'separation_m': distance}
                for row, distance in zip(rows, separations)],
            'body_separation_tolerances_m': {'mounted_max': .5, 'afoot_min': 1.0,
                                            'engineering_not_legal': True},
            'source_sha256':{name:acquisition[name]['sha256'] for name in REQUIRED},
            'legal_judgment':'unresolved'}


def build_report(attempt):
    attempt = Path(attempt)
    measurement = finalize(attempt)
    sources = {name:sha(attempt/name) for name in REQUIRED}
    return {'format':'worker-analysis-report',
            'measurements':{'dismount_turn_measurement':{
                'value':measurement,'method':'finalize','sources':sources}},
            'limitations':['Sign authorization and pedestrian obligations require independent source review; constructed phase labels and body proximity are not a legal verdict.'],
            'analysis_complete':True,'legal_verdict_claimed':False}


def saved_result(attempt, report):
    """Build a Native-shaped saved result without asserting physical acceptance."""
    from worker_exchange.native_output import physical_result, validate_result
    attempt = Path(attempt)
    config = json.loads((attempt/'config.json').read_text())
    construction = json.loads((attempt/'construction.json').read_text())
    acquisition = json.loads((attempt/'acquisition.json').read_text())
    event_path = read_bound(attempt, acquisition, 'phase-events.jsonl')
    rows = [json.loads(line) for line in event_path.read_text().splitlines() if line.strip()]
    contexts=[json.loads(line) for line in read_bound(attempt,acquisition,
        'pedestrian-context.jsonl').read_text().splitlines() if line.strip()]
    sign = json.loads(read_bound(attempt, acquisition, 'sign-inventory.json').read_text())
    channels = attempt/'channels'
    channels.mkdir(exist_ok=True)
    fields = {'operator_pose':'operator_body_vertices_m',
              'bicycle_pose':'bicycle_body_vertices_m',
              'phase_events':'phase'}
    recording = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        if name == 'sign_inventory':
            values = [sign for _ in rows]
        elif name == 'pedestrian_context':
            values=contexts
        elif name in fields:
            field = fields[name]
            if any(field not in row for row in rows):
                raise ValueError('Missing original recording channel: '+field)
            values = [row[field] for row in rows]
        else:
            raise ValueError('Unsupported declared recording channel: '+name)
        target = channels/(name+'.jsonl')
        with target.open('x') as stream:
            for row,value in zip(rows,values):
                stream.write(json.dumps({'time_s':row['time_s'],'value':value},allow_nan=False)+'\n')
        recording.append({'name':name,'unit':'structured record',
                          'reference':str(target.relative_to(attempt))})
    measured = report['measurements']['dismount_turn_measurement']['value']
    requested = bool(config['case']['dismount_before_turn'])
    target = {'target':'observed dismount before U-turn',
              'requested':requested,'measured':measured['dismounted_before_turn'],
              'method':'source-bound body separation and phase timing',
              'tolerance':0,'matched':requested==measured['dismounted_before_turn'],
              'physical_cause_confirmed':False,
              'cause_evidence':report['measurements']['dismount_turn_measurement']['sources']}
    result = {'case_id':config['selected_case_id'],'measured_values':measured,
              'target_checks':[target], 'setup_confirmed':False,
              'behavior_attempted':False,'maneuver_completed':False,
              'termination_reason':'Saved measurements pending physical assessment',
              'physical_failure_flags':[], 'trace_reference':'trace.jsonl',
              'video_references':['overview.mkv','approach.mkv',
                                  'reference_corner.mkv','driver_reference.mkv'],
              'video_frame_map_reference':'video_frames.jsonl',
              'recording_description':construction['recording_description'],
              'recording_evidence':recording,'realized_observables':{}}
    result = physical_result(attempt,result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = build_report(args.attempt)
    result = saved_result(args.attempt, report)
    report['physical_checks'] = result['physical_checks']
    report['realized_observables'] = result['realized_observables']
    with Path(args.attempt,'result.json').open('x') as stream:
        stream.write(json.dumps(result,indent=2)+'\n')
    with Path(args.output).open('x') as stream:
        stream.write(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__':
    main()
