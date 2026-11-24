"""Exercise synthetic capture closure and saved processing with exact source bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from worker_exchange.runtime_cli import materialize
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, run

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(case_id):
    label = case_id.rsplit('__', 1)[1]
    if case_id != ROOT.name + '__' + label or label not in ('probe_a', 'probe_b'):
        raise ValueError('Select exact curbside case')
    output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    if '.runtime-work' not in output_root.parts:
        raise ValueError('Scratch root must be under .runtime-work')
    source = REPO / '.runtime-work' / ('c230222-' + label + '-primary-compat-v6')
    receipt = json.loads((source / 'compatibility.json').read_text())
    if receipt['passed'] is not True or receipt['case_id'] != case_id:
        raise ValueError('Exact public compatibility receipt required')
    manifest = ROOT / 'draft-selected-execution-manifest.json'
    attempt = output_root / ('lifecycle-' + label + '-attempt')
    saved = output_root / ('lifecycle-' + label + '-saved')
    for stale in (attempt, saved):
        if stale.exists():
            shutil.rmtree(stale)
    materialize(manifest, case_id, attempt)
    for relative, original_sha in receipt['fixture_manifest'].items():
        file = source / relative
        destination = attempt / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, destination)
        if relative.endswith('.mkv'):
            continue  # Receipt binds decoded pixels; encoder bytes may vary.
        if sha(destination) != original_sha:
            raise ValueError('Source fingerprint changed during lifecycle staging: ' + relative)
    (attempt / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'original_native_observed': False}, indent=2) + '\n')
    seal = seal_capture(attempt, frames=600,
                        restoration={'restored': True, 'synthetic_diagnostic': True},
                        errors=[], encoder_exit_codes={name: 0 for name in
                        ('overview', 'approach', 'reference_corner', 'driver_reference')})
    exit_receipt = record_native_exit(attempt)
    owner_path = attempt / 'owner-release.json'
    owner = acknowledge_owner_release(attempt, owner_path, True)
    processed = run(manifest, case_id, attempt, saved, REPO / 'runtime/library',
                    REPO / '.runtime-work/c230222-decoder/.lake/build/bin/adapterCheck',
                    owner_path)
    events = seal['events'] + [exit_receipt['event'], owner['event'],
                                processed['events'][0]]
    expected = ['capture_finished', 'encoders_closed', 'restoration_verified',
                'native_exit', 'owner_released', 'saved_processing_started']
    if events != expected or not processed['passed'] or not processed['recorded_only']:
        raise AssertionError('Synthetic closure and saved processing order differ')
    if not processed['originals_preserved'] or processed['timestamp_joins']['frames'] != 600:
        raise AssertionError('Original source or timestamp join changed')
    log = ROOT / 'physical-preparation' / label / 'lifecycle.log'
    log.write_text('PASS ' + case_id + ' synthetic capture closure, owner release and recorded-only saved processing; 600 source joins; no physical acceptance\n')
    return {'events': events, 'exit_code': 0, 'log': str(log.relative_to(ROOT)),
            'log_sha256': sha(log), 'case_id': case_id,
            'synthetic_diagnostic': True, 'physical_acceptance_claimed': False,
            'saved_processing_receipt_sha256': sha(saved / 'v0001/processing.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    args = parser.parse_args()
    print(json.dumps(prove(args.case), indent=2))
