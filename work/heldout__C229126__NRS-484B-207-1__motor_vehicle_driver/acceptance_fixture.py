"""CPU acceptance protocol for exact C229126 diagnostic sources only."""

import argparse
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',
                      str(ROOT / '.runtime-work/c229126-pipeline-output'))
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources
from delivery_audit import audit
from overtake_finalizer import analyze


def run(case_id, negative=False):
    manifest = HERE / 'execution-manifest.json'
    entries = [e for e in json.loads(manifest.read_text())['cases']
               if e['case_id'] == case_id]
    if len(entries) != 1:
        raise ValueError('Unknown exact C229126 case')
    with TemporaryDirectory(prefix='c229126-acceptance-',
                            dir=ROOT / '.runtime-work') as temp:
        base = Path(temp)
        make_fixture(ROOT, ROOT / entries[0]['fixture_recipe'], base / 'fixture')
        make_attempt(manifest, case_id, base / 'attempt')
        copy_sources(base / 'fixture', base / 'attempt')
        source = audit(base / 'attempt', case_id)
        analysis = analyze(base / 'attempt')
        observation = analysis['measurements']['overtake_sequence']['value']
        if (not source['source_checks_passed'] or
                observation['frame_count'] != source['frame_count'] or
                not observation['all_abreast_left']):
            raise ValueError('Original source and measured pass disagree')
        review = {name: {'source_sha256': detail['sha256'],
                         'reviewed_frames': detail['frames'],
                         'both_bodies_visible': True, 'roadway_visible': True}
                  for name, detail in source['camera_sources'].items()}
        if negative:
            review['approach']['source_sha256'] = 'stale diagnostic source'
        for name, detail in source['camera_sources'].items():
            selected = review[name]
            if (selected['source_sha256'] != detail['sha256'] or
                    selected['reviewed_frames'] != source['frame_count'] or
                    not selected['both_bodies_visible'] or
                    not selected['roadway_visible']):
                raise ValueError('Missing, stale, or failed original-pixel review: ' + name)
        print(json.dumps({'case_id': case_id, 'fixture_only': True,
                          'frame_count': source['frame_count'],
                          'four_source_decodes': sorted(review),
                          'physical_completion_verified': False,
                          'actual_pixel_visibility_verified': False,
                          'legal_acceptance_claimed': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    run(args.case, args.negative)
