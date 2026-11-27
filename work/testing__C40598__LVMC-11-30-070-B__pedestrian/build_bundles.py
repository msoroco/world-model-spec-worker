"""Build four exact source-gated C40598 crossing constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULES = ('runner.py', 'native_entry.py', 'crosswalk_site.py',
           'crossing_measure.py', 'analysis.py')
OFFLINE_TEST = '''import json
import unittest
from pathlib import Path
from runner import check

class SelectedBusinessDistrictOffline(unittest.TestCase):
    def test_exact_source_gate(self):
        root = Path(__file__).resolve().parents[1]
        selected = check(root)
        self.assertEqual(selected["case_id"], json.loads((root / "config.json").read_text())["selected_case_id"])
        self.assertIn("reviewed original 600-foot", selected["source_gate"])

if __name__ == "__main__":
    unittest.main()
'''


def write(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> list[dict]:
    plan = json.loads((HERE / 'case-plan.json').read_text())
    ids = [case['case_id'] for case in plan['cases']]
    entries = []
    description = {'channels': [
        {'name': name, 'unit': unit, 'sampling_rate_hz': 20,
         'method': method, 'time_window': '900 original frames',
         'reference_frame': 'reviewed original roadway and 600-foot highway span',
         'uncertainty': 'physical source realization pending'}
        for name, unit, method in (
            ('district_frontage', 'ft', 'original building use, side and occupied frontage source readback'),
            ('crosswalk_geometry', 'state', 'original marked and all applicable unmarked crosswalk body overlap'),
            ('roadway_jurisdiction', 'state', 'original roadway/shoulder, public-access and municipal context'),
            ('pedestrian_crossing', 'state', 'original full-body road entry, crossing and opposite-curb exit'),
            ('governing_controls', 'state', 'original governing sign and signal inventory'))],
        'context_inputs': [{'name': 'reviewed_business_district_site', 'unit': 'source',
            'method': 'independently reviewed original roadway, district frontage and controls'}],
        'limitations': ['Worker does not assign a legal business-district or crosswalk verdict.',
            'A 600-foot source span and both frontage alternatives require independent review.']}
    for case in plan['cases']:
        case_id = case['case_id']
        short = case_id.split('__')[-1]
        folder = HERE / 'cases' / short
        config = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
            'actor': plan['actor'], 'selected_case_id': case_id,
            'supported_case_ids': ids, 'required_atoms': [], 'source_packets': [],
            'rate_hz': 20, 'duration_s': 45,
            'cameras': [{'name': name, 'width': width, 'height': height,
                'fov_deg': 75, 'pose_strategy': 'reviewed original district, crosswalk and pedestrian view'}
                for name, width, height in (('overview', 1920, 1080),
                    ('approach', 1280, 720), ('reference_corner', 1280, 720),
                    ('driver_reference', 1280, 720))],
            'physical_completion': {'criterion': 'travel_progress',
                'motion_source': 'trace.jsonl', 'position_key': 'position_m',
                'minimum_progress_m': 5.0, 'minimum_samples': 3,
                'engineering_tolerances_not_legal': True,
                'completion_goal_method': 'At least 5 m original pedestrian progress as engineering motion proxy; independently audit actual complete crossing.'},
            'case': {'case_id': case_id,
                'physical_target': 'complete reviewed business-district crossing in exact crosswalk category',
                'recording_description': description}}
        spec = {'case_id': case_id,
                'crosswalk_category': case['crosswalk_category'],
                'district_frontage_review': case['district_frontage_review'],
                'source_status': 'reviewed_original_business_district_packet_required_at_capture'}
        write(folder / 'config.json', config)
        write(folder / 'case-spec.json', spec)
        for candidate_id, speed in (('primary', 1.2), ('fallback1', 0.8)):
            controller = {'walker_speed_mps': speed,
                'source': 'predeclared path tracking on unchanged reviewed original site',
                'physical_acceptance': False}
            control_name = 'controller-' + candidate_id + '.json'
            write(folder / control_name, controller)
            files = [{'path': name, 'source': str((HERE / name).relative_to(ROOT)),
                'content': (HERE / name).read_text()} for name in MODULES]
            for name, value, source in (('config.json', config, folder / 'config.json'),
                    ('case-spec.json', spec, folder / 'case-spec.json'),
                    ('controller.json', controller, folder / control_name)):
                files.append({'path': name, 'source': str(source.relative_to(ROOT)),
                    'content': json.dumps(value, indent=2, sort_keys=True) + '\n'})
            files.append({'path': 'tests/test_offline.py', 'content': OFFLINE_TEST})
            construction = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                'actor': plan['actor'], 'case_id': case_id, 'entrypoint': 'runner.py',
                'files': files, 'recording_description': description,
                'measurement_plan': {'selected_requirement': plan['requirement_dispositions'][0]['requirement'],
                    'original_source': 'reviewed 600-foot district, crossing body, marked/unmarked and controls source readback',
                    'saved_method': 'source-bound full road crossing and both crosswalk categories'},
                'mechanisms': ['source-gated original district and full-body crossing selection',
                    'same-tick pedestrian and four-camera Native capture'],
                'static_checks': ['exact case, 20 Hz and four cameras',
                    'reviewed source packet required before Native world mutation'],
                'termination_rules': {'duration_s': 45,
                    'early_termination': 'retain failed capture; do not publish as original crossing'}}
            name = 'construction.json' if candidate_id == 'primary' else 'fallback1-construction.json'
            digest = write(folder / name, construction)
            if candidate_id == 'primary':
                entry = {'case_id': case_id, 'construction': str((folder / name).relative_to(HERE)),
                    'construction_sha256': digest, 'kind': 'delivery',
                    'measurement_procedure': {'entrypoint': 'analysis.py'},
                    'fixture_recipe': str((folder / 'fixture-recipe.json').relative_to(ROOT)),
                    'measurement_contract': str((folder / 'measurement-contract.json').relative_to(HERE)),
                    'acquisition': {channel['name']: {'entrypoint': 'analysis.py',
                        'method': channel['method'], 'evidence': 'channels/' + channel['name'] + '.jsonl'}
                        for channel in description['channels']},
                    'candidate_risk': {'status': 'physical',
                        'reason': 'Native walker may leave reviewed crossing corridor or all-camera footprint'},
                    'candidates': [],
                    'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                        'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}}
            else:
                entry['candidates'].append({'id': 'fallback1',
                    'construction': str((folder / name).relative_to(HERE)),
                    'construction_sha256': digest,
                    'trigger': {'source': 'original pedestrian body path and four-view pixel audit',
                        'metric': 'crossing path deviation or camera loss',
                        'failure_condition': 'primary missed reviewed complete crossing or lost a synchronized view'},
                    'changed_knobs': ['pedestrian speed 1.2 to 0.8 m/s on unchanged site and route']})
        entries.append(entry)
        print(short, 'primary/fallback1 source-deferred constructions', flush=True)
    write(HERE / 'execution-manifest.draft.json', {'format': 'worker-execution-manifest',
        'assignment_id': HERE.name,
        'status': 'reviewed_original_business_district_packet_required_at_capture',
        'runtime_manifest_sha256': hashlib.sha256((ROOT / 'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
        'cases': entries})
    first = HERE / 'cases' / plan['cases'][0]['case_id'].split('__')[-1]
    (HERE / 'construction.json').write_bytes((first / 'construction.json').read_bytes())
    (HERE / 'config.json').write_bytes((first / 'config.json').read_bytes())
    return entries


if __name__ == '__main__':
    build()
