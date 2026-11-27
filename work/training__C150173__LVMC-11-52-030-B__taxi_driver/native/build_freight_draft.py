"""Materialize three source-shaped taxi/light-express freight constructions."""
from datetime import datetime, timedelta
import copy
import hashlib
import json
from pathlib import Path

from build_draft import CAMERAS
from build_selected_draft import NAMES
from freight_plan import PREFIX, PURPOSES, check_request

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build(suffix):
    case_id = PREFIX + suffix
    start = datetime(2026, 11, 26, 10)
    config = {'case_id': case_id, 'selected_case_id': case_id,
              'assignment_id': PREFIX[:-2], 'cell_id': 'C150173',
              'law_id': 'LVMC-11-52-030-B', 'actor': 'taxi_driver',
              'duration_s': 30, 'rate_hz': 20, 'frames': 600,
              'civil_start_local': start.isoformat(),
              'timezone': 'America/Los_Angeles',
              'requested_purpose': PURPOSES[suffix],
              'taxi_stop_x_m': 5.25,
              'cargo_blueprint_filter': 'static.prop.*box*',
              'commercial_classification': 'pending_original_review',
              'sign_source_status': 'authored_proposal_unverified',
              'legal_verdict': None, 'cameras': CAMERAS,
              'required_atoms': [], 'source_packets': [],
              'case': {'case_id': case_id, 'target_law_id': 'LVMC-11-52-030-B'}}
    road = (HERE / 'yellow-freight-road.xodr').read_text()
    check_request(config, road)
    rows = [{'video_frame': i, 'time_s': (i + 1) / 20,
             'source_kind': 'authored_native_request',
             'civil_time_local': (start + timedelta(seconds=(i + 1) / 20)).isoformat(timespec='milliseconds'),
             'requested_taxi_role': 'taxi_unverified',
             'requested_purpose': PURPOSES[suffix],
             'requested_stop_x_m': config['taxi_stop_x_m'],
             'requested_cargo_proxy': config['cargo_blueprint_filter'],
             'commercial_classification': 'pending_original_review',
             'sign_authority': 'pending_original_review'} for i in range(600)]
    track = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows)
    files = [{'path': target, 'content': (HERE / source).read_text()}
             for source, target in (('freight_runner.py', 'runner.py'),
                                    ('freight_plan.py', 'freight_plan.py'),
                                    ('freight_finalize.py', 'freight_finalize.py'),
                                    ('freight_seal_review.py', 'freight_seal_review.py'),
                                    ('yellow-freight-road.xodr', 'yellow-freight-road.xodr'))]
    test = '''import unittest\nfrom pathlib import Path\nfrom runner import offline_check\n\nclass FreightRequest(unittest.TestCase):\n def test_exact_source_request(self):\n  result=offline_check(Path('.'))\n  self.assertEqual(result['request_frames'],600)\n  self.assertFalse(result['commercial_status_verified'])\n  self.assertFalse(result['sign_authority_verified'])\n'''
    files.extend(({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                  {'path': 'requested-track.jsonl', 'content': track},
                  {'path': 'tests/test_offline.py', 'content': test}))
    construction = {'case_id': case_id, 'cell_id': 'C150173',
                    'law_id': 'LVMC-11-52-030-B', 'actor': 'taxi_driver',
                    'entrypoint': 'runner.py', 'files': files,
                    'measurement_plan': {'method': 'source_hashed_freight_body_join',
                                         'entrypoint': 'freight_finalize.py'},
                    'recording_description': {
                        'duration_s': 30, 'rate_hz': 20,
                        'source_cameras': [c['name'] for c in CAMERAS],
                        'channels': [{'name': name, 'unit': 'source observation',
                                      'method': 'saved Native frame, body and independent review join',
                                      'reference_frame': 'C150173 taxi, cargo and curb source frames',
                                      'sampling_rate_hz': 20, 'time_window': '600 frames / 30 s',
                                      'uncertainty': 'Original identity, freight status, sign and legal eligibility require review'}
                                     for name in NAMES],
                        'context_inputs': [],
                        'limitations': ['Synthetic CPU sources prove software behavior only',
                                        'Commercial classification, effective sign and actual freight purpose require original review'],
                        'yellow_curb_and_freight_sign_source_required': True,
                        'taxicab_and_commercial_status_independent_review_required': True,
                        'actual_freight_transfer_source_required': True,
                        'legal_verdict': None},
                    'static_checks': ['freight_plan.check_request',
                                      'freight_runner.offline_check'],
                    'termination_rules': {'frames': 600,
                                          'stop_on_missing_source': True},
                    'mechanisms': ['taxi parking lane readback',
                                   'independent cargo-proxy actor',
                                   'per-frame cargo body extents and four camera sources'],
                    'status': 'source_shaped_freight_draft'}
    path = BASE / 'native-freight-draft' / suffix / 'construction.json'
    write(path, construction)
    fallback = copy.deepcopy(construction)
    fallback['candidate_id'] = 'fallback1'
    fallback_config = {**config, 'candidate_id': 'fallback1', 'taxi_stop_x_m': 4.75}
    check_request(fallback_config, road)
    for row in fallback['files']:
        if row['path'] == 'config.json':
            row['content'] = json.dumps(fallback_config, indent=2) + '\n'
        if row['path'] == 'requested-track.jsonl':
            row['content'] = ''.join(json.dumps({**item, 'requested_stop_x_m': 4.75}, sort_keys=True) + '\n'
                                    for item in rows)
    fallback_path = BASE / 'native-freight-draft' / suffix / 'fallback1-construction.json'
    write(fallback_path, fallback)
    return {'case_id': case_id, 'construction': str(path.relative_to(BASE)),
            'construction_sha256': sha(path), 'status': 'source_shaped_freight_draft',
            'candidate_risk': {'status': 'physical',
                               'reason': 'Taxi or cargo may obscure freight sign in original reference view.'},
            'candidates': [{'id': 'fallback1',
                            'construction': str(fallback_path.relative_to(BASE)),
                            'construction_sha256': sha(fallback_path),
                            'trigger': {'source': 'original reference_corner.mkv and sign review',
                                        'metric': 'visible freight sign near stopped taxi',
                                        'failure_condition': 'original taxi/cargo pose obscures sign or curb'},
                            'changed_knobs': ['taxi stop x coordinate 5.25 to 4.75 m; freight purpose, four views and sign fixed']}]}


def main():
    cases = [build(suffix) for suffix in PURPOSES]
    write(BASE / 'native-freight-draft-manifest.json', {
        'format': 'c150173-source-shaped-taxi-freight-draft-v1',
        'assignment_id': PREFIX[:-2], 'cases': cases,
        'original_native_observed': False, 'delivery_ready': False})
    print(json.dumps({'cases': len(cases), 'ids': [c['case_id'] for c in cases]}))


if __name__ == '__main__':
    main()
