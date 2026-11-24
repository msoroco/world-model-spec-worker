"""Exercise saved bypass finalization and source rejection under .runtime-work."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from finalize_bypass_diagnostic import finalize, sha


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c109128' / 'saved-finalizer-proof'


def attempt(condition, name):
    target = SCRATCH / name
    if target.exists():
        shutil.rmtree(target)
    (target / 'capture/native').mkdir(parents=True)
    (target / 'capture/cameras').mkdir(parents=True)
    shutil.copyfile(HERE / 'diagnostic-bypass' / (condition + '.jsonl'),
                    target / 'capture/native/pedestrian_samples.jsonl')
    shutil.copyfile(HERE / 'diagnostic-bypass/context.json',
                    target / 'capture/native/sidewalk_context.json')
    camera = ROOT / '.runtime-work/c109128/camera-proof' / condition
    shutil.copyfile(camera / 'video_frames.jsonl', target / 'video_frames.jsonl')
    for label in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        shutil.copyfile(camera / (label + '.mkv'),
                        target / 'capture/cameras' / (label + '.mkv'))
    return target


def reject(condition, label, mutate, expected):
    target = attempt(condition, condition + '-' + label)
    mutate(target)
    command = [sys.executable, str(HERE / 'native/finalize_bypass_diagnostic.py'),
               '--attempt', str(target), '--output', str(target / 'report.json')]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    log = SCRATCH / (condition + '-' + label + '.log')
    log.write_text(result.stdout + result.stderr)
    if result.returncode == 0 or expected not in log.read_text():
        raise ValueError('Damaged saved source was not rejected: ' + label)
    return {'condition': condition, 'mutation': label,
            'exit_code': result.returncode, 'expected_error': expected,
            'log_sha256': sha(log)}


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    positives = []
    for condition in ('condition_a', 'condition_b'):
        target = attempt(condition, condition + '-positive')
        report_path = SCRATCH / (condition + '-report.json')
        report = finalize(target, report_path)
        positives.append({'condition': condition,
                          'report_sha256': sha(report_path),
                          'first_full_footprint_return_frame': report['measurements']['first_full_footprint_return_frame'],
                          'road_center_frames': report['measurements']['road_center_frames'],
                          'source_hashes': report['original_sources_sha256']})
    negatives = []
    for condition in ('condition_a', 'condition_b'):
        negatives.append(reject(condition, 'missing-raw',
            lambda p: (p / 'capture/native/pedestrian_samples.jsonl').unlink(),
            'Missing required source: capture/native/pedestrian_samples.jsonl'))
        negatives.append(reject(condition, 'missing-camera',
            lambda p: (p / 'capture/cameras/approach.mkv').unlink(),
            'Missing required source: capture/cameras/approach.mkv'))
        def change_mapping(p):
            path = p / 'video_frames.jsonl'
            rows = path.read_text().splitlines()
            row = json.loads(rows[200])
            row['source_frame'] = 199
            rows[200] = json.dumps(row)
            path.write_text('\n'.join(rows) + '\n')
        negatives.append(reject(condition, 'changed-frame-map',
            change_mapping, 'Source/video frame join differs'))
    if positives[0]['road_center_frames'] == positives[1]['road_center_frames']:
        raise ValueError('Lateral bypass contrast absent')
    proof = {'format': 'c109128-saved-bypass-diagnostic-proof-v1',
             'passed': True, 'script_sha256': sha(Path(__file__)),
             'finalizer_sha256': sha(HERE / 'native/finalize_bypass_diagnostic.py'),
             'positive': positives, 'negative': negatives,
             'original_native_observed': False,
             'physical_completion_claimed': False,
             'legal_verdict_claimed': False}
    destination = HERE / 'saved-bypass-diagnostic-proof.json'
    destination.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'positives': len(positives),
                      'negatives': len(negatives), 'proof_sha256': sha(destination)}))


if __name__ == '__main__':
    main()
