"""Independently audit exact crossing sources and saved diagnostic outcomes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native' / 'crossing'))
from original_saved import measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def audit(case, candidate, attempt, processing, diagnostic):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((item for item in manifest['cases'] if item['case_id'] == case), None)
    if entry is None:
        raise ValueError('Exact selected case required')
    selected = entry if candidate == 'primary' else next(
        (item for item in entry['candidates'] if item['id'] == candidate), None)
    if selected is None:
        raise ValueError('Exact selected candidate required')
    saved = read(processing)
    if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('case_id') != case or saved.get('candidate_id') != candidate or
            saved.get('native_revision', {}).get('construction_sha256') != selected['construction_sha256'] or
            saved.get('timestamp_joins', {}).get('frames') != 600 or
            saved.get('final_video_checks', {}).get('frames') != 600):
        raise ValueError('Saved exact case or candidate source receipt differs')
    stage = Path(saved['analysis_directory']).resolve()
    observed = measure(stage)
    result = read(stage / 'result.json')
    analysis = read(stage / 'analysis-report.json')
    if (observed['case_id'] != case or observed['legal_verdict'] is not None or
            result.get('legal_verdict_claimed') is not False or
            analysis['measurements']['nrs_484b_290_exception']['value']['applicability'] != 'undetermined'):
        raise ValueError('Crossing or NRS 484B.290 source disposition differs')
    measured = analysis['measurements']['between_intersections_crossing']['value']['roadway_entry']
    if measured != observed['entry']:
        raise ValueError('Selected measurement differs from original pedestrian and device source')
    attempt = Path(attempt).resolve()
    if diagnostic:
        receipt = read(attempt / 'compatibility.json')
        if (receipt.get('passed') is not True or receipt.get('case_id') != case or
                receipt.get('candidate_id') != candidate or
                receipt.get('construction_sha256') != selected['construction_sha256'] or
                result.get('provenance_kind') != 'synthetic_fixture'):
            raise ValueError('Diagnostic public compatibility identity differs')
    else:
        provenance = read(stage / 'acquisition-provenance.json')
        survey = read(stage / 'native-survey.json')
        exception = read(stage / 'exception-applicability-source.json')
        if (provenance.get('provenance_kind') != 'native' or
                survey.get('review_status') != 'independently_reviewed' or
                exception.get('review_status') != 'independently_reviewed' or
                result.get('maneuver_completed') is not True):
            raise ValueError('Original Native source and independent exception review incomplete')
    return {'format': 'c109166-287-1c-source-audit-v1', 'case_id': case,
            'candidate_id': candidate, 'construction_sha256': selected['construction_sha256'],
            'saved_processing_sha256': sha(processing), 'original_source_sha256': observed['source_sha256'],
            'diagnostic_only': diagnostic, 'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.case, args.candidate, args.attempt, args.processing, args.diagnostic)
    if args.output.exists():
        raise ValueError('Retain prior delivery audit result')
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': args.case, 'diagnostic_only': args.diagnostic}))


if __name__ == '__main__':
    main()
