"""Generated 30-second source-shape diagnostic for green-turn-arrow timing."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
MEASURE = HERE / 'native/arrow_measure.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make(folder, mode):
    folder.mkdir()
    (folder / 'intersection-context.json').write_text(json.dumps({
        'arrow_direction': 'left', 'intersection_bounds_m': [0, 20, -8, 8],
        'adjacent_crosswalk_bounds_m': [8, 12, -8, 8],
        'source_kind': 'generated_software_diagnostic',
        'physical_signal_governance_verified': False,
        'participant_lawfulness_verified': False}) + '\n')
    with (folder / 'signal_frames.jsonl').open('w') as signals, (folder / 'motion_frames.jsonl').open('w') as motions:
        for frame in range(600):
            lit = 100 <= frame <= 500 and not (mode == 'unlit' and 220 <= frame <= 230)
            signals.write(json.dumps({'native_frame': frame, 'time_s': frame / 20,
                                      'green_arrow_alone': lit, 'illuminated': lit,
                                      'synthetic_diagnostic': True}) + '\n')
            ped_here = 250 <= frame <= 290
            other_here = 300 <= frame <= 340
            speed = 0 if mode == 'yield' and (ped_here or other_here) else 2
            motions.write(json.dumps({'native_frame': frame, 'time_s': frame / 20,
                'ego_xy_m': [(frame - 200) * .1, 0],
                'ego_heading_xy': [0, -1 if mode == 'wrong_direction' else 1],
                'ego_speed_mps': speed,
                'pedestrian_xy_m': [10, 0] if ped_here else [50, 50],
                'other_traffic_xy_m': [5, 0] if other_here else [50, 50],
                'synthetic_diagnostic': True}) + '\n')


def run(folder, output):
    return subprocess.run([sys.executable, str(MEASURE), '--attempt', str(folder),
        '--output', str(output)], capture_output=True, text=True, timeout=30)


def main():
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    root.mkdir(parents=True, exist_ok=True)
    records = []
    with tempfile.TemporaryDirectory(prefix='c111603-arrow-', dir=root) as scratch:
        scratch = Path(scratch)
        for mode in ('yield', 'crosswalk_overlap', 'wrong_direction', 'unlit'):
            folder = scratch / mode
            make(folder, mode)
            output = folder / 'measurement.json'
            run_result = run(folder, output)
            if run_result.returncode:
                raise AssertionError(run_result.stderr)
            report = json.loads(output.read_text())
            assert report['frames'] == 600 and not report['legal_verdict_claimed']
            assert report['source_sha256']['motion_frames.jsonl'] == sha(folder / 'motion_frames.jsonl')
            if mode == 'yield':
                assert report['first_pedestrian_crosswalk_motion_overlap_frame'] is None
                assert report['first_other_traffic_motion_overlap_frame'] is None
                assert report['first_direction_mismatch_frame'] is None
            elif mode == 'crosswalk_overlap':
                assert report['first_pedestrian_crosswalk_motion_overlap_frame'] == 250
                assert report['first_other_traffic_motion_overlap_frame'] == 300
            elif mode == 'wrong_direction':
                assert report['first_direction_mismatch_frame'] == 200
            else:
                assert report['first_unlit_intersection_motion_frame'] == 220
            records.append({'mode': mode,
                'first_pedestrian_overlap_frame': report['first_pedestrian_crosswalk_motion_overlap_frame'],
                'first_other_traffic_overlap_frame': report['first_other_traffic_motion_overlap_frame'],
                'first_direction_mismatch_frame': report['first_direction_mismatch_frame'],
                'first_unlit_motion_frame': report['first_unlit_intersection_motion_frame'],
                'source_sha256': report['source_sha256']})
        missing = scratch / 'missing'
        missing.mkdir()
        (missing / 'intersection-context.json').write_text((scratch / 'yield/intersection-context.json').read_text())
        failed = run(missing, missing / 'measurement.json')
        assert failed.returncode and 'Missing required source: signal_frames.jsonl' in failed.stderr
        bad = scratch / 'bad_join'
        make(bad, 'yield')
        path = bad / 'motion_frames.jsonl'
        lines = path.read_text().splitlines()
        item = json.loads(lines[211]); item['native_frame'] = 210
        lines[211] = json.dumps(item); path.write_text('\n'.join(lines) + '\n')
        failed = run(bad, bad / 'measurement.json')
        assert failed.returncode and 'Original Native frame join differs' in failed.stderr
    print(json.dumps({'passed': True, 'positive_count': 4, 'negative_count': 2,
                      'records': records, 'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
