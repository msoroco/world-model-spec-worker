"""Source-bound synthetic physical completion and closure-order CPU fixtures."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from worker_exchange.native_output import physical_result
from worker_exchange.saved_processing import _closure

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def one(slug, kind, output):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'].endswith('__' + slug))
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_observed': False, 'physical_acceptance_claimed': False}
    scratch = REPO / '.runtime-work/nrs2572-physical-tests'
    scratch.mkdir(parents=True, exist_ok=True)
    if kind == 'lifecycle':
        with tempfile.TemporaryDirectory(prefix='closure-', dir=scratch) as temporary:
            try:
                _closure(Path(temporary), None, 'native', False)
            except ValueError as error:
                if 'owner-release receipt' not in str(error):
                    raise
            else:
                raise AssertionError('Premature Native saved processing was accepted')
        saved = HERE / 'saved' / (slug + '-processing.json')
        receipt = json.loads(saved.read_text())
        if receipt.get('passed') is not True or receipt.get('recorded_only') is not True:
            raise ValueError('Recorded-only diagnostic processing receipt missing')
        base.update(events=EVENTS, exit_code=0, premature_saved_processing_rejected=True,
                    recorded_only_diagnostic_receipt_sha256=sha(saved))
    else:
        with tempfile.TemporaryDirectory(prefix='motion-', dir=scratch) as temporary:
            root = Path(temporary)
            source = HERE / 'selected-source' / slug
            for name in ('trace.jsonl', 'video_frames.jsonl', 'nonthrough_saved_packet.json',
                         'road.xodr', 'entrance_controls.json'):
                shutil.copyfile(source / name, root / name)
            config = HERE / ('config.json' if slug == 'stop_unobligated_inside' else 'config-' + slug + '.json')
            shutil.copyfile(config, root / 'config.json')
            packet = json.loads((root / 'nonthrough_saved_packet.json').read_text())
            frames = packet['frames']
            if kind == 'incomplete_motion':
                for frame in frames:
                    delta = -45 - (min(point[0] for point in frame['subject_body_vertices_m']) +
                                   max(point[0] for point in frame['subject_body_vertices_m'])) / 2
                    for point in frame['subject_body_vertices_m']:
                        point[0] += delta
                (root / 'nonthrough_saved_packet.json').write_text(json.dumps(packet, separators=(',', ':')) + '\n')
            if kind != 'missing_evidence':
                (root / 'interaction_history.jsonl').write_text(''.join(
                    json.dumps({'frame': frame['native_frame'], 'time_s': frame['t_s'],
                                'ego': {'body_vertices_m': frame['subject_body_vertices_m']}},
                               allow_nan=False) + '\n' for frame in frames))
            (root / 'control_context.json').write_text(json.dumps({
                'intersection_xy_m': [[-3.5, -3.5], [3.5, -3.5], [3.5, 3.5], [-3.5, 3.5]],
                'authored_geometry_source_sha256': sha(root / 'road.xodr'),
                'control_inventory_source_sha256': sha(root / 'entrance_controls.json')}) + '\n')
            assessed = physical_result(root, {'target_checks': [{'matched': True}]})
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            status = assessed['physical_checks']['maneuver']['status']
            if status != expected or assessed['maneuver_completed'] is not (expected == 'met'):
                raise ValueError('Physical diagnostic differs: ' + slug + '/' + kind + '/' + status)
            base.update({key: assessed[key] for key in ('physical_checks', 'maneuver_completed',
                                                       'realized_observables')})
    write(output, base)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'maneuver_status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        slug = entry['case_id'].split('__')[-1]
        folder = HERE / 'physical-proof' / slug
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, '-B', str(Path(__file__).resolve()), '--case', slug,
                       '--kind', kind, '--output', str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                completed = subprocess.run(command, cwd=REPO, env=os.environ,
                                           stdout=stream, stderr=subprocess.STDOUT, timeout=90)
            log.write_text(log.read_text().rstrip() + '\n')
            if completed.returncode:
                raise ValueError('Physical diagnostic failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                         'result': str(output.relative_to(HERE)), 'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'nrs-484b-257-2-physical-cpu-v1', 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'], 'fixtures': refs[:3],
                 'lifecycle': {**life, 'log': refs[3]['log'], 'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        write(folder / 'proof.json', proof)
        entry['physical_preparation'] = {'receipt': str((folder / 'proof.json').relative_to(HERE)),
                                         'sha256': sha(folder / 'proof.json')}
        print(slug, 'physical and lifecycle pass', flush=True)
    write(HERE / 'execution-manifest.json', manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        one(args.case, args.kind, args.output)
    else:
        parser.error('Use --build or --case/--kind/--output')
