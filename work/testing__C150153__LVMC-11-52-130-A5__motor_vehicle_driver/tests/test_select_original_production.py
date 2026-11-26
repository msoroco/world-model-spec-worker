"""Synthetic reviewed packets cannot select original production cases."""
import hashlib
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from select_original_production import select
from test_reviewed_site import ReviewedSiteTests


class OriginalSelectionTests(unittest.TestCase):
    def selected_hash(self):
        selected = HERE / 'execution-manifest.json'
        return hashlib.sha256(selected.read_bytes()).hexdigest() if selected.exists() else None

    def test_repository_diagnostic_packet_is_never_selected(self):
        before = self.selected_hash()
        scratch = Path('.runtime-work/c150153-original-selection-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            packet, sources, _ = ReviewedSiteTests().make_packet(Path(temp))
            with self.assertRaisesRegex(ValueError, 'external to worker repository'):
                select(packet, sources, 4.0)
            with patch('select_original_production.ROOT', Path('/unmatched-original-input-root')):
                with self.assertRaisesRegex(ValueError, 'original reviewed site provenance required'):
                    select(packet, sources, 4.0)
            self.assertEqual(self.selected_hash(), before)

    def test_changed_reviewed_source_fails_before_selection(self):
        before = self.selected_hash()
        scratch = Path('.runtime-work/c150153-original-selection-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            packet, sources, data = ReviewedSiteTests().make_packet(Path(temp))
            source = sources / data['sources']['map']['path']
            source.write_text('changed synthetic map source\n')
            with patch('select_original_production.ROOT', Path('/unmatched-original-input-root')):
                with self.assertRaisesRegex(ValueError, 'original source hash differs: map'):
                    select(packet, sources, 4.0)
            self.assertEqual(self.selected_hash(), before)


if __name__ == '__main__':
    unittest.main()
