"""Run full saved recording validation on 900-frame synthetic camera sources.

This proves the package's source/evidence interface, not Native head pixels.
"""
import hashlib
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from batch_pipeline.carla import validate_attempt
from worker_exchange.media import audit, check_four_view_sources
from worker_exchange.runtime_cli import materialize
from yellow_red_finalizer import finalize

CAMERAS = (('overview', 1920, 1080, 'black'),
           ('approach', 1280, 720, 'green'),
           ('reference_corner', 1280, 720, 'blue'),
           ('driver_reference', 1280, 720, 'red'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('entry_before_red', 'entry_at_red', 'entry_after_red'), default='entry_before_red')
    args = parser.parse_args()
    case = HERE.name + '__' + args.case
    stem = 'at-red' if args.case == 'entry_at_red' else 'after-red'
    root = REPO / ('.runtime-work/c158196-yellow-red-four-camera-validation' if args.case == 'entry_before_red' else '.runtime-work/c158196-yellow-red-' + stem + '-four-camera')
    attempt = root / 'attempt'
    source = REPO / '.runtime-work/c158196-yellow-red-source-proof' / args.case
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    manifest = HERE / 'execution-manifest.json'
    construction = materialize(manifest, case, attempt)
    for name in ('signal_vehicle_history.jsonl', 'video_frames.jsonl', 'junction_context.json'):
        shutil.copy2(source / name, attempt / name)
    (attempt / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'physical_acceptance_claimed': False}) + '\n')
    with (attempt / 'trace.jsonl').open('x') as stream:
        for line in (attempt / 'signal_vehicle_history.jsonl').read_text().splitlines():
            row = json.loads(line)
            body = row['ego_body_vertices_xy_m']
            center_x = sum(vertex[0] for vertex in body) / len(body)
            center_y = sum(vertex[1] for vertex in body) / len(body)
            stream.write(json.dumps({'frame': row['frame'], 'time_s': row['time_s'],
                                     'position': {'x': center_x, 'y': center_y, 'z': 0.3},
                                     'position_m': [center_x, center_y, 0.3],
                                     'heading_deg': 0.0,
                                     'speed_mps': row['ego_speed_mps']}) + '\n')
    for name, width, height, color in CAMERAS:
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                        '-f', 'lavfi', '-i', f'color=c={color}:s={width}x{height}:r=20',
                        '-frames:v', '900', '-an', '-c:v', 'ffv1', '-threads', '1',
                        '-fflags', '+bitexact', '-flags:v', '+bitexact',
                        str(attempt / (name + '.mkv'))], check=True, timeout=300)
    sources = {name: attempt / (name + '.mkv') for name, _, _, _ in CAMERAS}
    check_four_view_sources(sources)
    analysis = finalize(attempt, attempt / 'analysis-report.json')
    mapping_sha = sha(attempt / 'video_frames.jsonl')
    audits = {name + '.mkv': audit(path, 900, mapping_sha256=mapping_sha,
                                   receipt=root / (name + '-decode.json'))
              for name, path in sources.items()}
    result = validate_attempt(attempt,
                              {'case': {'case_id': case, 'variable_assignments': {}},
                               'cell': {'cell_id': 'C158196'}, 'actor': 'motor_vehicle_driver'},
                              construction, {'recorded_exit_code': 0}, {}, source_audits=audits)
    if not all(item['source_decode']['frames'] == 900 for item in result['video_validation']):
        raise AssertionError('Four complete source decodes required')
    expected_offset = {'entry_before_red': -10, 'entry_at_red': 0, 'entry_after_red': 10}[args.case]
    if analysis['measurements']['entry_minus_red_onset_frames']['value'] != expected_offset:
        raise AssertionError('Saved body-entry offset changed')
    if result['provenance_kind'] != 'synthetic_fixture' or result.get('situation_confirmed'):
        raise AssertionError('Diagnostic validation claimed physical situation')
    report = {'format': 'worker-yellow-red-four-camera-diagnostic',
              'case_id': case, 'provenance_kind': 'synthetic_fixture',
              'physical_acceptance_claimed': False,
              'construction_sha256': sha(HERE / ('construction.json' if args.case == 'entry_before_red' else 'cases/' + args.case + '/construction.json')),
              'manifest_sha256': sha(manifest),
              'source_sha256': analysis['source_report']['sources'],
              'video_decodes': {name: {'frames': value['frames'],
                                       'dimensions': value['dimensions'],
                                       'rgb_sequence_sha256': value['rgb_sequence_sha256']}
                                for name, value in audits.items()},
              'recording_evidence_checked': [item['name'] for item in result['recording_evidence']],
              'saved_native_validation': 'passed',
              'limitation': 'Solid-color CPU videos are diagnostic fixtures, not Native signal-head observations.'}
    output = HERE / ('four-camera-validation-diagnostic.json' if args.case == 'entry_before_red' else stem + '-four-camera-diagnostic.json')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'videos': len(audits), 'frames_each': 900,
                      'diagnostic_sha256': sha(output)}))


if __name__ == '__main__':
    main()
