"""Audit original motorcycle sources before any future delivery acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')
SOURCES = ('native_samples.jsonl', 'video_frames.jsonl', 'road_geometry.json',
           'capture/manifest.json', 'capture/evidence.jsonl', 'trace.jsonl',
           'body_history.jsonl', *(name + '.mkv' for name in CAMERAS))


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
    if len(rows) != len(frames) or len(rows) != 600 or any(
            row['native_frame'] != frame['carla_frame'] or abs(row['time_s'] - frame['time_s']) > 1e-8
            for row, frame in zip(rows, frames)):
        raise ValueError('Original source frame join differs')
    if len(bodies) != 600 or any(
            row['native_frame'] != body['frame'] or abs(row['time_s'] - body['time_s']) > 1e-8
            or len(body['body_vertices_m']) != 8
            for row, body in zip(rows, bodies)):
        raise ValueError('Motorcycle body history source join differs')
    if any(row['motorcycle_blueprint'] != 'vehicle.kawasaki.ninja' for row in rows):
        raise ValueError('Motorcycle identity differs')
    if any(str(row['signal_state_observed']).casefold() != 'red' for row in rows):
        raise ValueError('Held red signal source differs')
    if any(row['turn_prohibition_present'] for row in rows):
        raise ValueError('Authored turn prohibition context differs')
    turn = next((index for index, row in enumerate(rows) if row['ego_turn_entered']), None)
    if turn is None or rows[turn]['complete_cross_signal_cycles'] != (2 if case.endswith('condition_a') else 1):
        raise ValueError('Condition cycle contrast differs')
    result_path = Path(receipt['result'])
    if not result_path.is_file() or sha(result_path) != receipt['result_sha256']:
        raise ValueError('Saved result changed')
    result = read(result_path)
    if result['case_id'] != case or result.get('accepted') or result.get('legal_verdict_claimed'):
        raise ValueError('Saved result identity or acceptance differs')
    source_kind = read(attempt / 'capture/manifest.json').get('source_kind')
    common = {'format': 'c110919-delivery-audit', 'case_id': case,
              'candidate_id': candidate, 'source_kind': source_kind,
              'original_source_sha256': hashes,
              'cycle_count_at_turn': rows[turn]['complete_cross_signal_cycles']}
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
    required = ('signal_and_cycle_pixels_verified', 'motorcycle_full_body_verified',
                'detector_nonresponse_cause_verified', 'no_prohibiting_device_verified',
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
