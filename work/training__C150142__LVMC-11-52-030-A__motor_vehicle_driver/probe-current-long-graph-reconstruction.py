"""Verify compact reconstruction of a retained synthetic long Native graph set.

This is a worker-owned source transport probe. The pinned fixture recipe does
not execute this program, so its proof is not a public compatibility receipt.
"""

import base64
import hashlib
import json
from pathlib import Path
import zlib


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FIXTURE = REPO / '.runtime-work/owner150142/tour-bus-below-primary-current-direct-v1/fixture'
PACKED = HERE / 'current-tour-bus-below-capture-evidence.jsonl.zlib64'
PROOF = HERE / 'current-long-graph-reconstruction.json'
COUNT = 36120


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build_graph(row):
    frame = row['original_frame']
    graph = {
        'format': 'native-adapter-graph-v1',
        'multigraph': False,
        'metadata': {'frame': frame, 'observed_evidence': row['original_observations']},
        'nodes': [],
        'edges': [],
    }
    return json.dumps(graph, separators=(',', ':')).encode() + b'\n'


def build_frame(row):
    frame = row['original_frame']
    path = f'graphs/base/{frame:08d}.adapter.json'
    record = {
        'frame': frame,
        'time_s': row['recording_time_s'],
        'simulation_time': row['replay_simulation_time_s'],
        'base': path,
        'adapter_graph': path,
    }
    return json.dumps(record).encode() + b'\n'


def main():
    encoded = PACKED.read_bytes()
    evidence = zlib.decompress(base64.b64decode(encoded, validate=True))
    source = FIXTURE / 'capture/evidence.jsonl'
    if evidence != source.read_bytes():
        raise ValueError('Packed evidence differs from retained full evidence')
    rows = evidence.splitlines(keepends=True)
    if len(rows) != COUNT:
        raise ValueError('Long evidence row count differs')
    frame_hash = hashlib.sha256()
    graph_hash = hashlib.sha256()
    graph_bytes = 0
    for index, raw in enumerate(rows):
        row = json.loads(raw)
        if row['original_frame'] != index or row['replay_frame'] != index:
            raise ValueError('Evidence frame identity differs')
        graph = build_graph(row)
        frame_hash.update(build_frame(row))
        graph_hash.update(graph)
        graph_bytes += len(graph)
        actual = FIXTURE / f'capture/native/graphs/base/{index:08d}.adapter.json'
        if graph != actual.read_bytes():
            raise ValueError(f'Native graph differs at frame {index}')
    index_source = FIXTURE / 'capture/native/frames.jsonl'
    if frame_hash.hexdigest() != sha(index_source.read_bytes()):
        raise ValueError('Reconstructed frame index differs')
    mutated = json.loads(rows[0])
    mutated['original_observations']['frame'] = -1
    if build_graph(mutated) == (FIXTURE / 'capture/native/graphs/base/00000000.adapter.json').read_bytes():
        raise ValueError('Mutation probe did not change graph bytes')
    proof = {
        'format': 'c150142-long-synthetic-graph-reconstruction-v1',
        'case_id': HERE.name + '__tour_bus_below',
        'source_kind': 'synthetic_native_sample',
        'packed_evidence_sha256': sha(encoded),
        'expanded_evidence_sha256': sha(evidence),
        'expanded_evidence_bytes': len(evidence),
        'frame_count': COUNT,
        'frame_index_sha256': frame_hash.hexdigest(),
        'graph_count': COUNT,
        'graph_total_bytes': graph_bytes,
        'graph_sequence_sha256': graph_hash.hexdigest(),
        'per_graph_byte_identity': True,
        'frame_index_byte_identity': True,
        'changed_observation_rejected': True,
        'official_fixture_recipe_compatibility_passed': False,
        'original_native_observed': False,
    }
    PROOF.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps(proof, sort_keys=True))


if __name__ == '__main__':
    main()
