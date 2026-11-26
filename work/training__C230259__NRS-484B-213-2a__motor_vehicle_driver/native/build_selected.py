"""Bind six reviewed exact requests to lazy Native capture and saved finalization."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
HERE = Path(__file__).resolve().parent
SUFFIXES = ('probe_a', 'probe_b', 'curve_right', 'curve_left', 'one_way_crest', 'one_way_curve')
CHANNELS = ('st.grade', 'st.curvature', 'st.sight_distance',
            'drv.sight_distance_adequate', 'st.centre_line', 'rel.occupies',
            'drv.approaching', 'st.one_way_roadway', 'rel.oncoming')


def encode(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + '\n'


def sha_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


def main():
    entries = []
    assignment_path = REPO / 'inputs' / ROOT.name / 'assignment.json'
    assignment = assignment_path.read_text()
    sources = {'assignment-source.json': assignment,
               'draft_runner.py': (HERE / 'draft_runner.py').read_text(),
               'runner.py': (HERE / 'selected_runner.py').read_text(),
               'capture_feature.py': (HERE / 'capture_feature.py').read_text(),
               'finalize.py': (HERE / 'finalize_feature.py').read_text(),
               'measure_feature.py': (HERE / 'measure_feature.py').read_text(),
               'tests/test_selected.py': (HERE / 'test_selected_offline.py').read_text()}
    source_path = {'assignment-source.json': assignment_path,
                   'draft_runner.py': HERE / 'draft_runner.py',
                   'runner.py': HERE / 'selected_runner.py',
                   'capture_feature.py': HERE / 'capture_feature.py',
                   'finalize.py': HERE / 'finalize_feature.py',
                   'measure_feature.py': HERE / 'measure_feature.py',
                   'tests/test_selected.py': HERE / 'test_selected_offline.py'}
    descriptions = {}
    for suffix in SUFFIXES:
        draft_path = ROOT / 'draft-cases' / suffix / 'primary/construction.json'
        draft = json.loads(draft_path.read_text())
        draft_files = {item['path']: item['content'] for item in draft['files']}
        config = json.loads(draft_files['config.json'])
        case_id = config['case_id']
        description = {'channels': [
            {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': 'Original Native map, actor body, sight ray and synchronized camera source',
             'time_window': 'all 600 Native frames / 30 s',
             'reference_frame': 'original Native actor and map',
             'uncertainty': '50 ms sample interval; road authority and legal interpretation pending'}
            for name in CHANNELS],
            'context_inputs': [{'name': 'road_geometry_source', 'unit': 'structured',
                'method': 'Authored OpenDRIVE and original Native map readback; road authority pending'}],
            'limitations': ['No original Native capture or legal highway designation is claimed by CPU construction',
                            'Actual curve/crest obstruction and pixel visibility require local review']}
        config.update(candidate_id='primary', supported_case_ids=[case_id],
                      roadside_wall_height_m=4.0,
                      status='selected_native_cpu_prepared', original_native_observed=False,
                      required_atoms=['kin.position', 'kin.heading', 'rel.occupies'],
                      source_packets=[], recording_description=description,
                      case={'case_id': case_id, 'recording_description': description},
                      assignment_sha256=sha_text(assignment),
                      road_sha256=sha_text(draft_files['road.xodr']))
        files = {'config.json': encode(config), 'road.xodr': draft_files['road.xodr'], **sources}
        construction = {'format': 'worker-inline-construction',
                        'case_id': case_id, 'cell_id': 'C230259',
                        'law_id': 'NRS-484B-213-2a', 'actor': 'motor_vehicle_driver',
                        'entrypoint': 'runner.py',
                        'files': [{'path': name, 'content': content,
                                   **({'source': str(source_path[name].relative_to(REPO))}
                                      if name in source_path else {})}
                                  for name, content in files.items()],
                        'recording_description': description,
                        'measurement_plan': {'method': '600 original Native body, map, sight-ray and four-camera rows; saved-only meter',
                                             'status': 'cpu_prepared_original_native_unobserved'},
                        'termination_rules': ['Retain all 600 original frames', 'retain failure report and restore world'],
                        'mechanisms': ['Source-bound OpenDRIVE feature geometry',
                                       'CARLA generated four-meter roadside wall',
                                       'lane-target controller', 'four synchronized lossless cameras'],
                        'status': 'selected_cpu_construction'}
        target = ROOT / 'selected-constructions' / suffix / 'primary/construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(encode(construction))
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': str(target.relative_to(ROOT)),
                        'construction_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                        'candidate_risk': {'status': 'physical',
                            'reason': 'Original Native trajectory and line-of-sight may miss authored feature request'},
                        'candidates': []})
        descriptions[suffix] = description
    selected = {'format': 'worker-selected-construction-draft-v1',
                'assignment_id': ROOT.name, 'status': 'selected_offline_pending',
                'cases': entries, 'original_native_observed': False}
    path = ROOT / 'selected-construction-draft.json'
    path.write_text(encode(selected))
    print(json.dumps({'selected_draft_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'case_count': len(entries)}))


if __name__ == '__main__':
    main()
