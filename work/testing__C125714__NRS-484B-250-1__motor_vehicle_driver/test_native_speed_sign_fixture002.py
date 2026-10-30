import importlib.util
from pathlib import Path
import unittest
import networkx as nx
from traffic_spec_adapter.adapter import device_record
OWN=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sign_fixture',OWN/'native_speed_sign_fixture002.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
class SpeedSignDiagnostic(unittest.TestCase):
 def test_actual_scene_maps_exact_atom_without_authority_claim(self):
  scene=OWN.parents[0]/'testing__C136559__NRS-484B-600-1c__motor_vehicle_driver/scene.xodr'
  g=nx.MultiDiGraph();report=helper.augment_graph(g,scene);self.assertEqual(len(report['added_nodes']),1)
  n=report['added_nodes'][0];key,device=device_record(n,g.nodes[n],g,{})
  self.assertEqual(key,('landmark','6001'));self.assertEqual(device['kind'],'speed_limit_sign');self.assertAlmostEqual(device['speed_value'],30*.44704)
  self.assertEqual(device['position'],[200,-3.5]);self.assertNotIn('governs',device);self.assertEqual(g.number_of_edges(),0)
  self.assertEqual(helper.augment_graph(g,scene)['added_nodes'],[])
 def test_existing_observation_never_overwritten(self):
  scene=OWN.parent/'testing__C136559__NRS-484B-600-1c__motor_vehicle_driver/scene.xodr';g=nx.MultiDiGraph();g.add_node('actual',landmark_id='6001',landmark_value=99)
  self.assertEqual(helper.augment_graph(g,scene)['added_nodes'],[]);self.assertEqual(g.nodes['actual']['landmark_value'],99)
if __name__=='__main__':unittest.main()
