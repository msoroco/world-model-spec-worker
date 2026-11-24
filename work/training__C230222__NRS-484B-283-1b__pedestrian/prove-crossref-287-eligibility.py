"""Source-bound eligibility review for the three NRS 484B.287 alternatives."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IDS = ('NRS-484B-287-1c', 'NRS-484B-287-1d', 'NRS-484B-287-1e')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def road_shape(content):
    root = ET.fromstring(content)
    return {'road_count': len(root.findall('road')),
            'junction_count': len(root.findall('junction')),
            'signal_count': len(root.findall('.//signals/signal')),
            'crosswalk_count': sum(x.get('type') == 'crosswalk' for x in root.findall('.//objects/object'))}


def main():
    catalog_path = ROOT / 'inputs/coverage/candidate-cells.json'
    catalog = json.loads(catalog_path.read_text())['cells']
    require(len(catalog) == 1243, 'Candidate catalog length changed')
    eligible = [x for x in catalog if 'pedestrian' in x.get('candidate_ego_parties', [])]
    require(not eligible, 'An additional pedestrian binding may now be available')
    original = [x for x in catalog if x['cell_id'] == 'C230222']
    require(len(original) == 1, 'C230222 catalog identity changed')
    require((original[0]['layout'], original[0]['maneuver'], original[0]['control']) ==
            ('road', 'travel', 'curb'), 'C230222 fixed cell changed')

    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    shapes = []
    road_hashes = set()
    for entry in manifest['cases']:
        for variant in [entry] + entry['candidates']:
            construction_path = HERE / variant['construction']
            require(digest(construction_path) == variant['construction_sha256'],
                    'Selected construction hash differs')
            construction = json.loads(construction_path.read_text())
            road_files = [f['content'] for f in construction['files'] if f['path'] == 'road.xodr']
            require(len(road_files) == 1, 'Selected case road source differs')
            shape = road_shape(road_files[0])
            require(shape == {'road_count': 1, 'junction_count': 0,
                              'signal_count': 0, 'crosswalk_count': 0},
                    'Selected road has intersection, device or crossing geometry')
            road_hashes.add(hashlib.sha256(road_files[0].encode()).hexdigest())
            shapes.append({'case_id': entry['case_id'],
                           'candidate_id': variant.get('id', 'primary'),
                           'construction_sha256': variant['construction_sha256'],
                           'road_shape': shape})
    require(len(shapes) == 4 and len(road_hashes) == 1,
            'Selected primary and fallback road sources differ')
    mutated = road_files[0].replace('<signals />', '<signals><signal id="1" /></signals>')
    require(road_shape(mutated)['signal_count'] == 1,
            'Device negative control did not detect changed road')
    crosswalk = road_files[0].replace('<objects />',
        '<objects><object id="1" type="crosswalk" /></objects>')
    require(road_shape(crosswalk)['crosswalk_count'] == 1,
            'Crosswalk negative control did not detect changed road')
    junction = road_files[0].replace('</OpenDRIVE>', '<junction id="1" /></OpenDRIVE>')
    require(road_shape(junction)['junction_count'] == 1,
            'Junction negative control did not detect changed road')

    frozen = json.loads((ROOT / 'inputs/coverage/branch-sources.json').read_text())['laws']
    coverage = json.loads((ROOT / 'work/_shared/branch-coverage.json').read_text())['laws']
    review = json.loads((HERE / 'statutory-crossrefs.json').read_text())['crossrefs']
    rows = []
    for law_id in IDS:
        row = next(x for x in review if x['law_id'] == law_id)
        source = frozen[law_id]
        require(source['law']['text'] == row['exact_text'], 'Frozen cross-reference text differs')
        require(hashlib.sha256(row['exact_text'].encode()).hexdigest() == row['exact_text_sha256'],
                'Frozen cross-reference text hash differs')
        original_assignment = ROOT / 'inputs' / row['original_assignment_id'] / 'assignment.json'
        assignment = json.loads(original_assignment.read_text())
        require(assignment['cell_id'] == 'C109166' and assignment['actor'] == 'pedestrian' and
                (assignment['cell']['layout'], assignment['cell']['maneuver'], assignment['cell']['control']) ==
                ('intersection', 'enter_road', 'traffic_control_device'),
                'Original 287 intersection/device assignment differs')
        branch = coverage[law_id]['branches']
        require(len(branch) == 1 and branch[0]['assignment_id'] == assignment['assignment_id'] and
                branch[0]['status'] == 'pending_review', 'Shared 287 ownership differs')
        rows.append({'law_id': law_id,
                     'exact_text_sha256': row['exact_text_sha256'],
                     'original_assignment_id': assignment['assignment_id'],
                     'original_assignment_sha256': digest(original_assignment),
                     'original_cell': {'layout': 'intersection', 'maneuver': 'enter_road',
                                       'control': 'traffic_control_device'},
                     'selected_geometry_missing':
                         ['adjacent_intersections', 'operating_official_devices', 'marked_crosswalk']
                         if law_id.endswith('1c') else
                         ['intersection', 'official_diagonal_crossing_device'],
                     'required_original_observations': row['required_original_observations'],
                     'c230222_selected_road_has_required_intersection_device_context': False,
                     'new_pedestrian_binding_eligible_in_frozen_catalog': False,
                     'same_cell_positive_variant_status': 'unbuilt_pending_frozen_cell_compatibility_review',
                     'positive_287_branch_source_review_status': 'pending_review_in_original_assignment',
                     'c230222_exception_applicability': 'unresolved_until_original_native_review'})
    output = {'format': 'c230222-crossref-287-eligibility-source-review-v1',
              'candidate_catalog_sha256': digest(catalog_path),
              'candidate_cell_count': len(catalog),
              'pedestrian_candidate_cell_count': len(eligible),
              'selected_manifest_sha256': digest(HERE / 'execution-manifest.json'),
              'selected_case_road_sources': shapes,
              'common_selected_road_sha256': next(iter(road_hashes)),
              'changed_device_negative_control_detected': True,
              'changed_crosswalk_negative_control_detected': True,
              'changed_junction_negative_control_detected': True,
              'crossrefs': rows,
              'additional_binding_proposed': False,
              'capability_blocked_claim': False,
              'legal_applicability_conclusion': None}
    target = HERE / 'crossref-287-eligibility-proof.json'
    target.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'reviewed': len(rows), 'candidate_cell_count': len(catalog),
                      'pedestrian_candidate_cell_count': len(eligible),
                      'proof_sha256': digest(target)}))


if __name__ == '__main__':
    main()
