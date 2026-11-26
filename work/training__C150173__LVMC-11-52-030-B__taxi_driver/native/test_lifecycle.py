"""Prospective capture cleanup must preserve actor and world ownership."""
import unittest

from runner import finish_owned_capture


class FailedPipeline:
    def __init__(self, events):
        self.events = events

    def close(self, confirmed):
        self.events.append(('pipeline_close', confirmed))
        raise RuntimeError('pipeline close failed')


class Encoder:
    returncode = None

    def __init__(self, events):
        self.events = events

    def poll(self):
        self.events.append('encoder_poll')
        return None

    def kill(self):
        self.events.append('encoder_kill')

    def wait(self):
        self.events.append('encoder_wait')
        self.returncode = -9


class Actor:
    def __init__(self, events):
        self.events = events

    def stop(self):
        self.events.append('actor_stop')

    def destroy(self):
        self.events.append('actor_destroy')


class Cleanup(unittest.TestCase):
    def test_pipeline_failure_still_closes_encoders_actors_and_restores(self):
        events = []
        def restore(client, prior):
            events.append('world_restore')
            return {'restored': True}
        def seal(*args, **kwargs):
            events.append('sealed')
        with self.assertRaisesRegex(RuntimeError, 'pipeline close failed'):
            finish_owned_capture(FailedPipeline(events), {'overview': Encoder(events)},
                                 [Actor(events)], object(), {}, True, True,
                                 object(), {'case_id': 'synthetic'}, restore, seal)
        self.assertEqual(events, [('pipeline_close', True), 'encoder_poll',
                                  'encoder_kill', 'encoder_wait', 'actor_stop',
                                  'actor_destroy', 'world_restore'])

    def test_original_exception_survives_cleanup_failure(self):
        events = []
        def restore(client, prior):
            events.append('world_restore')
            return {'restored': True}
        with self.assertRaisesRegex(ValueError, 'original capture failure'):
            try:
                raise ValueError('original capture failure')
            finally:
                finish_owned_capture(FailedPipeline(events), {}, [Actor(events)],
                                     object(), {}, True, False, object(),
                                     {'case_id': 'synthetic'}, restore,
                                     lambda *args, **kwargs: None)
        self.assertEqual(events[-1], 'world_restore')


if __name__ == '__main__':
    unittest.main()
