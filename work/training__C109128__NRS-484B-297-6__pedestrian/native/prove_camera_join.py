"""Construct four-view CPU diagnostics tied to retained bypass rows."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from bypass import measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frames(path):
    run = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                          '-select_streams', 'v:0', '-show_entries',
                          'stream=nb_read_frames', '-of',
                          'default=noprint_wrappers=1:nokey=1', str(path)],
                         capture_output=True, text=True, check=True)
    return int(run.stdout.strip())


def main():
    assignment = Path(__file__).resolve().parents[1]
    root = assignment.parents[1]
    output = root / '.runtime-work' / 'c109128' / 'camera-proof'
    output.mkdir(parents=True, exist_ok=True)
    context = assignment / 'diagnostic-bypass/context.json'
    results = []
    for condition in ('condition_a', 'condition_b'):
        source = assignment / 'diagnostic-bypass' / (condition + '.jsonl')
        metric = measure(source, context)
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if len(rows) != 600:
            raise ValueError('Exact source frame count changed')
        stage = output / condition
        stage.mkdir(exist_ok=True)
        mapping = stage / 'video_frames.jsonl'
        mapping.write_text(''.join(json.dumps({'video_frame': i,
            'source_frame': row['frame'], 'time_s': row['time_s'],
            'pedestrian_xy_m': row['pedestrian_xy_m'],
            'source_kind': 'synthetic_cpu'}) + '\n'
            for i, row in enumerate(rows)))
        video = {}
        for name in ('overview', 'approach', 'reference_corner',
                     'driver_reference'):
            path = stage / (name + '.mkv')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi',
                            '-i', 'color=c=black:s=32x32:r=20:d=30',
                            '-an', '-c:v', 'ffv1', str(path)], check=True)
            if frames(path) != len(rows):
                raise ValueError('Camera frame count differs')
            video[name] = {'frames': 600, 'sha256': sha(path)}
        reread = [json.loads(line) for line in mapping.read_text().splitlines()]
        if any(row['video_frame'] != i or
               row['source_frame'] != rows[i]['frame'] or
               row['pedestrian_xy_m'] != rows[i]['pedestrian_xy_m']
               for i, row in enumerate(reread)):
            raise ValueError('Source/video frame join differs')
        results.append({'condition': condition, 'source_sha256': sha(source),
                        'context_sha256': sha(context),
                        'mapping_sha256': sha(mapping),
                        'source_measurement': metric,
                        'videos': video})
    if results[0]['source_measurement']['road_center_frames'] == \
            results[1]['source_measurement']['road_center_frames']:
        raise ValueError('Controlled bypass distance difference missing')
    receipt = {'format': 'c109128-four-view-synthetic-cpu-v1',
               'passed': True, 'conditions': results,
               'original_native_observed': False,
               'physical_obstruction_verified': False,
               'legal_verdict_claimed': False}
    destination = assignment / 'four-view-cpu-proof.json'
    destination.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'conditions': len(results),
                      'camera_streams': 8, 'receipt_sha256': sha(destination)}))


if __name__ == '__main__':
    sys.exit(main())
