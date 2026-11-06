"""Exact pinned v1 package CPU diagnostic on retained synthetic steady source."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pickle
import shutil
import subprocess
import sys
import tempfile

import networkx as nx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.runtime_cli import execution_env


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_rows(path, values):
    Path(path).write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in values))


def fixture_at(destination, suffix):
    summary = json.loads((HERE / 'saved-steady-summary.json').read_text())
    retained = next(item['retained_positive'] for item in summary['records'] if item['case_suffix'] == suffix)
    shutil.copytree(retained, destination)
    for name in ('config.json', 'road.xodr', 'result.json', 'analysis-report.json'):
        (destination / name).unlink(missing_ok=True)
    evidence = rows(destination / 'capture/evidence.jsonl')
    frames = rows(destination / 'capture/native/frames.jsonl')
    trace = rows(destination / 'trace.jsonl')
    graph_dir = destination / 'capture/native/graphs/base'
    graph_dir.mkdir(parents=True, exist_ok=True)
    for event, frame, telemetry in zip(evidence, frames, trace):
        assert frame['frame'] == event['replay_frame']
        event['ego']['speed_provenance'] = 'original_trace_actor_get_velocity'
        event['synthetic_diagnostic'] = True
        telemetry['synthetic_diagnostic'] = True
        telemetry['control'] = {'throttle': 0, 'brake': 0, 'hand_brake': False}
        graph = nx.DiGraph()
        graph.graph.update(frame=frame['frame'], simulation_time_s=frame['time_s'],
                           synthetic_diagnostic=True, source='C10316 authored steady source')
        graph.add_node('ego', sem_class='ego', entity_id=event['actor_id'],
                       vertex=event['ego']['position_m'], forward=[1.0, 0.0, 0.0],
                       threedbbox=event['ego']['body_vertices_m'])
        (destination / 'capture/native' / frame['base']).write_bytes(pickle.dumps(graph, protocol=4))
    write_rows(destination / 'capture/evidence.jsonl', evidence)
    write_rows(destination / 'trace.jsonl', trace)
    manifest_path = destination / 'capture/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['sources']['trace.jsonl'] = hashlib.sha256((destination / 'trace.jsonl').read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix', choices=('witness_1', 'witness_2'), default='witness_1')
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2', 'fallback3'), default='primary')
    args = parser.parse_args()
    os.environ['PATH'] = str(ROOT / '.runtime-work/linux_arm64') + os.pathsep + os.environ.get('PATH', '')
    os.environ['LD_LIBRARY_PATH'] = str(ROOT / '.runtime-work/geos-wheel/shapely.libs') + os.pathsep + os.environ.get('LD_LIBRARY_PATH', '')
    scratch = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c10316-steady-package-'))
    source = scratch / 'fixture'
    fixture_at(source, args.suffix)
    manifest = HERE / 'draft-execution-manifest.json'
    case = 'training__C10316__NRS-484B-283-1d4__pedestrian__' + args.suffix
    receipt = run(manifest, case, source, scratch / 'output',
                  ROOT / 'runtime/pipeline/library',
                  ROOT / '.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',
                  args.candidate)
    negative = scratch / 'negative'
    materialize_case(manifest, case, negative, source, args.candidate)
    (negative / 'steady-samples.jsonl').unlink()
    failed = subprocess.run([sys.executable, str(negative / 'finalize.py'), '--attempt', str(negative),
                             '--output', str(negative / 'analysis-report.json')],
                            cwd=negative, env=execution_env(), text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
    (scratch / 'negative-analysis.log').write_text(failed.stdout)
    expected = 'Missing required source: steady-samples.jsonl'
    if failed.returncode == 0 or expected not in failed.stdout:
        raise RuntimeError('Countdown negative did not reject missing source: ' + failed.stdout)
    print(json.dumps({'scratch': str(scratch), 'case_suffix': args.suffix,
                      'candidate': args.candidate,
                      'positive': {key: value for key, value in receipt.items() if key != 'fixture_manifest'},
                      'negative': {'exit_code': failed.returncode,
                                   'removed': 'steady-samples.jsonl', 'error_contains': expected},
                      'scope': 'synthetic v1 software diagnostic; unselected and unaccepted'}))


if __name__ == '__main__':
    main()
