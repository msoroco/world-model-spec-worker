"""Finalize C183370 control-variant sources without physical or legal acceptance."""
import argparse
import json
import sys
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon

from analyze import read_jsonl, sha
from pathing import repository_root
from variant_analyze import analyze
from variant_recording_contract import CHANNELS, config as expected_config

MEASUREMENT_SOURCES = ('native-actors.jsonl', 'video_frames.jsonl',
                       'live-readback.json')


def _write_result():
    repo = repository_root(__file__)
    runtime = str(repo / 'runtime/pipeline/scenario_pipeline')
    if runtime not in sys.path:
        sys.path.insert(0, runtime)
    from worker_exchange.native_output import write_result
    return write_result


def derive_channels(attempt, analysis):
    attempt = Path(attempt)
    actors = read_jsonl(attempt / 'native-actors.jsonl')
    frames = read_jsonl(attempt / 'video_frames.jsonl')
    readback = json.loads((attempt / 'live-readback.json').read_text())
    polygon = Polygon(readback['plan']['repair_polygon_xy_m'])
    source_sha = analysis['source_hashes']['native-actors.jsonl']
    folder = attempt / 'channels'
    folder.mkdir(exist_ok=False)
    streams = {name: (folder / (name + '.jsonl')).open('x') for name in CHANNELS}
    try:
        for actor, frame in zip(actors, frames):
            body = actor['ego_body_vertices_xyz_m']
            contact = MultiPoint([(v[0], v[1]) for v in body]).convex_hull.intersects(polygon)
            values = {
                'ego_pose': {'position_xyz_m': actor['ego_position_xyz_m'],
                             'yaw_deg': actor['ego_yaw_deg'],
                             'velocity_xyz_mps': actor['ego_velocity_xyz_mps'],
                             'speed_mps': actor['ego_speed_mps']},
                'ego_body_footprint': {'body_vertices_xyz_m': body,
                                       'road_id': actor['ego_road_id'],
                                       'lane_id': actor['ego_lane_id']},
                'control_actor_state': {
                    'actor_id': actor['control_actor_id'],
                    'type_id': actor['control_type_id'],
                    'position_xyz_m': actor['control_xyz_m'],
                    'control_content_verified': False},
                'pavement_footprint_contact': {
                    'intersects_surveyed_polygon': contact,
                    'newly_repaired_status_verified': False},
            }
            for name, value in values.items():
                streams[name].write(json.dumps({
                    'frame': frame['carla_frame'], 'time_s': frame['time_s'],
                    'value': value, 'source_actor_sha256': source_sha,
                }, allow_nan=False) + '\n')
    finally:
        for stream in streams.values():
            stream.close()
    context = attempt / 'recorded-context.json'
    with context.open('x') as stream:
        json.dump({'surveyed_repair_region': {
            'map_name': readback['plan']['map_name'],
            'road_id': readback['pavement_road_id'],
            'polygon_xy_m': readback['plan']['repair_polygon_xy_m'],
            'control_kind': readback['plan']['control_kind'],
            'control_actor_id': readback['control_actor_id'],
            'source_sha256': analysis['source_hashes']['live-readback.json'],
            'newly_repaired_status_verified': False}}, stream, allow_nan=False)
        stream.write('\n')
    return {name: sha(folder / (name + '.jsonl')) for name in CHANNELS}


