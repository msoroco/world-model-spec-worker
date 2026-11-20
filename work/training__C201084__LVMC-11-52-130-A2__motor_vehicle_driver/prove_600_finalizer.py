"""Exercise the full saved-source clock on synthetic diagnostic media only."""
import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

from fire_lane_survey import CAMERAS
from native_finalize import finalize
from source_measurement import sha
from test_native_finalize import fixture


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def run(output):
    output = Path(output).resolve()
    if output.exists() or ROOT/'.runtime-work' not in output.parents:
        raise ValueError('Use a fresh ignored .runtime-work diagnostic attempt')
    output.mkdir(parents=True)
    fixture(output)
    first = [json.loads(line) for line in
             (output/'native-actors.jsonl').read_text().splitlines()]
    actors = []
    frames = []
    for index in range(600):
        actor = copy.deepcopy(first[min(index, len(first)-1)])
        actor['frame'] = 100+index
        actors.append(actor)
        frames.append({'video_frame': index, 'carla_frame': 100+index,
                       'time_s': index/20})
    (output/'native-actors.jsonl').write_text(
        ''.join(json.dumps(row, allow_nan=False)+'\n' for row in actors))
    (output/'video_frames.jsonl').write_text(
        ''.join(json.dumps(row, allow_nan=False)+'\n' for row in frames))
    for name in CAMERAS:
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
                        '-y','-f','lavfi','-i','color=c=black:s=16x16:r=20',
                        '-frames:v','600','-c:v','ffv1',
                        str(output/(name+'.mkv'))], check=True)
    originals = {name: sha(output/name) for name in
                 ('native-actors.jsonl','video_frames.jsonl',
                  'native-survey-readback.json',
                  *(name+'.mkv' for name in CAMERAS))}
    report = finalize(output, output/'analysis-report.json')
    sys.path.insert(0, str(ROOT/'runtime/pipeline'))
    from scenario_pipeline.worker_exchange.native_output import validate_result
    validate_result(json.loads((output/'result.json').read_text()))
    if originals != {name: sha(output/name) for name in originals}:
        raise ValueError('Diagnostic finalization changed retained source bytes')
    return {'format': 'c201084-600-frame-synthetic-finalizer-proof',
            'attempt': str(output), 'frames': 600,
            'source_kind': 'synthetic_native_sample',
            'four_cameras_decoded': set(report['source_sha256']) >=
                {name+'.mkv' for name in CAMERAS},
            'originals_preserved': True,
            'native_result_schema_validated': True,
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False,
            'source_sha256': originals,
            'analysis_report_sha256': sha(output/'analysis-report.json'),
            'native_result_sha256': sha(output/'result.json')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
