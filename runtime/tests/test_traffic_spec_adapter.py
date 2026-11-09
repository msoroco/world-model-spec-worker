"""Contract tests for observed facts, coordinate conversion and evidence honesty."""
import json
import math
import tempfile
import unittest
from pathlib import Path
from traffic_spec_adapter.adapter import rates, rounded, validate_scene, verify_join, signals, device_record, atom_ids, recorded_traffic_props, live_kinematics
from traffic_spec_adapter.geometry import body, static_map, xy, painted_map_objects, native_centre_lines


def core_fixture_library():
    root = Path(__file__).resolve().parents[1]
    exported = root/'library'
    return exported if exported.is_dir() else root.parent/'repo_prep/nevada_sydney/pipeline/traffic-spec-agent/library'


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
        self.assertNotIn('boundary',line['region'])
        self.assertEqual(len(line['source']['native_centerline']),2)
        self.assertIn('thickness unobserved',line['source']['representation'])

    def test_positive_native_paint_dimensions_remain_a_polygon(self):
        xml='<OpenDRIVE><road id="1"><planView><geometry s="0" x="0" y="0" hdg="0" length="20"><line/></geometry></planView><objects><object id="line" name="StopLine" s="5" t="-2" length="4" width="0.3"/></objects></road></OpenDRIVE>'
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'road.xodr';path.write_text(xml);line=painted_map_objects(path)[0]
        self.assertEqual(len(line['region']['boundary']),4)
        self.assertAlmostEqual(line['shape'].area,1.2)

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

    def test_complete_generated_map_distinguishes_no_marking_and_terminal_lane(self):
        xml='''<OpenDRIVE><road id="1" length="10"><planView><geometry s="0" x="0" y="0" hdg="0" length="10"><line/></geometry></planView><lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="4" b="0" c="0" d="0"/></lane></right></laneSection></lanes></road></OpenDRIVE>'''
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'map.xodr';path.write_text(xml)
            known=static_map(path,complete_map=True)[0][0]['lane']
            unavailable=static_map(path)[0][0]['lane']
        self.assertEqual(known['marking_left'],['none','other'])
        self.assertEqual(known['marking_right'],['none','other'])
        self.assertEqual(known['leads_to'],[])
        self.assertNotIn('marking_left',unavailable)
        self.assertNotIn('leads_to',unavailable)

    def test_complete_native_lanes_require_bound_generated_map_and_capture_scope(self):
        from traffic_spec_adapter.inventory_observations import complete_generated_lanes
        digest='a'*64
        manifest={'map':'Carla/Maps/OpenDriveMap','complete_driving_lanes':True,'sources':{'road.xodr':digest}}
        facts={'map':manifest['map']}
        self.assertTrue(complete_generated_lanes(manifest,facts,digest))
        self.assertFalse(complete_generated_lanes(manifest,facts,'b'*64))
        self.assertFalse(complete_generated_lanes(manifest,{},digest))
        self.assertFalse(complete_generated_lanes(dict(manifest,complete_driving_lanes=False),facts,digest))
        self.assertFalse(complete_generated_lanes(dict(manifest,map='Town01'),facts,digest))

    def test_native_bicycle_surface_has_its_own_measured_region_and_highway_envelope(self):
        xml='''<OpenDRIVE><road id="1" length="10"><planView><geometry s="0" x="0" y="0" hdg="0" length="10"><line/></geometry></planView><lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="4" b="0" c="0" d="0"/></lane><lane id="-2" type="biking"><width sOffset="0" a="2" b="0" c="0" d="0"/></lane></right></laneSection></lanes></road></OpenDRIVE>'''
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'map.xodr';path.write_text(xml)
            regions,polygons,_=static_map(path,include_non_driving=True,public_way_roads=[1])
        bike=next(r for r in regions if r['kind']=='bicycle_lane_or_path')
        highway=next(r for r in regions if r['kind']=='highway')
        roadway=next(r for r in regions if r['kind']=='roadway')
        self.assertEqual(polygons[bike['id']].bounds,(0,-6,10,-4))
        self.assertTrue(polygons[highway['id']].covers(polygons[bike['id']]))
        self.assertEqual(polygons[roadway['id']].intersection(polygons[bike['id']]).area,0)

    def test_crossing_native_edges_do_not_invent_a_highway_surface(self):
        xml='<OpenDRIVE><road id="1" length="10"><planView><geometry s="0" x="0" y="0" hdg="0" length="10"><line/></geometry></planView><lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="4" b="-0.8" c="0" d="0"/></lane></right></laneSection></lanes></road></OpenDRIVE>'
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'map.xodr';path.write_text(xml)
            regions,polygons,_=static_map(path,public_way_roads=[1],partial=True)
        highway=next(r for r in regions if r['kind']=='highway')
        self.assertNotIn('boundary',highway)
        self.assertNotIn(highway['id'],polygons)

    def test_native_road_link_recovers_shared_strip_but_not_a_nearby_lane(self):
        lane='<lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="4" b="0" c="0" d="0"/></lane></right></laneSection></lanes>'
        def road(ident,x,y,link=''):
            return f'<road id="{ident}" length="10">{link}<planView><geometry s="0" x="{x}" y="{y}" hdg="0" length="10"><line/></geometry></planView>{lane}</road>'
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'map.xodr'
            for offset,expected in [(0,True),(.1,False)]:
                path.write_text('<OpenDRIVE>'+road(1,0,0,'<link><successor elementType="road" elementId="2" contactPoint="start"/></link>')+road(2,10,offset)+'</OpenDRIVE>')
                regions,_,keys=static_map(path,complete_map=True);by_id={r['id']:r for r in regions}
                self.assertEqual('leads_to'in by_id[keys[(1,0,-1)]]['lane'],expected)
                if expected:self.assertEqual(by_id[keys[(1,0,-1)]]['lane']['leads_to'],[keys[(2,0,-1)]])

    def test_collapsed_strip_end_does_not_establish_an_inferred_lane_link(self):
        def road(ident,x,a,b,link=''):
            return f'''<road id="{ident}" length="10">{link}<planView><geometry s="0" x="{x}" y="0" hdg="0" length="10"><line/></geometry></planView><lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="{a}" b="{b}" c="0" d="0"/></lane></right></laneSection></lanes></road>'''
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'map.xodr'
            path.write_text('<OpenDRIVE>'+road(1,0,4,-.4,'<link><successor elementType="road" elementId="2" contactPoint="start"/></link>')+road(2,10,0,.4)+'</OpenDRIVE>')
            regions,_,keys=static_map(path,complete_map=True)
        lane=next(r['lane']for r in regions if r['id']==keys[(1,0,-1)])
        self.assertNotIn('leads_to',lane)

    def test_marking_colour_and_compound_type_are_not_silently_discarded(self):
        from traffic_spec_adapter.geometry import lane_marking
        import xml.etree.ElementTree as ET
        source=ET.fromstring('<lane><roadMark sOffset="0" type="solid broken" color="red"/></lane>')
        self.assertEqual(lane_marking(source),['solid_broken','other'])
        self.assertIsNone(lane_marking(ET.fromstring('<lane><roadMark type="solid"/></lane>')))

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

    def test_curved_lane_partition_preserves_surface_chain_and_references(self):
        import copy
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        from traffic_spec_adapter.geometry import lane_segments,project_lane_segments
        xml='''<OpenDRIVE><road id="1" length="8"><planView><geometry s="0" x="0" y="0" hdg="0" length="8"><arc curvature="0.05"/></geometry></planView><lanes><laneSection s="0"><right><lane id="-1" type="driving"><width sOffset="0" a="4" b="0" c="0" d="0"/></lane></right></laneSection></lanes></road></OpenDRIVE>'''
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'map.xodr';path.write_text(xml);sources={}
            regions,_,keys=static_map(path,source_regions=sources,complete_map=True)
        ident=keys[(1,0,-1)];lane=next(r for r in regions if r['id']==ident)
        lane['lane']['enters_intersection']=99
        scene={'structures':regions,'users':[{'track':7,'kin':{'position':[1,-2],'heading':[1,0],'extent':[.4,.4]}}],
            'devices':[{'id':8,'governs':[ident]}],'occupies':[[7,ident]],'occupancy_observed':[7]}
        fields={ident:{'lane':lane['lane'],'_lane_source':sources[ident]}}
        segments,issues=lane_segments(scene,fields)
        self.assertEqual(issues,[]);self.assertEqual(len(segments[ident]),4)
        pieces=[p for p,_ in segments[ident]]
        self.assertLess(unary_union([Polygon(p['boundary']) for p in pieces]).symmetric_difference(Polygon(lane['boundary'])).area,1e-8)
        self.assertEqual([p['lane']['enters_intersection'] for p in pieces],[99]*4)
        self.assertEqual([p['lane']['leads_to'] for p in pieces],[[p['id']] for p in pieces[1:]]+[[]])
        # Classifications and way membership may be established after compiling
        # the static partition; stale templates must not restore old unknowns.
        lane['ways']=[88]
        lane.pop('unobserved_kinds',None)
        for piece,_ in segments[ident]:piece['unobserved_kinds']=['crosswalk']
        first=copy.deepcopy(scene);project_lane_segments(scene,segments)
        projected=[r for r in scene['structures'] if r['id'] in {p['id'] for p in pieces}]
        self.assertTrue(all(r.get('ways')==[88] and 'unobserved_kinds' not in r for r in projected))
        self.assertEqual(scene['devices'][0]['governs'],[p['id'] for p in pieces])
        self.assertEqual(scene['occupies'],[[7,pieces[0]['id']]])
        self.assertEqual(scene['users'],first['users']);self.assertEqual(scene['occupancy_observed'],[7])

    def test_lane_partition_never_guesses_a_scoped_intention_target(self):
        from traffic_spec_adapter.geometry import lane_segments
        scene={'structures':[{'id':1,'kind':'lane','lane':{},'boundary':[[0,0],[1,0],[1,1],[0,1]]}],
            'intents':[{'vehicle':7,'target':1,'values':[['int.left_turn',True]]}]}
        segments,issues=lane_segments(scene,{1:{'lane':{},'_lane_source':{'samples':[],'lane_id':-1}}})
        self.assertEqual(segments,{});self.assertIn('scoped intention',issues[0])

    def test_partition_entrance_uses_measured_line_without_inventing_paint_width(self):
        from traffic_spec_adapter.geometry import compile_lane_segments,project_lane_segments
        first={'id':1,'kind':'lane','boundary':[[0,0],[2,0],[2,-4],[0,-4]],'lane':{'direction':[1,0],'leads_to':[3]}}
        last={'id':3,'kind':'lane','boundary':[[2,0],[4,0],[4,-4],[2,-4]],'lane':{'direction':[1,0],'leads_to':[]}}
        segments={1:[(first,(0,2)),(last,(2,4))]}
        scene={'structures':[{'id':1,'kind':'lane','boundary':[[0,0],[4,0],[4,-4],[0,-4]]},
            {'id':2,'kind':'stop_line','position':[4,3],'entrance_of':[1]}],'users':[]}
        compiled=compile_lane_segments(segments,{2:{'_entrance_geometry':[[4,10],[4,-4]]}})
        project_lane_segments(scene,segments,compiled)
        entrance=next(r for r in scene['structures']if r['id']==2)
        self.assertEqual(entrance['entrance_of'],[3]);self.assertNotIn('boundary',entrance)

    def test_connector_stop_line_keeps_topology_binding_on_terminal_piece(self):
        from traffic_spec_adapter.geometry import compile_lane_segments,project_lane_segments
        first={'id':1,'kind':'lane','boundary':[[0,0],[2,0],[2,-4],[0,-4]],'lane':{'leads_to':[3]}}
        last={'id':3,'kind':'lane','boundary':[[2,0],[4,0],[4,-4],[2,-4]],'lane':{'leads_to':[4]}}
        segments={1:[(first,(0,2)),(last,(2,4))]}
        fields={1:{'_lane_source':{'road_id':10},'lane':{'leads_to':[4]}},
            4:{'_lane_source':{'road_id':20}},2:{'_entrance_geometry':[[5,0],[5,-4]],'_entrance_road':20}}
        def scene():return {'structures':[{'id':1,'kind':'lane','boundary':[[0,0],[4,0],[4,-4],[0,-4]]},
            {'id':2,'kind':'stop_line','position':[5,-2],'entrance_of':[1]},
            {'id':4,'kind':'lane','boundary':[[4,0],[8,0],[8,-4],[4,-4]]}],'users':[]}
        value=scene();project_lane_segments(value,segments,compile_lane_segments(segments,fields))
        self.assertEqual(next(r for r in value['structures']if r['id']==2)['entrance_of'],[3])
        fields[2]['_entrance_road']=30
        with self.assertRaisesRegex(ValueError,'does not meet'):
            project_lane_segments(scene(),segments,compile_lane_segments(segments,fields))

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

    def test_measured_signal_off_is_preserved(self):
        lamps=signals({'light_Brake':False,'light_LeftBlinker':False,'light_RightBlinker':False})
        self.assertEqual(lamps,{'brake_lamp':False,'hazard':False,'turn_indicator':'off'})
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
    def test_source_capabilities_are_exhaustive_except_hand_signals(self):
        from unittest.mock import patch
        from traffic_spec_adapter import adapter
        library=core_fixture_library()
        atoms=adapter.manifest(library)['atoms']
        self.assertNotIn('sig.hand_signal',atoms)
        self.assertEqual(set(atoms),set(adapter.atom_ids(library))-{'sig.hand_signal'})
        self.assertEqual(atoms['st.sight_distance'],'absent')
        self.assertEqual(atoms['st.entrance_of'],'estimate:recorded_control_and_map_topology_join')
        with patch.object(adapter,'atom_ids',return_value=adapter.atom_ids(library)+['st.future_atom']):
            with self.assertRaisesRegex(ValueError,'lacks an explicit acquisition decision'):
                adapter.manifest(library)


