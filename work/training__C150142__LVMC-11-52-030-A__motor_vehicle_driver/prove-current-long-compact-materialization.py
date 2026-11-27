"""Rebuild one complete synthetic long fixture from work text, then run Core.

The pinned public fixture recipe cannot call this pre-analysis materializer.
This diagnostic uses the selected construction but is not an official receipt.
"""

import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zlib


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.common import digest
from worker_exchange.fixture_recipe import fixture_fingerprint
from worker_exchange.measurement_contract import verify_report
from worker_exchange.package_compatibility import _process_fixture, materialize_case
from worker_exchange.runtime_cli import execution_env

INDEX = HERE / 'current-long-complete-source-index.json'
MANIFEST = HERE / 'execution-manifest.json'
CASE = HERE.name + '__tour_bus_below'
CONTRACT = HERE / 'selected-primary/tour_bus_below/selected-measurement-contracts/tour_bus_below.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def materialize_sources(folder, index):
    folder.mkdir()
    for name, info in index['packed_sources'].items():
        packed = (HERE / info['transport']).read_bytes()
        if sha(packed) != info['transport_sha256']:
            raise ValueError('Packed transport differs: ' + name)
        raw = zlib.decompress(base64.b64decode(packed, validate=True))
        if len(raw) != info['expanded_bytes'] or sha(raw) != info['expanded_sha256']:
            raise ValueError('Expanded source differs: ' + name)
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    for name, info in index['literal_sources'].items():
        source = HERE / info['source']
        if source.stat().st_size != info['bytes'] or sha(source.read_bytes()) != info['sha256']:
            raise ValueError('Literal source differs: ' + name)
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    module_spec = importlib.util.spec_from_file_location(
        'c150142_graph_reconstruction', HERE / 'probe-current-long-graph-reconstruction.py')
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    frame_digest = hashlib.sha256()
    graph_digest = hashlib.sha256()
    graph_root = folder / 'capture/native/graphs/base'
    graph_root.mkdir(parents=True)
    frames_path = folder / 'capture/native/frames.jsonl'
    with (folder / 'capture/evidence.jsonl').open('rb') as source, frames_path.open('wb') as frame_out:
        for number, raw in enumerate(source):
            row = json.loads(raw)
            if row['original_frame'] != number or row['replay_frame'] != number:
                raise ValueError('Evidence frame order differs')
            graph = module.build_graph(row)
            frame = module.build_frame(row)
            (graph_root / f'{number:08d}.adapter.json').write_bytes(graph)
            frame_out.write(frame)
            graph_digest.update(graph)
            frame_digest.update(frame)
    if number + 1 != index['frame_count']:
        raise ValueError('Rebuilt graph count differs')
    derived = index['derived_sources']
    if frame_digest.hexdigest() != derived['capture/native/frames.jsonl']['sha256']:
        raise ValueError('Rebuilt frame index differs')
    if graph_digest.hexdigest() != derived['capture/native/graphs/base/{frame:08d}.adapter.json']['sequence_sha256']:
        raise ValueError('Rebuilt graph sequence differs')
    return {'frames': number + 1, 'frame_index_sha256': frame_digest.hexdigest(),
            'graph_sequence_sha256': graph_digest.hexdigest()}


def run(output, validator):
    output = Path(output).resolve()
    validator = Path(validator).resolve()
    if REPO / '.runtime-work' not in output.parents or output.exists():
        raise ValueError('Use a fresh ignored .runtime-work output root')
    if not validator.is_file():
        raise ValueError('Pinned validator missing')
    index_bytes = INDEX.read_bytes()
    index = json.loads(index_bytes)
    if index['case_id'] != CASE or index['official_fixture_recipe_compatibility_passed']:
        raise ValueError('Source index scope differs')
    output.mkdir(parents=True)
    fixture = output / 'fixture'
    rebuilt = materialize_sources(fixture, index)
    inventory = fixture_fingerprint(fixture)
    source = {'fixture_sha256': digest(inventory), 'fixture_manifest': inventory}
    positive = output / 'positive'
    receipt = _process_fixture(MANIFEST, CASE, fixture, positive,
                               REPO / 'runtime/library', validator, 'primary', source)
    contract = json.loads(CONTRACT.read_text())
    measurements = verify_report(contract,
                                 json.loads((positive / 'analysis-report.json').read_text()), fixture)
    negative = output / 'negative'
    materialize_case(MANIFEST, CASE, negative, fixture, 'primary')
    removed = contract['negative']['remove'][0]
    (negative / removed).unlink()
    failure = subprocess.run(
        [sys.executable, str(negative / 'finalize_selected.py'),
         '--attempt', str(negative), '--output', str(negative / 'analysis-report.json')],
        cwd=negative, env=execution_env(), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, timeout=300)
    (output / 'negative-analysis.log').write_text(failure.stdout)
    expected = contract['negative']['error_contains']
    if failure.returncode == 0 or expected not in failure.stdout:
        raise ValueError('Missing-source negative did not reject ' + removed)
    return {
        'format': 'c150142-compact-materialized-long-core-v1',
        'case_id': CASE, 'candidate_id': 'primary', 'passed': True,
        'source_index_sha256': sha(index_bytes),
        'manifest_sha256': sha(MANIFEST.read_bytes()),
        'construction_sha256': receipt['construction_sha256'],
        'fixture_sha256': source['fixture_sha256'],
        'rebuilt': rebuilt,
        'core_checks': receipt['checks'],
        'measurement_keys': sorted(measurements),
        'negative_removed': removed,
        'negative_error_contains': expected,
        'negative_log_sha256': sha((output / 'negative-analysis.log').read_bytes()),
        'official_fixture_recipe_compatibility_passed': False,
        'original_native_observed': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--validator', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.validator), indent=2, sort_keys=True))
