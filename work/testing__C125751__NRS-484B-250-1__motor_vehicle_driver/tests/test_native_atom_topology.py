"""Exercise original native lane readback and Core entry applicability joins."""
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work' / 'c125751-topology-tests'
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH / 'pipeline-output')
sys.path[:0] = [str(REPO / 'runtime/python'), str(REPO / 'runtime/scenario_pipeline')]
from original_observations import map_lane_topology
from traffic_spec_adapter.native_control_observations import read_lane_sections


MAP = ('<OpenDRIVE>'
       '<road id="1" length="10" junction="-1"><lanes><laneSection s="0">'
       '<right><lane id="-1" type="driving"/></right></laneSection></lanes></road>'
       '<road id="2" length="5" junction="7"><lanes><laneSection s="0">'
       '<right><lane id="-1" type="driving"/></right></laneSection></lanes></road>'
       '<junction id="7"><connection incomingRoad="1" connectingRoad="2">'
       '<laneLink from="-1" to="-1"/></connection></junction></OpenDRIVE>')


class NativeMap:
    def __init__(self, wrong=False):
        self.wrong = wrong

    def get_waypoint_xodr(self, road_id, lane_id, station):
        return SimpleNamespace(road_id=road_id, section_id=0,
                               lane_id=(1 if self.wrong else lane_id),
                               is_junction=road_id == 2,
                               junction_id=7 if road_id == 2 else -1)


class NativeTopologyTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'capture').mkdir()
        (self.root / 'road.xodr').write_text(MAP)

    def _read(self, mapping):
        topology = map_lane_topology(mapping, self.root / 'road.xodr')
        (self.root / 'capture/native_map_facts.json').write_text(json.dumps({'native_lane_topology': topology}))
        regions = [
            {'id': 1, 'kind': 'lane', 'lane': {'enters_intersection': 3}},
            {'id': 2, 'kind': 'lane', 'lane': {}},
            {'id': 3, 'kind': 'intersection'}]
        result = read_lane_sections(self.root, [{'frame': 1000}],
                                    {(1, 0, -1): 1, (2, 0, -1): 2},
                                    regions, {'native_lane_topology': topology})
        return topology, result

    def test_complete_native_source_projects_incoming_and_nonincoming_scope(self):
        topology, result = self._read(NativeMap())
        self.assertTrue(topology['complete'])
        receipt = result['st.lane_enters'][0]
        self.assertEqual(receipt['incoming_core_entries'], {'1': 3})
        self.assertEqual(receipt['entry_applicability'], {'1': 3, '2': None})

    def test_native_identity_mismatch_cannot_claim_complete_topology(self):
        topology, result = self._read(NativeMap(wrong=True))
        self.assertFalse(topology['complete'])
        self.assertEqual(result, {})

    def test_missing_core_entry_cannot_claim_complete_topology(self):
        topology = map_lane_topology(NativeMap(), self.root / 'road.xodr')
        (self.root / 'capture/native_map_facts.json').write_text(json.dumps({'native_lane_topology': topology}))
        result = read_lane_sections(self.root, [{'frame': 1000}],
                                    {(1, 0, -1): 1, (2, 0, -1): 2},
                                    [{'id': 1, 'kind': 'lane', 'lane': {}},
                                     {'id': 2, 'kind': 'lane', 'lane': {}},
                                     {'id': 3, 'kind': 'intersection'}],
                                    {'native_lane_topology': topology})
        self.assertEqual(result, {})


if __name__ == '__main__':
    unittest.main()