# Regression checks shared by production export and retained-trace reconstruction.
from traffic_spec_adapter.adapter import lamp_state, repair_scene, source_packets, yaw_estimates, preserve_inventory_unknown
from shared_manifest import link, verify
import hashlib
class OfflineRepairTests(unittest.TestCase):
    def test_native_mask_preserves_zero_and_hazard(self):
        self.assertEqual(lamp_state(0)['turn_indicator'], 'off')
        self.assertEqual(lamp_state(32)['turn_indicator'], 'left')
        self.assertEqual(lamp_state(16)['turn_indicator'], 'right')
        self.assertTrue(lamp_state(48)['hazard'])
        self.assertNotIn('turn_indicator', lamp_state(48))
        with self.assertRaises(ValueError):lamp_state(False)

    def test_missing_measurement_never_becomes_off(self):
        scene={'t':0,'subject':1,'users':[{'track':1,'sig':{'left_indicator_enabled':False}}]}
        repair_scene(scene,{'sig.turn_indicator'},{},{},{})
        self.assertNotIn('turn_indicator',scene['users'][0]['sig'])
        self.assertNotIn('left_indicator_enabled',scene['users'][0]['sig'])

    def test_hazard_does_not_retain_an_invented_turn_side(self):
        scene={'subject':1,'users':[{'track':1,'sig':{'turn_indicator':'left'}}]}
        repair_scene(scene,{'sig.turn_indicator'},{'ego_lamps':lamp_state(48)},{},{})
        self.assertNotIn('turn_indicator',scene['users'][0]['sig'])
        self.assertTrue(scene['users'][0]['sig']['hazard'])

    def test_brake_control_does_not_set_lamp(self):
        scene={'subject':1,'users':[{'track':1,'kin':{'service_brake':1},'sig':{'brake_lamp':False}}]}
        repair_scene(scene,{'sig.brake_lamp'},{},{},{})
        self.assertFalse(scene['users'][0]['sig']['brake_lamp'])

    def test_heading_rate_wraps_and_does_not_bridge_disappearance(self):
        import math
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'trace.json'
            def user(deg):return {'track':2,'kin':{'heading':[math.cos(math.radians(deg)),math.sin(math.radians(deg))]}}
            path.write_text(json.dumps({'scenes':[{'t':0,'users':[user(179)]},
                {'t':1000,'users':[user(-179)]},{'t':2000,'users':[]},
                {'t':3000,'users':[user(-170)]}]}))
            rates=yaw_estimates(path)
            self.assertAlmostEqual(rates[0][2],2)
            self.assertNotIn(2,rates.get(1,{}))
            self.assertNotIn(2,rates.get(3,{}))

    def test_current_decoder_rejects_ignored_typed_keys(self):
        from traffic_spec_adapter.trace_contract import validate
        library=core_fixture_library()
        scene={'t':0,'users':[{'track':1,'sig':{'left_indicator_enabled':False}}]}
        with self.assertRaisesRegex(ValueError,'ignored'):
            validate(scene,library)

    def test_retired_classes_do_not_invent_current_membership(self):
        from traffic_spec_adapter.classifications import project_user
        source={'track':1,'classes':['retired_source_category']}
        current=project_user(source,{'motor_vehicle','pedestrian'})
        self.assertIsNone(current['classes'])
        self.assertEqual(current['unobserved_classes'],['motor_vehicle','pedestrian'])
        self.assertNotIn('source_classifications',current)
        self.assertEqual(source['classes'],['retired_source_category'])

    def test_inventory_uncertainty_preserves_positive_objects(self):
        from traffic_spec_adapter.adapter import preserve_inventory_unknown
        scene={'structures':[{'id':1,'kind':'highway'},{'id':2,'kind':'roadway'}]}
        preserve_inventory_unknown(scene,['highway'])
        self.assertNotIn('unobserved_kinds',scene['structures'][0])
        self.assertIn('highway',scene['structures'][1]['unobserved_kinds'])

    def test_optional_relation_coverage_checks_actual_fields(self):
        from traffic_spec_adapter.atom_contract import gaps
        scene={'users':[],'structures':[{'id':1,'kind':'stop_line','entrance_of':[2]}],
               'devices':[{'id':3,'kind':'stop_sign','governs':[]}]}
        self.assertEqual(gaps(scene,{'st.entrance_of','dev.governs'}),[])
        del scene['structures'][0]['entrance_of']
        self.assertIn('st.entrance_of',gaps(scene,{'st.entrance_of'}))
        self.assertEqual(gaps({'structures':[],'devices':[]},{'st.entrance_of','dev.governs','dev.traffic_signal'}),[])

    def test_manifest_link_rejects_wrong_target_and_changed_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);case=root/'recordings/case';case.mkdir(parents=True)
            value={'source':'test','atoms':{'sig.turn_indicator':'exact'}}
            link(root,case,value)
            self.assertFalse((case/'manifest.json').readlink().is_absolute())
            digest=hashlib.sha256((case/'manifest.json').read_bytes()).hexdigest()
            verify(root,case,digest)
            with self.assertRaises(ValueError):link(root,case,{'source':'changed'})
            with self.assertRaises(ValueError):verify(root,case,'0'*64)



