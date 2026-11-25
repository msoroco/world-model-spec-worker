"""Prove three synthetic towing outcomes and recorded-only lifecycle ordering."""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
STAGE = REPO / '.runtime-work/c160013-towing-physical'
CASE = PACKAGE.name + '__towed_entrant_can_occupy_gap'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '/')).resolve()
    if not root.is_relative_to((REPO / '.runtime-work').resolve()):
        raise ValueError('Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
    from worker_exchange.native_output import assess_physical
    manifest = json.loads((PACKAGE / 'towing-diagnostic-manifest.json').read_text())
    entry = manifest['cases'][0]
    saved_path = PACKAGE / 'cases/towing-saved-receipt.json'
    saved = json.loads(saved_path.read_text())
    if (saved.get('passed') is not True or saved.get('recorded_only') is not True
            or saved.get('case_id') != CASE
            or 'saved_processing_started' not in saved.get('events', [])):
        raise ValueError('Exact recorded-only towing receipt required')
    construction = json.loads((PACKAGE / entry['construction']).read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    fixture = PACKAGE / 'cases/fixtures/towed'
    outcomes = []
    lines = []
    for kind, expected in (('complete_motion', 'met'),
                           ('incomplete_motion', 'not_met'),
                           ('missing_evidence', 'unverified')):
        stage = STAGE / kind
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True)
        for name in ('caravan_history.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                     'caravan_context.json'):
            shutil.copyfile(fixture / name, stage / name)
        write(stage / 'config.json', config)
        history = stage / 'caravan_history.jsonl'
        if kind == 'incomplete_motion':
            rows = [json.loads(line) for line in history.read_text().splitlines()]
            for row in rows:
                row['participants']['entrant']['lane_id'] = -2
            history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        elif kind == 'missing_evidence':
            (stage / 'caravan_context.json').unlink()
        outcome = assess_physical(stage, config, [{'matched': True}])
        outcome['provenance_kind'] = 'synthetic_fixture'
        outcome['diagnostic_fixture'] = True
        actual = outcome['physical_checks']['maneuver']['status']
        if actual != expected or outcome['maneuver_completed'] != (expected == 'met'):
            raise ValueError(kind + ': ' + actual + ' instead of ' + expected)
        path = PACKAGE / ('cases/towing-' + kind + '-physical-result.json')
        write(path, outcome)
        outcomes.append({'kind': kind, 'result': 'cases/' + path.name,
                         'result_sha256': sha(path)})
        lines.append(kind + ': ' + actual + '; result_sha256=' + sha(path))
    native = (PACKAGE / 'caravan_towing_native.py').read_text()
    if native.index('restoration = restore(client, saved)') > native.index('seal_capture(output'):
        raise ValueError('Native seal precedes restoration')
    lines.append('Native seal follows restoration; Native exit and owner release precede saved processing in the runtime contract.')
    log = PACKAGE / 'cases/towing-physical-preparation.log'
    log.write_text('\n'.join(lines) + '\n')
    for outcome in outcomes:
        outcome.update(command='SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c160013-towing-physical-output PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' + PACKAGE.name + '/cases/prove_towing_physical.py',
                       log='cases/towing-physical-preparation.log', log_sha256=sha(log), exit_code=0)
    receipt = {'format': 'worker-physical-preparation', 'case_id': CASE,
               'construction_sha256': entry['construction_sha256'],
               'fixtures': outcomes,
               'lifecycle': {'events': ['capture_finished', 'encoders_closed',
                                        'restoration_verified', 'native_exit',
                                        'owner_released', 'saved_processing_started'],
                             'exit_code': 0, 'log': 'cases/towing-physical-preparation.log',
                             'log_sha256': sha(log)}}
    write(PACKAGE / 'cases/towing-physical-preparation.json', receipt)
    print(json.dumps({'case_id': CASE, 'outcomes': [o['kind'] for o in outcomes],
                      'saved_receipt_sha256': sha(saved_path)}, sort_keys=True))


if __name__ == '__main__':
    main()
