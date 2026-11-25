"""CPU source and lifecycle fixtures for the six exact speed/conditions cases.

Synthetic histories test the saved checker; they are never accepted recordings.
"""
import hashlib
import json
from pathlib import Path

from worker_exchange.native_output import assess_physical
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
OUT = REPO / '.runtime-work/c179789-physical'
SUFFIXES = ('dry_open_traffic', 'wet_same_traffic', 'dense_traffic',
            'narrow_same_traffic', 'low_visibility', 'ice_or_snow')
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def one(case, config, kind, folder):
    folder.mkdir(parents=True, exist_ok=True)
    write(folder / 'config.json', config)
    positions = []
    for index in range(900):
        t = index / 20
        x = t * (8 if kind == 'complete_motion' else .1)
        positions.append((index + 100, t, x))
    (folder / 'video_frames.jsonl').write_text(''.join(json.dumps({
        'video_frame': index, 'carla_frame': frame, 'time_s': t}) + '\n'
        for index, (frame, t, _) in enumerate(positions)))
    (folder / 'trace.jsonl').write_text(''.join(json.dumps({
        'frame': frame, 'time_s': t, 'position_m': [x, 0, 0]}) + '\n'
        for frame, t, x in positions))
    if kind != 'missing_evidence':
        (folder / 'condition_history.jsonl').write_text(''.join(json.dumps({
            'frame': frame, 'time_s': t, 'ego_position_m': [x, 0, 0]}) + '\n'
            for frame, t, x in positions))
    assessed = assess_physical(folder, config, [])
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    maneuver = assessed['physical_checks']['maneuver']
    if maneuver['status'] != expected or assessed['maneuver_completed'] != (expected == 'met'):
        raise ValueError('Physical outcome mismatch: ' + case + ' ' + kind)
    if kind != 'missing_evidence' and assessed['physical_checks']['setup']['status'] != 'met':
        raise ValueError('Full original frame/timestamp join failed')
    motion = assessed['realized_observables'].get('original_motion', {})
    result = {'case_id': case, 'physical_checks': assessed['physical_checks'],
              'maneuver_completed': assessed['maneuver_completed'],
              'realized_observables': {'sampled_path_m': motion['sampled_path_m']}
              if motion else {}, 'provenance_kind': 'synthetic_fixture',
              'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
              'legal_conclusion': 'unresolved'}
    return result


def lifecycle():
    folder = OUT / 'lifecycle'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'construction.json').write_text('{}\n')
    (folder / 'runner.py').write_text('# CPU lifecycle fixture\n')
    (folder / 'source.txt').write_text('synthetic lifecycle source\n')
    revision = {'construction_sha256': sha(folder / 'construction.json'),
                'runner_sha256': sha(folder / 'runner.py')}
    write(folder / 'capture-seal.json', {'events': ['capture_finished', 'encoders_closed',
                                                  'restoration_verified'],
                                       'sources': {'source.txt': sha(folder / 'source.txt')},
                                       'native_revision': revision})
    record_native_exit(folder)
    try:
        _closure(folder, None, 'native', False)
    except ValueError as error:
        if 'owner-release' not in str(error):
            raise
    else:
        raise ValueError('Saved processing accepted Native source before owner release')
    receipt = folder / 'owner-release.json'
    if receipt.exists():
        receipt.unlink()
    acknowledge_owner_release(folder, receipt, True)
    _closure(folder, receipt, 'native', False)
    return {'events': ['capture_finished', 'encoders_closed', 'restoration_verified',
                       'native_exit', 'owner_released', 'saved_processing_started'],
            'early_saved_processing_rejected': True, 'exit_code': 0}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    log = []
    lifecycle_receipt = lifecycle()
    for suffix in SUFFIXES:
        path = ROOT / ('construction.json' if suffix == 'dry_open_traffic' else
                       'cases/' + suffix + '-construction.json')
        construction = json.loads(path.read_text())
        case = construction['case_id']
        files = {row['path']: row['content'] for row in construction['files']}
        config = json.loads(files['config.json'])
        for kind in KINDS:
            outcome = one(case, config, kind, OUT / suffix / kind)
            result = ROOT / 'cases' / (suffix + '-' + kind + '-physical-result.json')
            write(result, outcome)
            log.append({'case_id': case, 'kind': kind,
                        'status': outcome['physical_checks']['maneuver']['status'],
                        'result': str(result.relative_to(ROOT)), 'sha256': sha(result)})
    write(ROOT / 'cases/physical-lifecycle.json', lifecycle_receipt)
    print(json.dumps({'format': 'worker-c179789-physical-fixture-proof',
                      'fixtures': log, 'lifecycle': lifecycle_receipt,
                      'physical_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
