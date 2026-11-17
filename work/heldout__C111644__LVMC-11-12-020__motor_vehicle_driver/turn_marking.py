"""Authorized intersection turn-course indication construction and observations."""
from __future__ import annotations
import argparse
import hashlib
import json
from math import atan2, cos, hypot, isfinite, sin
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('original_course_deviation_m', 'original_turn_path_length_m',
            'intersection_occupancy', 'turn_course_source_context',
            'realized_course_deviation_m',
            'realized_indication_placement_offset_m')


def construct(adapter, indication_type, route_variant):
    if indication_type not in ('marker','button','other_indication') or route_variant not in ('follow','depart'):
        raise ValueError('unknown indication or route variant')
    intersection=adapter.intersection(layout='intersection',maneuver='turn')
    course=[(-20,0),(-5,0),(0,5),(0,20)]
    indication=adapter.turn_course_indication(kind=indication_type,authorized=True,
                                               within_intersection=True,course_xy=course)
    route=course if route_variant=='follow' else [(-20,0),(-5,0),(5,5),(5,20)]
    ego=adapter.vehicle(role='ego',route=route,target_mps=3)
    return {'intersection':intersection,'indication':indication,'ego':ego}


def _segment_distance(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    d=dx*dx+dy*dy
    if d<.001:raise ValueError('degenerate indicated course segment')
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/d))
    return hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)


def measure(indication,frames):
    if indication.get('kind') not in ('marker','button','other_indication'):
        raise ValueError('indication type missing')
    if indication.get('authorized') is not True or indication.get('within_intersection') is not True or not indication.get('authorization_source'):
        raise ValueError('authorized in-intersection indication source missing')
    course=indication.get('course_xy')
    if not isinstance(course,list) or len(course)<3:
        raise ValueError('indicated course geometry missing')
    if not isinstance(frames,list) or len(frames)<3:raise ValueError('original turn motion missing')
    rows=[]
    first_frame=frames[0].get('frame')
    first_time=frames[0].get('time_s')
    if type(first_frame) is not int or not isinstance(first_time,(int,float)):
        raise ValueError('original synchronized subject source missing')
    for i,f in enumerate(frames):
        if (f.get('frame')!=first_frame+i or
                abs(f.get('time_s',-1)-first_time-i*.05)>.005 or
                not f.get('subject_source')):
            raise ValueError('original synchronized subject source missing')
        p=f.get('subject_center_xy')
        if not isinstance(p,list) or len(p)!=2:raise ValueError('original subject position missing')
        rows.append({'frame':i,'distance_to_indicated_course_m':min(_segment_distance(p,a,b) for a,b in zip(course,course[1:]))})
    return {'indication_type':indication['kind'],'max_center_deviation_m':max(r['distance_to_indicated_course_m'] for r in rows),
            'samples':rows,'legal_obedience_judgment':None}


def audit_comparison(a,b,variable):
    if variable not in ('route_response','indication_form') or not a.get('samples') or not b.get('samples'):
        raise ValueError('valid two-case comparison requires original measurements')
    for key in ('intersection_hash','course_hash','camera_plan_hash','duration_s','subject_hash'):
        if not a.get(key) or a[key]!=b.get(key):raise ValueError('fixed condition changed: '+key)
    fixed,varied=('indication_type','max_center_deviation_m') if variable=='route_response' else ('max_center_deviation_m','indication_type')
    if a.get(fixed)!=b.get(fixed):raise ValueError('held condition changed: '+fixed)
    if a.get(varied)==b.get(varied):raise ValueError('deliberate difference absent')
    return {'comparison_complete':True,'fixed_conditions_checked':True,'legal_obedience_judgment':None}


