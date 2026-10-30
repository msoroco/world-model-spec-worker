import unittest
from fallback_trigger import measure

class TriggerTests(unittest.TestCase):
    def rows(self, excursion=0):
        return [{'original_frame': i+1,'recording_time_s': (i+1)*.05,
                 'ego': {'body_vertices_m': [[0,0,excursion if i==19 else 0] for _ in range(8)]}}
                for i in range(20)]
    def test_settled(self):
        self.assertFalse(measure(self.rows())['triggered'])
    def test_vertical_excursion(self):
        self.assertTrue(measure(self.rows(.07))['triggered'])
    def test_short_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'Insufficient'):
            measure(self.rows()[:19])
    def test_bad_time_join_rejected(self):
        rows=self.rows();rows[1]['recording_time_s']=rows[0]['recording_time_s']
        with self.assertRaisesRegex(ValueError,'not increasing'):
            measure(rows)
if __name__=='__main__':unittest.main()