class ReconstructionTests(unittest.TestCase):
    def test_child_exclusion_uses_observed_nonpedestrian_not_missing_age(self):
        from traffic_spec_adapter.classifications import project_user
        known={'motor_vehicle','pedestrian','child'}
        vehicle={'track':1,'classes':['motor_vehicle'],'unobserved_classes':['child']}
        result=project_user(vehicle,known)
        self.assertNotIn('child',result['unobserved_classes'])
        self.assertEqual(vehicle['unobserved_classes'],['child'])
        walker={'track':2,'classes':['pedestrian'],'unobserved_classes':['child']}
        self.assertIn('child',project_user(walker,known)['unobserved_classes'])
        uncertain={'track':3,'classes':[],'unobserved_classes':['pedestrian','child']}
        self.assertIn('child',project_user(uncertain,known)['unobserved_classes'])
        unclassified={'track':4,'classes':None,'unobserved_classes':['child']}
        self.assertIn('child',project_user(unclassified,known)['unobserved_classes'])

    def test_geometry_match_ignores_winding_and_redundant_samples(self):
        from traffic_spec_adapter.geometry import match_regions
        native=[{'id':1,'kind':'lane','boundary':[[0,0],[2,0],[2,1],[0,1]]}]
        current=[{'id':7,'kind':'lane','boundary':[[2,1],[2,0],[1,0],[0,0],[0,1]]}]
        self.assertEqual(match_regions(native,current),{1:7})
        current.append(dict(current[0],id=8))
        self.assertEqual(match_regions(native,current),{})

    def test_numerically_collapsed_arc_edge_is_not_an_invalid_lane(self):
        from traffic_spec_adapter.geometry import clean_boundary
        from shapely.geometry import Polygon
        points=[[0,0],[1,0],[1,1],[1+1e-14,1],[0,1],[0,0]]
        result=clean_boundary(points)
        self.assertEqual(len(result),4)
        self.assertTrue(Polygon(result).is_valid)
        self.assertEqual(Polygon(result).area,1)

    def test_streaming_yaw_requires_contiguous_identity_and_time(self):
        from traffic_spec_adapter.adapter import heading_rate
        def scene(t,deg):return {'t':t,'users':[{'track':2,'kin':{'heading':[math.cos(math.radians(deg)),math.sin(math.radians(deg))]}}]}
        self.assertAlmostEqual(heading_rate(scene(0,179),scene(50,-179),scene(100,-177),2,50),40)
        self.assertIsNone(heading_rate(scene(0,0),scene(50,2),scene(200,4),2,50))
        self.assertIsNone(heading_rate({'t':0,'users':[]},scene(50,2),scene(100,4),2,50))

    def test_unchanged_reconstruction_does_not_write_a_trace(self):
        from traffic_spec_adapter.adapter import reconstruct
        from unittest.mock import patch
        library=core_fixture_library()
        scene={'t':0,'subject':1,'users':[{'track':1,'kin':{'speed':0,'path_length':0,'yaw_rate':0}}],
               'structures':[],'devices':[]}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);trace=root/'input.json';output=root/'output.json';trace.write_text(json.dumps({'scenes':[scene]}))
            with patch('traffic_spec_adapter.geometry.retained_map',return_value=({}, {}, [], {}, [])), \
                 patch('traffic_spec_adapter.entrance_associations.retained_associations',return_value=({},[])), \
                 patch('traffic_spec_adapter.adapter.source_packets',return_value={}):
                report=reconstruct(trace,root/'evidence',library,output)
            self.assertFalse(report['changed']);self.assertFalse(output.exists())


