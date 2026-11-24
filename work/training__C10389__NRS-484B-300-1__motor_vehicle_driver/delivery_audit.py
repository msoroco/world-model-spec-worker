"""Independently audit a saved device case without granting synthetic acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')
SOURCES = ('native-raw-actors.jsonl', 'native-map-readback.json', 'video_frames.jsonl',
           'capture/manifest.json', 'capture/evidence.jsonl', 'trace.jsonl',
           *(name + '.mkv' for name in CAMERAS))


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
    if (selection['candidate_id'] != candidate or
            selection['construction_sha256'] != selected['construction_sha256']):
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
    actors = [json.loads(s) for s in (attempt / 'native-raw-actors.jsonl').read_text().splitlines()]
    frames = [json.loads(s) for s in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if (len(actors) != 600 or len(frames) != 600 or
            any(a['frame'] != i or f['video_frame'] != i or
                a['native_frame'] != f['native_frame'] or
                abs(a['time_s'] - f['time_s']) > 1e-8 or
                len(a['ego']['body_native_xyz_m']) != 8
                for i, (a, f) in enumerate(zip(actors, frames)))):
        raise ValueError('Original body and video frame/time join differs')
    result_path = Path(receipt['result'])
    if not result_path.is_file() or sha(result_path) != receipt['result_sha256']:
        raise ValueError('Saved result changed')
    result = read(result_path)
    if result['case_id'] != case or result.get('accepted') or result.get('legal_verdict_claimed'):
        raise ValueError('Saved result identity or acceptance differs')
    source_kind = read(attempt / 'capture/manifest.json').get('source_kind')
    common = {'format': 'c10389-device-delivery-audit-v1', 'case_id': case,
              'candidate_id': candidate, 'source_kind': source_kind,
              'original_source_sha256': hashes}
    if diagnostic:
        return {**common, 'diagnostic_only': True, 'accepted': False,
                'checks': {key: key in ('time_join', 'full_video_decode') for key in CHECKS},
                'original_native_verified': False, 'actual_pixels_verified': False,
                'official_placement_verified': False, 'police_direction_verified': False,
                'nrs_484b_307_applicability_verified': False}
    if (source_kind != 'original_native' or
            selection.get('manifest_sha256') != sha(HERE / 'execution-manifest.json')):
        raise ValueError('Original Native source required')
    review_path = attempt / 'independent-physical-review.json'
    if not review_path.is_file() or read(review_path).get('passed') is not True:
        raise ValueError('Independent physical and pixel review required')
    review = read(review_path)
    required = ('original_device_instruction_verified', 'official_placement_reviewed',
                'nrs_484b_307_applicability_reviewed', 'police_direction_reviewed',
                'full_body_response_verified', 'four_original_camera_pixels_reviewed',
                'all_participants_reviewed')
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
