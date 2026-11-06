"""Run the pixel-review contract on an encoded 480-frame synthetic capture."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE/'native'))
spec = importlib.util.spec_from_file_location('fixture', HERE/'saved-fixture-proof.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
from fallback_triggers import evaluate
from pixel_visibility import measure as measure_pixels


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work', prefix='c329610-pixel-path-') as temporary:
        attempt = Path(temporary)/'attempt'
        fixture.make_base(attempt, 'controlled_1', 1.75, 480)
        finalizer = HERE/'native/finalize.py'
        env = dict(os.environ)
        env['PYTHONPATH'] = str(ROOT/'runtime/pipeline/scenario_pipeline')
        result = subprocess.run([sys.executable, str(finalizer), '--attempt', str(attempt),
                                 '--output', str(attempt/'analysis-report.json')],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env=env, timeout=300)
        if result.returncode:
            raise RuntimeError(result.stdout)
        native = rows(attempt/'native_samples.jsonl')
        mapping = rows(attempt/'video_frames.jsonl')
        approach = [i for i, sample in enumerate(native)
                    if -35 <= sample['native_center_xy_m'][0] <= -10]
        review = [{'video_frame': i, 'native_frame': mapping[i]['native_frame'],
                   'body_visible': True, 'centerline_visible': True} for i in approach]
        (attempt/'pixel_review.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in review))
        pixel = measure_pixels(attempt/'native_samples.jsonl', attempt/'video_frames.jsonl',
                               attempt/'approach.mkv', attempt/'pixel_review.jsonl')
        (attempt/'pixel_audit.json').write_text(json.dumps(pixel)+'\n')
        geometry = json.loads((attempt/'road_geometry.json').read_text())
        route = {'source_kind': 'native_map_readback', 'connected_lane_link': True,
                 'full_body_destination_exit_observed_by_24s': True,
                 'native_samples_sha256': sha(attempt/'native_samples.jsonl'),
                 'road_geometry_sha256': sha(attempt/'road_geometry.json'),
                 'native_map_sha256': geometry['native_map_sha256']}
        (attempt/'route_audit.json').write_text(json.dumps(route)+'\n')
        def trigger():
            return evaluate(attempt/'native_samples.jsonl', attempt/'road_geometry.json',
                            attempt/'route_audit.json', attempt/'pixel_audit.json', 1.75)
        baseline = trigger()
        if any(baseline[key] for key in ('fallback1','fallback2','fallback3')):
            raise RuntimeError('Synthetic baseline selected a fallback')
        review[-1]['centerline_visible'] = False
        (attempt/'pixel_review.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in review))
        try:
            trigger()
        except ValueError as error:
            if 'Pixel review source or count mismatch' not in str(error):
                raise
        else:
            raise RuntimeError('Changed review source was accepted')
        print(json.dumps({'passed': True, 'encoded_source_frames': 480,
                          'reviewed_approach_frames': len(approach),
                          'source_video_sha256': pixel['source_video_sha256'],
                          'changed_review_rejected': True,
                          'scope': 'synthetic encoded media and saved frame path only; no original pixels or CARLA'}))


if __name__ == '__main__':
    main()
