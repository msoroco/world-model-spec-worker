"""Draft Native result from retained C183370 capture sources only."""
import argparse
import json
import sys
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon

from analyze import analyze, read_jsonl, sha
from pathing import repository_root
from recording_contract import CHANNELS, ASSIGNMENT, description


def _write_result():
    repo = repository_root(__file__)
    runtime = str(repo/'runtime/pipeline/scenario_pipeline')
    if runtime not in sys.path:
        sys.path.insert(0, runtime)
    from worker_exchange.native_output import write_result
    return write_result


def derive_channels(attempt, analysis):
    attempt = Path(attempt)
    actors = read_jsonl(attempt/'native-actors.jsonl')
    frames = read_jsonl(attempt/'video_frames.jsonl')
    readback = json.loads((attempt/'live-readback.json').read_text())
    polygon = Polygon(readback['plan']['repair_polygon_xy_m'])
    source_sha = analysis['source_hashes']['native-actors.jsonl']
    folder = attempt/'channels'
    folder.mkdir(exist_ok=False)
    streams = {name: (folder/(name+'.jsonl')).open('x') for name in CHANNELS}
    try:
        for actor, frame in zip(actors, frames):
            body = actor['ego_body_vertices_xyz_m']
            contact = MultiPoint([(v[0], v[1]) for v in body]).convex_hull.intersects(polygon)
            values = {
                'ego_pose': {'position_xyz_m':actor['ego_position_xyz_m'],
                             'yaw_deg':actor['ego_yaw_deg'],
                             'velocity_xyz_mps':actor['ego_velocity_xyz_mps'],
                             'speed_mps':actor['ego_speed_mps']},
                'ego_body_footprint': {'body_vertices_xyz_m':body,
                                       'road_id':actor['ego_road_id'],
                                       'lane_id':actor['ego_lane_id']},
                'warning_person_state': {'actor_id':actor['warning_person_actor_id'],
                                         'type_id':actor['warning_person_type_id'],
                                         'position_xyz_m':actor['warning_person_xyz_m'],
                                         'warning_act_verified':False},
                'pavement_footprint_contact': {
                    'intersects_surveyed_polygon':contact,
                    'newly_repaired_status_verified':False},
            }
            for name, value in values.items():
                streams[name].write(json.dumps({
                    'frame':frame['carla_frame'], 'time_s':frame['time_s'],
                    'value':value, 'source_actor_sha256':source_sha,
                }, allow_nan=False)+'\n')
    finally:
        for stream in streams.values():
            stream.close()
    context = attempt/'recorded-context.json'
    with context.open('x') as stream:
        json.dump({'surveyed_repair_region': {
            'map_name':readback['plan']['map_name'],
            'road_id':readback['pavement_road_id'],
            'polygon_xy_m':readback['plan']['repair_polygon_xy_m'],
            'source_sha256':analysis['source_hashes']['live-readback.json'],
            'newly_repaired_status_verified':False,
        }},stream,allow_nan=False)
        stream.write('\n')
    return {name:sha(folder/(name+'.jsonl')) for name in CHANNELS}


