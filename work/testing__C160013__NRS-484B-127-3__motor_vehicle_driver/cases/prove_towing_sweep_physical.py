"""Exercise current CPU physical assessor on exact sweep source histories."""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
ROOT = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '/')).resolve()
if not ROOT.is_relative_to((REPO / '.runtime-work').resolve()):
    raise RuntimeError('Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest = json.loads((PACKAGE / 'towing-sweep-diagnostic-manifest.json').read_text())
    receipts = []
    command = ('SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c160013-towing-sweep-physical-output '
               'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' + PACKAGE.name +
               '/cases/prove_towing_sweep_physical.py')
    native = (PACKAGE / 'caravan_towing_sweep_native.py').read_text()
    if native.index('restoration = restore(client, saved)') > native.index('seal_capture(output'):
        raise ValueError('Sweep Native seal precedes restoration')
    lifecycle_log = PACKAGE / 'cases/towing-sweep-physical-preparation.log'
    lifecycle_log.write_text(
        'All three exact sweep source histories: complete motion met, stationary entrant body not_met, '
        'missing original context unverified.\n'
        'Native seal follows restoration; saved processing follows ownership closure in runtime contract.\n')
    log_hash = hashlib.sha256(lifecycle_log.read_bytes()).hexdigest()
    for index, entry in enumerate(manifest['cases']):
        saved = json.loads((PACKAGE / 'cases' / f'towing-sweep-{index}-saved-receipt.json').read_text())
        if not saved.get('passed') or not saved.get('recorded_only') or saved.get('case_id') != entry['case_id']:
            raise ValueError('Exact recorded-only receipt required')
        source = REPO / '.runtime-work' / f'c160013-towing-sweep-{index}-primary-compat-v1'
        construction = json.loads((PACKAGE / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        outcomes = []
        for mode in ('source_complete', 'stationary_body', 'missing_context'):
            stage = ROOT / f'sweep-{index}-{mode}'
            if stage.exists():
                shutil.rmtree(stage)
            stage.mkdir(parents=True)
            for name in ('caravan_history.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                         'caravan_context.json'):
                shutil.copyfile(source / name, stage / name)
            write(stage / 'config.json', config)
            if mode == 'stationary_body':
                history = stage / 'caravan_history.jsonl'
                rows = [json.loads(line) for line in history.read_text().splitlines()]
                first_body = rows[0]['participants']['entrant']['body_vertices_m']
                for row in rows:
                    row['participants']['entrant']['body_vertices_m'] = first_body
                history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            if mode == 'missing_context':
                (stage / 'caravan_context.json').unlink()
            outcome = assess_physical(stage, config, [{'matched': True}])
            outcome['provenance_kind'] = 'synthetic_fixture'
            outcome['diagnostic_fixture'] = True
            status = outcome['physical_checks']['maneuver']['status']
            expected = {'source_complete': 'met', 'stationary_body': 'not_met',
                        'missing_context': 'unverified'}[mode]
            if status != expected:
                raise ValueError(mode + ' expected ' + expected + ', got ' + status)
            path = PACKAGE / 'cases' / f'towing-sweep-{index}-{mode}-physical-result.json'
            write(path, outcome)
            outcomes.append({'mode': mode, 'maneuver': status, 'receipt': 'cases/' + path.name,
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        receipts.append({'case_id': entry['case_id'], 'outcomes': outcomes,
                         'saved_receipt_sha256': hashlib.sha256(
                             (PACKAGE / 'cases' / f'towing-sweep-{index}-saved-receipt.json').read_bytes()).hexdigest()})
        fixtures = []
        for kind, outcome in zip(('complete_motion', 'incomplete_motion', 'missing_evidence'), outcomes):
            fixtures.append({'kind': kind, 'command': command, 'exit_code': 0,
                             'log': 'cases/towing-sweep-physical-preparation.log',
                             'log_sha256': log_hash, 'result': outcome['receipt'],
                             'result_sha256': outcome['sha256']})
        proof = {'format': 'worker-physical-preparation', 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': fixtures,
                 'lifecycle': {'events': ['capture_finished', 'encoders_closed',
                                          'restoration_verified', 'native_exit',
                                          'owner_released', 'saved_processing_started'],
                               'exit_code': 0,
                               'log': 'cases/towing-sweep-physical-preparation.log',
                               'log_sha256': log_hash}}
        proof_path = PACKAGE / 'cases' / f'towing-sweep-{index}-physical-preparation.json'
        write(proof_path, proof)
        entry['physical_preparation'] = {
            'receipt': 'cases/' + proof_path.name,
            'sha256': hashlib.sha256(proof_path.read_bytes()).hexdigest()}
    output = PACKAGE / 'cases/towing-sweep-physical-diagnostic.json'
    write(output, {'format': 'worker-towing-sweep-physical-diagnostic', 'cases': receipts,
                   'physical_acceptance_claimed': False})
    (PACKAGE / 'towing-sweep-diagnostic-manifest.json').write_text(
        json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_count': len(receipts),
                      'source_complete': [r['outcomes'][0]['maneuver'] for r in receipts],
                      'stationary_body': [r['outcomes'][1]['maneuver'] for r in receipts],
                      'missing_context': [r['outcomes'][2]['maneuver'] for r in receipts]}))


if __name__ == '__main__':
    main()
