"""Exercise cargo transfer/rest and ownership closure using synthetic CPU rows."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

from freight_plan import PURPOSES, measure_saved
from prove_physical import PACKAGE, ROOT, lifecycle, sha, write


def assess(folder, config):
    case = config['case_id']
    source = folder / 'freight-native.jsonl'
    sources = {'freight-native.jsonl': sha(source)} if source.is_file() else {
        'config.json': sha(folder / 'config.json')}
    if not source.is_file():
        status, measured = 'unverified', {}
    else:
        try:
            measured = measure_saved([json.loads(line) for line in source.read_text().splitlines()], config)
        except (ValueError, KeyError, TypeError):
            status, measured = 'unverified', {}
        else:
            transfer = measured['cargo_transfer_motion_frames']
            displacement = measured['cargo_displacement_m']
            expected_transfer = config['requested_purpose'] != 'waiting_without_transfer'
            status = ('met' if ((transfer > 0 and displacement > 1.0) if expected_transfer
                                else (transfer == 0 and displacement < .01)) else 'not_met')
    return {'case_id': case,
            'physical_checks': {'maneuver': {
                'status': status, 'method': 'Source-shaped cargo body displacement and motion frame join; engineering request only',
                'sources': sources,
                'details': {'requested_purpose': config['requested_purpose'],
                            'observed_cargo_displacement_m': measured.get('cargo_displacement_m'),
                            'observed_transfer_frames': measured.get('cargo_transfer_motion_frames')},
                'physical_causation_claimed': False, 'legal_verdict_claimed': False}},
            'maneuver_completed': status == 'met',
            'realized_observables': ({'cargo_displacement_m': measured['cargo_displacement_m'],
                                     'cargo_transfer_motion_frames': measured['cargo_transfer_motion_frames']}
                                    if status == 'met' else {}),
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


def run(suffix):
    case = PACKAGE.name + '__' + suffix
    destination = PACKAGE / 'native-selected' / suffix
    construction_path = destination / 'construction.json'
    construction = json.loads(construction_path.read_text())
    config = json.loads(next(row['content'] for row in construction['files']
                             if row['path'] == 'config.json'))
    fixtures = []
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c150173-freight-physical-') as temporary:
        folder = Path(temporary)
        source_path = PACKAGE / 'native/freight-diagnostic' / suffix / 'sources/freight-native.jsonl'
        target = folder / 'freight-native.jsonl'
        shutil.copyfile(source_path, target)
        write(folder / 'config.json', config)
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            if kind == 'incomplete_motion':
                rows = [json.loads(line) for line in source_path.read_text().splitlines()]
                for row in rows:
                    row['cargo_transfer_motion_observed'] = (suffix == 'freight_wait')
                    if suffix != 'freight_wait':
                        center_x = 8.0 if suffix == 'freight_load' else 5.5
                        row['cargo_body_vertices_xyz_m'] = [
                            [center_x + (v[0] - sum(x[0] for x in row['cargo_body_vertices_xyz_m']) / 8),
                             v[1], v[2]] for v in row['cargo_body_vertices_xyz_m']]
                target.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            elif kind == 'missing_evidence':
                target.unlink()
            result = assess(folder, config)
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if result['physical_checks']['maneuver']['status'] != expected:
                raise ValueError('Freight physical outcome differs: ' + suffix + ' ' + kind)
            result_path = destination / ('physical-' + kind + '-result.json')
            log_path = destination / ('physical-' + kind + '.log')
            write(result_path, result)
            write(log_path, {'case_id': case, 'kind': kind, 'expected': expected,
                             'observed': expected, 'synthetic_only': True})
            fixtures.append({'kind': kind,
                'command': 'native/prove_freight_physical.py --case ' + case,
                'exit_code': 0, 'log': str(log_path.relative_to(PACKAGE)),
                'log_sha256': sha(log_path),
                'result': str(result_path.relative_to(PACKAGE)),
                'result_sha256': sha(result_path)})
            shutil.copyfile(source_path, target)
        trace = PACKAGE / 'native/freight-diagnostic' / suffix / 'sources/trace.jsonl'
        mapping = PACKAGE / 'native/freight-diagnostic' / suffix / 'sources/video_frames.jsonl'
        shutil.copyfile(trace, folder / 'trace.jsonl')
        shutil.copyfile(mapping, folder / 'video_frames.jsonl')
        life = lifecycle(folder, config, construction)
        life_path = destination / 'physical-lifecycle.log'
        write(life_path, life)
    receipt_path = destination / 'physical-preparation.json'
    write(receipt_path, {'format': 'c150173-freight-physical-preparation-cpu-v1',
        'case_id': case, 'construction_sha256': sha(construction_path),
        'fixtures': fixtures,
        'lifecycle': {'events': life['events'], 'exit_code': 0,
                      'log': str(life_path.relative_to(PACKAGE)),
                      'log_sha256': sha(life_path)},
        'original_native_executed': False})
    return {'case_id': case, 'receipt': str(receipt_path.relative_to(PACKAGE)),
            'sha256': sha(receipt_path)}


if __name__ == '__main__':
    print(json.dumps({'proofs': [run(suffix) for suffix in PURPOSES]}, sort_keys=True))