def build_result(config, analysis):
    kind, route = config['control_kind'], config['case_suffix']
    expected = expected_config(kind, route, analysis['observations']['source_frames'])
    if any(config.get(key) != value for key, value in expected.items()):
        raise ValueError('Native variant config differs from recording contract')
    observed = analysis['observations']
    requested = route == 'crossing'
    measured = observed['pavement_footprint_contact_observed']
    matched = observed['requested_footprint_contact_matched']
    sources = {name: analysis['source_hashes'][name] for name in MEASUREMENT_SOURCES}
    diagnostic = analysis.get('source_kind') == 'synthetic_diagnostic_capture'
    source_label = 'synthetic diagnostic' if diagnostic else 'original CARLA'
    common = {'status': 'unverified',
              'method': ('synthetic diagnostic; no physical review' if diagnostic
                         else 'independent original-source review pending'),
              'sources': sources, 'intervals': [],
              'legal_verdict_claimed': False, 'physical_causation_claimed': False}
    checks = {name: dict(common) for name in ('setup', 'target', 'maneuver')}
    checks['target']['status'] = 'met' if matched else 'not_met'
    checks['target']['method'] = source_label + ' eight-vertex body footprint versus surveyed pavement polygon'
    return {'case_id': config['case_id'], 'measured_values': observed,
            'target_checks': [{'target': 'sampled contact with surveyed pavement polygon',
                               'requested': requested, 'measured': measured,
                               'method': source_label + ' body vertices and source-joined surveyed polygon',
                               'tolerance': 'polygon intersection; no legal threshold',
                               'matched': matched, 'physical_cause_confirmed': False,
                               'cause_evidence': list(sources)}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False, 'physical_checks': checks,
            'termination_reason': ('synthetic diagnostic fixture processed' if diagnostic
                                   else 'full original source attempt retained'),
            'physical_failure_flags': ['control_content_unreviewed',
                                       'newly_repaired_surface_unverified',
                                       'paving_employee_exception_unreviewed'] +
                                      ([] if matched else ['requested_contact_target_not_observed']),
            'trace_reference': 'trace.jsonl',
            'video_references': [name + '.mkv' for name in
                                 ('overview', 'approach', 'reference_corner', 'driver_reference')],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': config['recording_description'],
            'recording_evidence': [
                {'name': name, 'unit': 'structured', 'reference': 'channels/' + name + '.jsonl'}
                for name in CHANNELS] + [
                {'name': 'surveyed_repair_region', 'unit': 'structured',
                 'reference': 'recorded-context.json'}],
            'realized_observables': {'surveyed_pavement_contact_frames': {
                'value': len(observed['pavement_footprint_contact_frames']),
                'unit': 'count', 'method': source_label + ' body versus surveyed polygon',
                'time_window': f"{observed['source_elapsed_s']:g} seconds",
                'statistic': 'frame_count',
                'reference': 'channels/pavement_footprint_contact.jsonl'}},
            'provenance_kind': 'synthetic_fixture' if diagnostic else 'native',
            'diagnostic_fixture': diagnostic,
            'accepted': False, 'legal_verdict_claimed': False}


def measurement_records(analysis):
    observed = analysis['observations']
    sources = {name: analysis['source_hashes'][name] for name in MEASUREMENT_SOURCES}
    return {'surveyed_pavement_contact': {
        'method': 'measure_variant_surveyed_pavement_contact',
        'value': {'requested_contact': analysis['case'] == 'crossing',
                  'measured_contact': observed['pavement_footprint_contact_observed'],
                  'contact_frames': observed['pavement_footprint_contact_frames'],
                  'requested_contact_matched': observed['requested_footprint_contact_matched'],
                  'newly_repaired_status_verified': False,
                  'control_content_verified': False,
                  'legal_verdict_claimed': False},
        'sources': sources},
        'control_actor_vicinity': {
            'method': 'measure_control_actor_vicinity',
            'value': {'control_kind': analysis['control_kind'],
                      'actor_near_surveyed_pavement_frames': observed['control_actor_near_pavement_frames'],
                      'control_content_verified': False,
                      'paving_employee_exception_verified': False,
                      'legal_verdict_claimed': False},
            'sources': sources}}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if (attempt / 'result.json').exists() or output.exists():
        raise ValueError('Preserve prior variant finalization; use a fresh attempt')
    for name in MEASUREMENT_SOURCES:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    marker = json.loads((attempt / 'acquisition-provenance.json').read_text())
    diagnostic = (marker.get('provenance_kind') == 'synthetic_fixture' and
                  marker.get('diagnostic_fixture') is True)
    if not diagnostic and (marker.get('provenance_kind') != 'native' or
                           marker.get('diagnostic_fixture') is not False):
        raise ValueError('Original Native provenance required')
    config = json.loads((attempt / 'config.json').read_text())
    analysis = analyze(attempt)
    channels = derive_channels(attempt, analysis)
    result = build_result(config, analysis)
    _write_result()(attempt, result)
    report = {'format': ('c183370-variant-diagnostic-finalization-v1' if diagnostic
                         else 'c183370-variant-native-finalization-v1'),
              'case_id': config['case_id'], 'source_hashes': analysis['source_hashes'],
              'derived_channel_sha256': channels,
              'native_result_sha256': sha(attempt / 'result.json'),
              'measurements': measurement_records(analysis),
              'provenance_kind': 'synthetic_fixture' if diagnostic else 'native',
              'diagnostic_fixture': diagnostic, 'analysis_complete': True,
              'physical_acceptance_claimed': False,
              'legal_acceptance_claimed': False,
              'limitations': (['Synthetic fixture only; no original CARLA capture or physical completion claim.']
                              if diagnostic else
                              ['Control content, newly repaired pavement status and paving-employee exception require independent original review.'])}
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)


if __name__ == '__main__':
    main()
