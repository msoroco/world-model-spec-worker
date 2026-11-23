"""Audit source preservation for all manifest-bound CPU chains."""
import hashlib
import json
import subprocess
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
VIDEOS = ('raw.mkv', 'overview.mkv', 'approach.mkv',
          'reference_corner.mkv', 'driver_reference.mkv')
PARTS = ('vehicle', 'load', 'trailer')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(row) for row in path.read_text().splitlines()]


def audit(case, candidate='primary', corrupt_final_join=False):
    group = case['case_id'].rsplit('__', 1)[-1]
    prefix = 'rebound-chain-' + group + '-' + candidate + '-'
    attempt = ROOT / '.runtime-work' / ('c229398-rebound-chain-' + group + '-' + candidate + '-compatibility')
    selected_manifest = PACKAGE / 'execution-manifest.json'
    selected = case if candidate == 'primary' else next(
        (item for item in case['candidates'] if item['id'] == candidate), None)
    if selected is None:
        raise ValueError('Unknown selected candidate: ' + group + '/' + candidate)
    proof = read(PACKAGE / (prefix + 'proof.json'))
    receipt_path = PACKAGE / (prefix + 'saved.log')
    receipt = read(receipt_path)
    selection = read(attempt / 'candidate-selection.json')
    if (proof['case_id'] != case['case_id'] or proof['candidate'] != candidate
            or proof['cpu_chain_passed'] is not True
            or proof['selected_manifest_sha256'] != sha(selected_manifest)
            or proof['receipts'][prefix + 'saved.log'] != sha(receipt_path)
            or selection['case_id'] != case['case_id']
            or selection['candidate_id'] != candidate
            or selection['construction_sha256'] != selected['construction_sha256']
            or selection['manifest_sha256'] != sha(selected_manifest)
            or sha(PACKAGE / selected['construction']) != selected['construction_sha256']):
        raise ValueError('Selected chain identity differs: ' + group)
    if (receipt.get('case_id') != case['case_id']
            or receipt.get('candidate_id') != candidate
            or receipt.get('passed') is not True
            or receipt.get('recorded_only') is not True
            or receipt.get('originals_preserved') is not True
            or receipt.get('missing_evidence') is not False
            or receipt.get('timestamp_joins') != {'frames': 600, 'passed': True,
                                                  'missing_original_trace_or_map': False}
            or receipt.get('physical_acceptance_claimed') is not False
            or receipt.get('legal_acceptance_claimed') is not False):
        raise ValueError('Selected saved receipt incomplete: ' + group)
    hashes = receipt['original_source_hashes']
    if not set(VIDEOS).issubset(hashes):
        raise ValueError('Selected video source absent: ' + group)
    for name, expected in hashes.items():
        source = attempt / name
        if not source.is_file() or sha(source) != expected:
            raise ValueError('Original source changed: ' + group + '/' + name)
    trace = lines(attempt / 'trace.jsonl')
    actors = lines(attempt / 'native-raw-actors.jsonl')
    frames = lines(attempt / 'video_frames.jsonl')
    if corrupt_final_join:
        frames[-1] = dict(frames[-1], native_frame=frames[-1]['native_frame'] + 1)
    if not (len(trace) == len(actors) == len(frames) == 600):
        raise ValueError('Source row count differs: ' + group)
    for index, (pose, actor, frame) in enumerate(zip(trace, actors, frames)):
        if (pose['frame'] != actor['native_frame']
                or pose['frame'] != frame['native_frame']
                or actor['frame'] != frame['video_frame']
                or abs(pose['time_s'] - frame['time_s']) > 1e-6
                or abs(pose['time_s'] - actor['time_s']) > 1e-6):
            raise ValueError('Source join differs: ' + group + '/' + str(index))
        if set(actor['actors']) != set(PARTS):
            raise ValueError('Source participant differs: ' + group + '/' + str(index))
        for part in PARTS:
            footprint = actor['actors'][part]
            if (len(footprint['center_xy_m']) != 2
                    or len(footprint['half_extent_xy_m']) != 2
                    or not all(value > 0 for value in footprint['half_extent_xy_m'])):
                raise ValueError('Source footprint differs: ' + group + '/' + str(index))
    result_path = Path(receipt['result'])
    if not result_path.is_file() or sha(result_path) != receipt['result_sha256']:
        raise ValueError('Saved result changed: ' + group)
    result = read(result_path)
    if (result['case_id'] != case['case_id'] or result.get('accepted') is not False
            or result.get('legal_verdict_claimed') is not False):
        raise ValueError('Saved acceptance claim differs: ' + group)
    capture = read(attempt / 'capture/manifest.json')
    if (capture['case_id'] != case['case_id'] or capture['frames'] != 600
            or capture.get('synthetic_diagnostic') is not True
            or not all(row.get('synthetic_diagnostic') is True for row in trace)):
        raise ValueError('Capture identity or provenance differs: ' + group)
    for video in VIDEOS:
        decode = subprocess.run(('ffmpeg', '-v', 'error', '-i', str(attempt / video),
                                 '-map', '0:v:0', '-f', 'null', '-'),
                                capture_output=True, text=True)
        if decode.returncode or decode.stderr.strip():
            raise ValueError('Full video decode failed: ' + group + '/' + video)
    return {'case_id': case['case_id'], 'candidate_id': candidate,
            'selected_manifest_sha256': sha(selected_manifest),
            'selected_chain_proof_sha256': sha(PACKAGE / (prefix + 'proof.json')),
            'saved_receipt_sha256': sha(receipt_path),
            'original_source_count': len(hashes), 'frames_joined': 600,
            'videos_fully_decoded': list(VIDEOS),
            'source_kind': 'synthetic_native_sample', 'diagnostic_only': True,
            'accepted': False, 'original_native_verified': False,
            'actual_pixels_verified': False, 'physical_completion_verified': False}


def main():
    manifest = read(PACKAGE / 'execution-manifest.json')
    records = []
    for case in manifest['cases']:
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            records.append(audit(case, candidate))
            try:
                audit(case, candidate, corrupt_final_join=True)
            except ValueError as error:
                if not str(error).startswith('Source join differs: '):
                    raise
            else:
                raise ValueError('Corrupted final frame join was accepted')
    output = {'format': 'c229398-rebound-delivery-audit',
              'selected_manifest_sha256': sha(PACKAGE / 'execution-manifest.json'),
              'selected_candidates': records, 'positive_count': len(records),
              'corrupt_final_frame_rejections': len(records),
              'diagnostic_only': True, 'delivery_ready': False}
    (PACKAGE / 'rebound-delivery-audit.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'positive_count': len(records),
                      'corrupt_final_frame_rejections': len(records)}))


if __name__ == '__main__':
    main()
