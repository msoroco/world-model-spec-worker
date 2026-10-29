import importlib.util
from pathlib import Path
import unittest
import networkx as nx
from traffic_spec_adapter.adapter import signals
OWN=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('indicator_fixture',OWN/'native_indicator_fixture002.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
class IndicatorDiagnostic(unittest.TestCase):
 def test_interruptions_and_left_legacy_name(self):
  for course,side in [('left_turn','left'),('right_turn','right'),('change_lane','right')]:
   values=[]
   for bit in [False,True,False,True]:
    graph=nx.MultiDiGraph();graph.add_node('ego',carla_id=107)
    helper.augment_graph(graph,{'right_indicator_api_bit':bit},{'course':course},107);value=signals(graph.nodes['ego']);values.append(value.get('turn_indicator'))
   self.assertEqual(values,[None,side,None,side])
 def test_missing_boolean_not_defaulted(self):
  with self.assertRaises(ValueError):helper.indicator_attributes({}, {})
 def test_original_conflict_is_rejected(self):
  graph=nx.MultiDiGraph();graph.add_node('ego',carla_id=1,light_RightBlinker=True)
  with self.assertRaises(ValueError):helper.augment_graph(graph,{'right_indicator_api_bit':False},{},1)
if __name__=='__main__':unittest.main()
