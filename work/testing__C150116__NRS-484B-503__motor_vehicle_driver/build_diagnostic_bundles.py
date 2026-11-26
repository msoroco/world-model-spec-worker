"""Build synthetic-only passenger zone construction protocol bundles."""
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from passenger_zone import CASES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
CAMERAS = ['overview', 'approach', 'reference_corner', 'driver_reference']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('returned file exceeds 2 MiB')


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    witness = plan['selected_branches'][0]
    plan['requirement_dispositions'] = [{
        'requirement': witness['requirement'], 'source': witness['source'],
        'status': 'selected_required',
        'case_ids': [row['case_id'] for row in plan['cases']],
        'evidence_or_gap': 'Synthetic CPU protocol only; original marked passenger zone, civil-time regulation and Native capture absent.',
        'reason': 'All selected conduct, passenger activity, timing and hours cases need original measurements; expeditious has no numeric legal cutoff.'}]
    write(HERE / 'case-plan.json', plan)
    note = HERE / 'diagnostic-source-note.json'
    write(note, {'format': 'c150116-synthetic-source-v1',
                 'source_kind': 'synthetic_diagnostic_fixture',
                 'accepted_original_source': False,
                 'case_ids': [row['case_id'] for row in plan['cases']]})
    description = {'channels': [
        {'name': 'zone_marking', 'unit': 'source context', 'method': 'original marked curb, designation and polygon', 'sampling_rate_hz': 20, 'time_window': 'all 900 frames', 'reference_frame': 'original map and frame', 'uncertainty': 'synthetic zone is not original designation'},
        {'name': 'regulation_hours', 'unit': 'civil time', 'method': 'original applicable jurisdiction regulation and synchronized civil clock', 'sampling_rate_hz': 20, 'time_window': 'all 900 frames', 'reference_frame': 'original civil clock', 'uncertainty': 'synthetic time is not legal effective-hours proof'},
        {'name': 'vehicle_halt_in_zone', 'unit': 'frames and m/s', 'method': 'original ego pose and speed joined to marked zone polygon', 'sampling_rate_hz': 20, 'time_window': 'all 900 frames', 'reference_frame': 'original map and frame', 'uncertainty': 'no realized halt from synthetic fixture'},
        {'name': 'passenger_activity', 'unit': 'events', 'method': 'original passenger boarding or alighting event source', 'sampling_rate_hz': 20, 'time_window': 'all 900 frames', 'reference_frame': 'original frame', 'uncertainty': 'requested action is not observed activity'},
        {'name': 'zone_boundary_signed_distance_m', 'unit': 'm', 'method': 'first original halted ego center signed distance to surveyed marked-zone polygon', 'sampling_rate_hz': 20, 'time_window': 'first original halt', 'reference_frame': 'original surveyed zone boundary', 'uncertainty': 'source-backed physical pose required'},
        {'name': 'civil_boundary_offset_min', 'unit': 'min', 'method': 'source-sealed civil clock minus applicable regulation boundary', 'sampling_rate_hz': 20, 'time_window': 'first original halt', 'reference_frame': 'original civil timezone and regulation', 'uncertainty': 'effective-hours judgment requires original authority'},
        {'name': 'passenger_event_delay_s', 'unit': 's', 'method': 'first source-backed passenger event minus first original halted frame', 'sampling_rate_hz': 20, 'time_window': 'first original halt through first passenger event', 'reference_frame': 'original Native frame clock', 'uncertainty': 'expeditiousness remains legal judgment'},
        {'name': 'camera_frame_identity', 'unit': 'frame ID', 'method': 'four synchronized original camera streams', 'sampling_rate_hz': 20, 'time_window': 'all 900 frames', 'reference_frame': 'original frame', 'uncertainty': 'synthetic pixels are not original evidence'}],
                   'context_inputs': [], 'limitations': ['Original zone/regulation sources absent.', 'Expeditious loading or unloading remains an unresolved judgment.']}
    entries = []
    for case in CASES:
        cid = AID + '__' + case.name
        if cid not in {row['case_id'] for row in plan['cases']}:
            raise ValueError('frozen exact case plan changed')
        source_sha = sha(note)
        clock_boundary = datetime.fromisoformat('2026-11-25T10:00:00-08:00')
        civil_time = (clock_boundary + timedelta(minutes=case.civil_clock_offset_min)
                      if case.civil_clock_offset_min is not None else
                      datetime.fromisoformat('2026-11-25T10:00:00-08:00' if case.hours == 'effective' else '2026-11-25T03:00:00-08:00'))
        effective = case.hours == 'effective' or (case.hours == 'source_readback' and case.civil_clock_offset_min >= 0)
        zone_pose = [2, 2 - case.zone_boundary_offset_m, 0] if case.zone_boundary_offset_m is not None else [2, 0, 0]
        site = {'case_id': cid, 'source_kind': 'synthetic_diagnostic_fixture',
                'accepted_original_source': False, 'cell_id': 'C150116', 'layout': 'one_way_road',
                'road': {'source_sha256': source_sha, 'one_way_readback': True,
                         'approach_waypoints': [[-15, 0, 0], [-5, 0, 0], [1, 0, 0]]},
                'zone': {'marking_source_sha256': source_sha, 'boundary_source_sha256': source_sha,
                         'designation': 'passenger_curb_loading', 'curb_adjacency_source_sha256': source_sha,
                         'polygon_xy': [[-1, -2], [5, -2], [5, 2], [-1, 2]],
                         'parking_pose': zone_pose, 'parking_pose_source_sha256': source_sha,
                         'boundary_offset_source_sha256': source_sha if case.zone_boundary_offset_m is not None else None,
                         'feasible_boundary_offsets_m': [-0.5, 0.5] if case.zone_boundary_offset_m is not None else None,
                         'passenger_anchor': [2, 1, 0]},
                'clock': {'civil_time_iso': civil_time.isoformat(),
                          'timezone': 'America/Los_Angeles', 'source_sha256': source_sha,
                          'effective_boundary_civil_iso': clock_boundary.isoformat() if case.civil_clock_offset_min is not None else None,
                          'effective_boundary_source_sha256': source_sha if case.civil_clock_offset_min is not None else None},
                'regulations': {'source_sha256': source_sha, 'jurisdiction': 'synthetic-only Nevada protocol',
                                'effective_hours_source_sha256': source_sha,
                                'effective_at_civil_time': effective},
                'passenger_event_source_sha256': source_sha if case.name.startswith('expeditious-') else None,
                'vehicle_blueprint': 'synthetic_ego_car', 'vehicle_blueprint_source_sha256': source_sha,
                'passenger_blueprint': 'synthetic_passenger', 'passenger_blueprint_source_sha256': source_sha}
        config = {'law_id': 'NRS-484B-503', 'cell_id': 'C150116', 'actor': 'motor_vehicle_driver',
                  'selected_case_id': cid, 'rate_hz': 20, 'duration_s': 45,
                  'required_atoms': [], 'source_packets': [], 'cameras': CAMERAS,
                  'case': {'case_id': cid, 'name': case.name, 'conduct': case.conduct,
                           'passenger_action': case.passenger_action,
                           'release_delay_s': case.release_delay_s, 'hours': case.hours,
                           'zone_boundary_offset_m': case.zone_boundary_offset_m,
                           'civil_clock_offset_min': case.civil_clock_offset_min,
                           'recording_description': description}}
        files = {'runner.py': (HERE / 'source_deferred_runner.py').read_text(),
                 'original_runner.py': (HERE / 'original_runner.py').read_text(),
                 'passenger_zone.py': (HERE / 'passenger_zone.py').read_text(),
                 'tests/test_bundle.py': (HERE / 'diagnostic_bundle_test.py').read_text(),
                 'config.json': json.dumps(config, indent=2) + '\n',
                 'scene.json': json.dumps(site, indent=2) + '\n'}
        construction = {'law_id': 'NRS-484B-503', 'cell_id': 'C150116',
                        'actor': 'motor_vehicle_driver', 'case_id': cid,
                        'entrypoint': 'runner.py', 'diagnostic_only': True,
                        'recording_description': description,
                        'files': [{'path': path, 'content': content} for path, content in files.items()]}
        target = HERE / ('construction-diagnostic-' + case.name + '.json')
        write(target, construction)
        entries.append({'case_id': cid, 'kind': 'capability_research',
                        'construction': target.name, 'construction_sha256': sha(target),
                        'diagnostic_only': True})
    write(HERE / 'execution-manifest.diagnostic.json',
          {'format': 'worker-execution-manifest', 'assignment_id': AID,
           'status': 'synthetic_only_original_zone_and_regulation_sources_pending',
           'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
           'cases': entries})
    return len(entries)


if __name__ == '__main__':
    print('synthetic passenger-zone bundles:', build())
