"""Independent saved-source delivery audit for selected bus and Walk cases."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = HERE / 'native'
sys.path.insert(0, str(NATIVE))
from finalize import CAMERAS, joined_sources, source, video_frames
from physical_walk_audit import audit_original as audit_physical

CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')
REQUIRED = ('native_samples.jsonl', 'video_frames.jsonl', 'road_geometry.json',
            'capture/manifest.json', 'capture/evidence.jsonl', 'trace.jsonl',
            'body_history.jsonl', *(name + '.mkv' for name in CAMERAS))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def audit(case_id, candidate_id, attempt, processing_path, *, diagnostic=False):
    manifest = read(HERE / 'execution-manifest.json')
    require(manifest.get('assignment_id') == HERE.name, 'Wrong delivery assignment')
    entry = next((row for row in manifest['cases'] if row['case_id'] == case_id), None)
    require(entry is not None and entry.get('kind') == 'delivery',
            'Unselected Walk delivery case')
    suffix = case_id.removeprefix(HERE.name + '__')
    require(suffix in ('reference', 'contrast'), 'Wrong selected Walk case')
    candidate = entry if candidate_id == 'primary' else next(
        (row for row in entry['candidates'] if row['id'] == candidate_id), None)
    require(candidate is not None and sha(HERE / candidate['construction']) ==
            candidate['construction_sha256'], 'Selected construction changed')
    attempt = Path(attempt).resolve()
    processing_path = Path(processing_path).resolve()
    require(attempt.is_dir() and processing_path.is_file(),
            'Saved delivery attempt or processing receipt missing')
    selection = read(source(attempt, 'candidate-selection.json'))
    require(selection.get('candidate_id') == candidate_id and
            selection.get('construction_sha256') == candidate['construction_sha256'],
            'Selected candidate source binding differs')
    processing = read(processing_path)
    require(processing.get('passed') is True and processing.get('recorded_only') is True and
            processing.get('originals_preserved') is True and
            processing.get('timestamp_joins', {}).get('passed') is True and
            processing.get('case_id') == case_id and
            processing.get('candidate_id') == candidate_id and
            processing.get('physical_acceptance_claimed') is False and
            processing.get('legal_acceptance_claimed') is False,
            'Saved processing chain incomplete')
    hashes = {}
    for name in REQUIRED:
        path = source(attempt, name)
        hashes[name] = sha(path)
        require(processing.get('original_source_hashes', {}).get(name) == hashes[name],
                'Saved original source changed: ' + name)
    samples, mapping, geometry, synthetic, joins = joined_sources(attempt, 480)
    counts = {name: video_frames(source(attempt, name + '.mkv')) for name in CAMERAS}
    require(set(counts.values()) == {480}, 'Original source camera frame count differs')
    result_path = Path(processing.get('result', '')).resolve()
    require(result_path.is_file() and processing_path.parent in result_path.parents,
            'Saved Native result path differs from processing output')
    result = read(result_path)
    require(processing.get('result_sha256') == sha(result_path) and
            result.get('case_id') == case_id and result.get('accepted') is False and
            result.get('legal_verdict_claimed') is False,
            'Sealed Native result differs or claims acceptance')
    if diagnostic:
        require(synthetic and result.get('provenance_kind') == 'synthetic_local_diagnostic' and
                result.get('maneuver_completed') is False,
                'Synthetic diagnostic source attempted physical promotion')
        return {'format': 'worker-delivery-audit', 'case_id': case_id,
                'candidate_id': candidate_id, 'passed': False,
                'source_shaped_unit_test': True,
                'checks': {name: False for name in CHECKS},
                'source_sha256': hashes, 'source_frame_counts': counts,
                'source_joins': joins, 'original_physical_acceptance_claimed': False,
                'legal_verdict_claimed': False}
    require(not synthetic and result.get('provenance_kind') == 'native',
            'Original Native Walk source required')
    require(selection.get('manifest_sha256') == sha(HERE / 'execution-manifest.json'),
            'Original attempt selects an outdated delivery manifest')
    review_path = source(attempt, 'official-walk-review.json')
    require(processing.get('original_source_hashes', {}).get('official-walk-review.json') ==
            sha(review_path), 'Independent Walk review source changed')
    physical = audit_physical(attempt, suffix, review_path)
    require(physical['physical_checks']['maneuver']['status'] == 'met' and
            result.get('maneuver_completed') is True and
            result.get('setup_confirmed') is True and
            result.get('behavior_attempted') is True,
            'Original Walk physical completion unverified')
    return {'format': 'worker-delivery-audit', 'case_id': case_id,
            'candidate_id': candidate_id, 'passed': True,
            'checks': {name: True for name in CHECKS},
            'source_sha256': {**hashes, 'official-walk-review.json': sha(review_path)},
            'source_frame_counts': counts, 'source_joins': joins,
            'result_sha256': sha(result_path), 'processing_sha256': sha(processing_path),
            'physical_audit': physical, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    require(not args.output.exists(), 'Retain prior delivery audit output')
    result = audit(args.case, args.candidate, args.attempt,
                   args.processing, diagnostic=args.diagnostic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'passed': result['passed'],
                      'diagnostic': args.diagnostic}))


if __name__ == '__main__':
    main()
