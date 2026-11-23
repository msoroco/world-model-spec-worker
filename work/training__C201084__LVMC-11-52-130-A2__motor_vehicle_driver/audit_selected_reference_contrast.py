"""Recompute the diagnostic stop comparison on exact selected attempts."""
import hashlib
import json
from pathlib import Path

from comparison_audit import audit as audit_sources

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit():
    manifest_path = HERE / 'execution-manifest.json'
    manifest_sha = sha(manifest_path)
    chains_path = HERE / 'selected-chains-audit.json'
    chains = read(chains_path)
    require(chains['passed'] is True and
            chains['selected_manifest_sha256'] == manifest_sha and
            chains['candidate_chains_proven'] == 32 and
            chains['delivery_ready'] is False,
            'Selected candidate chain audit differs')
    attempts = {group: REPO / '.runtime-work' /
                ('c201084-selected-' + group + '-primary-compatibility')
                for group in ('reference', 'contrast')}
    selected = {}
    for group, attempt in attempts.items():
        selection = read(attempt / 'candidate-selection.json')
        proof_path = HERE / ('selected-' + group + '-primary-proof.json')
        require(selection['manifest_sha256'] == manifest_sha and
                selection['case_id'] == HERE.name + '__' + group and
                selection['candidate_id'] == 'primary' and
                chains['candidate_proof_sha256'][group + '/primary'] == sha(proof_path),
                'Selected attempt or proof differs: ' + group)
        selected[group] = {'selection_sha256': sha(attempt / 'candidate-selection.json'),
                           'proof_sha256': sha(proof_path)}
    comparison = audit_sources(
        attempts['reference'], attempts['reference'] / 'result.json',
        attempts['contrast'], attempts['contrast'] / 'result.json')
    require(comparison['passed'] is True and
            comparison['diagnostic_only'] is True and
            comparison['accepted'] is False and
            comparison['sampled_reference_overlap_frames'] == 598 and
            comparison['sampled_contrast_disjoint_frames'] == 598 and
            comparison['reference_selection_sha256'] == selected['reference']['selection_sha256'] and
            comparison['contrast_selection_sha256'] == selected['contrast']['selection_sha256'],
            'Selected stop comparison differs')
    return {'format': 'c201084-selected-reference-contrast-cpu-audit-v1',
            'passed': True, 'diagnostic_only': True, 'accepted': False,
            'selected_manifest_sha256': manifest_sha,
            'selected_chains_audit_sha256': sha(chains_path),
            'selected_primary_bindings': selected,
            'comparison': comparison,
            'original_native_observed': False,
            'original_posting_verified': False,
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    (HERE / 'selected-reference-contrast-audit.json').write_text(
        json.dumps(audit(), indent=2, sort_keys=True) + '\n')
