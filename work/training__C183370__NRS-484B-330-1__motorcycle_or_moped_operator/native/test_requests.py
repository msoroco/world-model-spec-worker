"""Focused construction checks for the exact flagger response pair."""

import json
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from check_requests import check_pair, read_case
from runner import _cleanup_capture, _read_review


HERE = Path(__file__).resolve().parent


class ConstructionTests(unittest.TestCase):
    def setUp(self):
        scratch = Path('.runtime-work/c183370-construction-tests').resolve()
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.base = Path(self.temp.name)
        for suffix in ('probe_a', 'probe_b'):
            shutil.copytree(HERE / suffix, self.base / suffix)

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_pair(self):
        proof = check_pair(base=self.base)
        self.assertTrue(proof['passed'])
        self.assertEqual(proof['crossing_frames'], [1350, 1200])

    def test_reject_changed_case_scope(self):
        path = self.base / 'probe_b' / 'config.json'
        original = path.read_text()
        try:
            changed = json.loads(original)
            changed['controller_policy'] = 'hold_until_release'
            path.write_text(json.dumps(changed) + '\n')
            with self.assertRaisesRegex(ValueError, 'Exact flagger config'):
                read_case('probe_b', base=self.base)
        finally:
            path.write_text(original)

    def test_reject_changed_track_source(self):
        path = self.base / 'probe_a' / 'requested-tracks.jsonl'
        original = path.read_text()
        try:
            rows = original.splitlines()
            changed = json.loads(rows[120])
            changed['signal'] = 'release'
            rows[120] = json.dumps(changed)
            path.write_text('\n'.join(rows) + '\n')
            with self.assertRaisesRegex(ValueError, 'construction source'):
                read_case('probe_a', base=self.base)
        finally:
            path.write_text(original)

    def test_reject_changed_frozen_source(self):
        path = self.base / 'probe_a' / 'config.json'
        original = path.read_text()
        try:
            changed = json.loads(original)
            changed['assignment_sha256'] = '0' * 64
            path.write_text(json.dumps(changed) + '\n')
            with self.assertRaisesRegex(ValueError, 'Frozen assignment source'):
                read_case('probe_a', base=self.base)
        finally:
            path.write_text(original)

    def test_native_review_packet_is_required(self):
        with self.assertRaisesRegex(ValueError, 'Original flagger authority'):
            _read_review(self.base / 'absent-review.json', object())

    def test_native_review_sources_are_hashed(self):
        class Library:
            def find(self, name):
                if name not in ('static.prop.stop_source', 'static.prop.release_source'):
                    raise ValueError('Unavailable reviewed signal')
                return name
        review = {'governs_approach': True,
                  'stop_signal_blueprint': 'static.prop.stop_source',
                  'release_signal_blueprint': 'static.prop.release_source'}
        for stem in ('authority', 'zone_designation', 'signal_asset'):
            source = self.base / (stem + '.txt')
            source.write_text(stem + ' CPU source fixture\n')
            review[stem + '_source_path'] = str(source)
            review[stem + '_source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        packet = self.base / 'review.json'
        packet.write_text(json.dumps(review) + '\n')
        self.assertEqual(_read_review(packet, Library())['governs_approach'], True)
        for stem, copied in (('authority', 'original-authority-source'),
                             ('zone_designation', 'original-zone-source'),
                             ('signal_asset', 'original-signal-source')):
            self.assertEqual((self.base / copied).read_bytes(),
                             (self.base / (stem + '.txt')).read_bytes())
        (self.base / 'authority.txt').write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'source hash differs'):
            _read_review(packet, Library())

    def test_world_restoration_after_pipeline_close_error(self):
        events = []

        class Pipeline:
            def close(self, confirmed):
                events.append(('close', confirmed))
                raise RuntimeError('forced close failure')

        class Encoder:
            def poll(self):
                return None

            def kill(self):
                events.append('kill')

            def wait(self):
                events.append('wait')

        class Actor:
            def stop(self):
                events.append('stop')

            def destroy(self):
                events.append('destroy')

        def restore(client, prior):
            events.append(('restore', client, prior))
            return {'restored': True}

        with self.assertRaisesRegex(RuntimeError, 'forced close failure'):
            _cleanup_capture(Pipeline(), {'overview': Encoder()}, [Actor()],
                             'client', 'prior', True, False, restore)
        self.assertEqual(events, [('close', False), 'kill', 'wait', 'stop',
                                  'destroy', ('restore', 'client', 'prior')])

    def test_world_restoration_after_encoder_cleanup_error(self):
        events = []

        class Encoder:
            def poll(self):
                return None

            def kill(self):
                events.append('kill')
                raise RuntimeError('forced encoder failure')

        class Actor:
            def destroy(self):
                events.append('destroy')

        def restore(client, prior):
            events.append('restore')
            return {'restored': True}

        with self.assertRaisesRegex(RuntimeError, 'forced encoder failure'):
            _cleanup_capture(None, {'overview': Encoder()}, [Actor()],
                             'client', 'prior', True, False, restore)
        self.assertEqual(events, ['kill', 'destroy', 'restore'])


if __name__ == '__main__':
    unittest.main()
