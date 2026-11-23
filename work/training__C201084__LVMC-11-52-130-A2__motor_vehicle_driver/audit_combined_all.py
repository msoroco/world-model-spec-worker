"""Recompute and bind all eight combined-manifest diagnostic CPU case groups."""
import hashlib
import json
from pathlib import Path

from audit_combined_reference import audit as audit_reference
from audit_combined_contrast import audit as audit_contrast
from audit_combined_groups import audit_group
from audit_combined_reference_contrast import audit as audit_stop_pair
from audit_combined_traffic_pair import audit as audit_traffic_pair

HERE = Path(__file__).resolve().parent
GROUPS = ('reference', 'contrast', 'conflict', 'clear', 'near_lead',
          'absent_lead', 'device_direction', 'officer_direction')


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
    require(manifest['assignment_id'] == HERE.name and
            len(manifest['cases']) == 8 and
            {entry['case_id'] for entry in manifest['cases']} ==
            {HERE.name + '__' + group for group in GROUPS} and
            all(len(entry['candidates']) == 3 for entry in manifest['cases']),
            'Combined manifest case or candidate coverage differs')
    bindings = {}
    for group in GROUPS:
        path = HERE / ('current-combined-' + group + '-binding-audit.json')
        expected = (audit_reference() if group == 'reference' else
                    audit_contrast() if group == 'contrast' else
                    audit_group(group))
        require(read(path) == expected and expected['passed'] is True and
                expected['diagnostic_only'] is True and
                expected['delivery_selected'] is False,
                'Combined group audit differs: ' + group)
        if group in ('reference', 'contrast'):
            require(len(expected['fallback_proofs']) == 3 and
                    len(expected['fallback_offline_selection_sha256']) == 3,
                    'Combined pair case candidate coverage differs: ' + group)
        else:
            require(len(expected['candidate_proofs']) == 4,
                    'Combined group candidate coverage differs: ' + group)
        bindings[group] = sha(path)
    stop_path = HERE / 'current-combined-reference-contrast-binding-audit.json'
    traffic_path = HERE / 'current-combined-traffic-pair-audit.json'
    stop, traffic = audit_stop_pair(), audit_traffic_pair()
    require(read(stop_path) == stop and read(traffic_path) == traffic and
            stop['passed'] is True and stop['accepted'] is False and
            traffic['passed'] is True and
            traffic['canonical_comparison_audit'] is False,
            'Combined diagnostic comparison binding differs')
    return {'format': 'c201084-combined-eight-case-cpu-audit-v1',
            'passed': True, 'diagnostic_only': True,
            'combined_manifest_sha256': sha(manifest_path),
            'case_group_binding_sha256': bindings,
            'candidate_chains_passed': 32,
            'diagnostic_stop_comparison_sha256': sha(stop_path),
            'diagnostic_traffic_comparison_sha256': sha(traffic_path),
            'delivery_selected': False,
            'canonical_comparison_audits_passed': 0,
            'original_native_verified': False,
            'physical_or_legal_completion_claimed': False}


if __name__ == '__main__':
    (HERE / 'current-combined-all-binding-audit.json').write_text(
        json.dumps(audit(), indent=2, sort_keys=True) + '\n')
