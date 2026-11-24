"""Independent 287(c) exact-case delivery audit with diagnostic source rejection."""
import argparse
import hashlib
import json
from pathlib import Path

from physical_review import audit as physical_review

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def audit(case, candidate, attempt, processing, review, diagnostic):
    manifest = read(ASSIGNMENT / 'crossref-287c-manifest.json')
    entries = [item for item in manifest['cases'] if item['case_id'] == case]
    require(len(entries) == 1, 'Exact 287(c) case required')
    entry = entries[0]
    selected = entry if candidate == 'primary' else next(
        (item for item in entry['candidates'] if item['id'] == candidate), None)
    require(selected is not None, 'Exact 287(c) candidate required')
    attempt = Path(attempt)
    saved = read(processing)
    result = read(attempt / 'result.json')
    analysis = read(attempt / 'analysis-report.json')
    require(saved['passed'] and saved['recorded_only'] and saved['originals_preserved'] and
            saved['case_id'] == case and saved['candidate_id'] == candidate and
            saved['native_revision']['construction_sha256'] == selected['construction_sha256'] and
            saved['timestamp_joins']['passed'] and saved['timestamp_joins']['frames'] == 600 and
            saved['final_video_checks']['frames'] == 600 and
            not saved['physical_acceptance_claimed'] and not saved['legal_acceptance_claimed'] and
            result['case_id'] == case and result['accepted'] is False and
            analysis['case_id'] == case, '287(c) saved source or frame join differs')
    measurement = analysis['measurements']['curb_departure_conditional_margin']['value']
    require(measurement['original_frames'] == 600 and
            measurement['impossibility_to_yield_proven'] is False and
            measurement['legal_verdict_claimed'] is False,
            '287(c) conditional curb measurement differs')
    if diagnostic:
        compatibility = read(attempt / 'compatibility.json')
        require(compatibility['passed'] and compatibility['case_id'] == case and
                compatibility['candidate_id'] == candidate and
                compatibility['construction_sha256'] == selected['construction_sha256'] and
                compatibility['negative_removed'] == 'curb-samples.jsonl' and
                compatibility['negative_log_sha256'] == sha(attempt / 'negative-analysis.log') and
                measurement['source_kind'] == 'synthetic_scene_request',
                '287(c) diagnostic source binding differs')
        physical = None
    else:
        require(review is not None, 'Original Native source required')
        physical = physical_review(attempt, review)
        require(result.get('provenance_kind') == 'native_observation' and
                result.get('maneuver_completed') is True,
                'Original Native 287(c) curb completion required')
    return {'format': 'c230222-287c-source-bound-delivery-audit-v1',
            'case_id': case, 'candidate_id': candidate,
            'construction_sha256': selected['construction_sha256'],
            'processing_sha256': sha(processing),
            'analysis_sha256': sha(attempt / 'analysis-report.json'),
            'physical_review': physical, 'diagnostic_only': diagnostic,
            'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    outcome = audit(args.case, args.candidate, args.attempt,
                    args.processing, args.review, args.diagnostic)
    if args.output.exists():
        raise ValueError('Audit output already exists')
    args.output.write_text(json.dumps(outcome, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': args.case,
                      'candidate_id': args.candidate, 'diagnostic_only': args.diagnostic}))


if __name__ == '__main__':
    main()
