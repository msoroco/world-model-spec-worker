"""Audit original 8c right-turn sources before any future acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')
SOURCES = ('native_samples.jsonl', 'other_traffic_history.jsonl', 'video_frames.jsonl',
           'road_geometry.json', 'capture/manifest.json', 'capture/evidence.jsonl',
           'trace.jsonl', 'body_history.jsonl', *(name + '.mkv' for name in CAMERAS))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit(case, candidate, attempt, processing, diagnostic):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((item for item in manifest['cases'] if item['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unselected delivery case')
    selected = entry if candidate == 'primary' else next(
        (item for item in entry['candidates'] if item['id'] == candidate), None)
    if selected is None or sha(HERE / selected['construction']) != selected['construction_sha256']:
        raise ValueError('Selected construction changed')
    selection = read(attempt / 'candidate-selection.json')
    if selection['candidate_id'] != candidate or selection['construction_sha256'] != selected['construction_sha256']:
        raise ValueError('Candidate selection differs')
    receipt = read(processing)
    if (receipt.get('passed') is not True or receipt.get('recorded_only') is not True
            or receipt.get('originals_preserved') is not True
            or receipt.get('timestamp_joins', {}).get('frames') != 600
            or receipt.get('final_video_checks', {}).get('passed') is not True
            or receipt.get('missing_evidence') or receipt.get('case_id') != case
            or receipt.get('candidate_id') != candidate
            or receipt.get('physical_acceptance_claimed') or receipt.get('legal_acceptance_claimed')):
        raise ValueError('Saved source proof incomplete')
    hashes = {}
    for name in SOURCES:
        path = attempt / name
        if not path.is_file():
            raise ValueError('Missing original source: ' + name)
        hashes[name] = sha(path)
        if receipt['original_source_hashes'].get(name) != hashes[name]:
            raise ValueError('Saved original source changed: ' + name)
    rows = [json.loads(line) for line in (attempt / 'native_samples.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    bodies = [json.loads(line) for line in (attempt / 'body_history.jsonl').read_text().splitlines()]
    other = [json.loads(line) for line in (attempt / 'other_traffic_history.jsonl').read_text().splitlines()]
    if len(rows) != 600 or any(len(group) != 600 for group in (frames, bodies, other)):
        raise ValueError('Original source frame count differs')
    for index, (row, frame, body, traffic) in enumerate(zip(rows, frames, bodies, other)):
        if (row['native_frame'] != frame['carla_frame'] or row['native_frame'] != body['frame']
                or traffic['native_frame'] != row['native_frame']
                or any(abs(row['time_s'] - item['time_s']) > 1e-8 for item in (frame, body, traffic))
                or len(body['body_vertices_m']) != 2 * len(row['native_body_xy_m'])
                or len(body['body_vertices_m']) != 8
                or {(vertex[0], vertex[1]) for vertex in body['body_vertices_m']}
                   != {tuple(vertex) for vertex in row['native_body_xy_m']}):
            raise ValueError('Original source frame/body join differs')
    geometry = read(attempt / 'road_geometry.json')
    lanes = geometry['lanes']
    if (lanes['approach_right']['forward_xy'] != [0, 1]
            or lanes['destination_right']['forward_xy'] != [1, 0]
            or lanes['destination_left']['forward_xy'] != [-1, 0]):
        raise ValueError('Authored extreme-right/two-way geometry differs')
    if any(str(row['signal_state_observed']).casefold() not in ('red', 'trafficlightstate.red', 'steady_red')
           for row in rows):
        raise ValueError('Held-red signal source differs')
    result_path = Path(receipt['result'])
    if not result_path.is_file() or sha(result_path) != receipt['result_sha256']:
        raise ValueError('Saved result changed')
    result = read(result_path)
    if result['case_id'] != case or result.get('accepted') or result.get('legal_verdict_claimed'):
        raise ValueError('Saved result identity/acceptance differs')
    measured = result['measured_values']['right_turn_permission']
    expected_halt = case.endswith('probe_a')
    if (measured['pre_turn_full_halt'] is not expected_halt
            or measured['pre_crossing_stationary_frames'] != (30 if expected_halt else 0)
            or measured['steady_red_frames'] != 600
            or measured['pedestrian_clearance_s'] != 4.55
            or measured['other_traffic_clearance_s'] != 4.8
            or measured['two_way_destination'] is not True
            or measured['destination_exit_observed'] is not True):
        raise ValueError('Controlled source-bound right-turn measurements differ')
    source_kind = read(attempt / 'capture/manifest.json').get('source_kind')
    common = {'format': 'c110919-8c-delivery-audit', 'case_id': case,
              'candidate_id': candidate, 'source_kind': source_kind,
              'original_source_sha256': hashes,
              'pre_turn_full_halt': measured['pre_turn_full_halt']}
    if diagnostic:
        return {**common, 'diagnostic_only': True, 'accepted': False,
                'checks': {key: key in ('all_participants', 'time_join', 'full_video_decode')
                           for key in CHECKS},
                'original_native_verified': False, 'actual_pixels_verified': False}
    if source_kind != 'original_native' or selection.get('manifest_sha256') != sha(HERE / 'execution-manifest.json'):
        raise ValueError('Original Native source required')
    review_path = attempt / 'independent-physical-review.json'
    if not review_path.is_file() or read(review_path).get('passed') is not True:
        raise ValueError('Independent physical and pixel review required')
    review = read(review_path)
    required = ('governing_red_pixels_verified', 'full_body_stop_and_turn_verified',
                'extreme_right_and_destination_lane_verified',
                'pedestrian_and_directed_traffic_yield_verified')
    if any(review.get(key) is not True for key in required):
        raise ValueError('Independent statutory source review incomplete')
    return {**common, 'accepted': True, 'checks': {key: True for key in CHECKS}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('case', 'candidate', 'attempt', 'processing', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    value = audit(args.case, args.candidate, Path(args.attempt), Path(args.processing), args.diagnostic)
    target = Path(args.output)
    if target.exists():
        raise ValueError('Retain previous audit output')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case_id': args.case, 'diagnostic_only': args.diagnostic,
                      'accepted': value['accepted']}))
