"""Independent source audit for the selected fire-lane delivery cases."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')
SOURCES = ('native-actors.jsonl', 'video_frames.jsonl', 'native-survey-readback.json',
           'road.xodr', 'capture/manifest.json', 'capture/evidence.jsonl',
           'trace.jsonl', *(name + '.mkv' for name in CAMERAS))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(case, candidate, attempt, processing, diagnostic):
    manifest_path = HERE / 'execution-manifest.json'
    manifest = read(manifest_path)
    entry = next((row for row in manifest['cases'] if row['case_id'] == case), None)
    require(entry is not None and entry.get('kind') == 'delivery',
            'Unselected delivery case')
    selected = entry if candidate == 'primary' else next(
        (row for row in entry['candidates'] if row['id'] == candidate), None)
    require(selected is not None and
            sha(HERE / selected['construction']) == selected['construction_sha256'],
            'Selected construction changed')
    selection = read(attempt / 'candidate-selection.json')
    source_manifest_sha = selection.get('manifest_sha256')
    current_manifest_sha = sha(manifest_path)
    if source_manifest_sha != current_manifest_sha:
        proof_path = HERE / 'current-refresh-v2' / (case.rsplit('__', 1)[-1] +
                                                    '-' + candidate + '-proof.json')
        require(proof_path.is_file() and
                read(proof_path).get('selected_manifest_sha256_at_run') == source_manifest_sha,
                'Candidate source manifest has no retained current-runtime proof')
    require(selection.get('case_id') == case and
            selection.get('candidate_id') == candidate and
            selection.get('construction_sha256') == selected['construction_sha256'],
            'Candidate selection differs')
    receipt = read(processing)
    require(receipt.get('passed') is True and
            receipt.get('recorded_only') is True and
            receipt.get('originals_preserved') is True and
            receipt.get('missing_evidence') is False and
            receipt.get('case_id') == case and
            receipt.get('candidate_id') == candidate and
            receipt.get('timestamp_joins', {}).get('frames') == 600 and
            receipt.get('timestamp_joins', {}).get('passed') is True and
            receipt.get('final_video_checks', {}).get('passed') is True and
            receipt.get('physical_acceptance_claimed') is False and
            receipt.get('legal_acceptance_claimed') is False,
            'Saved source proof incomplete')
    hashes = {}
    for name in SOURCES:
        path = attempt / name
        require(path.is_file(), 'Missing original source: ' + name)
        hashes[name] = sha(path)
        require(receipt['original_source_hashes'].get(name) == hashes[name],
                'Saved original source changed: ' + name)
    actors = [json.loads(line) for line in (attempt / 'native-actors.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    require(len(actors) == len(frames) == 600 and
            all(actor.get('frame') == frame.get('carla_frame') and
                frame.get('video_frame') == index and
                abs(frame.get('time_s', -1) - index / 20) < 1e-6
                for index, (actor, frame) in enumerate(zip(actors, frames))),
            'Original source frame join differs')
    result_path = Path(receipt['result'])
    require(result_path.is_file() and sha(result_path) == receipt['result_sha256'],
            'Saved result changed')
    result = read(result_path)
    require(result.get('case_id') == case and result.get('accepted') is False and
            result.get('physical_acceptance_claimed') is False and
            result.get('legal_verdict_claimed') is False,
            'Saved result identity or acceptance differs')
    provenance = read(attempt / 'acquisition-provenance.json')
    synthetic = provenance.get('provenance_kind') == 'synthetic_fixture'
    require(synthetic == (result.get('provenance_kind') == 'synthetic_fixture') and
            result.get('diagnostic_fixture') is synthetic,
            'Source provenance differs')
    if diagnostic:
        require(synthetic, 'Diagnostic fixture provenance required')
        return {'format': 'c201084-delivery-audit', 'case_id': case,
                'candidate_id': candidate, 'diagnostic_only': True,
                'accepted': False,
                'checks': {key: key in ('all_participants', 'time_join',
                                        'full_video_decode') for key in CHECKS},
                'original_source_sha256': hashes,
                'saved_result_sha256': sha(result_path),
                'original_native_verified': False,
                'actual_pixels_verified': False,
                'physical_completion_verified': False}
    require(not synthetic and provenance.get('provenance_kind') == 'original_native',
            'Original Native source required')
    review_path = attempt / 'independent-physical-review.json'
    require(review_path.is_file() and read(review_path).get('passed') is True,
            'Independent physical and pixel review required')
    return {'format': 'c201084-delivery-audit', 'case_id': case,
            'candidate_id': candidate, 'accepted': True,
            'checks': {key: True for key in CHECKS},
            'original_source_sha256': hashes,
            'saved_result_sha256': sha(result_path)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('case', 'candidate', 'attempt', 'processing', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    value = audit(args.case, args.candidate, Path(args.attempt),
                  Path(args.processing), args.diagnostic)
    target = Path(args.output)
    require(not target.exists(), 'Retain previous audit output')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': args.case, 'diagnostic_only': args.diagnostic,
                      'accepted': value['accepted']}, sort_keys=True))
