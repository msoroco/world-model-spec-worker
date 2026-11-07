"""Pin the exact frozen source dependencies for the prior-entry branch."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'inputs/coverage/branch-sources.json'
OFFICIAL = HERE / 'official-cited-context.json'
FIELDS = {
    'NRS-484B-283-1d4': ['governing_pedestrian_signal', 'facing_signal', 'steady_indication'],
    'NRS-484B-283-1d1': ['governing_pedestrian_signal', 'facing_signal', 'walk_at_entry'],
    'NRS-484B-283-1d2': ['governing_pedestrian_signal', 'facing_signal',
                         'flashing_with_countdown_at_entry', 'cleared_before_countdown_zero'],
    'NRS-484B-287-1c': ['between_adjacent_signalized_intersections', 'marked_crosswalk'],
    'NRS-484B-287-1d': ['diagonal_crossing', 'diagonal_device_authorization'],
    'NRS-484B-287-1e': ['diagonal_crossing', 'diagonal_device_authorization',
                         'followed_diagonal_device'],
    'LVMC-11-30-060-A': ['outside_marked_or_intersection_crosswalk', 'vehicle_right_of_way_context'],
    'LVMC-11-30-060-B': ['tunnel_or_overhead_crossing_provided', 'vehicle_right_of_way_context'],
    'LVMC-11-30-140-B': ['blind_person_encounter', 'white_or_red_tipped_cane_or_assistance'],
    'LVMC-11-46-030': ['school_pedestrian_lane', 'children_crossing_warning', 'vehicle_operator_context'],
}


def main():
    frozen = json.loads(SOURCE.read_text())['laws']
    dependencies = []
    for law_id, fields in FIELDS.items():
        law = frozen[law_id]['law']
        dependencies.append({'law_id': law_id, 'source': law['source'],
            'text_sha256': hashlib.sha256(law['text'].encode()).hexdigest(),
            'source_kind': 'frozen_inventory',
            'required_source_facts': fields,
            'scope': 'measurement inventory, no legal applicability conclusion'})
    official = json.loads(OFFICIAL.read_text())
    if (official.get('format') != 'c10316-official-cited-context-v1' or
            len(official.get('sections', [])) != 2 or
            official.get('physical_context_observed') is not False or
            official.get('legal_applicability_determined') is not False):
        raise ValueError('Official cited-context packet differs')
    for section in official['sections']:
        dependencies.append({'law_id': section['law_id'],
            'source': official['source_url'] + '#' + section['official_section'].replace(' ', '-'),
            'text_sha256': None,
            'source_summary_sha256': hashlib.sha256(section['source_summary'].encode()).hexdigest(),
            'source_kind': 'official_reference_outside_frozen_inventory',
            'required_source_facts': section['required_source_facts'],
            'scope': 'current official section reviewed; physical applicability and legal conclusion unverified',
            'frozen_companion_law_id': section['frozen_companion_law_id'],
            'companion_is_exact_equivalent': False})
    contract = {'format': 'c10316-prior-entry-statutory-context-contract-v2',
        'frozen_branch_source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'official_cited_context_sha256': hashlib.sha256(OFFICIAL.read_bytes()).hexdigest(),
        'target_law_id': 'NRS-484B-283-1d4', 'dependencies': dependencies,
        'cited_exact_sources_absent_from_frozen_inventory': ['NRS 484B.290', 'NRS 484B.350'],
        'official_cited_sections_reviewed': ['NRS 484B.290', 'NRS 484B.350'],
        'legal_applicability_determined': False, 'physical_context_observed': False}
    (HERE / 'statutory-context-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
    print(json.dumps({'pinned_dependencies': len(dependencies),
                      'missing_exact_cited_sources_in_frozen_inventory': 2,
                      'official_sections_reviewed': 2,
                      'legal_applicability_determined': False}))


if __name__ == '__main__':
    main()
