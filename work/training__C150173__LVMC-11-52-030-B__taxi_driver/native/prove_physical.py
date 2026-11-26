"""Exercise taxi standing completion and ownership closure on synthetic sources."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

from finalize_original import SOURCES, inspect

PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import seal_capture  # noqa: E402
from worker_exchange.saved_processing import (  # noqa: E402
    record_native_exit, acknowledge_owner_release)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def source_fixture(folder, suffix):
    source = PACKAGE / 'native/diagnostic' / suffix / 'sources'
    for name in SOURCES:
        target = folder / name
        if name.endswith('.mkv'):
            target.write_bytes(b'synthetic camera placeholder, not original video')
        elif name == 'yellow-road.xodr':
            target.write_bytes((PACKAGE / 'native/yellow-road.xodr').read_bytes())
        else:
            shutil.copyfile(source / name, target)
    construction = json.loads((PACKAGE / 'native-selected' / suffix / 'construction.json').read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    write(folder / 'config.json', config)
    return config, construction


def seal_synthetic(folder):
    write(folder / 'source-manifest.json', {
        'source_kind': 'synthetic_cpu_fixture',
        'sha256': {name: sha(folder / name) for name in SOURCES}})


def assess(folder, case_id):
    sources = {name: sha(folder / name) for name in SOURCES if (folder / name).is_file()}
    try:
        measured = inspect(folder, folder / 'source-manifest.json',
                           'synthetic_cpu_fixture')
    except (ValueError, KeyError, OSError, TypeError) as error:
        status, detail = 'unverified', str(error)
        observations = {}
    else:
        status = ('met' if measured['stopped_frames'] == 600 and
                  measured['yellow_zone_body_frames'] == 600 else 'not_met')
        detail = ('Full source-joined taxi rest interval within authored yellow zone'
                  if status == 'met' else
                  'Taxi rest or yellow-zone body occupancy did not cover full interval')
        observations = {'stopped_frames': measured['stopped_frames'],
                        'yellow_zone_body_frames': measured['yellow_zone_body_frames'],
                        'posted_active_stopped_frames':
                            measured['posted_active_stopped_frames']}
    return {'case_id': case_id,
            'physical_checks': {'maneuver': {
                'status': status,
                'method': 'Source-joined original-style body and velocity samples; engineering rest criterion only',
                'sources': sources, 'details': {'reason': detail},
                'physical_causation_claimed': False,
                'legal_verdict_claimed': False}},
            'maneuver_completed': status == 'met',
            'realized_observables': observations if status == 'met' else {},
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


def lifecycle(folder, config, construction):
    sub = folder / 'lifecycle'
    sub.mkdir()
    write(sub / 'config.json', config)
    (sub / 'runner.py').write_text('synthetic lifecycle runner\n')
    (sub / 'trace.jsonl').write_bytes((folder / 'trace.jsonl').read_bytes())
    (sub / 'video_frames.jsonl').write_bytes((folder / 'video_frames.jsonl').read_bytes())
    write(sub / 'construction.json', construction)
    write(sub / 'acquisition-provenance.json', {'diagnostic_fixture': True})
    seal = seal_capture(sub, frames=600, restoration={'restored': True}, errors=[],
                        encoder_exit_codes={'overview': 0})
    native = record_native_exit(sub)
    owner = acknowledge_owner_release(sub, folder / 'owner-release.json', True)
    events = seal['events'] + [native['event'], owner['event'],
                               'saved_processing_started']
    expected = ['capture_finished', 'encoders_closed', 'restoration_verified',
                'native_exit', 'owner_released', 'saved_processing_started']
    if events != expected:
        raise ValueError('Taxi saved processing began before Native ownership closure')
    return {'events': events, 'capture_seal_sha256': sha(sub / 'capture-seal.json'),
            'native_exit_sha256': sha(sub / 'native-exit.json'),
            'owner_release_sha256': sha(folder / 'owner-release.json')}


def run(suffix):
    case = PACKAGE.name + '__' + suffix
    destination = PACKAGE / 'native-selected' / suffix
    construction_path = destination / 'construction.json'
    fixtures = []
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c150173-physical-') as temporary:
        folder = Path(temporary)
        config, construction = source_fixture(folder, suffix)
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            source = folder / 'yellow-zone-native.jsonl'
            if kind == 'incomplete_motion':
                rows = [json.loads(line) for line in source.read_text().splitlines()]
                for row in rows:
                    row['taxi_velocity_xyz_mps'] = [4.0, 0.0, 0.0]
                source.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            elif kind == 'missing_evidence':
                source.unlink()
            if kind != 'missing_evidence':
                seal_synthetic(folder)
            result = assess(folder, case)
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if result['physical_checks']['maneuver']['status'] != expected:
                raise ValueError(kind + ' taxi physical assessment differs')
            result_path = destination / ('physical-' + kind + '-result.json')
            log_path = destination / ('physical-' + kind + '.log')
            write(result_path, result)
            write(log_path, {'case_id': case, 'kind': kind,
                             'expected': expected, 'observed': expected,
                             'synthetic_only': True})
            fixtures.append({'kind': kind,
                'command': 'native/prove_physical.py --case ' + case,
                'exit_code': 0, 'log': str(log_path.relative_to(PACKAGE)),
                'log_sha256': sha(log_path),
                'result': str(result_path.relative_to(PACKAGE)),
                'result_sha256': sha(result_path)})
            shutil.copyfile(PACKAGE / 'native/diagnostic' / suffix / 'sources' /
                            'yellow-zone-native.jsonl', source)
            seal_synthetic(folder)
        life = lifecycle(folder, config, construction)
        life_path = destination / 'physical-lifecycle.log'
        write(life_path, life)
    receipt_path = destination / 'physical-preparation.json'
    write(receipt_path, {
        'format': 'c150173-physical-preparation-cpu-proof-v1',
        'case_id': case, 'construction_sha256': sha(construction_path),
        'fixtures': fixtures,
        'lifecycle': {'events': life['events'], 'exit_code': 0,
                      'log': str(life_path.relative_to(PACKAGE)),
                      'log_sha256': sha(life_path)},
        'original_native_executed': False})
    return {'case_id': case, 'receipt': str(receipt_path.relative_to(PACKAGE)),
            'sha256': sha(receipt_path)}


if __name__ == '__main__':
    print(json.dumps({'proofs': [run(s) for s in
                      ('probe_a', 'probe_b', 'probe_c', 'probe_d')]}, sort_keys=True))