def native_route_plan(indication_source, route_variant, *, departure_side='right',
                      departure_m=4.0):
    """Use the sourced turn course to make a follow/depart route.

    A departure is an engineering counterfactual, not a legal threshold. The
    source file must already have passed indication_native.load_source.
    """
    if route_variant not in ('follow', 'depart'):
        raise ValueError('Unknown turn route variant')
    if departure_side not in ('right', 'left') or not 2.0 <= departure_m <= 8.0:
        raise ValueError('Invalid departure engineering knob')
    course = indication_source['indicated_course_xy_m']
    polygon = indication_source['intersection_polygon_xy_m']
    if len(course) < 3:
        raise ValueError('Sourced turn course too short')
    from indication_native import _inside
    interior = [index for index in range(1, len(course) - 1)
                if _inside(course[index], polygon)]
    if not interior:
        raise ValueError('Sourced turn course misses intersection interior')
    # The first interior vertex is held fixed in the comparison. Changing the
    # latter portion isolates route response while retaining the approach.
    last = interior[-1]
    if last == len(course) - 1:
        raise ValueError('Turn route needs an exit beyond the intersection')
    route = [list(point) for point in course]
    if route_variant == 'depart':
        anchor = course[last]
        exit_point = course[-1]
        dx, dy = exit_point[0] - anchor[0], exit_point[1] - anchor[1]
        distance = hypot(dx, dy)
        if distance < 1.0:
            raise ValueError('Sourced turn exit segment is degenerate')
        sign = -1.0 if departure_side == 'right' else 1.0
        lateral = (-dy / distance * departure_m * sign,
                   dx / distance * departure_m * sign)
        # Move the exit and all subsequent samples to a parallel, visibly
        # distinct course. The Native run will measure the realized body path.
        for index in range(last + 1, len(route)):
            route[index][0] += lateral[0]
            route[index][1] += lateral[1]
    return {'indication_form': indication_source['indication_form'],
            'intersection_id': indication_source['intersection_id'],
            'course_xy_m': [list(point) for point in course],
            'target_route_xy_m': route, 'route_variant': route_variant,
            'departure_side': departure_side if route_variant == 'depart' else None,
            'departure_m': departure_m if route_variant == 'depart' else None,
            'legal_obedience_judgment': None}


def control_to_target(position_xy, heading_xy, velocity_xy, target_xy,
                      target_speed_mps):
    """Pure 20 Hz vehicle control for a later CARLA-lazy Native runner."""
    values = (*position_xy, *heading_xy, *velocity_xy, *target_xy,
              target_speed_mps)
    if any(isinstance(value, bool) or not isinstance(value, (int, float))
           or not isfinite(value) for value in values):
        raise ValueError('Nonfinite route control input')
    if not 1.0 <= target_speed_mps <= 12.0:
        raise ValueError('Invalid target turn speed')
    forward_length = hypot(*heading_xy)
    if forward_length < .8:
        raise ValueError('Native forward vector missing')
    direction = (target_xy[0] - position_xy[0],
                 target_xy[1] - position_xy[1])
    distance = hypot(*direction)
    if distance < .6:
        return {'throttle': 0.0, 'steer': 0.0, 'brake': 1.0}
    current_angle = atan2(heading_xy[1], heading_xy[0])
    desired_angle = atan2(direction[1], direction[0])
    error = atan2(sin(desired_angle - current_angle),
                  cos(desired_angle - current_angle))
    steer = max(-1.0, min(1.0, error / .65))
    speed = hypot(*velocity_xy)
    return {'throttle': max(0.0, min(.6, (target_speed_mps - speed) * .22)),
            'steer': steer,
            'brake': max(0.0, min(.8, (speed - target_speed_mps) * .3))}


