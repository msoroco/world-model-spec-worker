"""Exact-case CPU fixture for independent source and physical-outcome checks.

The fixture supplies synthetic pixel-review declarations solely to exercise
acceptance logic. It does not verify actual body visibility or legal facts.
"""
import argparse
from hashlib import sha256
import importlib.util
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

folder = Path(__file__).resolve().parent
repo = folder.parents[1]
sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources


def sibling(name, source_folder=folder):
    spec = importlib.util.spec_from_file_location(name, source_folder / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(case_id, negative=False):
    manifest = json.loads((folder / 'execution-manifest.json').read_text())
    entry = next((item for item in manifest['cases'] if item['case_id'] == case_id), None)
    if entry is None:
        raise ValueError('Unknown exact case: ' + case_id)
    outcome = sibling('physical_outcome')
    with TemporaryDirectory(prefix='fire-acceptance-', dir=repo / '.runtime-work') as temp:
        base = Path(temp)
        fixture, attempt = base / 'fixture', base / 'attempt'
        make_fixture(repo, repo / entry['fixture_recipe'], fixture)
        make_attempt(folder / 'execution-manifest.json', case_id, attempt)
        copy_sources(fixture, attempt)
        source = sibling('delivery_audit', attempt)
        analysis = source._finalizer().analyze(attempt, write_channel=False)
        audited = source.audit_attempt(attempt, analysis)
        config = json.loads((attempt / 'config.json').read_text())
        target = config['target_distance_ft']
        review = {
            'case_id': case_id, 'alarm_premise_source_reviewed': True,
            'authorization_source_reviewed': True,
            'official_business_source_reviewed': True,
            'cameras': {name: {'source_sha256': detail['source_sha256'],
                               'reviewed_frames': audited['frame_count'],
                               'required_bodies_visible': True}
                        for name, detail in audited['camera_decodes'].items()},
        }
        if negative:
            review['cameras']['approach']['source_sha256'] = 'stale synthetic source'
        result = outcome.check_physical_outcome(audited, analysis, review, target_ft=target)
        print(json.dumps({'fixture_only': True, 'case_id': case_id,
                          'source_frame_count': audited['frame_count'],
                          'source_decoded_cameras': list(audited['camera_decodes']),
                          'outcome_checker': result,
                          'actual_visibility_verified': False,
                          'physical_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    run(args.case, args.negative)
