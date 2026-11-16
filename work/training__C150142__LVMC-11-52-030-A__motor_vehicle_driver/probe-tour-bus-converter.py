"""Exercise the frozen converter on a three-frame slice of a synthetic capture."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(
    REPO / '.runtime-work/c150142-tour-bus-converter-probe-cache')
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
sys.path.insert(1, str(REPO / 'runtime/pipeline/python'))
from traffic_spec_adapter.adapter import convert


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def first_rows(source, target, count=3):
    with Path(source).open() as incoming, Path(target).open('x') as outgoing:
        for _ in range(count):
            row = incoming.readline()
            if not row:
                raise ValueError('Synthetic source is shorter than micro probe')
            outgoing.write(row)


def probe(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    private = REPO / '.runtime-work'
    if private not in source.parents or private not in output.parents or output.exists():
        raise ValueError('Use a fresh ignored diagnostic output')
    original = output / 'original'
    capture = original / 'capture'
    graph_dir = capture / 'native/graphs/base'
    graph_dir.mkdir(parents=True)
    for name in ('config.json', 'road.xodr', 'acquisition-provenance.json',
                 'native-map-readback.json', 'statutory-context.json'):
        shutil.copy2(source / name, original / name)
    shutil.copy2(source / 'capture/recorder_info.txt', capture / 'recorder_info.txt')
    for i in range(3):
        name = f'{i:08d}.pkl'
        shutil.copy2(source / 'capture/native/graphs/base' / name, graph_dir / name)
    first_rows(source / 'trace.jsonl', original / 'trace.jsonl')
    first_rows(source / 'capture/evidence.jsonl', capture / 'evidence.jsonl')
    first_rows(source / 'capture/native/frames.jsonl', capture / 'native/frames.jsonl')
    manifest = json.loads((source / 'capture/manifest.json').read_text())
    manifest['frames'] = 3
    manifest['sources']['trace.jsonl'] = sha(original / 'trace.jsonl')
    (capture / 'manifest.json').write_text(json.dumps(manifest) + '\n')
    converted = output / 'converted'
    report = convert(capture, original, REPO / 'runtime/pipeline/library',
                     converted, diagnostic_fixture=True)
    return {'source_kind': 'synthetic_native_sample', 'frames': 3,
            'original_native_observed': False,
            'converted': str(converted), 'report_keys': sorted(report)}


if __name__ == '__main__':
    print(json.dumps(probe(sys.argv[1], sys.argv[2]), sort_keys=True))
