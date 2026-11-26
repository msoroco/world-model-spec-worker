"""Materialize exact source-gated truck-following construction bundles."""
from __future__ import annotations

import json
from pathlib import Path

from truck_following import CASES
from native_packet import AID, VIEWS

HERE = Path(__file__).resolve().parent
SCRIPTS = ('runner.py', 'native_packet.py', 'truck_following.py', 'analysis.py')
SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('construction exceeds 2 MiB')


def description():
    channels = (
        ('sealed_native_original_frames', 'frame identity', 'byte-sealed 20 Hz Native source'),
        ('original_body_vertices', 'metres', 'eight body vertices projected on surveyed route'),
        ('full_mesh_width', 'metres', 'Native mesh bounds for each truck'),
        ('map_lane_availability', 'lane count', 'per-frame Native map readback'),
        ('vehicle_inventory', 'identity', 'source-bound subject, lead and entrants'),
        ('controller_commands', 'command', 'intent retained separately from observation'),
        ('video_four_views', 'frame identity', 'four synchronized original camera views'))
    return {'channels': [{'name': name, 'unit': unit, 'method': method,
                         'sampling_rate_hz': 20, 'time_window': 'all 900 original frames',
                         'reference_frame': 'reviewed Native route and source packet',
                         'uncertainty': 'physical realization and legal judgment remain unverified'}
                        for name, unit, method in channels],
            'context_inputs': [], 'limitations': [
                'Whenever conditions permit and without danger require independent review.',
                '500 feet and 80 inches are statutory quantities, not inferred from controller commands.']}


def make_config(case, fallback=False):
    ids = [AID + '__' + item.suffix for item in CASES]
    return {'assignment_id': AID, 'law_id': 'NRS-484B-127-2', 'cell_id': 'C149237',
            'actor': 'heavy_vehicle_driver', 'selected_case_id': AID + '__' + case.suffix,
            'supported_case_ids': ids, 'rate_hz': 20, 'duration_s': 45,
            'frame_count': 900, 'required_atoms': [], 'source_packets': [],
            'requested_gap_m': case.gap_target_m,
            'requested_subject_width_m': case.ego_width_target_m,
            'requested_lead_width_m': case.lead_width_target_m,
            'requested_same_direction_lanes': case.available_same_direction_lanes,
            'engineering': {'subject_target_mps': 11.0 if fallback else 13.0,
                            'lead_target_mps': 11.0 if fallback else 13.0},
            'cameras': [{'name': name, 'width': width, 'height': height,
                         'pose_strategy': 'reviewed Native route and four-view source survey',
                         'fov_deg': 90}
                        for name, (width, height) in zip(VIEWS, SIZES)],
            'case': {'case_id': AID + '__' + case.suffix,
                     'recording_description': description()}}


def build():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    ids = [AID + '__' + case.suffix for case in CASES]
    if [row['case_id'] for row in plan['cases']] != ids:
        raise ValueError('exact nine-case plan changed')
    branch = plan['selected_branches'][0]
    plan['selected_branch'] = branch['branch']
    plan['requirement_dispositions'] = [{
        'requirement': branch['requirement'], 'source': branch['source'],
        'status': 'selected_required', 'case_ids': ids,
        'evidence_or_gap': 'Frozen accepted recording metadata lacks original width, gap, lane and entrant histories.',
        'reason': 'Nine exact controlled probes require original route and full-body capture.'}]
    plan['observations'] = [{'name': row['name'], 'mandatory': True}
                            for row in description()['channels']]
    plan['source_observation_mapping'] = {}
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 45,
        'composition': 'synchronized_four_view_primary',
        'coverage': [{'view': view, 'subject': subject, 'interval': 'all original 900 frames'}
                     for view, subject in zip(VIEWS, (
                         'all road lanes and subject/lead gap', 'subject and lead body intervals',
                         'full truck meshes and entering vehicle', 'driver route and pass phase'))]}
    for row in plan['cases']:
        row['new_capture_selected'] = True
        row['construction_status'] = 'source_gated_exact_bundle'
    write(plan_path, plan)
    code = {name: (HERE / name).read_text(encoding='utf-8') for name in SCRIPTS}
    for index, case in enumerate(CASES):
        case_id = ids[index]
        config = make_config(case)
        config_text = json.dumps(config, indent=2) + '\n'
        test_text = ('"""Exact source-gated truck bundle identity."""\n'
                     'import unittest\nimport sys\nfrom pathlib import Path\n'
                     'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n'
                     'from runner import check\n\nclass ExactBundleTest(unittest.TestCase):\n'
                     '    def test_selected_identity(self):\n'
                     '        self.assertTrue(check().endswith("__' + case.suffix + '"))\n')
        files = [{'path': name, 'content': content} for name, content in code.items()]
        files += [{'path': 'config.json', 'content': config_text},
                  {'path': 'tests/test_bundle.py', 'content': test_text}]
        construction = {'law_id': 'NRS-484B-127-2', 'cell_id': 'C149237',
            'actor': 'heavy_vehicle_driver', 'case_id': case_id,
            'entrypoint': 'runner.py', 'diagnostic_only': True,
            'recording_description': description(), 'files': files,
            'measurement_plan': '900 original body, width, route gap, lane and entrant observations',
            'static_checks': ['reviewed Native map and blueprint hashes',
                              'qualifying truck width readback', 'four camera frame joins'],
            'termination_rules': ['900 synchronized Native ticks', 'restore world'],
            'mechanisms': ['source-gated truck and Native lane construction',
                           'following, pass and entrant controller intents',
                           'sealed original histories and four-view capture']}
        write(HERE / ('construction-' + case.suffix + '.json'), construction)
        if case.passing:
            fallback = dict(construction)
            fallback['files'] = [dict(item) for item in files]
            fallback_config = make_config(case, fallback=True)
            fallback['files'][-2]['content'] = json.dumps(fallback_config, indent=2) + '\n'
            fallback['measurement_plan'] += '; reduced matched truck speeds for pass geometry'
            write(HERE / ('construction-' + case.suffix + '-fallback1.json'), fallback)
        if index == 0:
            (HERE / 'config.json').write_text(config_text, encoding='utf-8')
            (HERE / 'tests/test_bundle.py').write_text(test_text, encoding='utf-8')
            write(HERE / 'construction.json', construction)
    return ids


if __name__ == '__main__':
    print('\n'.join(build()))
