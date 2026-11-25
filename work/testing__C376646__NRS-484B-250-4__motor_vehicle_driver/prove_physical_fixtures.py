"""Source-shaped CPU classifier and ownership fixtures; no Native acceptance claim."""
import hashlib
import io
import json
import shlex
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(entry, kind, source, saved):
    with tempfile.TemporaryDirectory(prefix='c376646-physical-') as directory:
        root = Path(directory)
        names = ('config.json', 'trace.jsonl', 'video_frames.jsonl',
                 'vehicle_signal_history.jsonl', 'junction_context.json')
        for name in names:
            shutil.copy2(source / name, root / name)
        if read(root / 'config.json')['selected_case_id'] != entry['case_id']:
            raise ValueError('Wrong selected source')
        write(root / 'acquisition-provenance.json', {
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'scope': 'Source-shaped CPU classifier fixture only'})
        motion = root / 'vehicle_signal_history.jsonl'
        rows = [json.loads(line) for line in motion.read_text().splitlines()]
        if kind == 'complete_motion':
            for point in rows[-2]['ego']['body_vertices_xy_m']:
                point[0] += 7.0
            body = rows[-1]['ego']['body_vertices_xy_m']
            original_x = body[0][0]
            for point in body:
                point[0] = 12.0 + (point[0] - original_x)
        elif kind == 'incomplete_motion':
            first = rows[0]['ego']['body_vertices_xy_m']
            for row in rows:
                row['ego']['body_vertices_xy_m'] = first
        elif kind == 'missing_evidence':
            motion.unlink()
        else:
            raise ValueError('Unknown outcome fixture')
        if motion.exists():
            motion.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
        result = physical_result(root, {'target_checks': []})
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if (result['physical_checks']['maneuver']['status'] != expected or
                result['maneuver_completed'] != (expected == 'met') or
                result['provenance_kind'] != 'synthetic_fixture' or
                result['physical_acceptance_claimed'] is not False):
            raise ValueError('Classifier outcome mismatch for ' + kind)
        if kind == 'complete_motion' and not result['realized_observables']:
            raise ValueError('Missing measured fixture observations')
        return result


def lifecycle(source, saved):
    with tempfile.TemporaryDirectory(prefix='c376646-lifecycle-') as directory:
        root = Path(directory)
        shutil.copy2(source / 'video_frames.jsonl', root / 'video_frames.jsonl')
        shutil.copy2(source / 'trace.jsonl', root / 'trace.jsonl')
        shutil.copy2(source / 'construction.json', root / 'construction.json')
        construction = read(root / 'construction.json')
        (root / 'runner.py').write_text(next(f['content'] for f in construction['files']
                                             if f['path'] == 'runner.py'))
        write(root / 'acquisition-provenance.json', {
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
        resource = io.StringIO('fixture camera'); resource.close()
        if not resource.closed:
            raise ValueError('Camera resource remains open')
        frames = sum(bool(line.strip()) for line in (root / 'video_frames.jsonl').read_text().splitlines())
        seal = seal_capture(root, frames=frames,
                            restoration={'restored': True, 'fixture_only': True},
                            errors=[], encoder_exit_codes={'fixture_encoder': 0},
                            context={'diagnostic_fixture': True})
        exited = record_native_exit(root)
        released = acknowledge_owner_release(root, root / 'owner-release.json', True)
        receipt = read(saved)
        if receipt.get('passed') is not True or receipt.get('recorded_only') is not True:
            raise ValueError('Current saved-processing receipt required')
        events = seal['events'] + [exited['event'], released['event'], receipt['events'][0]]
        expected = ['capture_finished', 'encoders_closed', 'restoration_verified',
                    'native_exit', 'owner_released', 'saved_processing_started']
        if events != expected:
            raise ValueError('Ownership event ordering differs')
        return events


def main():
    manifest_path = HERE / 'review-draft-manifest.json'
    manifest = read(manifest_path)
    proof_root = HERE / 'physical-proofs'
    proof_root.mkdir(exist_ok=True)
    records = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        tokens = shlex.split(entry['compatibility']['replay_command'])
        source = REPO / tokens[tokens.index('--output') + 1]
        saved_tokens = shlex.split(entry['post_capture']['command'])
        saved_root = REPO / saved_tokens[saved_tokens.index('--output') + 1] / 'v0001'
        saved = saved_root / 'processing.json'
        if not saved.is_file():
            raise ValueError('Saved processing receipt lookup failed: ' + str(saved_root))
        folder = proof_root / suffix
        folder.mkdir(exist_ok=True)
        fixture_rows = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            output = folder / (kind + '.json')
            write(output, run(entry, kind, source, saved))
            fixture_rows.append((kind, output))
        events = lifecycle(source, saved)
        records.append((entry, folder, source, saved, fixture_rows, events))
    log = proof_root / 'cpu-physical-fixtures.log'
    log.write_text(''.join(f"{entry['case_id']}: met/not_met/unverified; lifecycle ordered; synthetic only\n"
                           for entry, *_ in records))
    for entry, folder, source, saved, fixtures, events in records:
        receipt = {'format': 'worker-physical-preparation-fixtures',
                   'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                   'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
                   'saved_processing_sha256': sha(saved), 'fixtures': []}
        for kind, output in fixtures:
            receipt['fixtures'].append({
                'kind': kind,
                'command': f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python {Path(__file__).relative_to(REPO)}',
                'exit_code': 0, 'log': str(log.relative_to(HERE)),
                'log_sha256': sha(log), 'result': str(output.relative_to(HERE)),
                'result_sha256': sha(output)})
        receipt['lifecycle'] = {'events': events, 'exit_code': 0,
                                'log': str(log.relative_to(HERE)), 'log_sha256': sha(log)}
        path = folder / 'receipt.json'
        write(path, receipt)
        entry['physical_preparation'] = {'receipt': str(path.relative_to(HERE)), 'sha256': sha(path)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
    write(manifest_path, manifest)
    print(log.read_text(), end='')


if __name__ == '__main__':
    main()