def analyze_original_sources(attempt):
    """Join retained Native sources and derive turn geometry without a verdict."""
    root = Path(attempt)
    receipt = json.loads((root / 'turn_source_receipt.json').read_text())
    hashes = receipt.get('source_sha256')
    required = {'turn_indication_original.json',
                'turn_indication_readback_original.json', 'turn_route_plan.json',
                'turn_body_original.jsonl', 'trace.jsonl', 'video_frames.jsonl'}
    required |= {name + '.mkv' for name in CAMERAS}
    required |= {name + '-frames.jsonl' for name in CAMERAS}
    if not isinstance(hashes, dict) or set(hashes) != required:
        raise ValueError('Original turn source inventory incomplete')
    for name, digest in hashes.items():
        path = root / name
        if not path.is_file():
            raise ValueError('Missing required source: ' + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Original turn source SHA-256 mismatch: ' + name)
    source = json.loads((root / 'turn_indication_original.json').read_text())
    readback = json.loads((root / 'turn_indication_readback_original.json').read_text())
    plan = json.loads((root / 'turn_route_plan.json').read_text())
    from indication_native import _inside, load_source
    kind = source.get('indication_form')
    load_source(root / 'turn_indication_original.json',
                hashes['turn_indication_original.json'], kind)
    reference = source['indicated_course_xy_m'][1]
    actual = readback.get('physical_xy_m')
    if (readback.get('source_sha256') != hashes['turn_indication_original.json']
            or readback.get('reference_kind') != 'unchanged_sourced_indicated_course_point_1'
            or readback.get('reference_xy_m') != reference
            or not isinstance(actual, list)
            or len(actual) != len(source['indications'])):
        raise ValueError('Original indication readback or reference differs')
    for point, item in zip(actual, source['indications']):
        if (not isinstance(point, list) or len(point) != 2
                or any(type(value) not in (int, float) or not isfinite(value)
                       for value in point)
                or hypot(point[0]-item['x'], point[1]-item['y']) > .05):
            raise ValueError('Original indication position readback differs')
    if len(actual) != 1:
        raise ValueError('Sweep requires one source-identified indication')
    placement_offset = hypot(actual[0][0]-reference[0], actual[0][1]-reference[1])
    if (plan.get('course_xy_m') != source['indicated_course_xy_m'] or
            plan.get('indication_form') != kind or
            plan.get('intersection_id') != source['intersection_id']):
        raise ValueError('Sourced turn course and route plan differ')
    if receipt.get('case_id') is None or not receipt['case_id'].endswith(
            kind + '_' + plan['route_variant']):
        raise ValueError('Turn source receipt case identity differs')
    def rows(name):
        return [json.loads(line) for line in (root / name).read_text().splitlines()
                if line.strip()]
    body = rows('turn_body_original.jsonl')
    trace = rows('trace.jsonl')
    mapping = rows('video_frames.jsonl')
    if not body or len(body) != len(trace) or len(body) != len(mapping):
        raise ValueError('Original turn body/trace/frame count differs')
    frames = []
    centers = []
    for index, (sample, trow, fmap) in enumerate(zip(body, trace, mapping)):
        frame, time_s = sample.get('frame'), sample.get('time_s')
        if (type(frame) is not int or not isinstance(time_s,(int,float)) or
                fmap.get('video_frame') != index or fmap.get('native_frame') != frame or
                fmap.get('carla_frame') != frame or trow.get('frame') != frame or
                abs(fmap.get('time_s', -1000)-time_s) > .005 or
                abs(trow.get('time_s', -1000)-time_s) > .005):
            raise ValueError('Original turn body/trace/frame identity join differs')
        participant = sample.get('subject', {})
        vertices = participant.get('body_vertices_m')
        if (not isinstance(vertices,list) or len(vertices) != 4 or
                any(not isinstance(v,list) or len(v) != 2 or
                    any(type(x) not in (int,float) or not isfinite(x) for x in v)
                    for v in vertices)):
            raise ValueError('Original turn body footprint incomplete')
        center = [sum(v[axis] for v in vertices)/4 for axis in (0,1)]
        reported = participant.get('center_xy_m')
        if (not isinstance(reported,list) or len(reported) != 2 or
                hypot(center[0]-reported[0],center[1]-reported[1]) > .05):
            raise ValueError('Original turn center/body geometry differs')
        position = trow.get('position', {})
        if (not isinstance(position,dict) or
                hypot(center[0]-position.get('x',1e9),
                      center[1]-position.get('y',1e9)) > .4):
            raise ValueError('Original turn body/trace position differs')
        frames.append({'frame':frame,'time_s':time_s,
                       'subject_source':'turn_body_original.jsonl',
                       'subject_center_xy':center})
        centers.append(center)
    for name in CAMERAS:
        camera_rows = rows(name + '-frames.jsonl')
        if len(camera_rows) != len(frames):
            raise ValueError('Original turn camera frame count differs: ' + name)
        for index,(camera,frame) in enumerate(zip(camera_rows,frames)):
            if (camera.get('video_frame') != index or
                    camera.get('native_frame') != frame['frame'] or
                    abs(camera.get('time_s', -1000)-frame['time_s']) > .05):
                raise ValueError('Original turn camera frame join differs: ' + name)
    indication = {'kind':kind, 'authorized':True, 'within_intersection':True,
                  'authorization_source':'turn_indication_original.json',
                  'course_xy':source['indicated_course_xy_m']}
    geometry = measure(indication, frames)
    total = 0.0
    samples = []
    for index,(frame,center,deviation) in enumerate(zip(frames,centers,geometry['samples'])):
        if index:
            total += hypot(center[0]-centers[index-1][0],
                           center[1]-centers[index-1][1])
        samples.append({'frame':frame['frame'],'time_s':frame['time_s'],
                        'deviation_m':deviation['distance_to_indicated_course_m'],
                        'path_length_m':total,
                        'inside_intersection':_inside(center,source['intersection_polygon_xy_m'])})
    return {'case_id':receipt['case_id'],'source_sha256':hashes,'samples':samples,
            'placement_offset_m':placement_offset,
            'indication_form':kind,'intersection_id':source['intersection_id'],
            'authority_claim':source['authority_document'],
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def _route_response_from_reports(follow, depart, follow_source, depart_source,
                                 follow_plan, depart_plan):
    """Compare retained follow/depart outcomes without deciding legal obedience."""
    forms = ('marker', 'button', 'other_indication')
    matched = [form for form in forms
               if follow['case_id'].endswith('__' + form + '_follow') and
               depart['case_id'].endswith('__' + form + '_depart')]
    if len(matched) != 1:
        raise ValueError('Turn route comparison case identity differs')
    if follow_source != depart_source:
        raise ValueError('Fixed indication source changed between route responses')
    if (follow_plan.get('route_variant') != 'follow' or
            depart_plan.get('route_variant') != 'depart' or
            follow_plan.get('course_xy_m') != depart_plan.get('course_xy_m') or
            follow_plan.get('target_route_xy_m') == depart_plan.get('target_route_xy_m')):
        raise ValueError('Declared route response difference absent or course changed')
    left, right = follow['samples'], depart['samples']
    if (len(left) < 3 or len(left) != len(right) or
            [(r['frame'],r['time_s']) for r in left] !=
            [(r['frame'],r['time_s']) for r in right]):
        raise ValueError('Fixed frame/time sampling changed')
    follow_deviation = max(r['deviation_m'] for r in left)
    depart_deviation = max(r['deviation_m'] for r in right)
    if not isfinite(follow_deviation) or not isfinite(depart_deviation) or depart_deviation <= follow_deviation:
        raise ValueError('Original route response difference absent')
    return {'comparison_complete':True,'source_joined':True,'frames':len(left),
            'follow_max_course_deviation_m':follow_deviation,
            'depart_max_course_deviation_m':depart_deviation,
            'fixed_source_sha256':hashlib.sha256(follow_source).hexdigest(),
            'legal_obedience_judgment':None,'physical_acceptance_claimed':False}


def audit_saved_turn_route_response(follow_attempt, depart_attempt):
    """Recompute both cases from their retained SHA-bound original acquisition."""
    follow_root, depart_root = Path(follow_attempt), Path(depart_attempt)
    follow = analyze_original_sources(follow_root)
    depart = analyze_original_sources(depart_root)
    follow_source = (follow_root / 'turn_indication_original.json').read_bytes()
    depart_source = (depart_root / 'turn_indication_original.json').read_bytes()
    follow_plan = json.loads((follow_root / 'turn_route_plan.json').read_text())
    depart_plan = json.loads((depart_root / 'turn_route_plan.json').read_text())
    return _route_response_from_reports(follow, depart, follow_source,
                                        depart_source, follow_plan, depart_plan)


audit_saved_marker_route_response = audit_saved_turn_route_response


def finalize_original_sources(attempt):
    root = Path(attempt)
    source = analyze_original_sources(root)
    streams = {name:[] for name in CHANNELS}
    for sample in source['samples']:
        shared = {'frame':sample['frame'],'time_s':sample['time_s']}
        values = {'original_course_deviation_m':sample['deviation_m'],
                  'realized_course_deviation_m':sample['deviation_m'],
                  'realized_indication_placement_offset_m':source['placement_offset_m'],
                  'original_turn_path_length_m':sample['path_length_m'],
                  'intersection_occupancy':sample['inside_intersection'],
                  'turn_course_source_context':{
                      'indication_form':source['indication_form'],
                      'intersection_id':source['intersection_id'],
                      'authority_source':'turn_indication_original.json',
                      'authorization_verified_by_worker':False}}
        for name,value in values.items():
            streams[name].append(dict(shared,value=value))
    for name,entries in streams.items():
        path = root / 'channels' / (name + '.jsonl')
        path.parent.mkdir(exist_ok=True)
        if path.exists():
            raise ValueError('Derived turn source channel already exists: ' + name)
        path.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in entries))
    return {'format':'worker-analysis-report','case_id':source['case_id'],
            'measurements':{name:{'method':'finalize_original_sources',
                                  'value':rows,'sources':source['source_sha256']}
                            for name,rows in streams.items()},
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,
            'limitations':['Source record contains an authority claim, not municipal verification',
                           'Original pixels and physical turn completion require independent review']}


