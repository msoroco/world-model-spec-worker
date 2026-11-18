"""Live projection preserves adapter inputs without any binary graph fallback."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import networkx as nx
from traffic_spec_adapter.adapter import adapter_graph_path, load_adapter_graph

HELPER = Path(__file__).resolve().parents[1] / 'python/native_graph_json.py'
spec = importlib.util.spec_from_file_location('native_graph_json_fixture', HELPER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LiveGraphJsonTests(unittest.TestCase):
    def test_preserves_measurements_identity_and_parallel_governance(self):
        import numpy as np
        from shapely.geometry import Polygon
        graph = nx.MultiDiGraph(frame=17, simulation_time_s=1.25,
                               observed_evidence={'frame': 17, 'devices': []})
        graph.add_node('ego', vertex=np.array([2., 3., 4.]),
                       original_observation={'velocity_mps': [1., 2., 3.]})
        graph.add_node(9, waypoint_obj=object(), vertex_point=object(),
                       waypoint_bbox_polygon=Polygon([(0, 0), (1, 0), (1, 1)]),
                       waypoint_road_id=12, waypoint_lane_id=-1)
        for _ in range(2):
            graph.add_edge('ego', 9, dist_relationship='controlsTrafficOf', distance=float('nan'))
        with tempfile.TemporaryDirectory() as directory:
            native = Path(directory)/'native'; native.mkdir()
            module.write(graph, native/'frame.json')
            result = load_adapter_graph(adapter_graph_path(directory, {'adapter_graph': 'frame.json'}))
        self.assertEqual(result.graph, graph.graph)
        self.assertEqual(result.nodes['ego']['vertex'], [2., 3., 4.])
        self.assertEqual(result.nodes['ego']['original_observation'], graph.nodes['ego']['original_observation'])
        self.assertEqual(result.nodes[9], {'waypoint_road_id': 12, 'waypoint_lane_id': -1})
        self.assertEqual(result.number_of_edges(), 2)
        self.assertTrue(all(a == {'dist_relationship': 'controlsTrafficOf'} for _, _, a in result.edges(data=True)))

    def test_contraction_history_is_not_a_live_measurement_or_mutated(self):
        handle=object()
        history={9:{'waypoint_obj':handle,'vertex_point':object()}}
        graph=nx.DiGraph();graph.add_node('lane',contraction=history,waypoint_road_id=7,waypoint_lane_id=-1)
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'graph.json';module.write(graph,path);result=module.read(path)
        self.assertEqual(result.nodes['lane'],{'waypoint_road_id':7,'waypoint_lane_id':-1})
        self.assertIs(graph.nodes['lane']['contraction'],history)
        self.assertIs(history[9]['waypoint_obj'],handle)

    def test_undefined_turn_abstractions_remain_unknown(self):
        graph=nx.DiGraph()
        graph.add_node('branch',angle=float('nan'),curve=float('nan'))
        graph.add_node('ordinary',angle=12.5,curve=2)
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'graph.json';module.write(graph,path);result=module.read(path)
        self.assertEqual(result.nodes['branch'],{'angle':None,'curve':None})
        self.assertEqual(result.nodes['ordinary'],{'angle':12.5,'curve':2})
        self.assertNotEqual(graph.nodes['branch']['angle'],graph.nodes['branch']['angle'])
        graph.nodes['branch']['angle']=float('inf')
        with tempfile.TemporaryDirectory()as directory,self.assertRaises(ValueError):
            module.write(graph,Path(directory)/'bad.json')

    def test_rejects_unsupported_or_nonfinite_measurement(self):
        for value in (object(), float('nan'), float('inf')):
            graph = nx.DiGraph(); graph.add_node('ego', measurement=value)
            with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
                module.write(graph, Path(directory)/'bad.json')

    def test_rejects_pickle_fallback_and_escaping_path(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'unpickling is disabled'):
                adapter_graph_path(directory, {'base': 'old.pkl'})
            with self.assertRaisesRegex(ValueError, 'Invalid or missing'):
                adapter_graph_path(directory, {'adapter_graph': '../../outside.json'})

    def test_rejects_corrupt_endpoint_and_duplicate_identity(self):
        graph = nx.DiGraph(); graph.add_edge('ego', 'lane')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'graph.json'; module.write(graph, path)
            original = json.loads(path.read_text())
            corrupt = dict(original); corrupt['edges'] = [{'source': -1, 'target': 0, 'attributes': {}}]
            path.write_text(json.dumps(corrupt))
            with self.assertRaisesRegex(ValueError, 'endpoint'): module.read(path)
            original['nodes'].append(original['nodes'][0]); path.write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError, 'duplicate'): module.read(path)
