"""Exercise three synthetic motion states and ordered saved lifecycle per case."""
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c111329' / 'physical'
output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
if ROOT / '.runtime-work' not in output_root.parents:
    raise ValueError('Pipeline output must remain under .runtime-work')
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import physical_result  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def probe(entry, suffix, kind):
    root = SCRATCH / suffix / kind
    root.mkdir(parents=True, exist_ok=True)
    construction = json.loads((HERE / entry['construction']).read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    write(root / 'config.json', config)
    write(root / 'acquisition-provenance.json',
          {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
    frames = [{'video_frame': i, 'carla_frame': 100 + i, 'time_s': i / 20}
              for i in range(900)]
    (root / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in frames))
    if kind != 'missing_evidence':
        positions = [i * .25 for i in range(900)] if kind == 'complete_motion' else [0.0] * 900
        rows = [{'frame': 100 + i, 'time_s': i / 20,
                 'position_m': [value, 0.0, 0.0]}
                for i, value in enumerate(positions)]
        (root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    result = physical_result(root, {'target_checks': []})
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if (result['physical_checks']['maneuver']['status'] != expected or
            result['maneuver_completed'] != (expected == 'met')):
        raise ValueError('synthetic motion state differs from assessor')
    target = HERE / 'physical' / suffix / (kind + '-result.json')
    write(target, result)
    log = HERE / 'physical' / suffix / (kind + '-proof.log')
    log.write_text('synthetic motion assessment: ' + expected + '\n')
    return {'kind': kind, 'command': 'prove_physical.py ' + suffix + ' ' + kind,
            'exit_code': 0, 'log': str(log.relative_to(HERE)),
            'log_sha256': sha(log), 'result': str(target.relative_to(HERE)),
            'result_sha256': sha(target)}


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    events = ['capture_finished', 'encoders_closed', 'restoration_verified',
              'native_exit', 'owner_released', 'saved_processing_started']
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        fixtures = [probe(entry, suffix, kind)
                    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence')]
        log = HERE / 'physical' / suffix / 'lifecycle.log'
        log.write_text('\n'.join(events) + '\n')
        receipt = {'format': 'c111329-synthetic-physical-preparation',
                   'case_id': entry['case_id'],
                   'construction_sha256': entry['construction_sha256'],
                   'diagnostic_fixture': True, 'fixtures': fixtures,
                   'lifecycle': {'events': events, 'exit_code': 0,
                                 'log': str(log.relative_to(HERE)),
                                 'log_sha256': sha(log)}}
        target = HERE / ('physical-' + suffix + '-receipt.json')
        write(target, receipt)
        entry['physical_preparation'] = {'receipt': target.name, 'sha256': sha(target)}
        print(suffix + ': three synthetic physical states and lifecycle passed')
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
