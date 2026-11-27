"""Exercise the pinned generator with long evidence split into bounded chunks."""
import hashlib
import json
import shutil
from pathlib import Path

from worker_exchange import fixture_generator


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / '.runtime-work/lvmc030-owner-20261126/chunked-fixture'
LIMIT = 2 * 1024 * 1024
FRAMES = 36120


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    pieces = {}
    for chunk_index in range(4):
        first = chunk_index * (FRAMES // 4)
        end = (chunk_index + 1) * (FRAMES // 4)
        rows = []
        for frame in range(first, end):
            rows.append(json.dumps({
                'original_frame': frame, 'replay_frame': frame,
                'actor_id': 0, 'recording_time_s': 0,
                'replay_simulation_time_s': 0,
                'ego': {'speed_provenance': 'synthetic_native_sample',
                        'speed_mps': 0, 'position_m': []},
            }, separators=(',', ':')))
        text = '\n'.join(rows) + '\n'
        if len(text.encode()) >= LIMIT:
            raise ValueError('Bounded chunk itself exceeds returned-file limit')
        pieces[f'capture/evidence.part{chunk_index}.jsonl'] = text
    spec = {'files': pieces, 'graphs': [], 'videos': []}
    fixture_generator.inspect(spec)
    fixture_generator.generate(spec, SCRATCH)
    produced = sorted(p.relative_to(SCRATCH).as_posix()
                      for p in SCRATCH.rglob('*') if p.is_file())
    if produced != sorted(pieces):
        raise ValueError('Pinned generator did not preserve chunk paths')
    if (SCRATCH / 'capture/evidence.jsonl').exists():
        raise ValueError('Pinned generator unexpectedly joined the chunks')
    graph = {'files': {}, 'graphs': [{
        'path': 'capture/evidence.jsonl', 'attributes': {},
        'nodes': [], 'edges': [],
    }], 'videos': []}
    try:
        fixture_generator.inspect(graph)
    except ValueError as exc:
        graph_rejection = str(exc)
    else:
        raise ValueError('Pinned graph route unexpectedly accepted JSONL')
    if 'adapter JSON' not in graph_rejection:
        raise ValueError('Unexpected graph route rejection')
    output = {
        'format': 'c150142-pinned-chunked-fixture-probe-v1',
        'fixture_generator_sha256': sha(Path(fixture_generator.__file__)),
        'frames': FRAMES,
        'returned_file_limit_bytes': LIMIT,
        'chunk_bytes': {name: len(value.encode()) for name, value in pieces.items()},
        'combined_explicit_text_bytes': sum(len(value.encode()) for value in pieces.values()),
        'generated_paths': produced,
        'canonical_evidence_generated': False,
        'graph_jsonl_rejection': graph_rejection,
        'scratch_output': str(SCRATCH.relative_to(REPO)),
        'finding': 'Scratch outputs may exceed the return limit, but the pinned generator preserves explicit chunk paths and cannot construct the required single evidence.jsonl from bounded returned members.',
        'official_public_compatibility_passed': False,
    }
    print(json.dumps(output, sort_keys=True, separators=(',', ':')))


if __name__ == '__main__':
    main()
