"""Materialize and seal a diagnostic acquisition for saved-only CPU proof."""
import argparse
import json
import shutil
from pathlib import Path

from scenario_pipeline.worker_exchange.fixture_recipe import materialize
from scenario_pipeline.worker_exchange.package_compatibility import materialize_case
from scenario_pipeline.worker_exchange.native_output import seal_capture
from scenario_pipeline.worker_exchange.saved_processing import acknowledge_owner_release, record_native_exit

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def main(suffix, fixture, attempt):
    fixture, attempt = Path(fixture).resolve(), Path(attempt).resolve()
    assert REPO / '.runtime-work' in fixture.parents
    assert REPO / '.runtime-work' in attempt.parents
    for path in (fixture, attempt):
        if path.exists():
            shutil.rmtree(path)
    case = ROOT.name + '__' + suffix
    materialize(REPO, ROOT / 'diagnostic' / suffix / 'fixture-recipe.json', fixture)
    materialize_case(ROOT / 'selected-public-draft-manifest.json', case, attempt, fixture)
    (attempt / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
    seal_capture(attempt, frames=600, restoration={'restored': True}, errors=[],
                 encoder_exit_codes={name: 0 for name in
                                     ('overview', 'approach', 'reference_corner', 'driver_reference')})
    record_native_exit(attempt)
    acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
    print(json.dumps({'case_id': case, 'attempt': str(attempt),
                      'provenance_kind': 'synthetic_fixture'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('bicycle_pass_wide', 'electric_bicycle_pass_wide',
                                            'electric_bicycle_pass_narrow'), required=True)
    parser.add_argument('--fixture', required=True)
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    main(args.case, args.fixture, args.attempt)
