"""Run the 600-frame bundled finalizer on fresh synthetic source-shaped attempts."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c422978-30s-finalize-v5'
SAVED = ROOT / '.runtime-work/c422978-30s-saved'
BUNDLES = ROOT / '.runtime-work/c422978-30s-v5'
MEDIA = ROOT / '.runtime-work/c422978-30s-media'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(bundle, folder):
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH / 'runtime-output')
    env['PYTHONPATH'] = str(ROOT / 'runtime/scenario_pipeline')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return subprocess.run([sys.executable, str(bundle / 'finalize.py'),
                           '--attempt', str(folder),
                           '--output', str(folder / 'analysis-report.json')],
                          text=True, capture_output=True, env=env)


def attempt(case, candidate):
    name = case + '-' + candidate
    bundle, source = BUNDLES / name, SAVED / name
    folder = SCRATCH / name
    folder.mkdir(parents=True, exist_ok=True)
    for item in ('native-observed.jsonl', 'native-map-readback.json',
                 'video_frames.jsonl', 'capture/evidence.jsonl', 'city-context.json'):
        output = folder / item
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / item, output)
    for item in ('config.json', 'construction.json'):
        shutil.copy2(bundle / item, folder / item)
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        shutil.copy2(MEDIA / (name + '.mkv'), folder / (name + '.mkv'))
    observed = [json.loads(line) for line in (folder / 'native-observed.jsonl').read_text().splitlines()]
    (folder / 'trace.jsonl').write_text(''.join(json.dumps({
        'frame': row['native_frame'], 'time_s': row['time_s'],
        'position_m': [*row['center_native_xy_m'], .5],
        'heading_deg': 0, 'speed_mps': row['speed_mps']}) + '\n' for row in observed))
    return bundle, folder


def main():
    positives = []
    media_hashes = {}
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        path = MEDIA / (name + '.mkv')
        check = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                '-select_streams', 'v:0', '-show_entries',
                                'stream=nb_read_frames,r_frame_rate', '-of', 'json', str(path)],
                               text=True, capture_output=True, check=True)
        stream = json.loads(check.stdout)['streams'][0]
        if stream['nb_read_frames'] != '600' or stream['r_frame_rate'] != '20/1':
            raise ValueError('Synthetic video frame count or rate differs')
        media_hashes[path.name] = sha(path)
    for candidate in ('primary', 'fallback1', 'fallback3'):
        for case in ('witness_1', 'witness_2'):
            bundle, folder = attempt(case, candidate)
            result = run(bundle, folder)
            if result.returncode:
                raise ValueError('Bundled finalizer failed: ' + result.stderr)
            analysis = json.loads((folder / 'analysis-report.json').read_text())
            output = json.loads((folder / 'result.json').read_text())
            measured = analysis['measurements']['motorcycle_sidewalk_occupancy']['value']
            expected = 0 if case == 'witness_1' else (535 if candidate == 'fallback1' else 520)
            if (measured['frames'] != 600 or measured['moving_sidewalk_overlap_frames'] != expected or
                    output['accepted'] is not False or output['provenance_kind'] != 'synthetic_local_diagnostic' or
                    analysis['selected'] is not False or analysis['legal_verdict_claimed'] is not False or
                    len(output['recording_evidence']) != 6 or
                    len(list((folder / 'channels').glob('*.jsonl'))) != 3):
                raise ValueError('Bundled finalization output differs')
            for item in (folder / 'channels').glob('*.jsonl'):
                if len(item.read_text().splitlines()) != 600:
                    raise ValueError('Finalized channel frame count differs')
            positives.append({'case_id': output['case_id'], 'candidate_id': candidate,
                              'construction_sha256': sha(HERE / 'extended-primary' / case / ('construction.json' if candidate == 'primary' else candidate + '/construction.json')),
                              'analysis_sha256': sha(folder / 'analysis-report.json'),
                              'result_sha256': sha(folder / 'result.json'),
                              'channel_sha256': {item.name: sha(item) for item in sorted((folder / 'channels').glob('*.jsonl'))},
                              'moving_overlap_frames': expected})
    bundle, folder = BUNDLES / 'witness_2-primary', SCRATCH / 'negative-missing-source'
    folder.mkdir(parents=True, exist_ok=True)
    source = SCRATCH / 'witness_2-primary'
    for item in ('native-map-readback.json', 'video_frames.jsonl',
                 'capture/evidence.jsonl', 'city-context.json', 'config.json', 'construction.json',
                 'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'):
        output = folder / item
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / item, output)
    failure = run(bundle, folder)
    if failure.returncode == 0 or 'Missing required source: native-observed.jsonl' not in failure.stderr:
        raise ValueError('Deleted observed-source negative was accepted')
    report = {'format': 'c422978-30s-synthetic-finalization-proof-v1',
              'selected': False, 'original_native_observed': False,
              'legal_verdict': None, 'positive': positives,
              'media_sha256': media_hashes,
              'negative_error': 'Missing required source: native-observed.jsonl',
              'video_profile': {'frames': 600, 'fps': 20,
                                'overview': [1920, 1080], 'other_cameras': [1280, 720]}}
    path = HERE / 'extended-primary/finalization-proof.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'proof_sha256': sha(path), 'positive': len(positives),
                      'negative_rejections': 1}))


if __name__ == '__main__':
    main()