def build_result(config, analysis):
    case = config['case_suffix']
    if (case not in ('reference','contrast') or
            config['case_id'] != ASSIGNMENT+'__'+case or
            config['law_id'] != 'LVMC-11-22-100' or
            config['recording_description'] != description(analysis['observations']['source_frames'])):
        raise ValueError('Native config differs from C183370 recording contract')
    observations = analysis['observations']
    requested = case == 'reference'
    measured = observations['pavement_footprint_contact_observed']
    matched = observations['requested_footprint_contact_matched']
    sources = {name: analysis['source_hashes'][name] for name in
               ('native-actors.jsonl','video_frames.jsonl','live-readback.json')}
    common = {'status':'unverified', 'method':'independent original-source review pending',
              'sources':sources, 'intervals':[],
              'legal_verdict_claimed':False, 'physical_causation_claimed':False}
    checks = {name:dict(common) for name in ('setup','target','maneuver')}
    checks['target']['status'] = 'met' if matched else 'not_met'
    checks['target']['method'] = 'original eight-vertex body footprint versus surveyed repair polygon'
    return {
        'case_id':config['case_id'],
        'measured_values':observations,
        'target_checks':[{'target':'sampled contact with surveyed repair polygon',
                          'requested':requested, 'measured':measured,
                          'method':'original CARLA body vertices and source-joined surveyed polygon',
                          'tolerance':'polygon intersection; no legal threshold',
                          'matched':matched, 'physical_cause_confirmed':False,
                          'cause_evidence':list(sources)}],
        'setup_confirmed':False, 'behavior_attempted':True,
        'maneuver_completed':False, 'physical_checks':checks,
        'termination_reason':'full original source attempt retained',
        'physical_failure_flags':['warning_act_unreviewed',
                                  'newly_repaired_surface_unverified',
                                  'paving_employee_exception_unreviewed']+
                                 ([] if matched else ['requested_contact_target_not_observed']),
        'trace_reference':'trace.jsonl',
        'video_references':[name+'.mkv' for name in
                            ('overview','approach','reference_corner','driver_reference')],
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':config['recording_description'],
        'recording_evidence':[
            {'name':name,'unit':'structured','reference':'channels/'+name+'.jsonl'}
            for name in CHANNELS]+[
            {'name':'surveyed_repair_region','unit':'structured',
             'reference':'recorded-context.json'}],
        'realized_observables':{
            'surveyed_pavement_contact_frames':{
                'value':len(observations['pavement_footprint_contact_frames']),
                'unit':'count', 'method':'original body versus surveyed polygon',
                'time_window':f"{observations['source_elapsed_s']:g} seconds",
                'statistic':'frame_count',
                'reference':'channels/pavement_footprint_contact.jsonl'}},
        'provenance_kind':'native', 'diagnostic_fixture':False,
        'accepted':False, 'legal_verdict_claimed':False,
    }


def finalize(attempt, output):
    attempt = Path(attempt)
    output = Path(output)
    if (attempt/'result.json').exists() or output.exists():
        raise ValueError('Preserve prior Native finalization; use a fresh attempt')
    marker = json.loads((attempt/'acquisition-provenance.json').read_text())
    if marker.get('provenance_kind') != 'native' or marker.get('diagnostic_fixture') is not False:
        raise ValueError('Original Native provenance required')
    config = json.loads((attempt/'config.json').read_text())
    analysis = analyze(attempt)
    trace = read_jsonl(attempt/'trace.jsonl')
    actors = read_jsonl(attempt/'native-actors.jsonl')
    frames = read_jsonl(attempt/'video_frames.jsonl')
    if len(trace) != len(actors) or any(
            row['frame'] != frame['carla_frame'] or
            row['time_s'] != frame['time_s'] or
            row['position_m'] != actor['ego_position_xyz_m'][:2] or
            row['speed_mps'] != actor['ego_speed_mps'] or
            row.get('speed_provenance') != 'original_carla_velocity'
            for row,actor,frame in zip(trace,actors,frames)):
        raise ValueError('Original trace differs from actor/frame sources')
    channels = derive_channels(attempt, analysis)
    result = build_result(config, analysis)
    _write_result()(attempt,result)
    report = {'format':'c183370-native-finalization-v1',
              'case_id':config['case_id'], 'source_hashes':analysis['source_hashes'],
              'derived_channel_sha256':channels,
              'native_result_sha256':sha(attempt/'result.json'),
              'provenance_kind':'native','diagnostic_fixture':False,
              'analysis_complete':True,
              'physical_acceptance_claimed':False,
              'legal_acceptance_claimed':False,
              'limitations':['Human warning act, newly repaired pavement status and paving-employee exception require independent original review.']}
    output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    finalize(args.attempt,args.output)


if __name__=='__main__':
    main()
