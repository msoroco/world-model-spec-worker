import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from delivery_audit import audit_live_sources, sha


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value, sort_keys=True) + '\n')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


class LiveSourceAuditTests(unittest.TestCase):
    def test_live_source_chain_and_rejections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = 'exact-case'
            for kind in ('route', 'boundary', 'camera'):
                put(root/f'reviewed-{kind}.json', {'kind': kind})
            index = {'case_id': case, 'reviewer': 'independent-reviewer',
                     'review_note': 'original packet review',
                     'packet_refs': {kind: {'sha256': sha(root/f'reviewed-{kind}.json')}
                                     for kind in ('route', 'boundary', 'camera')}}
            put(root/'reviewed-source-index.json', index)
            put(root/'acquisition-provenance.json', {
                'provenance_kind': 'native', 'diagnostic_fixture': False,
                'source_index_sha256': sha(root/'reviewed-source-index.json')})
            for name in ('road.xodr', 'trace.jsonl', 'carla_recorder.log',
                         'video_frames.jsonl', 'source-manifest.json', 'extra-source.txt'):
                put(root/name, name)
            put(root/'capture/evidence.jsonl', {'original_frame': 1,
                'replay_frame': 1, 'recording_time_s': 0.05})
            put(root/'capture/manifest.json', {'extraction_confirmed': True, 'frames': 1,
                'sources': {name: sha(root/name) for name in
                            ('road.xodr', 'trace.jsonl', 'carla_recorder.log')}})
            videos = {'overview': {'sha256': 'a', 'rgb_sequence_sha256': 'b'}}
            put(root/'native-export-receipt.json', {'case_id': case,
                'graph_manifest_sha256': sha(root/'capture/manifest.json'),
                'trace_sha256': sha(root/'trace.jsonl'),
                'frame_map_sha256': sha(root/'video_frames.jsonl'),
                'videos': videos})
            names = ('road.xodr', 'trace.jsonl', 'video_frames.jsonl',
                     'capture/manifest.json', 'capture/evidence.jsonl',
                     'native-export-receipt.json', 'extra-source.txt')
            sources = {name: sha(root/name) for name in names}
            put(root/'capture-seal.json', {'provenance_kind': 'native', 'frames': 1,
                'restoration': {'restored': True},
                'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
                'sources': sources, 'source_digest': digest(sources)})
            put(root/'physical-review.json', {'case_id': case,
                'reviewer': 'independent-reviewer', 'physical_completion_verified': True,
                'source_sha256': {'capture-seal.json': sha(root/'capture-seal.json'),
                                  'source-manifest.json': sha(root/'source-manifest.json')}})
            frames = [{'frame': 1}]
            mapping = [{'time_s': 0.05}]
            self.assertIn('capture_seal_sha256',
                          audit_live_sources(root, case, frames, videos, mapping))
            (root/'physical-review.json').unlink()
            with self.assertRaises(FileNotFoundError):
                audit_live_sources(root, case, frames, videos, mapping)
            put(root/'physical-review.json', {'case_id': case,
                'reviewer': 'independent-reviewer', 'physical_completion_verified': True,
                'source_sha256': {'capture-seal.json': sha(root/'capture-seal.json'),
                                  'source-manifest.json': sha(root/'source-manifest.json')}})
            seal = json.loads((root/'capture-seal.json').read_text())
            seal['source_digest'] = '0' * 64
            put(root/'capture-seal.json', seal)
            with self.assertRaisesRegex(ValueError, 'source tree digest differs'):
                audit_live_sources(root, case, frames, videos, mapping)
            seal['source_digest'] = digest(sources)
            put(root/'capture-seal.json', seal)
            put(root/'extra-source.txt', 'changed sealed context')
            with self.assertRaisesRegex(ValueError, 'source tree differs'):
                audit_live_sources(root, case, frames, videos, mapping)


if __name__ == '__main__':
    unittest.main()
