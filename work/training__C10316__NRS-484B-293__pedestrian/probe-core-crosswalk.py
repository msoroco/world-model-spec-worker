"""CPU-only synthetic Core integration from C10316 source-bound saved frames."""
import argparse
import hashlib
import json
import pickle
import shutil
import sys
import tempfile
from pathlib import Path

import networkx as nx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import process, render
from worker_exchange.media import audit


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_rows(path, values):
    path.write_text(''.join(json.dumps(value, allow_nan=False) + '\n' for value in values))


def make_attempt(attempt, suffix):
    summary = json.loads((HERE / 'saved-crosswalk-summary.json').read_text())
    record = next(r for r in summary['records'] if r['case_suffix'] == suffix)
    source = Path(record['retained_positive'])
    shutil.copytree(source, attempt)
    graph_dir = attempt / 'capture/native/graphs/base'
    graph_dir.mkdir(parents=True)
    evidence = rows(attempt / 'capture/evidence.jsonl')
    frames = rows(attempt / 'capture/native/frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    assert len(evidence) == len(frames) == 240
    for event, frame, telemetry in zip(evidence, frames, trace):
        assert frame['frame'] == event['replay_frame']
        # The pinned adapter requires this exact enum for its diagnostic input.
        # Retain the explicit synthetic marker; this does not establish a Native reading.
        event['ego']['speed_provenance'] = 'original_trace_actor_get_velocity'
        event['synthetic_diagnostic'] = True
        telemetry['synthetic_diagnostic'] = True
        telemetry['control'] = {'throttle': 0, 'brake': 0, 'hand_brake': False}
        graph = nx.DiGraph()
        graph.graph.update(frame=frame['frame'], simulation_time_s=frame['time_s'],
                           synthetic_diagnostic=True,
                           source='C10316 authored saved pedestrian observation')
        graph.add_node('ego', sem_class='ego', entity_id=event['actor_id'],
                       vertex=event['ego']['position_m'],
                       forward=[1.0, 0.0, 0.0],
                       threedbbox=event['ego']['body_vertices_m'])
        (attempt / 'capture/native' / frame['base']).write_bytes(pickle.dumps(graph, protocol=4))
    write_rows(attempt / 'capture/evidence.jsonl', evidence)
    write_rows(attempt / 'trace.jsonl', trace)
    manifest_path = attempt / 'capture/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['sources']['trace.jsonl'] = hashlib.sha256((attempt / 'trace.jsonl').read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix', choices=('reference', 'contrast'), default='reference')
    args = parser.parse_args()
    scratch = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c10316-core-'))
    attempt = scratch / 'attempt'
    make_attempt(attempt, args.suffix)
    core = process(attempt, attempt / 'converted', ROOT / 'runtime/pipeline/library',
                   ROOT / '.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck')
    scenes = json.loads((attempt / 'converted/trace.json').read_text())['scenes']
    assert len(scenes) == 240
    assert all('pedestrian' in u['classes'] for scene in scenes for u in scene['users'] if u['track'] == 107)
    print(json.dumps({'scratch': str(scratch), 'core': core,
                      'scenes': len(scenes), 'scope': 'synthetic source-bound Core diagnostic; no Native acceptance'}),
          flush=True)
    config = json.loads((attempt / 'config.json').read_text())
    video = render(attempt, attempt / 'converted', config['case'])
    decoded = audit(video['video'], 240, mapping_sha256=video['frame_map_sha256'],
                    receipt=attempt / 'final-decode.json')
    print(json.dumps({'render_frames': video['frames'], 'final_decode_passed': decoded['passed'],
                      'scope': 'synthetic software integration; no physical observation or acceptance'}))


if __name__ == '__main__':
    main()
