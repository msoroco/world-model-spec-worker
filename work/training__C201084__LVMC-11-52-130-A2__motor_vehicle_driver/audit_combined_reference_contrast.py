"""Bind the combined-manifest diagnostic comparison to source and review proofs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ATTEMPTS = {
    'reference': REPO / '.runtime-work/c201084-combined-reference-primary-compatibility-v2',
    'contrast': REPO / '.runtime-work/c201084-combined-contrast-primary-compatibility',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit():
    manifest_path = HERE / 'current-combined-delivery-draft.json'
    manifest = read(manifest_path)
    comparison_path = HERE / 'current-combined-reference-contrast-comparison.json'
    comparison = read(comparison_path)
    require(comparison['passed'] is True and
            comparison['diagnostic_only'] is True and
            comparison['accepted'] is False and
            comparison['original_posting_verified'] is False and
            comparison['legal_verdict_claimed'] is False and
            comparison['physical_acceptance_claimed'] is False and
            comparison['sampled_reference_overlap_frames'] == 598 and
            comparison['sampled_contrast_disjoint_frames'] == 598 and
            comparison['source_cases'] == [HERE.name + '__reference',
                                           HERE.name + '__contrast'],
            'Combined comparison measurement or acceptance differs')
    case_bindings = {}
    for case, attempt in ATTEMPTS.items():
        entry = next(row for row in manifest['cases']
                     if row['case_id'] == HERE.name + '__' + case)
        prefix = 'current-combined-' + case + '-primary-'
        offline_path = HERE / (prefix + 'offline-selection.json')
        saved_path = HERE / (prefix + 'saved.log')
        compatibility_path = HERE / (prefix + ('compatibility-v2.log'
                                               if case == 'reference' else 'compatibility.log'))
        binding_path = HERE / ('current-combined-' + case + '-binding-audit.json')
        offline, saved, compatibility, binding = [read(path) for path in
                                                   (offline_path, saved_path,
                                                    compatibility_path, binding_path)]
        require(binding['passed'] is True and
                binding['diagnostic_only'] is True and
                binding['delivery_selected'] is False and
                binding['manifest_sha256'] == sha(manifest_path) and
                binding['construction_sha256'] == entry['construction_sha256'] and
                binding['offline_selection_sha256'] == sha(offline_path) and
                binding['compatibility_receipt_sha256'] == sha(compatibility_path) and
                binding['saved_receipt_sha256'] == sha(saved_path),
                'Combined case chain binding differs: ' + case)
        require(offline['manifest_sha256'] == sha(manifest_path) and
                offline['construction_sha256'] == entry['construction_sha256'] and
                compatibility['passed'] is True and saved['passed'] is True and
                sha(attempt / 'candidate-selection.json') == sha(offline_path) and
                comparison[case + '_selection_sha256'] == sha(offline_path) and
                comparison[case + '_result_sha256'] == sha(attempt / 'result.json'),
                'Combined comparison attempt differs: ' + case)
        event_path = HERE / ('current-' + case + '-event-evidence.json')
        event = read(event_path)
        context_path = HERE / ('current-' + case + '-context-binding.json')
        context = read(context_path)
        posting_path = HERE / ('current-' + case + '-posting-binding.json')
        posting = read(posting_path)
        require(event['case'] == case and event['diagnostic_fixture'] is True and
                event['frames'] == 600 and event['legal_act_classification'] is None and
                context['event_evidence_sha256'] == sha(event_path) and
                context['original_context_review_bound'] is False and
                context['property_legally_verified'] is False and
                context['property_and_attendance_review'] is None and
                posting['event_evidence_sha256'] == sha(event_path) and
                posting['original_posting_review_bound'] is False and
                posting['posting_review'] is None and
                posting['fire_code_designation_verified'] is False and
                posting['legal_applicability_verified'] is False,
                'Combined comparison original review overclaims: ' + case)
        for source, digest in event['source_sha256'].items():
            require(sha(attempt / source) == digest and
                    saved['original_source_hashes'].get(source) == digest,
                    'Combined comparison source differs: ' + case + '/' + source)
        for review in (context, posting):
            for camera, digest in review['camera_source_sha256'].items():
                source = camera + '.mkv'
                require(sha(attempt / source) == digest and
                        saved['original_source_hashes'].get(source) == digest,
                        'Combined comparison camera differs: ' + case + '/' + camera)
        case_bindings[case] = {
            'combined_chain_audit_sha256': sha(binding_path),
            'event_evidence_sha256': sha(event_path),
            'context_binding_sha256': sha(context_path),
            'posting_binding_sha256': sha(posting_path)}
    return {'format': 'c201084-combined-comparison-binding-v1',
            'passed': True, 'diagnostic_only': True, 'accepted': False,
            'combined_manifest_sha256': sha(manifest_path),
            'comparison_sha256': sha(comparison_path),
            'case_bindings': case_bindings,
            'delivery_selected': False,
            'physical_or_legal_completion_claimed': False}


if __name__ == '__main__':
    (HERE / 'current-combined-reference-contrast-binding-audit.json').write_text(
        json.dumps(audit(), indent=2, sort_keys=True) + '\n')
