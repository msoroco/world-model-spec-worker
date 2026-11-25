import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from delivery_audit import VIEWS, audit
from overpass_source import sha


def write(path, value):
    path.write_text(json.dumps(value) + '\n')


def fixture(root):
    names = {'scene.json', 'candidate-overpass.xodr', 'body-history.jsonl',
             'video_frames.jsonl', 'camera-frame-joins.jsonl', 'reviewed-site.json',
             'reviewed-site-source.txt', 'municipal-designation-source.txt',
             'original-sources.json', *(name + '.mkv' for name in VIEWS)}
    for name in names:
        (root / name).write_text(name + '\n')
    sources = {name: sha(root / name) for name in names}
    from hashlib import sha256
    digest = sha256(json.dumps(sources, sort_keys=True, separators=(',', ':'),
                               ensure_ascii=False).encode()).hexdigest()
    write(root / 'capture-seal.json', {
        'format': 'worker-sealed-capture', 'provenance_kind': 'native',
        'diagnostic_fixture': False, 'frames': 900,
        'restoration': {'restored': True},
        'encoder_exit_codes': {name: 0 for name in VIEWS},
        'sources': sources, 'source_digest': digest})
    write(root / 'acquisition-provenance.json',
          {'provenance_kind': 'native', 'diagnostic_fixture': False})
    site_sha = sources['reviewed-site.json']
    write(root / 'original-pixel-review.json', {
        'format': 'c188132-original-pixel-review-v1',
        'provenance_kind': 'original_review', 'case_id': 'test-case',
        'capture_seal_sha256': sha(root / 'capture-seal.json'),
        'reviewer': 'fixture reviewer', 'source_method': 'unit fixture',
        'observations': {name: {'video_sha256': sources[name + '.mkv'],
                                'original_frames_reviewed': 900,
                                'pedestrian_visible': True,
                                'roadway_vehicles_visible': True,
                                'overpass_structure_visible': True} for name in VIEWS},
        'physical_review': {'provided_overhead_crossing': True,
                            'usable_deck_access': True,
                            'pedestrian_crossing_completed': True,
                            'all_roadway_vehicles_reviewed': True,
                            'reviewed_site_sha256': site_sha}})
    original = {'measurement': {'case_id': 'test-case'},
                'source_hashes': {'site_review': site_sha}}
    media = {'case_id': 'test-case', 'frames': 900,
             'cameras': {name: {'sha256': sources[name + '.mkv']} for name in VIEWS}}
    return original, media


class DeliveryAuditTests(unittest.TestCase):
    def test_requires_seal_and_original_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, 'missing or escaped original source'):
                audit(root, pixel_review=root / 'original-pixel-review.json')
            fixture(root)
            provenance = root / 'acquisition-provenance.json'
            write(provenance, {'provenance_kind': 'synthetic_fixture',
                               'diagnostic_fixture': True})
            with self.assertRaisesRegex(ValueError, 'sealed original Native'):
                audit(root, pixel_review=root / 'original-pixel-review.json')

    def test_reaudits_sealed_media_and_review_bindings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original, media = fixture(root)
            with patch('delivery_audit.audit_saved', return_value=original), \
                 patch('delivery_audit.audit_media', return_value=media) as decode:
                result = audit(root, pixel_review=root / 'original-pixel-review.json')
                self.assertTrue(result['checks']['actual_pixels'])
                self.assertEqual(decode.call_count, 1)
                review = root / 'original-pixel-review.json'
                value = json.loads(review.read_text())
                value['observations']['overview']['video_sha256'] = 'stale'
                write(review, value)
                with self.assertRaisesRegex(ValueError, 'visibility review incomplete'):
                    audit(root, pixel_review=review)
                value['observations']['overview']['video_sha256'] = media['cameras']['overview']['sha256']
                value['physical_review']['usable_deck_access'] = False
                write(review, value)
                with self.assertRaisesRegex(ValueError, 'physical completion review incomplete'):
                    audit(root, pixel_review=review)
                (root / 'overview.mkv').write_text('changed\n')
                with self.assertRaisesRegex(ValueError, 'sealed Native source hash differs'):
                    audit(root, pixel_review=review)


if __name__ == '__main__':
    unittest.main()
