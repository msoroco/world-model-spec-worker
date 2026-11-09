"""Physical API-indicator lead to an engineering departure annotation.

This is neither emitted-light continuity nor a legal course-change definition.
Inputs are original, synchronized post-tick samples; no resampling or new ticks.
"""
import math

METHOD = 'Planar original-pose path integral from first reported sole-left API state to first center lateral displacement exceeding 0.05 m; upper sampled event times, original bracketing samples retained'
WINDOW = 'Reported sole-left API onset through engineering lane-departure annotation'


def measure(rows, departure):
    if not departure:
        return {'status': 'unavailable', 'value': None, 'reason': 'Departure annotation not observed'}
    onset = next((i for i, r in enumerate(rows) if r['reported_device_state'] == 'left'), None)
    if onset is None or onset == 0 or rows[onset-1]['reported_device_state'] != 'off':
        return {'status': 'unavailable', 'value': None, 'reason': 'Sole-left transition lacks a preceding original off sample'}
    bracket = departure['time_bracket_s']
    end = next((i for i, r in enumerate(rows) if abs(r['time_s']-bracket[1]) < 1e-7), None)
    if end is None or end == 0 or abs(rows[end-1]['time_s']-bracket[0]) >= 1e-7:
        return {'status': 'unavailable', 'value': None, 'reason': 'Departure bracket does not match original consecutive samples'}
    if onset>end or any(r['reported_device_state']!='left' for r in rows[onset:end+1]):
        return {'status':'unavailable','value':None,'reason':'Indicator activation is not continuous through departure'}
    start, finish = min(onset-1, end-1), max(onset, end)
    distances = [0.0]
    for a, b in zip(rows[start:finish], rows[start+1:finish+1]):
        dt = b['time_s']-a['time_s']
        if b['frame'] != a['frame']+1 or not 0 < dt <= 0.05001:
            return {'status': 'unavailable', 'value': None, 'reason': 'Original frame or cadence gap across integration interval'}
        step = math.hypot(b['x']-a['x'], b['y']-a['y'])
        if not math.isfinite(step):
            return {'status': 'unavailable', 'value': None, 'reason': 'Nonfinite original pose'}
        distances.append(distances[-1]+step)
    def distance(i):
        return distances[i-start]
    value = distance(end)-distance(onset)
    return {'status': 'measured', 'value': value, 'unit': 'm', 'method': METHOD,
            'time_window': WINDOW, 'statistic': 'last',
            'sample_window_s': [rows[onset]['time_s'], rows[end]['time_s']],
            'onset_time_bracket_s': [rows[onset-1]['time_s'], rows[onset]['time_s']],
            'departure_time_bracket_s': bracket,
            'sampling_distance_interval_m': [distance(end-1)-distance(onset), distance(end)-distance(onset-1)],
            'references': ['ego_trajectory.jsonl', 'ego_turn_indicator.jsonl', 'ego_course_change.jsonl'],
            'limitations': ['Interval reflects original temporal sampling only; spatial calibration is unverified',
                           'API enabled state does not measure emitted light, visibility or perception',
                           'Departure annotation is an engineering event and carries no legal meaning']}


def project_saved_measurement(result, attempt, case):
    """Recompute and flatten a completed event report; originals stay immutable.

The integration input window and the scalar report's availability window are
separate: the completed onset-to-departure distance first exists at departure.
"""
    import copy
    import hashlib
    import json
    from pathlib import Path
    name = 'ego_signal_lead_distance'
    if not case.get('sweep_id', '').endswith('appropriate-signal'):
        raise ValueError('Projection is restricted to the frozen API signal sweep')
    expected = next(a for a in case['sweep_measurements'] if a['observable'] == name)
    if expected['unit'] != 'm' or expected['measurement'] != {'method': METHOD, 'time_window': WINDOW, 'statistic': 'last'}:
        raise ValueError('Projection differs from frozen measurement definition')
    attempt = Path(attempt)
    names = ('ego_trajectory', 'ego_turn_indicator', 'ego_course_change', name)
    streams = {k:[json.loads(line) for line in (attempt/(k+'.jsonl')).read_text().splitlines()] for k in names}
    if len({len(v) for v in streams.values()}) != 1:
        raise ValueError('Original measurement channel lengths differ')
    rows = []; departure = None
    for values in zip(*(streams[k] for k in names)):
        if len({v['time_s'] for v in values}) != 1:
            raise ValueError('Original measurement channels are not synchronized')
        trajectory, indicator, motion, _ = values
        p = trajectory['value']['position_local_m']
        rows.append({'frame':trajectory['value']['source_frame'], 'time_s':trajectory['time_s'], 'x':p['x'], 'y':p['y'], 'reported_device_state':indicator['value']['reported_device_state']})
        departure = motion['value']['departure_annotation'] or departure
    measured = measure(rows, departure)
    summary = result['realized_observables'][name]
    if measured['status'] != 'measured' or not math.isclose(measured['value'], summary['value'], rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError('Original summary contradicts recomputed actual API/pose path integral')
    if summary.get('integration_input_window_s', summary['sample_window_s']) != measured['sample_window_s']:
        raise ValueError('Original summary input event window differs')
    event = measured['sample_window_s'][1]
    projected = []
    for row in streams[name]:
        value = row['value']
        if row['time_s'] >= event:
            if value.get('status') != 'measured' or not math.isclose(value['value'], measured['value'], rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError('Original completed event channel contradicts recomputed measurement')
            value = value['value']
        projected.append({'time_s':row['time_s'], 'value':value})
    projection = copy.deepcopy(result)
    reference = 'offline_projection/'+name+'.jsonl'
    path = attempt/reference; path.parent.mkdir(exist_ok=True)
    content = ''.join(json.dumps(row,allow_nan=False)+'\n' for row in projected)
    if path.exists() and path.read_text() != content:
        raise ValueError('Existing audited scalar projection would change')
    path.write_text(content)
    projection['realized_observables'][name].update(
        reference=reference, sample_window_s=[event,event],
        integration_input_window_s=measured['sample_window_s'],
        availability='Completed event report first available at departure; scalar statistic uses that event sample. Full integration inputs remain in original pose/indicator channels.')
    for evidence in projection['recording_evidence']:
        if evidence['name'] == name:
            evidence['reference'] = reference
    audit = {'acquisition':'offline_recomputed_original_synchronized_samples',
             'original_result_unchanged':True, 'original_channels_unchanged':True,
             'measurement':measured,'scalar_report_sample_window_s':[event,event],
             'reason':'Original event distance was wrapped in metadata; flatten only the confirmed completed report, preserve unavailable pre-event values and all original metadata.',
             'reference':reference,'projection_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
             'source_sha256':{k:hashlib.sha256((attempt/(k+'.jsonl')).read_bytes()).hexdigest() for k in names}}
    return projection, audit


def measure_for_side(rows,departure,side='left'):
    """Reuse the original continuity/integration algorithm for either indicator.

    Source rows are preserved. The departure bracket remains an engineering
    annotation; this does not establish emitted flashing or legal course change.
    """
    if side not in ('left','right'):raise ValueError('Expected left or right')
    if side=='left':return measure(rows,departure)
    converted=[]
    for row in rows:
        value=dict(row)
        state=row['reported_device_state']
        value['reported_device_state']='left' if state=='right' else 'opposite' if state=='left' else state
        converted.append(value)
    result=measure(converted,departure)
    if 'method' in result:result['method']=result['method'].replace('left','right')
    result['measured_indicator_side']=side
    return result
