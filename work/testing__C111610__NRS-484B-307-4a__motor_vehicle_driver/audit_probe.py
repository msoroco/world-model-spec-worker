"""Exercise the independent auditor with decoded synthetic media and a source mutation.

This proves CPU audit behavior only. It does not claim Native capture or pixel visibility.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_delivery_audit import setup, sha
from pixel_checks import check as pixel_presence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    if not args.case.startswith(ROOT.name + '__'):
        raise ValueError('audit probe selects another assignment')
    output = Path(args.output).resolve()
    if not output.is_relative_to(REPO / '.runtime-work'):
        raise ValueError('audit probe output must stay under .runtime-work')
    pipeline_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if not pipeline_root.is_relative_to(REPO / '.runtime-work'):
        raise ValueError('export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first')
    sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
    from worker_exchange.media import audit as decode
    from delivery_audit import audit
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    occupied = args.case.endswith('__crosswalk_occupied_yield')
    traffic_case = args.case.endswith('__lawful_traffic_yield')
    case_id = setup(output, occupied, traffic_case)
    if case_id != args.case:
        raise ValueError('audit probe selected another case')
    video = output / 'analysis/raw.mkv'
    video.unlink()
    subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                    '-f', 'lavfi', '-i', 'testsrc2=size=64x64:rate=20',
                    '-frames:v', '4', '-c:v', 'ffv1', '-pix_fmt', 'yuv444p',
                    str(video)], check=True, timeout=60)
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        shutil.copyfile(video, output / (name + '.mkv'))
    acquisition = json.loads((output / 'acquisition.json').read_text())
    for name in ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                 'driver_reference.mkv'):
        acquisition[name] = {'kind': 'original_native',
                             'sha256': sha(output / name)}
    (output / 'acquisition.json').write_text(json.dumps(acquisition))
    seal = json.loads((output / 'capture-seal.json').read_text())
    seal['sources'] = {name: sha(output / name) for name in seal['sources']}
    (output / 'capture-seal.json').write_text(json.dumps(seal))
    native = json.loads((output / 'native-exit.json').read_text())
    native['capture_seal_sha256'] = sha(output / 'capture-seal.json')
    (output / 'native-exit.json').write_text(json.dumps(native))
    owner = json.loads((output / 'owner-release.json').read_text())
    owner['native_exit_sha256'] = sha(output / 'native-exit.json')
    (output / 'owner-release.json').write_text(json.dumps(owner))
    (output / 'decode.json').unlink()
    receipt = decode(video, 4,
        checkers={'pixel_presence': (sha(ROOT / 'pixel_checks.py'), pixel_presence)},
        mapping_sha256=sha(output / 'video_frames.jsonl'),
        receipt=output / 'decode.json')
    assert receipt['passed'] and receipt['frames'] == 4
    if args.negative:
        with (output / 'turn-history.jsonl').open('a') as stream:
            stream.write('{}\n')
    report = audit(output, output / 'processing.json', output / 'decode.json',
                   case_id)
    print(json.dumps({'scope': 'synthetic_cpu_audit_probe', 'report': report}, indent=2))


if __name__ == '__main__':
    main()
