"""Contract tests for observed facts, coordinate conversion and evidence honesty."""
import json
import math
import tempfile
import unittest
from pathlib import Path
from traffic_spec_adapter.adapter import rates, rounded, validate_scene, verify_join, signals, device_record, atom_ids, recorded_traffic_props, live_kinematics
from traffic_spec_adapter.geometry import body, static_map, xy, painted_map_objects, native_centre_lines


class AdapterTests(unittest.TestCase):
    def test_native_centre_line_retains_offset_and_omits_one_way_road(self):
        xml='''<OpenDRIVE><road id="1" length="10"><planView><geometry s="0" x="0" y="0" hdg="0" length="10"><line/></geometry></planView><lanes><laneOffset s="0" a="2" b="0" c="0" d="0"/><laneSection s="0"><left><lane id="1" type="driving"/></left><center><lane id="0"><roadMark type="solid" color="yellow" width="0.12"/></lane></center><right><lane id="-1" type="driving"/></right></laneSection></lanes></road><road id="2" length="10"><planView><geometry s="0" x="0" y="20" hdg="0" length="10"><line/></geometry></planView><lanes><laneSection s="0"><right><lane id="-1" type="driving"/></right></laneSection></lanes></road></OpenDRIVE>'''
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'road.xodr';path.write_text(xml);lines=native_centre_lines(path)
        self.assertEqual(len(lines),1)
        self.assertEqual(lines[0]['region']['boundary'][0],[0.,2.])
        self.assertEqual(lines[0]['region']['boundary'][-1],[10.,2.])
        self.assertEqual(lines[0]['shape'].area,0.)
        self.assertEqual(lines[0]['source']['centre_road_marks'][0]['color'],'yellow')

    def test_native_stop_line_does_not_gain_an_invented_width(self):
        xml='<OpenDRIVE><road id="1"><planView><geometry s="0" x="0" y="0" hdg="0" length="20"><line/></geometry></planView><objects><object id="line" name="StopLine" s="5" t="-2" hdg="1.5707963267948966" length="4" width="0"/></objects></road></OpenDRIVE>'
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'road.xodr';path.write_text(xml);objects=painted_map_objects(path)
        line=objects[0]
        self.assertEqual(line['region']['kind'],'stop_line')
        self.assertEqual(line['shape'].geom_type,'LineString')
        self.assertEqual(line['shape'].area,0.)
        self.assertEqual(line['region']['position'],[5.,-2.])
        self.assertIn('thickness unobserved',line['source']['representation'])

    def test_participant_motion_requires_original_live_acquisition(self):
        attrs={'carla_speed':5.,'carla_vel_x':3.,'carla_vel_y':4.,'carla_vel_z':0.}
        self.assertEqual(live_kinematics(attrs,'original_live_run'),{'speed':5.,'velocity':[3.,-4.]})
        self.assertEqual(live_kinematics(attrs,'recorder_replay'),{})
        self.assertEqual(live_kinematics(attrs,None),{})
        self.assertEqual(live_kinematics({},'original_live_run'),{})

    def test_reflection(self):
        self.assertEqual(xy([1,2,3]),[1,-2])

    def test_body_half_sizes_and_offset(self):
        points=[[x,y,z] for x in (3,7) for y in (1,3) for z in (0,2)]
        c,e,p=body(points,0)
        self.assertEqual(c,[5,-2]);self.assertEqual(e,[2,1,1]);self.assertEqual(p.area,8)

    def test_wrapped_heading_is_not_spin(self):
        self.assertEqual(rates([0,1,2],[179,-179,-177]),[-2,-2,-2])
        self.assertEqual(rates([0,1,2],[0,-10,-20]),[10,10,10])

    def test_gap_not_interpolated(self):
        self.assertIsNone(rates([0,.05,.1,2],[0,1,2,3])[-1])

    def test_observed_false_preserved(self):
        self.assertEqual(rounded({'lamp':False,'unknown':None}),{'lamp':False,'unknown':None})
        with self.assertRaises(ValueError):rounded(float('nan'))

    def test_dangling_occupancy_rejected(self):
        s={'subject':1,'users':[{'track':1}],'structures':[],'devices':[],'occupies':[[1,7]]}
        with self.assertRaises(ValueError):validate_scene(s)

    def test_duplicate_identity_rejected(self):
        s={'subject':1,'users':[{'track':1},{'track':1}],'structures':[],'devices':[]}
        with self.assertRaises(ValueError):validate_scene(s)

    def test_ambiguous_join_and_replay_speed_rejected(self):
        e={'original_frame':1,'actor_id':1,'recording_time_s':0,'replay_frame':10,'replay_simulation_time_s':2,
           'ego':{'speed_mps':1,'speed_provenance':'replay','position_m':[0,0,0]}}
        t={'frame':1,'time_s':0,'speed_mph':1/.44704,'position_m':[0,0,0]}
        f={'frame':10,'simulation_time':2}
        with self.assertRaises(ValueError):verify_join([e],[t],[f])
        e['ego']['speed_provenance']='original_trace_actor_get_velocity'
        self.assertEqual(verify_join([e],[t],[f])[0][1],t)
        with self.assertRaises(ValueError):verify_join([e,e],[t],[f])

    def test_map_is_static_and_curvature_is_local(self):
        xml='''<OpenDRIVE><road id="1" length="20"><planView>
        <geometry s="0" x="0" y="0" hdg="0" length="10"><line/></geometry>
        <geometry s="10" x="10" y="0" hdg="0" length="10"><arc curvature="0.01"/></geometry>
        </planView><lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="4" b="0" c="0" d="0"/></lane></right></laneSection></lanes></road></OpenDRIVE>'''
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'road.xodr';p.write_text(xml)
            regions,polys,keys=static_map(p)
        self.assertEqual(len(keys),1)
        self.assertNotIn('direction',regions[0]['lane'])
        self.assertEqual([r['curvature'] for r in regions if r['kind']=='roadway'],[0,.01])
        self.assertTrue(all(p.is_valid for p in polys.values()))

    def test_native_junction_surface_and_lane_connections(self):
        lane='<lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="4" b="0" c="0" d="0"/></lane></right></laneSection></lanes>'
        def road(ident,x,junction):
            return f'<road id="{ident}" junction="{junction}" length="20"><planView><geometry s="0" x="{x}" y="0" hdg="0" length="20"><line/></geometry></planView>{lane}</road>'
        xml='<OpenDRIVE>'+road(1,0,-1)+road(2,20,3)+'<junction id="3"><connection incomingRoad="1" connectingRoad="2" contactPoint="start"><laneLink from="-1" to="-1"/></connection></junction></OpenDRIVE>'
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'road.xodr';p.write_text(xml);notes=[]
            regions,polygons,keys=static_map(p,junctions=True,junction_report=notes)
        intersection=next(r for r in regions if r['kind']=='intersection')
        approach=next(r['lane'] for r in regions if r['id']==keys[(1,0,-1)])
        self.assertEqual(approach['enters_intersection'],intersection['id'])
        self.assertEqual(approach['leads_to'],[keys[(2,0,-1)]])
        self.assertEqual(polygons[intersection['id']].bounds,(20.,-4.,40.,0.))
        self.assertIn('not a painted stop line',notes[0]['scope'])

    def test_native_speed_actor_value_and_governance(self):
        import networkx as nx
        graph=nx.MultiDiGraph()
        graph.add_node('speed',sem_class='traffic.speed_limit.30',carla_id=10,
                       landmark_value=30,landmark_unit='km/h')
        graph.add_node('lane',waypoint_road_id=1,waypoint_section_id=0,waypoint_lane_id=-1)
        graph.add_edge('speed','lane',dist_relationship='controlsTrafficOf')
        key,device=device_record('speed',graph.nodes['speed'],graph,{(1,0,-1):5})
        self.assertEqual(key,('actor','10'))
        self.assertAlmostEqual(device['speed_value'],30/3.6)
        self.assertEqual(device['governs'],[5])

    def test_atom_inventory_does_not_include_primitives(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'TrafficSpec/Core'
            (p/'Vocab/Ontology').mkdir(parents=True)
            (p/'Runtime').mkdir()
            (p/'Runtime/Decode.lean').write_text('-- fixture')
            (p/'Vocab/Ontology/Ids.lean').write_text('def atomIds : List String := ["kin.speed", "st.lane"]\ndef primitiveIds : List String := ["prim.heading_change"]')
            self.assertEqual(atom_ids(Path(d)),['kin.speed','st.lane'])

    def test_recorder_prop_position_has_no_invented_boundary(self):
        p=recorded_traffic_props('Frame 1 at 0 seconds\n Create 38: static.prop.streetbarrier (0) at (2808.97, -3028.97, 10)\nFrame 2 at 0.05 seconds')
        self.assertAlmostEqual(p[38]['position'][0],28.0897)
        self.assertAlmostEqual(p[38]['position'][1],30.2897)
        self.assertNotIn('boundary',p[38])

    def test_lamps_preserve_recorded_on_off_and_unknown(self):
        on=signals({'light_Brake':True,'light_Position':True,'light_Reverse':True,
                    'light_LeftBlinker':True,'light_RightBlinker':True,
                    'light_HighBeam':True,'light_LowBeam':False})
        self.assertEqual(on,{'brake_lamp':True,'position_lamp':True,
                             'reverse_lamp':True,'hazard':True,'headlamp':'high_beam'})
        self.assertEqual(signals({'brake':1.,'reverse':True}),{})
        self.assertEqual(signals({'light_Brake':False,'light_Reverse':False}),
                         {'brake_lamp':False,'reverse_lamp':False})
        self.assertEqual(signals({'light_HighBeam':False,'light_LowBeam':True}),
                         {'headlamp':'low_beam'})

    def test_signal_off_does_not_become_false_indicator(self):
        lamps=signals({'light_Brake':False,'light_LeftBlinker':False,'light_RightBlinker':False})
        self.assertEqual(lamps,{'brake_lamp':False,'hazard':False})
        self.assertNotIn('turn_indicator',lamps)
        self.assertEqual(signals({'light_LeftBlinker':True,'light_RightBlinker':False})['turn_indicator'],'left')

    def test_device_governance_requires_real_edge(self):
        import networkx as nx
        g=nx.DiGraph()
        g.add_node('signal',sem_class='traffic.traffic_light',carla_id=99,vertex=[1,2],light_state='Red')
        g.add_node('lane',waypoint_road_id=1,waypoint_section_id=0,waypoint_lane_id=-1)
        g.add_edge('signal','lane',dist_relationship='mayAffect')
        key,d=device_record('signal',g.nodes['signal'],g,{(1,0,-1):7})
        self.assertNotIn('governs',d)
        g.edges['signal','lane']['dist_relationship']='controlsTrafficOf'
        _,d=device_record('signal',g.nodes['signal'],g,{(1,0,-1):7})
        self.assertEqual(d['governs'],[7]);self.assertEqual(d['indications'],['circular_red'])
        self.assertEqual(d['position'],[1,-2])

    def test_governance_merge_preserves_unknown_empty_and_positive(self):
        from traffic_spec_adapter.adapter import merge_device_governance
        value={}
        merge_device_governance(value,{})
        self.assertNotIn('governs',value)
        merge_device_governance(value,{'governs':[]})
        self.assertEqual(value['governs'],[])
        merge_device_governance(value,{'governs':[4,2]})
        merge_device_governance(value,{})
        merge_device_governance(value,{'governs':[2,3]})
        self.assertEqual(value['governs'],[2,3,4])

    def test_observed_empty_governance_is_preserved(self):
        import networkx as nx
        graph=nx.DiGraph()
        graph.add_node('signal',sem_class='traffic.traffic_light',carla_id=99,
                       light_state='Red',observed_governs=[])
        _,device=device_record('signal',graph.nodes['signal'],graph,{})
        self.assertEqual(device['governs'],[])
        del graph.nodes['signal']['observed_governs']
        _,device=device_record('signal',graph.nodes['signal'],graph,{})
        self.assertNotIn('governs',device)
        graph.nodes['signal']['observed_governs']=None
        _,device=device_record('signal',graph.nodes['signal'],graph,{})
        self.assertNotIn('governs',device)

    def test_unknown_geometry_fails_not_empty(self):
        from traffic_spec_adapter.geometry import reference
        import xml.etree.ElementTree as ET
        with self.assertRaises(ValueError):reference(ET.fromstring('<geometry s="0" x="0" y="0" hdg="0"><poly3/></geometry>'),0)

if __name__=='__main__':unittest.main()


class ManifestAvailabilityTests(unittest.TestCase):
    def test_missing_visibility_is_absent_not_estimate(self):
        from unittest.mock import patch
        from traffic_spec_adapter import adapter
        with patch.object(adapter,'atom_ids',return_value=['st.sight_distance']):
            self.assertEqual(adapter.manifest(None)['atoms']['st.sight_distance'],'absent')
            self.assertEqual(adapter.manifest(None,visibility_observed=True)['atoms']['st.sight_distance'],
                             'estimate:subject_relative_any_body_sampled_minimum')
