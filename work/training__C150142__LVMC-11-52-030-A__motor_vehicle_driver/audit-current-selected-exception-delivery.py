"""Recheck current-manifest selected long saved sources without legal claims."""
import hashlib
import json
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
sys.path.insert(0, str(WORK / 'native'))
from delivery_audit import (lines, read, validate_exception_measurement,
                            validate_rows)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def audit():
    manifest = read(WORK / 'execution-manifest.json')
    manifest_sha = sha(WORK / 'execution-manifest.json')
    selected = {entry['case_id']: entry for entry in manifest['cases']}
    plan = read(WORK / 'case-plan.json')
    rows = []
    for path in sorted(WORK.glob('current-*-primary-selected-saved-proof.json')):
        proof = read(path)
        case_id = proof['case_id']
        entry = selected[case_id]
        slug = case_id.rsplit('__', 1)[-1]
        require(proof['selected_manifest_sha256'] == manifest_sha and
                proof['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256'] and
                proof['candidate_id'] == 'primary' and proof['recorded_only'] is True and
                proof['source_preserved'] is True and
                proof['official_public_compatibility_claimed'] is False,
                'Current selected saved proof differs: ' + slug)
        case_scratch = REPO / '.runtime-work/owner150142/long-selected-v1' / slug
        matches = [candidate.parent for candidate in case_scratch.glob('saved*/v0001/processing.json')
                   if sha(candidate) == proof['processing_sha256']]
        require(len(matches) == 1, 'Missing exact current selected saved source: ' + slug)
        result = matches[0]
        processing_path = result / 'processing.json'
        require(processing_path.is_file() and sha(processing_path) == proof['processing_sha256'] and
                sha(result / 'analysis/analysis-report.json') == proof['analysis_report_sha256'] and
                sha(result / 'analysis/result.json') == proof['result_sha256'] and
                sha(result / 'final-decode.json') == proof['final_decode_sha256'],
                'Current selected processing source differs: ' + slug)
        for index in range(4):
            require(sha(result / ('source-%d.json' % index)) ==
                    proof['source_decode_sha256']['source-%d' % index],
                    'Current selected original source decode differs: ' + slug)
        analysis = result / 'analysis'
        selection = read(analysis / 'candidate-selection.json')
        require(selection['case_id'] == case_id and selection['candidate_id'] == 'primary' and
                selection['manifest_sha256'] == manifest_sha and
                selection['construction_sha256'] == entry['construction_sha256'],
                'Selected Native source differs: ' + slug)
        checked = validate_exception_measurement(
            analysis, plan, case_id, 'synthetic_native_sample')
        require(checked['frames'] == proof['final_video']['frames'], 'Measured frame count differs: ' + slug)
        joined = validate_rows(lines(analysis / 'native-raw-actors.jsonl'),
                               lines(analysis / 'video_frames.jsonl'),
                               lines(analysis / 'trace.jsonl'),
                               read(analysis / 'native-map-readback.json'),
                               case_id, checked['frames'],
                               'synthetic_native_sample', True)
        require(joined['red_curb_stop_or_park_observed'] is True,
                'Missing source-observed red curb relation: ' + slug)
        rows.append({'case_id': case_id, 'frames': checked['frames'],
                     'processing_sha256': proof['processing_sha256'],
                     'proof_sha256': sha(path)})
    require(len(rows) == 16, 'Expected all 16 selected long primary cases')
    negatives = []
    short_index = read(WORK / 'current-short-selected-saved-index.json')
    require(short_index['manifest_sha256'] == manifest_sha and short_index['passed'] is True,
            'Current selected short saved index differs')
    for saved in short_index['rows']:
        slug = saved['case']
        if slug in ('reference', 'contrast', 'ordinary_red_signed'):
            continue
        case_id = WORK.name + '__' + slug
        entry = selected[case_id]
        analysis = Path(saved['scratch_result']) / 'v0001/analysis'
        require(REPO / '.runtime-work' in analysis.parents and analysis.is_dir(),
                'Short saved analysis path differs: ' + slug)
        selection = read(analysis / 'candidate-selection.json')
        require(selection['case_id'] == case_id and selection['candidate_id'] == 'primary' and
                selection['manifest_sha256'] == manifest_sha and
                selection['construction_sha256'] == entry['construction_sha256'],
                'Short selected Native source differs: ' + slug)
        checked = validate_exception_measurement(
            analysis, plan, case_id, 'synthetic_native_sample')
        joined = validate_rows(lines(analysis / 'native-raw-actors.jsonl'),
                               lines(analysis / 'video_frames.jsonl'),
                               lines(analysis / 'trace.jsonl'),
                               read(analysis / 'native-map-readback.json'),
                               case_id, checked['frames'],
                               'synthetic_native_sample', True)
        require(joined['red_curb_stop_or_park_observed'] is True,
                'Missing short source-observed red curb relation: ' + slug)
        if slug == 'mail_adjacent_deposit':
            try:
                validate_exception_measurement(analysis, plan, case_id)
            except ValueError as error:
                require('provenance or declared context differs' in str(error),
                        'Wrong synthetic-provenance rejection')
                negatives.append('synthetic_as_original')
            else:
                raise ValueError('Synthetic source passed as original')
            try:
                validate_rows(lines(analysis / 'native-raw-actors.jsonl')[:-1],
                              lines(analysis / 'video_frames.jsonl'),
                              lines(analysis / 'trace.jsonl'),
                              read(analysis / 'native-map-readback.json'),
                              case_id, checked['frames'],
                              'synthetic_native_sample', True)
            except ValueError:
                negatives.append('missing_native_actor_frame')
            else:
                raise ValueError('Incomplete Native actor source passed')
        processing_path = analysis.parent / 'processing.json'
        require(sha(processing_path) == saved['processing']['processing']['sha256'],
                'Current selected short processing differs: ' + slug)
        rows.append({'case_id': case_id, 'frames': checked['frames'],
                     'processing_sha256': sha(processing_path),
                     'returned_processing_sha256': sha(WORK / saved['processing']['processing']['path'])})
    require(len(rows) == 27, 'Expected 16 long plus 11 short selected exceptions')
    require(negatives == ['synthetic_as_original', 'missing_native_actor_frame'],
            'Current selected source negatives missing')
    return {'format': 'c150142-current-exceptions-selected-delivery-diagnostic-v1',
            'passed': True, 'manifest_sha256': manifest_sha, 'rows': rows,
            'rejected': negatives,
            'source_kind': 'synthetic_native_sample',
            'original_native_observed': False,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
