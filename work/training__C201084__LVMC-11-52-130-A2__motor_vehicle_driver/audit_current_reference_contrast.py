"""Bind the current diagnostic comparison to exact CPU proof receipts."""
import argparse
import json
from pathlib import Path

from comparison_audit import audit, require
from source_measurement import sha


HERE = Path(__file__).resolve().parent
RUNTIME_MANIFEST = Path('runtime/pipeline/SOURCE-MANIFEST.json')
CASES = ('reference', 'contrast')


def read(path):
    return json.loads(Path(path).read_text())


def bind_case(case, attempt):
    prefix = HERE / ('current-' + case + '-primary-')
    manifest_path = HERE / ('draft-' + case + '-fallback-manifest.json')
    manifest = read(manifest_path)
    entry = manifest['cases'][0]
    selection = read(Path(str(prefix) + 'offline-selection.json'))
    compatibility = read(Path(str(prefix) + 'compatibility-receipt.json'))
    saved = read(Path(str(prefix) + 'saved-receipt.json'))
    event_path = HERE / ('current-' + case + '-event-evidence.json')
    event = read(event_path)
    context_path = HERE / ('current-' + case + '-context-binding.json')
    context = read(context_path)
    posting_path = HERE / ('current-' + case + '-posting-binding.json')
    posting = read(posting_path)
    runtime_sha = sha(RUNTIME_MANIFEST)
    case_id = HERE.name + '__' + case
    construction_sha = entry['construction_sha256']
    require(manifest['runtime_manifest_sha256'] == runtime_sha and
            entry['case_id'] == case_id and
            sha(HERE / entry['construction']) == construction_sha,
            'Current comparison manifest or construction binding differs: ' + case)
    require(selection['case_id'] == case_id and
            selection['candidate_id'] == 'primary' and
            selection['construction_sha256'] == construction_sha and
            selection['manifest_sha256'] == sha(manifest_path),
            'Current comparison offline selection differs: ' + case)
    require(compatibility['case_id'] == case_id and
            compatibility['candidate_id'] == 'primary' and
            compatibility['construction_sha256'] == construction_sha and
            compatibility['runtime_manifest_sha256'] == runtime_sha and
            compatibility['passed'] is True and
            compatibility['negative_removed'] and
            compatibility['negative_error_contains'],
            'Current comparison compatibility or negative proof differs: ' + case)
    require(saved['case_id'] == case_id and
            saved['candidate_id'] == 'primary' and
            saved['passed'] is True and
            saved['recorded_only'] is True and
            saved['originals_preserved'] is True and
            saved['analysis_revision']['construction_sha256'] == construction_sha and
            saved['analysis_revision']['runtime_manifest_sha256'] == runtime_sha and
            saved['physical_acceptance_claimed'] is False and
            saved['legal_acceptance_claimed'] is False,
            'Current comparison saved-processing proof differs: ' + case)
    require(event['case'] == case and
            event['diagnostic_fixture'] is True and
            event['frames'] == 600 and
            event['legal_act_classification'] is None and
            event['physical_or_legal_completion_claimed'] is False,
            'Current comparison source event overclaims or differs: ' + case)
    for source, digest in event['source_sha256'].items():
        require(sha(attempt / source) == digest and
                saved['original_source_hashes'].get(source) == digest,
                'Current comparison source/saved binding differs: ' + case + '/' + source)
    require(context['case'] == case and
            context['event_evidence_sha256'] == sha(event_path) and
            context['diagnostic_fixture'] is True and
            context['property_and_attendance_review'] is None and
            context['original_context_review_bound'] is False and
            context['property_legally_verified'] is False and
            context['posting_or_fire_code_designation_verified'] is False and
            context['physical_or_legal_completion_claimed'] is False,
            'Current comparison context review overclaims: ' + case)
    for camera, digest in context['camera_source_sha256'].items():
        require(sha(attempt / (camera + '.mkv')) == digest and
                saved['original_source_hashes'].get(camera + '.mkv') == digest,
                'Current comparison context camera differs: ' + case + '/' + camera)
    require(posting['case'] == case and
            posting['event_evidence_sha256'] == sha(event_path) and
            posting['diagnostic_fixture'] is True and
            posting['posting_review'] is None and
            posting['original_posting_review_bound'] is False and
            posting['sign_text_verified'] is False and
            posting['fire_code_designation_verified'] is False and
            posting['legal_applicability_verified'] is False and
            posting['physical_or_legal_completion_claimed'] is False,
            'Current comparison posting review overclaims: ' + case)
    for camera, digest in posting['camera_source_sha256'].items():
        require(sha(attempt / (camera + '.mkv')) == digest and
                saved['original_source_hashes'].get(camera + '.mkv') == digest,
                'Current comparison posting camera differs: ' + case + '/' + camera)
    return {
        'manifest_sha256': sha(manifest_path),
        'construction_sha256': construction_sha,
        'offline_selection_sha256': sha(Path(str(prefix) + 'offline-selection.json')),
        'compatibility_receipt_sha256': sha(Path(str(prefix) + 'compatibility-receipt.json')),
        'saved_receipt_sha256': sha(Path(str(prefix) + 'saved-receipt.json')),
        'event_evidence_sha256': sha(event_path),
        'context_binding_sha256': sha(context_path),
        'posting_binding_sha256': sha(posting_path),
        'source_sha256': event['source_sha256'],
    }


def build(reference_attempt, contrast_attempt):
    reference_attempt, contrast_attempt = Path(reference_attempt), Path(contrast_attempt)
    comparison = audit(reference_attempt, reference_attempt / 'result.json',
                       contrast_attempt, contrast_attempt / 'result.json')
    require(comparison['passed'] is True and
            comparison['diagnostic_only'] is True and
            comparison['accepted'] is False and
            comparison['original_posting_verified'] is False and
            comparison['legal_verdict_claimed'] is False and
            comparison['physical_acceptance_claimed'] is False,
            'Current comparison asserted unsupported acceptance')
    bindings = {case: bind_case(case, attempt) for case, attempt in
                (('reference', reference_attempt), ('contrast', contrast_attempt))}
    require(comparison['sampled_reference_overlap_frames'] == 598 and
            comparison['sampled_contrast_disjoint_frames'] == 598,
            'Current comparison measured event differs')
    return {'format': 'c201084-current-runtime-comparison-binding-v1',
            'passed': True, 'diagnostic_only': True, 'accepted': False,
            'runtime_manifest_sha256': sha(RUNTIME_MANIFEST),
            'comparison': comparison, 'case_bindings': bindings,
            'delivery_selected': False,
            'original_posting_verified': False,
            'legal_act_classification_verified': False,
            'physical_or_legal_completion_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference-attempt', required=True, type=Path)
    parser.add_argument('--contrast-attempt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Retain previous comparison binding')
    result = build(args.reference_attempt, args.contrast_attempt)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': True, 'diagnostic_only': True}))


if __name__ == '__main__':
    main()
