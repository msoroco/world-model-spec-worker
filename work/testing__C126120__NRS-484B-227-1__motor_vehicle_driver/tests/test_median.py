import queue
import unittest
from types import SimpleNamespace

import runner
from scenario import median_status,route,static_check


class MedianTests(unittest.TestCase):
    def test_opening_and_intact_segments(self):
        runner.check()
        self.assertEqual([190,220],static_check()['opening_x_m'])
        opening=median_status([[202,8,0],[208,8,0],[208,12,0],[202,12,0]])
        intact=median_status([[145,8,0],[155,8,0],[155,12,0],[145,12,0]])
        self.assertTrue(opening['wholly_within_opening_x'])
        self.assertTrue(intact['intact_divider_overlap'])

    def test_frame_queue_discards_warmup(self):
        q=queue.Queue()
        for n in (1,2,3):q.put(SimpleNamespace(frame=n))
        self.assertEqual(3,runner.image_for_frame(q,3).frame)


if __name__=='__main__':unittest.main()
