"""Source-derived full-duration CPU delivery diagnostics for C125714 cases.

Every generated source and pixel pattern is synthetic and cannot establish a
physical recording, actor visibility, or legal priority.
"""
import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from delivery_acceptance import CAMERAS, SIZES, audit  # noqa: E402
from delivery_fixture_proof import write  # noqa: E402
from worker_exchange.common import sha  # noqa: E402
from worker_exchange.fixture_recipe import materialize as materialize_fixture  # noqa: E402
from worker_exchange.package_compatibility import materialize_case  # noqa: E402
from worker_exchange.media import compose_four_views  # noqa: E402
from worker_exchange.runtime_cli import execution_env  # noqa: E402

FRAMES = 1100
SOURCE_FRAMES = 60


def read(path):
    return json.loads(Path(path).read_text())


def extend_rows(path, frame_key, time_key):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(rows) != SOURCE_FRAMES:
        raise ValueError('Expected 60 exact source-derived diagnostic frames: ' + path.name)
    initial_frame = rows[0][frame_key]
    initial_time = rows[0][time_key]
    for index in range(SOURCE_FRAMES, FRAMES):
        row = copy.deepcopy(rows[-1])
        row[frame_key] = initial_frame + index
        row[time_key] = round(initial_time + index / 20, 6)
        if path.name == 'video_frames.jsonl':
            row['video_frame'] = index
            if 'native_frame' in row:
                row['native_frame'] = row[frame_key]
        rows.append(row)
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
    return rows


def create_video(path, size):
    if path.exists():
        path.unlink()
    width, height = size
    subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                    '-f', 'lavfi', '-i', f'color=c=black:s={width}x{height}:r=20',
                    '-vf', 'drawbox=x=20:y=20:w=64:h=64:color=red:t=fill',
                    '-frames:v', str(FRAMES), '-an', '-c:v', 'ffv1', '-threads', '2',
                    str(path)], check=True, timeout=900)


def build(root, case_id):
    if root.exists():
        raise ValueError('Use a fresh diagnostic output root')
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = read(manifest_path)
    entry = next((item for item in manifest['cases'] if item['case_id'] == case_id), None)
    if entry is None or entry.get('delivery_acceptance') is not None:
        raise ValueError('Select an incomplete exact C125714 case')
    root.mkdir(parents=True)
    fixture = root / 'fixture'
    materialize_fixture(REPO, REPO / entry['fixture_recipe'], fixture)
    attempt = root / 'attempt'
    materialize_case(manifest_path, case_id, attempt, fixture)
    for name in ('crossing_history.jsonl', 'controller_history.jsonl', 'trace.jsonl'):
        extend_rows(attempt / name, 'frame', 'time_s')
    mapping = extend_rows(attempt / 'video_frames.jsonl', 'carla_frame', 'time_s')
    evidence = attempt / 'capture/evidence.jsonl'
    if evidence.exists():
        evidence_rows = [json.loads(line) for line in evidence.read_text().splitlines() if line.strip()]
        if len(evidence_rows) == SOURCE_FRAMES:
            extend_rows(evidence, 'original_frame', 'recording_time_s')
    history = [json.loads(line) for line in (attempt / 'crossing_history.jsonl').read_text().splitlines()]
    for row in history:
        row['ego']['actor_id'] = 101
        row['other']['actor_id'] = 102
    (attempt / 'crossing_history.jsonl').write_text(''.join(
        json.dumps(row, allow_nan=False) + '\n' for row in history))
    for camera in CAMERAS:
        create_video(attempt / (camera + '.mkv'), SIZES[camera])
    subprocess.run([sys.executable, str(attempt / 'finalizer.py'), '--attempt', str(attempt),
                    '--output', str(attempt / 'analysis-report.json')],
                   check=True, timeout=120, env=execution_env())
    result = read(attempt / 'result.json')
    if (result.get('case_id') != case_id or result.get('diagnostic_fixture') is not True
            or result.get('provenance_kind') != 'synthetic_fixture'
            or result['physical_checks']['setup']['status'] != 'met'
            or result['physical_checks']['maneuver']['status'] != 'met'):
        raise ValueError('Full-duration diagnostic classifier did not pass')
    write(attempt / 'converted/trace.json', {
        'scenes': [{'t': round(row['time_s'] * 1000)} for row in mapping]})
    compose_four_views({camera: attempt / (camera + '.mkv') for camera in CAMERAS},
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
    write(attempt / 'native-exit.json', {'event': 'native_exit',
          'diagnostic_fixture': True,
          'capture_seal_sha256': sha(attempt / 'capture-seal.json')})
    write(attempt / 'owner-release.json', {'event': 'owner_released',
          'operator_attested': True, 'diagnostic_fixture': True,
          'native_exit_sha256': sha(attempt / 'native-exit.json')})
    observations = [{'camera': camera, 'video_frame': 0, 'actor': role,
                     'actor_id': history[0][role]['actor_id'],
                     'bbox_xyxy': [0, 0, 128, 128]}
                    for camera in CAMERAS for role in ('ego', 'other')]
    write(root / 'pixel-review.json', {
        'case_id': case_id, 'reviewer': 'synthetic CPU fixture generator',
        'method': 'static red test box; no real actor identity or visibility assertion',
        'frame_map_sha256': sha(attempt / 'video_frames.jsonl'),
        'source_sha256': {name: sha(attempt / (name + '.mkv')) for name in CAMERAS},
        'observations': observations})
    return attempt


def positive(root, case_id):
    attempt = build(root, case_id)
    receipt = audit(attempt, case_id, root / 'pixel-review.json',
                    attempt / 'delivery-audit.json', diagnostic=True)
    if (receipt['passed'] is not False or receipt['software_checks_passed'] is not True
            or receipt['frames'] != FRAMES or receipt['diagnostic_fixture'] is not True):
        raise ValueError('Diagnostic proof incorrectly claimed physical acceptance')
    print(json.dumps({'case_id': case_id, 'frames': FRAMES,
                      'software_checks_passed': True, 'diagnostic_fixture': True,
                      'physical_acceptance_claimed': False,
                      'audit_sha256': sha(attempt / 'delivery-audit.json')}))


def negative(root, source_root, case_id):
    if root.exists():
        raise ValueError('Use a fresh negative output root')
    if not (source_root / 'attempt/delivery-audit.json').is_file():
        raise ValueError('Positive diagnostic audit required first')
    attempt = root / 'attempt'
    attempt.mkdir(parents=True)
    for name in ('capture-seal.json', 'native-exit.json', 'owner-release.json'):
        (attempt / name).write_bytes((source_root / 'attempt' / name).read_bytes())
    audit(attempt, case_id, source_root / 'pixel-review.json',
          attempt / 'delivery-audit.json', diagnostic=True)
    raise ValueError('Missing sealed originals were accepted')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--output-root', required=True, type=Path)
    parser.add_argument('--negative-source-root', type=Path)
    args = parser.parse_args()
    if args.negative_source_root:
        negative(args.output_root.resolve(), args.negative_source_root.resolve(), args.case)
    else:
        positive(args.output_root.resolve(), args.case)


if __name__ == '__main__':
    main()
