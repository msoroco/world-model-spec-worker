"""Saved-only mode-specific measurements and native output finalization."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from worker_exchange.media import audit
from worker_exchange.native_output import write_result


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def approach_controls(controls, road_id):
    signs = [item for item in controls['landmarks']
        if str(item.get('type')) in ('206', 'Stop', 'stop')
        and item.get('road_id') == road_id
        and (str(item.get('orientation', '')).lower() == '+' or
             str(item.get('orientation', '')).lower().endswith('positive'))
        and item.get('t_m', 0) < 0 and 55 <= item.get('s_m', -1) <= 70]
    near_vertices = [v for v in controls['crosswalk_vertices_m']
                     if -20 <= v[0] <= -5 and -8 <= v[1] <= 8]
    return signs, min((v[0] for v in near_vertices), default=None)


def analyze(attempt):
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    case = config['case']
    mode = config['mode']
    trace = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    source = rows(attempt / 'channels/source_observations.jsonl')
    if not trace or not (len(trace) == len(evidence) == len(mapping) == len(source)):
        raise ValueError('Original trace/evidence/frame/channel counts differ')
    for i, (point, event, frame, observation) in enumerate(zip(trace, evidence, mapping, source)):
        if point['frame'] != event['original_frame'] or point['frame'] != frame.get('carla_frame') or \
                frame.get('native_frame') != point['frame'] or frame.get('video_frame') != i or \
                abs(point['time_s']-frame['time_s']) > 1e-6 or \
                abs(point['time_s']-observation['time_s']) > 1e-6 or observation['value'] is None:
            raise ValueError('Original acquisition identity/time/value join differs')
    for name in ('kin.position', 'kin.heading', 'kin.speed'):
        path = attempt / 'channels' / (name + '.jsonl')
        if not path.is_file():
            raise ValueError('Missing original channel: ' + name)
        values = rows(path)
        if len(values) != len(trace) or any(v.get('value') is None or
                abs(v['time_s']-t['time_s']) > 1e-6 for v, t in zip(values, trace)):
            raise ValueError('Original kinematic channel mismatch: ' + name)
    fixture = (attempt / 'fixture-provenance.json').is_file()
    videos = ['raw.mkv'] if fixture else ['view%d.mkv' % i for i in range(4)]
    mapping_sha = hashlib.sha256((attempt / 'video_frames.jsonl').read_bytes()).hexdigest()
    counts = {}
    for i, ref in enumerate(videos):
        receipt = audit(attempt / ref, len(trace), mapping_sha256=mapping_sha,
                        receipt=attempt / ('source-%d.json' % i))
        if not fixture:
            expected = [1920, 1080] if i == 0 else [1280, 720]
            if receipt['dimensions'] != expected:
                raise ValueError('Original source camera dimensions differ')
        counts[ref] = receipt['frames']
    points = [r['position'] for r in trace]
    speed = [r['speed_mps'] for r in trace]
    observed = [r['value'] for r in source]
    heading_delta = ((trace[-1]['heading_deg'] - trace[0]['heading_deg'] + 180) % 360) - 180
    other = [v.get('other') for v in observed]
    actual_other_count = int(any(v is not None for v in other))
    dt = (trace[-1]['time_s']-trace[0]['time_s'])/(len(trace)-1) if len(trace)>1 else .05
    measurements = {'original_frames': len(trace), 'heading_change_deg': heading_delta,
                    'other_actor_observed': bool(actual_other_count)}
    checks = []
    if mode == 'left_turn':
        target = case['variable_assignments']['exit_right_offset_m']['value']
        measured = points[-1]['x']
        measurements.update(exit_world_x_m=measured, right_of_new_centerline_observed=measured>0,
                            turn_complete=not fixture and abs(heading_delta-90)<15 and points[-1]['y']>65)
        checks.append(dict(target='exit_right_offset_m', requested=target, measured=measured,
                           method='last original world X relative to northbound centerline', tolerance=.5,
                           matched=abs(measured-target)<=.5, physical_cause_confirmed=False,
                           cause_evidence='trace.jsonl'))
    elif mode == 'yield_turn':
        requested = case['variable_assignments']['yield_wait_s']['value']
        measured = sum(s < .05 for s in speed)*dt
        approach_other = [v for v in other if v]
        gap = min((math.dist([p['x'],p['y']],v['position_m'][:2]) for p,v in zip(points,other) if v),default=None)
        oncoming_frames = sum(v is not None and abs(abs(v['heading_deg']-trace[i]['heading_deg'])-180)<30
                              for i,v in enumerate(other))
        signal_frames = sum('LeftBlinker' in str(v.get('native_light_state')) for v in observed)
        ego_entry = next((trace[i]['time_s'] for i,p in enumerate(points) if p['x'] >= -7),None)
        other_entry = next((trace[i]['time_s'] for i,v in enumerate(other)
                            if v and v['position_m'][0] <= 7),None)
        measurements.update(stopped_duration_s=measured,minimum_other_centre_gap_m=gap,
                            oncoming_actor_observed=bool(approach_other),
                            opposite_heading_frames=oncoming_frames,
                            left_signal_frames=signal_frames,
                            ego_entry_time_s=ego_entry, other_entry_time_s=other_entry,
                            entry_order_observed=ego_entry is not None and other_entry is not None)
        checks.append(dict(target='yield_wait_s', requested=requested, measured=measured,
                           method='count original stationary ticks times observed sample interval', tolerance=.1,
                           matched=abs(measured-requested)<=.1, physical_cause_confirmed=False,
                           cause_evidence='trace.jsonl; channels/source_observations.jsonl'))
    elif mode == 'lane_change':
        target = case['variable_assignments']['signal_lead_m']['value']
        signal = [i for i,v in enumerate(observed) if 'LeftBlinker' in str(v.get('native_light_state'))]
        lane = [i for i,p in enumerate(points) if p['y'] < -2]
        measured = max(0, points[lane[0]]['x']-points[signal[0]]['x']) if signal and lane else 0.
        surface_gaps = []
        for row, counterpart in zip(observed,other):
            ego_body = row.get('ego_body_vertices_m')
            other_body = counterpart.get('body_vertices_m') if counterpart else None
            if ego_body and other_body:
                ego_x = [p[0] for p in ego_body]
                other_x = [p[0] for p in other_body]
                surface_gaps.append(max(0., max(min(other_x)-max(ego_x),min(ego_x)-max(other_x))))
        measurements.update(signal_onset_frame=signal[0] if signal else None,
                            lane_departure_frame=lane[0] if lane else None,
                            signal_lead_m=measured,
                            minimum_target_lane_surface_gap_m=min(surface_gaps) if surface_gaps else None,
                            counterpart_gap_samples=len(surface_gaps))
        checks.append(dict(target='signal_lead_m', requested=target, measured=measured,
                           method='original signal onset to first lateral lane departure world X', tolerance=2.,
                           matched=abs(measured-target)<=2., physical_cause_confirmed=False,
                           cause_evidence='channels/source_observations.jsonl'))
    elif mode == 'following':
        target = case['variable_assignments']['commanded_gap_m']['value']
        gaps = [v['position_m'][0]-p['x'] for p,v in zip(points,other) if v]
        measured = sum(gaps)/len(gaps) if gaps else 0.
        surface_gaps = []
        for row,counterpart in zip(observed,other):
            ego_body=row.get('ego_body_vertices_m')
            other_body=counterpart.get('body_vertices_m') if counterpart else None
            if ego_body and other_body:
                surface_gaps.append(min(p[0] for p in other_body)-max(p[0] for p in ego_body))
        measurements.update(mean_centre_gap_m=measured, gap_samples=len(gaps),
                            gap_unmeasured=not bool(gaps),
                            minimum_longitudinal_surface_gap_m=min(surface_gaps) if surface_gaps else None,
                            merge_occupancy_unknown=fixture)
        checks.append(dict(target='commanded_gap_m', requested=target, measured=measured,
                           method='mean original other-minus-ego world X; zero is explicit no-other diagnostic censoring',
                           tolerance=2., matched=bool(gaps) and abs(measured-target)<=2.,
                           physical_cause_confirmed=False,
                           cause_evidence='channels/source_observations.jsonl'))
    elif mode == 'stop':
        target = case['variable_assignments']['stop_duration_s']['value']
        before = [s for s,p in zip(speed,points) if p['x'] < -10]
        measured = sum(s < .05 for s in before)*dt
        controls_path = attempt / 'native-controls.json'
        if not controls_path.is_file():
            raise ValueError('Native sign/crosswalk inventory missing')
        controls = json.loads(controls_path.read_text())
        approach_road = next((v['road_projection']['road_id'] for p,v in zip(points,observed)
            if v.get('road_projection') and p['x'] < -20), None)
        signs, boundary_x = approach_controls(controls, approach_road)
        before = [(s,row) for s,row in zip(speed,observed)
                  if boundary_x is not None and row.get('ego_body_vertices_m')
                  and max(v[0] for v in row['ego_body_vertices_m']) < boundary_x]
        measured = sum(s < .05 for s,_ in before)*dt
        front_before = [max(v[0] for v in row['ego_body_vertices_m']) for _,row in before]
        measurements.update(pre_crosswalk_stop_s=measured, pre_crosswalk_samples=len(before),
                            native_stop_sign_metadata_observed=bool(signs),
                            approach_road_id=approach_road,
                            governing_stop_sign_ids=[item['id'] for item in signs],
                            native_crosswalk_vertices_observed=boundary_x is not None,
                            near_side_crosswalk_boundary_x_m=boundary_x,
                            max_body_front_before_crosswalk_m=max(front_before) if front_before else None)
        checks.append(dict(target='stop_duration_s', requested=target, measured=measured,
                           method='original stationary ticks with entire body before native near-side crosswalk boundary',
                           tolerance=.1, matched=abs(measured-target)<=.1,
                           physical_cause_confirmed=False, cause_evidence='trace.jsonl'))
    else:
        raise ValueError('Unknown package mode')
    route_end = not fixture and bool(observed[-1].get('route_index') is not None and
        observed[-1]['route_index'] >= config['route_last_index']-2)
    report = {'format':'partition01-capability-report-v1','case_id':case['case_id'],
              'mode':mode,'measurements':measurements,'decoded_sources':counts,
              'original_join':True,'physical_acceptance':False,
              'decision':'inspect_original_native_evidence' if route_end else 'repair_same_frozen_case',
              'follow_up':{'same_case_id':case['case_id'],'preserve_targets':True,
                           'requires_new_attempt':not route_end},
              'unresolved':['native geometry/device authority', 'physical motion and timing',
                            'camera visibility and final delivery video']}
    result = {'case_id':case['case_id'],'measured_values':measurements,'target_checks':checks,
              'setup_confirmed':False,'behavior_attempted':not fixture and len(trace)>1,
              'maneuver_completed':bool(route_end),
              'termination_reason':'diagnostic subset without maneuver' if fixture else
                                   ('measured route endpoint' if route_end else 'incomplete original route'),
              'physical_failure_flags':{'setup_unconfirmed':True,'visibility_unverified':True},
              'trace_reference':'trace.jsonl','video_references':videos,
              'video_frame_map_reference':'video_frames.jsonl',
              'recording_description':case['recording_description'],
              'recording_evidence':[{'name':c['name'],'unit':c['unit'],
                  'reference':'channels/'+c['name']+'.jsonl'} for c in case['recording_description']['channels']],
              'realized_observables':{}}
    return report, result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    report,result=analyze(args.attempt)
    write_result(args.attempt,result)
    Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
