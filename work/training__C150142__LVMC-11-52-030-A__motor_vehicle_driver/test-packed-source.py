"""Exercise the lossless scratch-only synthetic source expansion proposal."""
import base64
import hashlib
import json
import tempfile
import zlib
from pathlib import Path

from packed_source import expand


ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT / '.runtime-work'
SCRATCH.mkdir(exist_ok=True)
sha = lambda data: hashlib.sha256(data).hexdigest()
rows = [dict(video_frame=i, native_frame=i, carla_frame=i,
             time_s=i / 20, views=['overview', 'approach',
                                    'reference_corner', 'driver_reference'])
        for i in range(2)]
full = ''.join(json.dumps(row) + '\n' for row in rows).encode()
compact = ''.join(json.dumps({k: row[k] for k in
                              ('video_frame', 'carla_frame', 'time_s')}) + '\n'
                  for row in rows).encode()
encoded = base64.b64encode(zlib.compress(full, 9))
with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='c150142-packed-test-') as name:
    folder = Path(name)
    (folder / 'video_frames.jsonl').write_bytes(compact)
    (folder / 'frames.zlib64').write_bytes(encoded)
    index = {'format': 'c150142-lossless-synthetic-source-pack-v1',
             'source_kind': 'synthetic_native_sample', 'sources': [
                 {'packed': 'frames.zlib64', 'packed_sha256': sha(encoded),
                  'expanded': 'video_frames.full.jsonl',
                  'expanded_sha256': sha(full), 'expanded_bytes': len(full)}]}
    (folder / 'packed-source-index.json').write_text(json.dumps(index))
    assert expand(folder) == 'synthetic_native_sample'
    assert (folder / 'video_frames.full.jsonl').read_bytes() == full
    (folder / 'video_frames.full.jsonl').unlink()
    (folder / 'frames.zlib64').write_bytes(encoded[:-1] + b'X')
    try:
        expand(folder)
    except ValueError as error:
        assert 'Packed source hash differs' in str(error)
    else:
        raise AssertionError('Changed packed source was accepted')
print('lossless synthetic source round trip passes; changed packed source rejects')
