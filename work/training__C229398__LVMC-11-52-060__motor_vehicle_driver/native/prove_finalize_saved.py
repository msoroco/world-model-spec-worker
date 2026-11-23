"""Reproduce 600-frame synthetic saved-source analysis for the three boundaries.

Camera placeholders are intentionally not media evidence. This proves only the
source-derived measurement and required-source negative path.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parent.parent
ASSIGNMENT = PACKAGE.name
FEET_PER_METER = 3.280839895013123
TARGETS = {'below_15_ft': 14, 'at_15_ft': 15, 'above_15_ft': 16}
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def actor(ident, y, attachment=None):
    row = {'actor_id': ident, 'center_xy_m': [0, y],
           'half_extent_xy_m': [0.5, 0.5], 'yaw_deg': 0}
    if attachment is not None:
        row['attached_to'] = attachment
    return row


def fixture(folder, construction, target):
    folder.mkdir()
    for item in construction['files']:
        path = folder / item['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['content'])
    (folder / 'construction.json').write_text(json.dumps(construction) + '\n')
    (folder / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
    curb_source = folder / 'native-curb-proposal.json'
    curb_source.write_text(json.dumps({'source_kind': 'synthetic_native_sample',
                                       'synthetic_curb_line': 'y=0'}) + '\n')
    (folder / 'reviewed-curb.json').write_text(json.dumps({
        'format': 'c229398-reviewed-curb-v1', 'reviewed': True,
        'reviewed_curb': {'line': 'y=0', 'source_kind': 'synthetic_native_sample'},
        'source_kind': 'synthetic_native_sample',
        'source_file': curb_source.name, 'source_sha256': sha(curb_source),
        'origin_xy_m': [0, 0], 'street_normal_xy': [0, 1]}) + '\n')
    maximum_y = target / FEET_PER_METER
    with (folder / 'native-raw-actors.jsonl').open('w') as raw, \
         (folder / 'trace.jsonl').open('w') as trace, \
         (folder / 'video_frames.jsonl').open('w') as mapping:
        for index in range(600):
            frame = 1000 + index
            time_s = (index + 1) / 20
            raw.write(json.dumps({
                'frame': index, 'native_frame': frame, 'time_s': time_s,
                'source_kind': 'synthetic_native_sample',
                'actors': {'vehicle': actor('ego', maximum_y-0.5),
                           'load': actor('load', maximum_y-1, 'ego'),
                           'trailer': actor('trailer', maximum_y-1.5, 'ego')}}) + '\n')
            trace.write(json.dumps({'frame': frame, 'time_s': time_s,
                                    'position': {'x': 0.0, 'y': maximum_y-0.5,
                                                 'z': 0.0},
                                    'position_m': [0.0, maximum_y-0.5, 0.0],
                                    'heading_deg': 0.0, 'speed_mps': 0.0,
                                    'speed_mph': 0.0,
                                    'velocity_mps': [0.0, 0.0, 0.0],
                                    'control': {'brake': 1.0, 'gear': 0,
                                                'hand_brake': True, 'reverse': False,
                                                'steer': 0.0, 'throttle': 0.0},
                                    'synthetic_diagnostic': True,
                                    'speed_source_kind': 'synthetic_native_sample'}) + '\n')
            mapping.write(json.dumps({'video_frame': index, 'carla_frame': frame,
                                      'native_frame': frame, 'time_s': time_s}) + '\n')
    for view in VIEWS:
        (folder / (view + '.mkv')).write_bytes(b'')


def invoke(folder, env):
    return subprocess.run([
        sys.executable, str(folder / 'finalize_saved.py'),
        '--attempt', str(folder),
        '--output', str(folder / 'analysis-report.json')],
        cwd=folder, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=120)


def prove(log_dir):
    log_dir = Path(log_dir).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / '.runtime-work' / 'c229398-finalizer-proof'
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PYTHONPATH'] = str(ROOT / 'runtime/pipeline/scenario_pipeline')
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(scratch)
    os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(scratch)
    sys.path.insert(0, env['PYTHONPATH'])
    from worker_exchange.measurement_contract import verify_report
    manifest = json.loads((PACKAGE / 'draft-primary-manifest.json').read_text())
    outputs = []
    with tempfile.TemporaryDirectory(dir=scratch, prefix='saved-') as temporary:
        base = Path(temporary)
        for suffix, target in TARGETS.items():
            entry = next(x for x in manifest['cases'] if x['case_id'].endswith('__'+suffix))
            path = PACKAGE / entry['construction']
            if sha(path) != entry['construction_sha256']:
                raise ValueError('Draft construction changed')
            construction = json.loads(path.read_text())
            positive = base / (suffix + '-positive')
            fixture(positive, construction, target)
            result = invoke(positive, env)
            log = log_dir / (suffix + '.log')
            log.write_text(result.stdout)
            if result.returncode:
                raise ValueError('Saved source analysis failed: ' + result.stdout[-1000:])
            report = json.loads((positive / 'analysis-report.json').read_text())
            native = json.loads((positive / 'result.json').read_text())
            contract = json.loads((PACKAGE / entry['measurement_contract']).read_text())
            verify_report(contract, report, positive)
            measured = report['measurements']['text_0_projection']['value']
            channel = positive / 'channels/maximum_projection_perpendicular_to_curb.jsonl'
            if (abs(measured-target) > 1e-7 or
                    len(channel.read_text().splitlines()) != 600 or
                    native['target_checks'][0]['matched'] is not True or
                    native['provenance_kind'] != 'synthetic_local_diagnostic'):
                raise ValueError('Full source-derived boundary failed')
            outputs.append({'case_id': entry['case_id'], 'requested_ft': target,
                            'measured_ft': measured, 'channel_frames': 600,
                            'construction_sha256': sha(path),
                            'raw_source_sha256': sha(positive/'native-raw-actors.jsonl'),
                            'analysis_report_sha256': sha(positive/'analysis-report.json'),
                            'log_sha256': sha(log), 'log': str(log.relative_to(PACKAGE))})
            if suffix == 'at_15_ft':
                negative = base / 'at_15_ft-negative'
                fixture(negative, construction, target)
                (negative / 'reviewed-curb.json').unlink()
                failed = invoke(negative, env)
                negative_log = log_dir / 'missing-reviewed-curb.log'
                negative_log.write_text(failed.stdout)
                if failed.returncode == 0 or 'Missing required source: reviewed-curb.json' not in failed.stdout:
                    raise ValueError('Missing reviewed curb was not rejected')
    return {'format': 'c229398-saved-source-cpu-proof-v1', 'passed': True,
            'cases': outputs, 'negative_removed': 'reviewed-curb.json',
            'negative_log': str(negative_log.relative_to(PACKAGE)),
            'negative_log_sha256': sha(negative_log),
            'source_kind': 'synthetic_native_sample',
            'original_native_observed': False, 'camera_media_validated': False,
            'measurement_contracts_validated': True,
            'runtime_compatibility_passed': False,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--log-dir', required=True)
    args = parser.parse_args()
    proof = prove(args.log_dir)
    Path(args.output).write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': proof['passed'],
                      'cases': len(proof['cases']),
                      'runtime_compatibility_passed': False}, sort_keys=True))
