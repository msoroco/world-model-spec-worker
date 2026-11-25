"""CPU diagnostic for the full-length C158196 independent delivery audit."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CAMERAS = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def write_rows(path, records):
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in records))


def build_media(media):
    media.mkdir(parents=True, exist_ok=True)
    for name, (width, height) in CAMERAS.items():
        path = media / (name + '.mkv')
        if path.is_file():
            continue
        command = ['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i',
                   f'color=c=gray:s={width}x{height}:r=20', '-frames:v', '600',
                   '-c:v', 'ffv1', '-level', '3', '-y', str(path)]
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def build_attempt(case_id, attempt, media):
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    matches = [entry for entry in manifest['cases'] if entry['case_id'] == case_id]
    if len(matches) != 1:
        raise ValueError('Unselected exact case')
    entry = matches[0]
    construction_path = ROOT / entry['construction']
    if hashlib.sha256(construction_path.read_bytes()).hexdigest() != entry['construction_sha256']:
        raise ValueError('Selected construction changed')
    construction = json.loads(construction_path.read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    suffix = case_id.rsplit('__', 1)[-1]
    spec = json.loads((ROOT / 'cases' / (suffix + '-diagnostic-sources.json')).read_text())
    recipe = json.loads((ROOT / 'cases' / (suffix + '-fixture-recipe.json')).read_text())
    source = next(item for item in recipe['sources']
                  if item['path'] == 'entrance_inventory.json')
    source_path = REPO / source['source']
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != source['sha256']:
        raise ValueError('Inventory source changed')
    attempt.mkdir(parents=True, exist_ok=True)
    (attempt / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    (attempt / 'entrance_inventory.json').write_bytes(source_path.read_bytes())
    (attempt / 'acquisition-provenance.json').write_text(json.dumps(
        {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
    template = json.loads(spec['files']['crossing_history.jsonl'].splitlines()[0])
    frame_template = json.loads(spec['files']['video_frames.jsonl'].splitlines()[0])
    trace_template = json.loads(spec['files']['trace.jsonl'].splitlines()[0])
    evidence_template = json.loads(spec['files']['capture/evidence.jsonl'].splitlines()[0])
    history, mapping, trace, evidence = [], [], [], []
    for index in range(600):
        frame_id, time = 100 + index, round(5 + index / 20, 8)
        center_x = -15.0 if index < 100 else -15.0 + 30.0 * (index - 100) / 499
        row = dict(template)
        row.update(frame=frame_id, time_s=time, ego_speed_mps=0.0 if index < 100 else 30 / 24.95,
                   ego_distance_to_conflict_m=max(0.0, -center_x),
                   ego_body_vertices_xy_m=[[center_x-1, -1], [center_x-1, 1],
                                           [center_x+1, 1], [center_x+1, -1]],
                   other_speed_mps=0.0)
        history.append(row)
        frame = dict(frame_template)
        frame.update(video_frame=index, carla_frame=frame_id, time_s=time,
                     camera_frames={name: frame_id for name in CAMERAS})
        mapping.append(frame)
        observed = dict(trace_template)
        observed.update(frame=frame_id, time_s=time)
        trace.append(observed)
        event = dict(evidence_template)
        event['original_frame'] = frame_id
        evidence.append(event)
    write_rows(attempt / 'crossing_history.jsonl', history)
    write_rows(attempt / 'video_frames.jsonl', mapping)
    write_rows(attempt / 'trace.jsonl', trace)
    (attempt / 'capture').mkdir(exist_ok=True)
    write_rows(attempt / 'capture/evidence.jsonl', evidence)
    for name in CAMERAS:
        path = attempt / (name + '.mkv')
        if not path.exists():
            os.link(media / (name + '.mkv'), path)
    command = [sys.executable, str(ROOT / 'saved_finalizer.py'), '--attempt', str(attempt),
               '--output', str(attempt / 'analysis-report.json')]
    completed = subprocess.run(command, env=os.environ.copy(), capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError('Saved finalizer rejected diagnostic sources: ' + completed.stderr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    args = parser.parse_args()
    output_root = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
    if not output_root:
        raise ValueError('SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work is required')
    private = (REPO / '.runtime-work').resolve()
    output = Path(output_root).resolve()
    if output != private and private not in output.parents:
        raise ValueError('Output root outside .runtime-work')
    sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
    from delivery_audit import audit_delivery
    if args.mode == 'negative':
        audit_delivery(output / 'missing-native-source', ROOT, args.case, diagnostic_fixture=True)
        raise AssertionError('Missing source unexpectedly accepted')
    media = output / 'media'
    build_media(media)
    attempt = output / args.case.rsplit('__', 1)[-1]
    if not (attempt / 'analysis-report.json').is_file():
        build_attempt(args.case, attempt, media)
    receipt = audit_delivery(attempt, ROOT, args.case, diagnostic_fixture=True,
                             receipt_dir=attempt / 'audit-receipts')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
