"""Generated source-shaped CPU diagnostic for the NRS 484B.213(2)(b) temporal split."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
MEASURE = HERE / 'native/zone_measure.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_attempt(folder, mode):
    folder.mkdir()
    one_way = mode == 'one_way'
    (folder / 'road-context.json').write_text(json.dumps({
        'approach_axis_xy': [1, 0], 'centerline_y_m': 0,
        'intersection_x_m': [0, 20], 'one_way_highway': one_way,
        'source_kind': 'generated_software_diagnostic',
        'highway_and_intersection_status_verified': False}) + '\n')
    with (folder / 'vehicle-footprints.jsonl').open('w') as stream:
        for frame in range(600):
            x = -45 + frame * 0.125
            left = (mode == 'approach_left' and 150 <= frame <= 300 or
                    mode == 'traversal_left' and 390 <= frame <= 450 or
                    mode == 'one_way' and 150 <= frame <= 300 or
                    mode == 'right' and 10 <= frame <= 40)
            y = 2 if left else -2
            body = [[x - 2, y - .8], [x + 2, y - .8],
                    [x + 2, y + .8], [x - 2, y + .8]]
            stream.write(json.dumps({'native_frame': frame, 'time_s': frame / 20,
                                     'body_xy_m': body, 'synthetic_diagnostic': True}) + '\n')


def run(folder, output):
    return subprocess.run([sys.executable, str(MEASURE), '--attempt', str(folder),
                           '--output', str(output)], capture_output=True, text=True,
                          timeout=30)


def main():
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    root.mkdir(parents=True, exist_ok=True)
    records = []
    with tempfile.TemporaryDirectory(prefix='c111250-zone-', dir=root) as scratch:
        scratch = Path(scratch)
        for mode in ('right', 'approach_left', 'traversal_left', 'one_way'):
            folder = scratch / mode
            make_attempt(folder, mode)
            output = folder / 'zone-report.json'
            finished = run(folder, output)
            if finished.returncode:
                raise AssertionError(finished.stderr)
            report = json.loads(output.read_text())
            assert report['frames'] == 600 and report['measurement_only'] is True
            assert report['legal_verdict_claimed'] is False
            assert report['source_sha256']['vehicle-footprints.jsonl'] == sha(folder / 'vehicle-footprints.jsonl')
            if mode == 'right':
                assert report['last_left_before_zone_frame'] == 40
                assert report['first_left_active_frame'] is None
            elif mode == 'approach_left':
                assert report['first_left_approach_frame'] == 150
            elif mode == 'traversal_left':
                assert report['first_left_traversal_frame'] == 390
            else:
                assert report['subsection_2_applicability'] == 'excluded_by_explicit_one_way_context'
                assert report['first_left_active_frame'] == 150
            records.append({'mode': mode, 'first_active_frame': report['first_active_frame'],
                            'first_left_active_frame': report['first_left_active_frame'],
                            'first_left_approach_frame': report['first_left_approach_frame'],
                            'first_left_traversal_frame': report['first_left_traversal_frame'],
                            'one_way_highway': report['one_way_highway'],
                            'source_sha256': report['source_sha256']})
        missing = scratch / 'missing'
        missing.mkdir()
        (missing / 'road-context.json').write_text((scratch / 'right/road-context.json').read_text())
        rejected = run(missing, missing / 'zone-report.json')
        assert rejected.returncode and 'Missing required source: vehicle-footprints.jsonl' in rejected.stderr
        corrupt = scratch / 'corrupt'
        make_attempt(corrupt, 'right')
        source = corrupt / 'vehicle-footprints.jsonl'
        lines = source.read_text().splitlines()
        row = json.loads(lines[200]); row['time_s'] = -1
        lines[200] = json.dumps(row)
        source.write_text('\n'.join(lines) + '\n')
        rejected = run(corrupt, corrupt / 'zone-report.json')
        assert rejected.returncode and 'Original frame/time order invalid' in rejected.stderr
    print(json.dumps({'passed': True, 'positive_count': len(records),
                      'negative_count': 2, 'records': records,
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
