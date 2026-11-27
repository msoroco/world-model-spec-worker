"""Inventory a complete compact synthetic long source transport.

The index is a portable design and byte audit. The pinned fixture recipe does
not support its graph/index synthesis or packed-source expansion.
"""

import hashlib
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FIXTURE = REPO / '.runtime-work/owner150142/tour-bus-below-primary-current-direct-v1/fixture'
STATIC = (
    'acquisition-provenance.json',
    'native-map-readback.json',
    'road.xodr',
    'statutory-context.json',
    'capture/manifest.json',
    'capture/recorder_info.txt',
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    transport = json.loads((HERE / 'current-tour-bus-below-source-transport.json').read_text())
    graph = json.loads((HERE / 'current-long-graph-reconstruction.json').read_text())
    packed = {}
    for item in transport['sources']:
        source = FIXTURE / item['source_path']
        if sha(source.read_bytes()) != item['expanded_sha256']:
            raise ValueError('Expanded source changed: ' + item['source_path'])
        if sha((HERE / item['packed_path']).read_bytes()) != item['packed_sha256']:
            raise ValueError('Packed source changed: ' + item['packed_path'])
        packed[item['source_path']] = {
            'transport': item['packed_path'],
            'transport_sha256': item['packed_sha256'],
            'expanded_sha256': item['expanded_sha256'],
            'expanded_bytes': item['expanded_bytes'],
        }
    static = {}
    literal_folder = HERE / 'current-tour-bus-below-source-literals'
    literal_folder.mkdir(exist_ok=True)
    for name in STATIC:
        raw = (FIXTURE / name).read_bytes()
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError('Literal source exceeds returned-file cap: ' + name)
        target = literal_folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FIXTURE / name, target)
        if target.read_bytes() != raw:
            raise ValueError('Literal transport differs: ' + name)
        static[name] = {'source': str(target.relative_to(HERE)),
                        'sha256': sha(raw), 'bytes': len(raw)}
    if graph['expanded_evidence_sha256'] != packed['capture/evidence.jsonl']['expanded_sha256']:
        raise ValueError('Graph reconstruction evidence binding differs')
    if graph['frame_index_sha256'] != sha((FIXTURE / 'capture/native/frames.jsonl').read_bytes()):
        raise ValueError('Graph reconstruction index binding differs')
    index = {
        'format': 'c150142-complete-synthetic-long-source-index-v1',
        'case_id': HERE.name + '__tour_bus_below',
        'source_kind': 'synthetic_native_sample',
        'frame_count': graph['frame_count'],
        'packed_sources': packed,
        'literal_sources': static,
        'derived_sources': {
            'capture/native/frames.jsonl': {
                'method': 'probe-current-long-graph-reconstruction.py:build_frame',
                'sha256': graph['frame_index_sha256'],
            },
            'capture/native/graphs/base/{frame:08d}.adapter.json': {
                'method': 'probe-current-long-graph-reconstruction.py:build_graph',
                'count': graph['graph_count'],
                'sequence_sha256': graph['graph_sequence_sha256'],
                'total_bytes': graph['graph_total_bytes'],
            },
        },
        'all_fixture_source_classes_inventoried': True,
        'source_bytes_verified_against_retained_scratch': True,
        'official_fixture_recipe_compatibility_passed': False,
        'original_native_observed': False,
    }
    path = HERE / 'current-long-complete-source-index.json'
    path.write_text(json.dumps(index, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'index': path.name, 'sha256': sha(path.read_bytes()),
                      'packed_sources': len(packed), 'literal_sources': len(static),
                      'derived_source_classes': len(index['derived_sources'])}, sort_keys=True))


if __name__ == '__main__':
    main()
