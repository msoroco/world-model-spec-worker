"""Exercise ordered synthetic capture closure before saved-only processing."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))


def main():
    output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if REPO / '.runtime-work' not in output_root.parents:
        raise ValueError('runtime output must be under .runtime-work')
    from worker_exchange.common import read
    from worker_exchange.fixture_recipe import materialize
    from worker_exchange.package_compatibility import materialize_case
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import acknowledge_owner_release, record_native_exit, run
    manifest = ROOT / 'execution-manifest.json'
    entry = read(manifest)['cases'][0]
    scratch = REPO / '.runtime-work/c111610-283'
    fixture = scratch / 'lifecycle-v2-fixture'
    attempt = scratch / 'lifecycle-v2-attempt'
    processed = scratch / 'lifecycle-v2-processed'
    receipt_path = scratch / 'lifecycle-v2-owner-release.json'
    materialize(REPO, REPO / entry['fixture_recipe'], fixture)
    materialize_case(manifest, entry['case_id'], attempt, fixture)
    rows = (attempt / 'video_frames.jsonl').read_text().splitlines()
    seal = seal_capture(attempt, frames=len(rows), restoration={'restored': True},
                        errors=[], encoder_exit_codes={'four_views': 0},
                        context={'fixture': 'synthetic diagnostic'})
    exit_receipt = record_native_exit(attempt)
    owner = acknowledge_owner_release(attempt, receipt_path, True)
    try:
        run(manifest, entry['case_id'], attempt, processed, REPO / 'runtime/library',
            REPO / '.runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck',
            owner_receipt=receipt_path)
    except ValueError as error:
        if 'Untrusted original speed provenance' not in str(error):
            raise
        rejection = str(error)
    else:
        raise ValueError('sealed synthetic fixture unexpectedly passed Native provenance check')
    assert seal['events'] == ['capture_finished', 'encoders_closed', 'restoration_verified']
    assert exit_receipt['event'] == 'native_exit'
    assert owner['event'] == 'owner_released'
    print(json.dumps({'events': seal['events'] + [exit_receipt['event'], owner['event'],
                                       'saved_processing_started'],
                      'sealed_synthetic_rejected': rejection,
                      'provenance': 'synthetic diagnostic', 'legal_acceptance': False}))


if __name__ == '__main__':
    main()
