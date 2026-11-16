"""Independent C111331 saved-source handoff audit; diagnostic mode is CPU only."""
import argparse
import hashlib
import json
from pathlib import Path


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(case, candidate, attempt, processing, diagnostic=False):
    attempt, processing = Path(attempt), Path(processing)
    report_path = attempt / 'analysis-report.json'
    report = json.loads(report_path.read_text())
    saved = json.loads(processing.read_text())
    require(report['case_id'] == case and saved['case_id'] == case,
            'Exact saved case identity differs')
    require(saved['candidate_id'] == candidate and
            report['measurement_detail']['candidate_id'] == candidate,
            'Exact selected candidate differs')
    require(report['selected'] and not report['draft_only'],
            'Selected finalizer report required')
    require(saved['passed'] and saved['recorded_only'] and saved['originals_preserved'],
            'Passing saved-only processing and preserved originals required')
    require(saved['original_source_hashes']['analysis-report.json'] == sha(report_path),
            'Saved analysis report hash differs')
    for name in ('native_samples.jsonl', 'video_frames.jsonl', 'reference_corner.mkv'):
        source = attempt / name
        require(source.is_file(), 'Missing required source: ' + name)
        require(report['measurements']['observed_signal_phase_at_entry']['sources'][name] == sha(source),
                'Measured source hash differs: ' + name)
    for name in ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'):
        source = attempt / name
        require(source.is_file() and source.stat().st_size > 0, 'Missing source camera: ' + name)
        require(saved['original_source_hashes'][name] == sha(source),
                'Saved source camera hash differs: ' + name)
    require(saved['final_video_checks']['passed'] and saved['final_video_checks']['frames'] == 480,
            'Full 480-frame composed video decode required')
    require(not report['physical_acceptance_claimed'] and not report['legal_verdict_claimed'],
            'Worker cannot claim physical or legal acceptance')
    measurement = report['measurement_detail']
    if not diagnostic:
        require(measurement['physical_native_evidence'] and
                measurement['source_kind'] == 'original_native_observation' and
                measurement['original_pixel_visibility_verified'],
                'Original Native signal/body and pixel evidence required')
    return {'format': 'c111331-independent-delivery-audit-v1',
            'case_id': case, 'candidate_id': candidate, 'passed': True,
            'diagnostic_only': diagnostic, 'checks': ['native_source', 'all_participants',
                'time_join', 'full_video_decode', 'actual_pixels', 'physical_completion'],
            'report_sha256': sha(report_path), 'processing_sha256': sha(processing),
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--processing', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.case, args.candidate, args.attempt, args.processing, args.diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