class EvidenceReceiptTests(unittest.TestCase):
    def test_changed_derived_export_does_not_discard_bound_raw_map(self):
        from traffic_spec_adapter.inventory_observations import Evidence
        from batch_pipeline.completion import seal
        with tempfile.TemporaryDirectory() as temp:
            recording=Path(temp);original=recording/'evidence';original.mkdir()
            for name in ('road.xodr','trace.jsonl','frames.json','video.webm'):(original/name).write_text(name)
            derived=original/'traffic_spec';derived.mkdir();(derived/'trace.json').write_text('old')
            result={'trace_reference':'trace.jsonl','video_frame_map_reference':'frames.json','video_references':['video.webm']}
            (original/'result.json').write_text(json.dumps(result))
            seal(original,{'case_id':'c'})
            (derived/'trace.json').write_text('new derived trace')
            evidence=Evidence(recording)
            self.assertEqual(evidence.path('road.xodr'),original/'road.xodr')
            (original/'trace.jsonl').write_text('tampered')
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):evidence.path('trace.jsonl')


class UnknownMeasurementTests(unittest.TestCase):
    def test_null_lamps_stay_unknown_but_measured_mask_zero_is_off(self):
        self.assertEqual(signals({'light_Brake':None,'light_LeftBlinker':None,'light_RightBlinker':False}),{})
        self.assertEqual(signals({'vehicle_light_state':0})['turn_indicator'],'off')

    def test_unknown_indication_does_not_mean_definitely_not_red(self):
        scene={'users':[],'structures':[],'devices':[{'id':1,'kind':'traffic_signal','indications':['unknown']}]}
        repair_scene(scene,{'dev.traffic_signal'},{},{},{})
        self.assertNotIn('indications',scene['devices'][0])


