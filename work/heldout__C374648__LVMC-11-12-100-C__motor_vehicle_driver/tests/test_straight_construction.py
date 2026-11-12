"""Portable connected straight-route checks."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from center_turn_construction import select_candidate
from straight_construction import straight_route
from test_center_turn_construction import Node, scene


def straight_scene(*, two_exits=False):
    fake = scene()
    center = fake.start
    outer = center.right
    for chain, lane in ((center, 1), (outer, 2)):
        current = chain
        for _ in range(4):
            current = current.successor[0]
        junction = current.successor[0]
        straight = Node(12, 0 if lane == 1 else 3, 0, lane, road=26)
        junction.successor.append(straight)
        if two_exits:
            junction.successor.append(Node(12, 1, 0, lane, road=27))
    return fake


class StraightConstructionTests(unittest.TestCase):
    def test_distinct_connected_straight_origins(self):
        selected = select_candidate(straight_scene(), approach_steps=4)
        center = straight_route(selected, origin='center')
        outer = straight_route(selected, origin='outer')
        self.assertEqual(center['exit'].road_id, outer['exit'].road_id)
        self.assertNotEqual(center['targets'][0], outer['targets'][0])
        self.assertEqual(center['exit'].lane_id, 1)
        self.assertEqual(outer['exit'].lane_id, 2)
        self.assertFalse(center['designation_authority_verified'])

    def test_missing_or_ambiguous_straight_exit_rejects(self):
        selected = select_candidate(scene(), approach_steps=4)
        with self.assertRaisesRegex(ValueError, 'one connected'):
            straight_route(selected)
        selected = select_candidate(straight_scene(two_exits=True), approach_steps=4)
        with self.assertRaisesRegex(ValueError, 'one connected'):
            straight_route(selected)
