import unittest

from mobility_asset_probe import PATTERNS, collect


class Blueprint:
    def __init__(self, identifier):
        self.id = identifier


class Library:
    def __init__(self, matches):
        self.matches = matches
        self.queries = []

    def filter(self, pattern):
        self.queries.append(pattern)
        return [Blueprint(identifier) for identifier in self.matches.get(pattern, [])]


class MobilityAssetProbeTests(unittest.TestCase):
    def test_inventory_deduplicates_without_eligibility_claim(self):
        library = Library({PATTERNS[0]: ['vehicle.wheelchair_candidate'],
                           PATTERNS[1]: ['vehicle.wheelchair_candidate']})
        result = collect(library)
        self.assertEqual(library.queries, list(PATTERNS))
        self.assertEqual(len(result['matches']), 1)
        self.assertEqual(result['matches'][0]['matched_patterns'], sorted(PATTERNS[:2]))
        self.assertFalse(result['device_design_established'])
        self.assertFalse(result['impaired_person_use_established'])
        self.assertFalse(result['frozen_actor_eligibility_established'])

    def test_empty_inventory_does_not_invent_asset(self):
        result = collect(Library({}))
        self.assertEqual(result['matches'], [])
        self.assertFalse(result['physical_capture_established'])
