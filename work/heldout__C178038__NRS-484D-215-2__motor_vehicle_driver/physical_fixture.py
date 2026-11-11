"""Exercise prospective Native source handling with synthetic CPU packets only."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
sys.path.insert(0, str(HERE))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources
from headlamp_finalizer import analyze
from headlamp_delivery_audit import audit_attempt, CAMERAS
from headlamp_physical_outcome import check_physical_outcome


SOURCES = ('video_frames.jsonl', 'trace.jsonl', 'following_footprints.jsonl',
           'headlamp_readbacks.jsonl', 'roadway_environment.jsonl',
           'lighting_context.json')


def run(case_id, kind):
    entry = next((e for e in json.loads((HERE / 'execution-manifest.json').read_text())['cases']
                  if e['case_id'] == case_id), None)
    if entry is None or kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown exact physical fixture')
    with TemporaryDirectory(prefix='headlamp-motion-', dir=ROOT / '.runtime-work') as temporary:
        base = Path(temporary)
        make_fixture(ROOT, ROOT / entry['fixture_recipe'], base / 'fixture')
        make_attempt(HERE / 'execution-manifest.json', case_id, base / 'attempt')
        copy_sources(base / 'fixture', base / 'attempt')
        attempt = base / 'attempt'
        if kind == 'incomplete_motion':
            path = attempt / 'following_footprints.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            for row in rows:
                row['lead_heading_xy'] = [-v for v in row['ego_heading_xy']]
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        elif kind == 'missing_evidence':
            (attempt / 'headlamp_readbacks.jsonl').unlink()
        hashes = {name: sha256((attempt / name).read_bytes()).hexdigest()
                  for name in SOURCES if (attempt / name).is_file()}
        observation = None
        if kind == 'missing_evidence':
            try:
                analyze(attempt)
            except ValueError as error:
                if 'Missing required source: headlamp_readbacks.jsonl' not in str(error):
                    raise
                status = 'unverified'
            else:
                raise ValueError('Missing source was accepted')
        else:
            report = analyze(attempt)
            audit = audit_attempt(attempt, report)
            review = {'case_id': case_id, 'cameras': {name: {
                'source_sha256': audit['camera_decodes'][name]['source_sha256'],
                'reviewed_frames': audit['frame_count'],
                'required_bodies_visible': True, 'beam_region_visible': True}
                for name in CAMERAS},
                'civil_time_source_reviewed': True,
                'roadway_occupancy_source_reviewed': True,
                'beam_distribution_source_reviewed': True}
            target = json.loads((attempt / 'config.json').read_text())['requested_gap_ft']
            try:
                check_physical_outcome(audit, report, review, target_ft=target)
                status = 'met'
            except ValueError as error:
                if kind != 'incomplete_motion' or 'does not show following' not in str(error):
                    raise
                status = 'not_met'
            observation = report['measurements']['headlamp_following_observation']['value']
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Physical fixture outcome differs')
        return {'case_id': case_id, 'fixture_kind': kind, 'fixture_only': True,
                'diagnostic_fixture': True, 'actual_native_capture': False,
                'physical_checks': {'maneuver': {
                    'status': status,
                    'method': 'original-shaped synchronized body/lamp/roadway/frame and four-camera source protocol; synthetic fixture',
                    'sources': hashes,
                    'missing_evidence': ['headlamp_readbacks.jsonl'] if kind == 'missing_evidence' else []}},
                'maneuver_completed': status == 'met',
                'realized_observables': ({'headlamp_gap_ft': observation['minimum_surface_gap_ft'],
                                          'frame_count': len(observation['observations'])}
                                         if status == 'met' else {}),
                'provenance_kind': 'native',
                'provenance_note': 'Native-shaped synthetic test protocol; no actual Native acquisition or physical review',
                'physical_acceptance_claimed': False,
                'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True,
                        choices=('complete_motion', 'incomplete_motion', 'missing_evidence'))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(args.case, args.kind, result['physical_checks']['maneuver']['status'],
          'synthetic_fixture_only')
