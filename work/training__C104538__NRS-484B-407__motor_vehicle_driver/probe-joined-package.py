"""Join case saved sources to the retained Core graph for a synthetic v1 probe."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.runtime_cli import execution_env
import subprocess
import xml.etree.ElementTree as ET
from traffic_spec_adapter.geometry import reference


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def put_rows(path, values):
    path.write_text(''.join(json.dumps(value, sort_keys=True) + '\n' for value in values))


def align_case_path(fixture):
    """Rigidly place the saved local synthetic path on the authored road at s=200 m."""
    road = ET.parse(fixture / 'road.xodr').getroot()
    geometry = road.find('./road/planView/geometry')
    map_x, map_y, heading, curvature = reference(geometry, 200.0)
    if curvature == 0:
        raise ValueError('Authored sightline road lost its curve')
    cosine, sine = math.cos(heading), math.sin(heading)

    def position(value):
        x, y, z = value
        return [map_x + cosine*x + sine*y, -map_y - sine*x + cosine*y, z]

    def velocity(value):
        x, y, z = value
        return [cosine*x + sine*y, -sine*x + cosine*y, z]

    def transform_history(path):
        data = rows(path)
        for row in data:
            row['ego_body_vertices_m'] = [position(p) for p in row['ego_body_vertices_m']]
            row['ego_center_xyz_m'] = position(row['ego_center_xyz_m'])
            row['ego_heading_deg'] -= math.degrees(heading)
        put_rows(path, data)

    transform_history(fixture / 'native_body_history.jsonl')
    traces = rows(fixture / 'trace.jsonl')
    evidences = rows(fixture / 'capture/evidence.jsonl')
    viewpoints = rows(fixture / 'driver_eye_rays.jsonl')
    for trace, evidence, view in zip(traces, evidences, viewpoints):
        trace['position_m'] = position(trace['position_m'])
        trace['velocity_mps'] = velocity(trace['velocity_mps'])
        trace['heading_deg'] -= math.degrees(heading)
        trace['c104538_native']['ego_body_vertices_m'] = [
            position(p) for p in trace['c104538_native']['ego_body_vertices_m']]
        evidence['ego']['position_m'] = position(evidence['ego']['position_m'])
        evidence['ego']['body_vertices_m'] = [position(p) for p in evidence['ego']['body_vertices_m']]
        evidence['ego']['heading_deg'] -= math.degrees(heading)
        for name in ('reference_left', 'reference_right'):
            item = view['views'][name]
            item['driver_viewpoint_xyz_m'] = position(item['driver_viewpoint_xyz_m'])
            trace['approaching_driver_views'][name] = item
    put_rows(fixture / 'trace.jsonl', traces)
    put_rows(fixture / 'capture/evidence.jsonl', evidences)
    put_rows(fixture / 'driver_eye_rays.jsonl', viewpoints)
    context_path = fixture / 'native-construction-context.json'
    context = json.loads(context_path.read_text())
    for barrier in context['barrier_inventory']:
        barrier['requested']['native_xyz_m'] = position(barrier['requested']['native_xyz_m'])
        barrier['world_vertices_m'] = [position(p) for p in barrier['world_vertices_m']]
    context['synthetic_coordinate_alignment'] = {
        'kind': 'rigid_local_to_authored_road', 'road_station_m': 200.0,
        'road_reference_xy_m': [map_x, map_y], 'road_heading_rad': heading,
        'physical_native_observation': False}
    write(context_path, context)


def synthesize_environment(fixture):
    """Build an explicitly synthetic, hash-bound environmental processing fixture."""
    calibration_dir = fixture / 'environment-calibration'
    calibration_dir.mkdir()
    samples = []
    for distance in (50, 100, 200):
        rgb = calibration_dir / f'rgb-{distance:04d}.ppm'
        instance = calibration_dir / f'instance-{distance:04d}.pgm'
        pixels = bytes(90 if 2 <= x < 6 and 2 <= y < 6 else 180
                       for y in range(8) for x in range(8))
        mask = bytes(255 if 2 <= x < 6 and 2 <= y < 6 else 0
                     for y in range(8) for x in range(8))
        rgb.write_bytes(b'P6\n8 8\n255\n' + b''.join(bytes((p, p, p)) for p in pixels))
        instance.write_bytes(b'P5\n8 8\n255\n' + mask)
        samples.append({'distance_m': distance, 'target_pixels': 16,
            'target_median_luminance': 90, 'background_median_luminance': 180,
            'weber_contrast': 0.5, 'contrast_detected': True,
            'rgb': {'path': str(rgb.relative_to(fixture)), 'sha256': sha(rgb)},
            'instance': {'path': str(instance.relative_to(fixture)), 'sha256': sha(instance)}})
    traces = rows(fixture / 'trace.jsonl')
    weather = traces[0]['environment_measurements']['weather']
    calibration = {'schema': 'rendered-target-contrast-range-v1', 'passed': True,
        'method': '8x8 synthetic CPU PPM grayscale target and PGM mask; exact Weber contrast, software processing only',
        'visibility_m': 200, 'distance_kind': 'sampled_lower_bound',
        'upper_bracket_m': None, 'weather': weather, 'samples': samples,
        'uncertainty': 'Synthetic palette and sampled distances do not measure physical visibility',
        'source_kind': 'synthetic_cpu_fixture', 'original_native_pixels': False}
    calibration_path = fixture / 'environment_calibration.json'
    write(calibration_path, calibration)
    declaration = fixture / 'surface-declaration.json'
    write(declaration, {'kind': 'synthetic_authored_surface_assumption',
        'description': 'No ice or snow layer is authored in this CPU fixture',
        'ice_or_snow': False, 'physical_surface_observed': False})
    surface = {'schema': 'authored-native-road-surface-v1', 'ice_or_snow': False,
        'map_sha256': sha(fixture / 'road.xodr'),
        'authorship': 'Explicit synthetic CPU surface assumption; physical road surface unverified',
        'source_assets': [{'path': str(declaration), 'sha256': sha(declaration)}],
        'source_kind': 'synthetic_cpu_fixture'}
    surface_path = fixture / 'surface_provenance.json'
    write(surface_path, surface)
    write(fixture / 'asset_relocations.json', {
        'surface_provenance_sha256': sha(surface_path),
        'paths': {str(declaration): declaration.name}})
    for trace in traces:
        measured = {'frame': trace['frame'], 'time_s': trace['time_s'],
            'weather': weather, 'visibility_m': 200, 'ice_or_snow': False,
            'calibration_sha256': sha(calibration_path),
            'surface_sha256': sha(surface_path)}
        trace['environment_measurements'] = measured
        trace['speed_comparison_native']['environment_measurements'] = measured
    put_rows(fixture / 'trace.jsonl', traces)


def build(fixture, suffix='below_500_ft'):
    if suffix not in ('below_500_ft', 'at_500_ft', 'above_500_ft'):
        raise ValueError('Unknown C104538 case')
    saved = REPO / '.runtime-work/c104538/full-saved-v3' / suffix / 'positive'
    core = REPO / '.runtime-work/c104538/core-diagnostic-v2/below_500_ft/positive'
    if not (saved / 'analysis-report.json').is_file() or not (core / 'converted/adapter_report.json').is_file():
        raise ValueError('Build saved and Core probes first')
    shutil.copytree(core, fixture, ignore=shutil.ignore_patterns(
        'converted', 'traffic_spec', 'event_review*', 'review*', 'cleanup-progress-v3.jsonl',
        'source-*', 'final-decode.json', 'synthetic-480.mkv'))
    for name in ('config.json', 'case.json', 'result.json', 'analysis-report.json'):
        (fixture / name).unlink(missing_ok=True)
    for name in ('environment_calibration.json', 'surface_provenance.json',
                 'asset_relocations.json'):
        (fixture / name).unlink(missing_ok=True)
    for name in ('environment-calibration', 'asset-snapshots'):
        shutil.rmtree(fixture / name, ignore_errors=True)
    core_trace = rows(fixture / 'trace.jsonl')
    saved_trace = rows(saved / 'trace.jsonl')
    core_evidence = rows(fixture / 'capture/evidence.jsonl')
    saved_evidence = rows(saved / 'capture/evidence.jsonl')
    saved_history = rows(saved / 'native_body_history.jsonl')
    if not all(len(group) == 480 for group in (core_trace, saved_trace, core_evidence, saved_evidence)):
        raise ValueError('Source duration differs')
    for i in range(480):
        assert core_trace[i]['frame'] == saved_trace[i]['frame']
        assert core_evidence[i]['original_frame'] == saved_evidence[i]['original_frame']
        core_trace[i].update(saved_trace[i])
        core_evidence[i]['ego'].update(saved_evidence[i]['ego'])
        velocity = saved_trace[i]['velocity_mps']
        speed = math.hypot(velocity[0], velocity[1])
        core_trace[i]['speed_mps'] = speed
        core_trace[i]['speed_mph'] = speed / .44704
        core_trace[i]['heading_deg'] = saved_history[i]['ego_heading_deg']
        core_evidence[i]['ego']['position_m'] = saved_trace[i]['position_m']
        core_evidence[i]['ego']['speed_mps'] = speed
        core_evidence[i]['ego']['heading_deg'] = saved_history[i]['ego_heading_deg']
    put_rows(fixture / 'trace.jsonl', core_trace)
    put_rows(fixture / 'capture/evidence.jsonl', core_evidence)
    for name in ('native_road_readback.xodr', 'driver_eye_rays.jsonl',
                 'native_body_history.jsonl', 'native-construction-context.json',
                 'video_frames.jsonl', 'overview.mkv', 'reference_left.mkv',
                 'reference_right.mkv', 'ego.mkv'):
        shutil.copyfile(saved / name, fixture / name)
    authored_dir = HERE / 'draft-sightline' / suffix
    authored_road = authored_dir / 'road.xodr'
    shutil.copyfile(authored_road, fixture / 'road.xodr')
    shutil.copyfile(authored_road, fixture / 'native_road_readback.xodr')
    shutil.copyfile(authored_dir / 'obstruction.json', fixture / 'authored-obstruction-source.json')
    context_path = fixture / 'native-construction-context.json'
    context = json.loads(context_path.read_text())
    context['native_road_sha256'] = sha(fixture / 'native_road_readback.xodr')
    context['authored_road_sha256'] = sha(fixture / 'road.xodr')
    context['synthetic_road_substitution'] = True
    context['authored_obstruction_sha256'] = sha(fixture / 'authored-obstruction-source.json')
    write(context_path, context)
    shutil.copytree(saved / 'channels', fixture / 'channels', dirs_exist_ok=True)
    align_case_path(fixture)
    synthesize_environment(fixture)
    manifest = json.loads((fixture / 'capture/manifest.json').read_text())
    manifest['case_id'] = HERE.name + '__' + suffix
    manifest['source_run'] = 'synthetic:road-aligned-case-saved-sources-plus-retained-core-graph'
    manifest['synthetic_fixture'] = True
    manifest['sources']['trace.jsonl'] = sha(fixture / 'trace.jsonl')
    manifest['sources']['road.xodr'] = sha(fixture / 'road.xodr')
    manifest['sources']['authored-obstruction-source.json'] = sha(fixture / 'authored-obstruction-source.json')
    write(fixture / 'capture/manifest.json', manifest)


def main():
    scratch = REPO / '.runtime-work/c104538/joined-package-v5'
    if scratch.exists():
        raise ValueError('Retain previous joined package probe')
    scratch.mkdir(parents=True)
    fixture = scratch / 'fixture'
    build(fixture)
    case = HERE.name + '__below_500_ft'
    manifest = HERE / 'draft-execution-manifest.json'
    library = REPO / 'runtime/pipeline/library'
    validator = REPO / '.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck'
    receipt = run(manifest, case, fixture, scratch / 'output', library, validator, 'primary')
    negative = scratch / 'negative'
    materialize_case(manifest, case, negative, fixture, 'primary')
    (negative / 'native_body_history.jsonl').unlink()
    env = execution_env()
    env['PATH'] = str(REPO / '.runtime-work/linux_arm64') + os.pathsep + env.get('PATH', '')
    env['LD_LIBRARY_PATH'] = str(REPO / '.runtime-work/geos-wheel/shapely.libs')
    failed = subprocess.run([sys.executable, str(negative / 'finalize.py'), '--attempt',
        str(negative), '--output', str(negative / 'analysis-report.json')],
        cwd=negative, env=env, text=True, capture_output=True, timeout=300)
    (scratch / 'negative-analysis.log').write_text(failed.stdout + failed.stderr)
    if failed.returncode == 0 or 'native_body_history.jsonl' not in failed.stderr:
        raise ValueError('Case-source negative did not reject')
    output = {'format': 'c104538-joined-synthetic-package-v1', 'case_id': case,
        'candidate_id': 'primary', 'positive': receipt, 'negative_exit_code': failed.returncode,
        'negative_removed': 'native_body_history.jsonl',
        'negative_log_sha256': sha(scratch / 'negative-analysis.log'),
        'source_kind': 'synthetic_cpu_fixture', 'core_graph_kind': 'retained_speed_graph',
        'case_saved_sources_joined': True, 'selected': False, 'accepted': False,
        'original_native_observed': False, 'original_pixel_observed': False}
    write(HERE / 'joined-package-probe-summary.json', output)
    print(json.dumps({'passed': receipt['passed'], 'negative_rejected': True,
                      'case': case, 'core_graph_kind': output['core_graph_kind']}))


if __name__ == '__main__':
    main()