def native_result(attempt, report):
    """Write the pinned Native result schema without inferring a legal verdict."""
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config['case']['recording_description']
    units = {item['name']:item['unit'] for item in description['channels']}
    if set(units) != set(CHANNELS) or report['case_id'] != config['selected_case_id']:
        raise ValueError('Exact turn recording description or case identity differs')
    evidence = []
    realized = {}
    for name in CHANNELS:
        path = root / 'channels' / (name + '.jsonl')
        rows = report['measurements'][name]['value']
        reference='channels/' + path.name
        evidence.append({'name':name,'unit':units[name],'reference':reference,
                         'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        if name == 'realized_course_deviation_m':
            method = 'Original body-center deviation from unchanged indicated marker course over the complete turn; no legal threshold is asserted.'
            statistic, value = 'max', max(row['value'] for row in rows)
        elif name == 'realized_indication_placement_offset_m':
            method = 'Original marker placement shift from the unchanged sourced in-intersection reference; no legal authority threshold is asserted.'
            statistic, value = 'max', max(row['value'] for row in rows)
        else:
            method = 'source-hashed original 20 Hz turn join'
            statistic, value = 'sample count', len(rows)
        realized[name] = {'unit':units[name], 'method':method,
                          'time_window':'all 160 original turn frames' if name.startswith('realized_') else 'all original turn frames',
                          'statistic':statistic,'reference':reference,
                          'value':value,
                          'sample_window_s':[rows[0]['time_s'],rows[-1]['time_s']]}
    deviation = max(row['value'] for row in report['measurements'][
        'original_course_deviation_m']['value'])
    return {'case_id':report['case_id'],
            'measured_values':{'maximum_center_course_deviation_m':deviation,
                               'sampled_path_length_m':report['measurements'][
                                   'original_turn_path_length_m']['value'][-1]['value']},
            'target_checks':[{'target':'sourced indicated intersection turn course',
                              'requested':config['selected_case_id'],
                              'measured':deviation,
                              'method':'original source-joined body center to indicated course',
                              'tolerance':None,'matched':False,
                              'physical_cause_confirmed':False,
                              'cause_evidence':'Physical course realization and pixels pending independent review'}],
            'setup_confirmed':False,'behavior_attempted':False,
            'maneuver_completed':False,
            'termination_reason':'Original turn source geometry measured; physical outcome unverified',
            'physical_failure_flags':{'independent_visibility_pending':True,
                                      'authority_review_pending':True},
            'trace_reference':'trace.jsonl',
            'video_references':[name+'.mkv' for name in CAMERAS],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':description,
            'recording_evidence':evidence,'realized_observables':realized,
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior turn analysis report')
    report = finalize_original_sources(args.attempt)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt,native_result(args.attempt,report))


if __name__ == '__main__':
    main()
