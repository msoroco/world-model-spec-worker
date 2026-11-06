"""Bind the curb rule's seven named cross-references to frozen source topics."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW_IDS = (
    'NRS-484B-287-1c', 'NRS-484B-287-1d', 'NRS-484B-287-1e',
    'LVMC-11-30-060-A', 'LVMC-11-30-060-B',
    'LVMC-11-30-140-B', 'LVMC-11-46-030',
)
REQUIRED = {
    'NRS-484B-287-1c': ['adjacent_intersections', 'operating_official_devices', 'crossing_location', 'marked_crosswalk_geometry'],
    'NRS-484B-287-1d': ['intersection_geometry', 'pedestrian_diagonal_path', 'official_device_authorization'],
    'NRS-484B-287-1e': ['intersection_geometry', 'official_diagonal_authorization', 'device_indication', 'pedestrian_path_compliance'],
    'LVMC-11-30-060-A': ['crossing_location', 'marked_or_unmarked_crosswalk_geometry', 'vehicle_right_of_way', 'designated_place_prohibition'],
    'LVMC-11-30-060-B': ['tunnel_or_overhead_crossing_provided', 'crossing_location', 'vehicle_right_of_way', 'designated_place_prohibition'],
    'LVMC-11-30-140-B': ['blindness_context', 'white_or_red_tipped_cane_or_assistance', 'approaching_driver_stop', 'collision_avoidance_precautions'],
    'LVMC-11-46-030': ['school_pedestrian_lane', 'warning_actor_or_device', 'children_crossing_context', 'vehicle_stop_distance_ft', 'release_signal'],
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    source = ROOT / 'inputs/coverage/branch-sources.json'
    inventory = json.loads(source.read_text())['laws']
    plan = json.loads((HERE / 'case-plan.json').read_text())
    introductory = plan['source_law']['text']
    rows = []
    for law_id in LAW_IDS:
        if law_id not in introductory:
            raise ValueError('Cross-reference is absent from exact curb clause: ' + law_id)
        record = inventory[law_id]
        law = record['law']
        rows.append({'law_id': law_id, 'source': law['source'], 'exact_text': law['text'],
                     'exact_text_sha256': hashlib.sha256(law['text'].encode()).hexdigest(),
                     'topic_ids': sorted(record['topics']),
                     'original_assignment_id': record['original_assignment_id'],
                     'required_original_observations': REQUIRED[law_id],
                     'current_curb_pair_proves_applicability': False,
                     'same_cell_construction_status': 'pending_physical_construction_and_review',
                     'proposed_case_id': HERE.name + '__crossref_' + law_id.lower().replace('-', '_'),
                     'legal_applicability_conclusion': None})
    report = {'format': 'c230222-exact-crossref-review-v1',
              'curb_clause_source': plan['source_law']['source'],
              'curb_clause_sha256': plan['source_law']['sha256'],
              'frozen_inventory_path': str(source.relative_to(ROOT)),
              'frozen_inventory_sha256': sha(source),
              'authored_road_sha256': sha(HERE / 'native/road.xodr'),
              'current_road_context': {'one_straight_road': True, 'intersection_objects': 0,
                                       'marked_crosswalk_objects': 0,
                                       'school_lane_or_tunnel_objects': 0},
              'crossrefs': rows, 'applicability_resolved': False,
              'physical_crossref_cases_constructed': 0, 'selected_crossref_cases': 0}
    (HERE / 'statutory-crossrefs.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'exact_crossrefs': len(rows), 'frozen_source_bound': True,
                      'applicability_resolved': False, 'selected_crossref_cases': 0}))


if __name__ == '__main__':
    build()
