"""Full-duration primary-case diagnostic audit proof; never a recording receipt."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from delivery_acceptance import CAMERAS, audit, read  # noqa: E402
from saved_full_duration_proof import CASE, FRAMES, write_sources  # noqa: E402
from worker_exchange.common import sha  # noqa: E402
from worker_exchange.media import compose_four_views  # noqa: E402
from worker_exchange.runtime_cli import execution_env  # noqa: E402


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def textured_video(path):
    fresh = path.with_name(path.stem + '-textured.mkv')
    subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                    '-i', str(path), '-vf', 'drawbox=x=20:y=20:w=64:h=64:color=red:t=fill',
                    '-an', '-c:v', 'ffv1', '-threads', '2', str(fresh)],
                   check=True, timeout=900)
    path.unlink()
    fresh.rename(path)


def build(root):
    if root.exists():
        raise ValueError('Use a fresh diagnostic proof root')
    attempt = root / 'attempt'
    write_sources(attempt)
    config = read(attempt / 'config.json')
    config['actor'] = 'motor_vehicle_driver'
    write(attempt / 'config.json', config)
    shutil.copyfile(ROOT / 'finalizer.py', attempt / 'finalizer.py')
    history = attempt / 'crossing_history.jsonl'
    rows = [json.loads(line) for line in history.read_text().splitlines() if line]
    for row in rows:
        row['ego']['actor_id'] = 101
        row['other']['actor_id'] = 102
    history.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
    for camera in CAMERAS:
        textured_video(attempt / (camera + '.mkv'))
    subprocess.run([sys.executable, str(ROOT / 'finalizer.py'), '--attempt', str(attempt),
                    '--output', str(attempt / 'analysis-report.json')],
                   check=True, timeout=120, env=execution_env())
    result = read(attempt / 'result.json')
    if (result.get('case_id') != CASE or result.get('provenance_kind') != 'synthetic_fixture'
            or result.get('diagnostic_fixture') is not True
            or result['physical_checks']['setup']['status'] != 'met'
            or result['physical_checks']['maneuver']['status'] != 'met'):
        raise ValueError('Full-duration synthetic physical classifier did not pass')
    mapping = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if len(mapping) != FRAMES:
        raise ValueError('Full-duration frame map missing')
    write(attempt / 'converted/trace.json', {
        'scenes': [{'t': round(row['time_s'] * 1000)} for row in mapping]})
    compose_four_views({name: attempt / (name + '.mkv') for name in CAMERAS},
                       attempt / 'video_frames.jsonl', attempt / 'raw.mkv')
    names = ('config.json', 'crossing_history.jsonl', 'road_geometry.json',
             'video_frames.jsonl', 'controller_history.jsonl', 'trace.jsonl',
             *(camera + '.mkv' for camera in CAMERAS))
    write(attempt / 'capture-seal.json', {
        'format': 'worker-sealed-capture', 'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True, 'frames': FRAMES,
        'physical_acceptance_claimed': False,
        'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
        'sources': {name: sha(attempt / name) for name in names}})
    write(attempt / 'native-exit.json', {
        'event': 'native_exit', 'diagnostic_fixture': True,
        'capture_seal_sha256': sha(attempt / 'capture-seal.json')})
    write(attempt / 'owner-release.json', {
        'event': 'owner_released', 'operator_attested': True,
        'diagnostic_fixture': True,
        'native_exit_sha256': sha(attempt / 'native-exit.json')})
    observations = [{'camera': camera, 'video_frame': 0, 'actor': role,
                     'actor_id': rows[0][role]['actor_id'],
                     'bbox_xyxy': [0, 0, 128, 128]}
                    for camera in CAMERAS for role in ('ego', 'other')]
    write(root / 'pixel-review.json', {
        'case_id': CASE, 'reviewer': 'synthetic CPU fixture generator',
        'method': 'static red test box; no real actor identity or visibility assertion',
        'frame_map_sha256': sha(attempt / 'video_frames.jsonl'),
        'source_sha256': {name: sha(attempt / (name + '.mkv')) for name in CAMERAS},
        'observations': observations})
    return attempt


def positive(root):
    attempt = build(root)
    receipt = audit(attempt, CASE, root / 'pixel-review.json',
                    attempt / 'delivery-audit.json', diagnostic=True)
    if (receipt['passed'] is not False or receipt['software_checks_passed'] is not True
            or receipt['frames'] != FRAMES or receipt['diagnostic_fixture'] is not True):
        raise ValueError('Diagnostic proof incorrectly claimed physical acceptance')
    print(json.dumps({'case_id': CASE, 'frames': FRAMES,
                      'software_checks_passed': True,
                      'diagnostic_fixture': True,
                      'physical_acceptance_claimed': False,
                      'audit_sha256': sha(attempt / 'delivery-audit.json')}))


def negative(root, positive_root):
    if root.exists():
        raise ValueError('Use a fresh negative proof root')
    root.mkdir(parents=True)
    original = positive_root / 'attempt'
    if not (original / 'delivery-audit.json').is_file():
        raise ValueError('Positive diagnostic audit required first')
    attempt = root / 'attempt'
    attempt.mkdir()
    for name in ('capture-seal.json', 'native-exit.json', 'owner-release.json'):
        shutil.copyfile(original / name, attempt / name)
    # The capture seal refers to originals that are absent here.
    audit(attempt, CASE, positive_root / 'pixel-review.json',
          attempt / 'delivery-audit.json', diagnostic=True)
    raise ValueError('Missing sealed originals were accepted')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--output-root', required=True, type=Path)
    parser.add_argument('--negative-source-root', type=Path)
    args = parser.parse_args()
    if args.case != CASE:
        raise ValueError('Exact primary C125714 case required')
    if args.negative_source_root:
        negative(args.output_root.resolve(), args.negative_source_root.resolve())
    else:
        positive(args.output_root.resolve())


if __name__ == '__main__':
    main()
