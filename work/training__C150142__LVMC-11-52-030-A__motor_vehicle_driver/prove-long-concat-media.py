"""Check repeated synthetic fixture frames, timestamps and missing segment rejection."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
SCRATCH = ROOT / '.runtime-work' / 'owner150142' / 'concat-fixture-v2'
sys.path.insert(0, str(ROOT / 'runtime' / 'scenario_pipeline'))
from worker_exchange.media import audit


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def timestamps(path):
    command = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
               '-show_entries', 'frame=best_effort_timestamp_time',
               '-of', 'csv=p=0', str(path)]
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
    count = 0
    first = last = None
    for line in proc.stdout:
        value = float(line.strip())
        if last is not None and not value > last:
            raise ValueError('Synthetic concat timestamps are not increasing')
        if first is None:
            first = value
        last = value
        count += 1
    if proc.wait() != 0:
        raise ValueError('Synthetic concat timestamp probe failed')
    if count != 36120 or abs(first) > 1e-6 or abs(last - 1805.95) > 1e-4:
        raise ValueError(f'Unexpected concat time bounds: {count}, {first}, {last}')
    return {'frames': count, 'first_s': first, 'last_s': last}


def main():
    output = {'format': 'c150142-synthetic-long-concat-media-proof-v1',
              'scope': 'repeated synthetic pixels only; no original Native or physical claim',
              'recipe': 'current-long-concat-recipe.json',
              'recipe_sha256': digest(WORK / 'current-long-concat-recipe.json'),
              'spec_sha256': digest(WORK / 'current-long-concat-spec.json'),
              'views': {}}
    for view in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        path = SCRATCH / (view + '.mkv')
        source = audit(path, 36120)
        output['views'][view] = {'source_sha256': digest(path),
                                 'frames': source['frames'],
                                 'dimensions': source['dimensions'],
                                 'rgb_sequence_sha256': source['rgb_sequence_sha256'],
                                 'time': timestamps(path)}
    negative = ROOT / '.runtime-work' / 'owner150142' / 'concat-negative'
    negative.mkdir(parents=True, exist_ok=True)
    (negative / 'long-segments').mkdir(exist_ok=True)
    shutil.copyfile(SCRATCH / 'long-segments' / 'overview-full.mkv',
                    negative / 'long-segments' / 'overview-full.mkv')
    altered = negative / 'overview.mkv'
    altered.write_text((SCRATCH / 'overview.mkv').read_text().replace(
        "file 'long-segments/overview-tail.mkv'", "file 'missing-tail.mkv'"))
    try:
        audit(altered, 36120)
    except Exception as error:
        output['negative'] = {'removed_source': 'long-segments/overview-tail.mkv',
                              'rejected': True, 'error': str(error)[:400]}
    else:
        raise ValueError('Missing synthetic segment was accepted')
    output['passed'] = True
    target = WORK / 'current-long-concat-media-proof.json'
    target.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'receipt': str(target), 'sha256': digest(target),
                      'frames_per_view': 36120, 'negative_rejected': True}))


if __name__ == '__main__':
    configured = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
    if not configured or ROOT / '.runtime-work' not in Path(configured).resolve().parents:
        raise ValueError('Set physical output root under .runtime-work')
    main()