class MeasuredSidecarTests(unittest.TestCase):
    def test_sidecar_uses_native_mask_and_actor_identity_not_labels(self):
        from unittest.mock import patch
        from traffic_spec_adapter.inventory_observations import Evidence
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);original=root/'evidence';original.mkdir()
            raw=original/'vehicle_turn_signal_history.jsonl'
            raw.write_text(json.dumps({'time_s':.05,'value':{'ego':{'actor_id':7,'lamp_bits':0},'command':'left'}})+'\n')
            (root/'evidence-checksums.json').write_text(json.dumps({'evidence/'+raw.name:hashlib.sha256(raw.read_bytes()).hexdigest()}))
            packets=source_packets(Evidence(root),read_graphs=False)
            scene={'t':50,'subject':7,'users':[{'track':7}], 'structures':[], 'devices':[]}
            repair_scene(scene,{'sig.turn_indicator'},packets[50],{},{})
            self.assertEqual(scene['users'][0]['sig']['turn_indicator'],'off')


class ConflictingMeasurementTests(unittest.TestCase):
    def test_conflicting_same_frame_lamps_remain_unknown(self):
        scene={'subject':1,'users':[{'track':1,'sig':{'turn_indicator':'left'}}], 'structures':[], 'devices':[]}
        packet={'ego_lamps':{'turn_indicator':'left'},'lamp_sources':[{'track':1,'lamps':{'turn_indicator':'off'}}]}
        repair_scene(scene,{'sig.turn_indicator'},packet,{},{})
        self.assertNotIn('turn_indicator',scene['users'][0]['sig'])


class OperabilityProjectionTests(unittest.TestCase):
    def test_valid_indication_excludes_inoperability_but_darkness_does_not_supply_it(self):
        from traffic_spec_adapter.adapter import project_operability
        devices=[{'kind':'traffic_signal','indications':['circular_red']},
                 {'kind':'traffic_signal','indications':['dark'],'inoperative':True},
                 {'kind':'traffic_signal','inoperative':False}]
        project_operability(devices)
        self.assertIs(devices[0]['inoperative'],False)
        self.assertNotIn('inoperative',devices[1]);self.assertNotIn('inoperative',devices[2])
