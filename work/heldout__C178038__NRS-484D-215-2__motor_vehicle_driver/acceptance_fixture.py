"""Exercise exact-case source, pixel-review binding and stale-source rejection."""

import argparse
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
from headlamp_delivery_audit import audit_attempt
from headlamp_physical_outcome import check_physical_outcome


def run(case_id, negative=False):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((item for item in manifest['cases'] if item['case_id'] == case_id), None)
    if entry is None:
        raise ValueError('Unknown exact case: ' + case_id)
    with TemporaryDirectory(prefix='headlamp-acceptance-', dir=ROOT / '.runtime-work') as temporary:
        base = Path(temporary)
        make_fixture(ROOT, ROOT / entry['fixture_recipe'], base / 'fixture')
        make_attempt(HERE / 'execution-manifest.json', case_id, base / 'attempt')
        copy_sources(base / 'fixture', base / 'attempt')
        attempt = base / 'attempt'
        analysis = analyze(attempt)
        audited = audit_attempt(attempt, analysis)
        config = json.loads((attempt / 'config.json').read_text())
        review = {'case_id': case_id, 'cameras': {name: {
            'source_sha256': detail['source_sha256'],
            'reviewed_frames': audited['frame_count'],
            'required_bodies_visible': True, 'beam_region_visible': True}
            for name, detail in audited['camera_decodes'].items()},
            'civil_time_source_reviewed': True,
            'roadway_occupancy_source_reviewed': True,
            'beam_distribution_source_reviewed': True}
        if negative:
            review['cameras']['approach']['source_sha256'] = 'stale synthetic source'
        result = check_physical_outcome(audited, analysis, review,
                                        target_ft=config['requested_gap_ft'])
        print(json.dumps({'fixture_only': True, 'case_id': case_id,
                          'source_frame_count': audited['frame_count'],
                          'source_decoded_cameras': list(audited['camera_decodes']),
                          'outcome_checker': result,
                          'actual_visibility_verified': False,
                          'physical_acceptance_claimed': False,
                          'legal_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    run(args.case, args.negative)
