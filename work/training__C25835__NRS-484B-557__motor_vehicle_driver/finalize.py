"""Source-bound rail-stop finalization; no legal or physical acceptance verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from rail_stop_measure import measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('dev.stop_sign', 'dev.governs', 'st.railway_crossing',
            'rel.centre_distance', 'drv.stopped', 'drv.approaching',
            'drv.time_to_conflict', 'ru.rail_vehicle')
SOURCES = ('road.xodr', 'rail-inventory.json', 'rail-trace.jsonl',
           'video_frames.jsonl', 'designation-authority.txt',
           'sign-authority.txt', 'designation-review.json',
           'sign-review.json', 'occluder-review.json', 'overview.mkv',
           'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def facts(root):
    root = Path(root)
    paths = {name: required(root, name) for name in SOURCES}
    inventory = json.loads(paths['rail-inventory.json'].read_text())
    designation = json.loads(paths['designation-review.json'].read_text())
    sign = json.loads(paths['sign-review.json'].read_text())
    occluder = json.loads(paths['occluder-review.json'].read_text())
    diagnostic = (root / 'fixture-provenance.json').is_file()
    expected = 'synthetic_diagnostic' if diagnostic else 'independently_reviewed'
    if any(review.get('review_status') != expected for review in (designation, sign, occluder)):
        raise ValueError('Independent designation, sign and occluder reviews required')
    if len({review.get('reviewer') for review in (designation, sign, occluder)}) < 2:
        raise ValueError('Independent review identities or sources missing')
    if inventory.get('source_kind') != 'native_saved_sample' or inventory.get('cell_id') != 'C25835':
        raise ValueError('Original Native rail inventory missing')
    if len(inventory.get('rail_actor_ids', [])) != 2 or not inventory.get('vehicle_actor_id'):
        raise ValueError('Original rail or vehicle actor identity missing')
    if designation.get('source_sha256') != sha(paths['designation-authority.txt']):
        raise ValueError('Dangerous-crossing designation source differs')
    if sign.get('source_sha256') != sha(paths['sign-authority.txt']):
        raise ValueError('Official stop-sign source differs')
    for review in (designation, sign, occluder):
        if review.get('inventory_sha256') != sha(paths['rail-inventory.json']):
            raise ValueError('Original rail inventory review binding differs')
    if designation.get('road_sha256') != sha(paths['road.xodr']):
        raise ValueError('Crossing road source differs')
    if sign.get('overview_sha256') not in (sha(paths['overview.mkv']),
                                           'synthetic_rgb_source' if diagnostic else ''):
        raise ValueError('Sign review pixel source differs')
    if designation.get('crossing_kind') != 'highway_rail_at_grade':
        raise ValueError('Highway railroad grade-crossing source missing')
    if designation.get('designation_authority') not in (
            'department_of_transportation', 'local_with_department_approval'):
        raise ValueError('Dangerous-crossing designation authority missing')
    if sign.get('official_stop_sign') is not True or sign.get('sign_governs') != 'rail_crossing_approach':
        raise ValueError('Official stop sign governance missing')
    if occluder.get('occluder_geometry_observed') is not True:
        raise ValueError('Original occluder geometry missing')
    rows = [json.loads(line) for line in paths['rail-trace.jsonl'].read_text().splitlines() if line]
    if not rows or any(row.get('vehicle_actor_id') != inventory['vehicle_actor_id'] for row in rows):
        raise ValueError('Original vehicle/rail trace identity differs')
    lengths = [row.get('vehicle_extent', {}).get('length_m') for row in rows]
    if any(type(x) not in (int, float) or x <= 0 for x in lengths) or max(lengths) - min(lengths) > .2:
        raise ValueError('Original vehicle extent incomplete or unstable')
    frame_map = [json.loads(line) for line in paths['video_frames.jsonl'].read_text().splitlines() if line]
    if len(frame_map) != 600 or any(frame_map[i].get('native_frame') != rows[i].get('native_frame')
                                   or frame_map[i].get('video_frame') != i for i in range(600)):
        raise ValueError('Original Native and video frame map differs')
    context = {'source_kind': 'native_grade_crossing_readback',
        'map_sha256': sha(paths['road.xodr']),
        'rail_geometry_sha256': sha(paths['rail-inventory.json']),
        'vehicle_extent_sha256': sha(paths['rail-trace.jsonl']),
        'official_sign_source_sha256': sha(paths['sign-authority.txt']),
        'designation_source_sha256': sha(paths['designation-authority.txt']),
        'occluder_geometry_sha256': sha(paths['occluder-review.json']),
        'crossing_kind': designation['crossing_kind'],
        'sign_governs': sign['sign_governs'],
        'designation_authority': designation['designation_authority'],
        'nearest_track_approach_edge_x_m': inventory['rail_track_x_m'][0],
        'vehicle_length_m': lengths[0]}
    measurement = measure(context, rows)
    measurement['source_sha256'] = {name: sha(path) for name, path in paths.items()}
    measurement['designation_review_status'] = designation['review_status']
    measurement['sign_review_status'] = sign['review_status']
    measurement['occluder_review_status'] = occluder['review_status']
    return measurement


def stop_position(root):
    fact = facts(root)
    return {'distances_ft': fact['stop_reference_distances_from_nearest_track_ft'],
            'first_stop_frame': fact['first_stop_frame']}


def crossing_designation(root):
    fact = facts(root)
    return {'source_sha256': fact['designation_source_sha256'],
            'review_status': fact['designation_review_status']}


def official_stop_sign(root):
    fact = facts(root)
    return {'source_sha256': fact['sign_governance_source_sha256'],
            'review_status': fact['sign_review_status']}


def approach_proceeding(root):
    fact = facts(root)
    return {'approach_observed': fact['approach_observed'],
            'subsequent_proceeding_observed': fact['subsequent_proceeding_observed']}


def due_care_context(root):
    fact = facts(root)
    return {'visibility': fact['visibility_on_proceeding'],
            'train_states': fact['train_states_on_proceeding'],
            'judgment': 'requires_independent_review'}


def report(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text())
    fact = facts(root)
    outputs = {key: globals()[key](root) for key in
               ('stop_position', 'crossing_designation', 'official_stop_sign',
                'approach_proceeding', 'due_care_context')}
    return {'format': 'worker-analysis-report-v1', 'case_id': config['case_id'],
            'measurements': {key: {'method': key, 'value': value,
                                  'sources': fact['source_sha256']}
                             for key, value in outputs.items()},
            'scope': 'Original Native crossing, stop and proceeding; independent authority and due-care review pending'}


def finalize(root, output):
    from worker_exchange.native_output import physical_result, provenance_record, write_result
    root, output = Path(root), Path(output)
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Use a fresh finalization stage')
    config = json.loads(required(root, 'config.json').read_text())
    report_data = report(root)
    fact = facts(root)
    if {row['name'] for row in config['recording_description']['channels']} != set(CHANNELS):
        raise ValueError('Declared rail-stop channels differ')
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    for name in CHANNELS:
        value = {'measured_stop': fact['stop_reference_distances_from_nearest_track_ft'],
                 'source_sha256': fact['source_sha256'], 'legal_outcome': 'unassessed'}
        (channels / (name + '.jsonl')).write_text(''.join(
            json.dumps({'time_s': i / 20, 'value': value}) + '\n' for i in range(600)))
    observed = fact['stop_reference_distances_from_nearest_track_ft']['center_ft']
    requested = config['requested_stop_center_ft']
    evidence = [{'name': name, 'unit': 'source', 'reference': name} for name in SOURCES]
    evidence += [{'name': row['name'], 'unit': row['unit'], 'reference': row['source']}
                 for row in config['recording_description']['channels']]
    result = {'case_id': config['case_id'], 'measured_values': fact,
        'target_checks': [{'target': 'vehicle-centre stop distance from source-identified nearest track',
             'requested': requested, 'measured': observed,
             'method': 'Original trace, rail readback and vehicle extent join',
             'tolerance': 1.0, 'matched': abs(observed - requested) <= 1.0,
             'physical_cause_confirmed': False, 'cause_evidence': list(SOURCES)}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Original physical, administrative and due-care review pending',
        'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': evidence, 'realized_observables': {},
        **provenance_record(root), 'accepted': False,
        'legal_verdict_claimed': False}
    physical_result(root, result)
    output.write_text(json.dumps(report_data, indent=2, allow_nan=False) + '\n')
    write_result(root, result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
